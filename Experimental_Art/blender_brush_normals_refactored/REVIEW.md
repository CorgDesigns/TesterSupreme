# Review of the original script

Reviewed source:
`../blender_brush_normals/procedural_normal_blobs.py` (601 lines).

## Findings addressed in this copy

1. **Successful processing always deletes the source.** The behavior is safe
   against deletion after a failed export, but it is still an implicit,
   destructive default. The refactor preserves sources and makes consumption
   explicit with `--delete-source`.

2. **Brush edge blending can use the same stroke twice.** The KD-tree indexes
   several samples per stroke, so its nearest candidate list contains repeated
   stroke IDs. The original takes list positions zero and one as the nearest
   and second-nearest cells even when both IDs are identical. Compatibility
   mode preserves that result by default; `--edge-selection distinct` selects
   the first different second stroke when a corrected blend is wanted.

3. **The header documentation is stale.** It describes two algorithms while
   four are implemented, says parameters must be edited in the source, and
   omits SciPy from installation even though `cKDTree` requires it. The new
   README and per-command `--help` are generated around the four real
   algorithms and list all three dependencies.

4. **Configuration is global and algorithm concerns are interleaved.** This
   makes testing or importing one algorithm difficult and lets the main script
   grow with every new mode. Each algorithm now owns a typed config and
   processing function; only the registry connects it to the CLI.

5. **Several numeric settings are not validated.** Zero edge softness can
   divide by zero, invalid blend values can extrapolate, and reversed stroke
   lengths are accepted. CLI types now constrain ranges and cross-field checks
   reject inconsistent settings before touching inputs.

6. **A blend strength of zero can still alter pixels.** The original
   renormalizes pixels even where the paint weight is zero, including areas
   outside the soft circles. The refactor renormalizes only pixels receiving
   paint, so zero strength is a true no-op.

7. **Output replacement and partial failure are not visible to automation.**
   The original silently replaces an existing same-name PNG and finishes with
   exit code zero even when files were skipped. The refactor protects existing
   outputs unless `--overwrite` is supplied, writes atomically, and returns
   nonzero when any queued file fails.

8. **Seeded output changed during the first refactor.** NumPy's modern
   `Generator` does not reproduce the original NumPy/Python random streams.
   `--rng-mode legacy` is now the default and retains the original seeded
   Algorithm 4 path for single-island maps. Multi-island results intentionally
   differ because black-padding isolation is mandatory.

9. **Irregular-cell algorithms allocated candidate data for the entire
   texture.** At 2048 or 4096 this can consume several gigabytes. Assignment,
   averaging, and painting now run in configurable row chunks. The default is
   64 rows; `--chunk-rows` can lower peak memory further.

10. **Queue dimensions were not validated.** The runner now inspects real PNG
    headers before decoding pixels. Automatic mode accepts only square 1024,
    2048, and 4096 maps. `--resolution` filters a run to one allowed size;
    unsupported or non-selected maps are logged and skipped without stopping
    later files. No source resampling is performed.

11. **Algorithm 4 shape was uniformly capsule-like.** Optional shape presets
    now provide swirl, either one-ended taper, two-ended taper, and a
    teardrop-scale form. Normalized density, size, and overlap controls map to
    documented 1024/2048/4096 safety profiles. Defaults still follow the
    original capsule path and its golden compatibility checksum.

12. **A source could be replaced in the final instant before deletion.**
    Metadata checks narrowed the race but did not make the destructive action
    atomic. Source consumption now moves the exact queue entry to a unique
    pending name, verifies its original identity, and deletes only that claim.
    Failure restores it without overwriting a newer queue file.

13. **A future algorithm regression could modify black padding.** Island-aware
    algorithms already prevent cross-padding averages and blends, and the
    runner now adds an independent pre-export integrity gate that refuses any
    result whose source-padding pixels changed.

14. **A committed output did not identify its exact bytes.** Manifest schema 2
    records source and output SHA-256 values, output byte count, and runtime
    dependency versions. Output hashing occurs on the verified temporary PNG
    before atomic commit, so a hashing failure cannot leave an unreported
    committed output.

15. **Zero-strength runs could be skipped by an algorithm memory estimate even
    though the effect was disabled.** `--blend-strength 0` now bypasses the
    expensive algorithm and uses a conservative load/validation/export
    estimate while retaining every input and export integrity check.

16. **Unsafe threshold, suffix, and log fields remained possible.** Padding
    threshold is capped below the minimum encoded unit-normal RGB sum,
    filesystem-reserved suffix characters are rejected, and tabs/newlines are
    escaped so each text-log issue remains one parseable record.

17. **Robotics materials needed regular geometric paneling.** Algorithm 4 now
    includes an opt-in `hexagon` brush with a true regular-hex distance metric.
    Its default honeycomb layout uses bounded staggered centers, uniform
    orientation and size, optional seeded jitter, and resolution-aware panel
    scale. A scattered layout remains available for irregular armor. Hexagons
    use corrected distinct-edge selection and retain the shared RAM, worker,
    output-validation, and UV-island padding protections.

18. **The brush library did not cover a broad artistic surface vocabulary.**
    Algorithm 4 now adds fifteen geometry-backed presets: leaf, petal,
    pine-needle, scallop, vine, bark, pebble, boulder, crack, crystal, shard,
    chevron, circuit-trace, diamond-panel, and octagon-panel. They reuse the
    existing bounded taper, sampled-path, or centered-panel processing paths.
    Shape-specific sample minimums prevent curved and angular strokes from
    silently becoming straight, while centered panels avoid unnecessary path
    samples. The original capsule path and golden compatibility output remain
    unchanged.

19. **Built-in help did not explain how to choose an algorithm.** Traditional
    per-command `--help` existed, but each algorithm had only a one-line
    description and users had to open the README to compare them. The CLI now
    supports `help`, `help <algorithm>`, `help all`, and `--help-all`.
    Algorithm modules own their detailed purpose, visual guidance, option
    effects, and examples, keeping the dispatcher small while ensuring the
    command reference stays next to the implementation.

## Intentionally preserved behavior

- Black pixels are treated as empty UV padding.
- Neighboring, nearly identical averages are nudged before painting.
- Processed surface normals are renormalized by default.
- Original random processing can be reproduced with a seed and legacy mode.
- One failed image does not prevent later queued images from being attempted.

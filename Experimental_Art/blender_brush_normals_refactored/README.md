# Modular Procedural Normal Blobs

This is a refactored copy of
`../blender_brush_normals/procedural_normal_blobs.py`. The original script is
unchanged.

The tool modifies object-space normal-map PNGs with one of four procedural
patterns. Its entry script is intentionally small; queue handling, shared
image operations, and each algorithm live in separate modules under
`normal_blobs/`.

These exports remain object-space intermediate maps. Re-bake them to tangent
space in Blender before direct s&box use. Normal-vector validity can be checked
from pixels, but object-space versus tangent-space intent cannot be identified
reliably from PNG data alone.

## Setup

From this folder in PowerShell:

```powershell
py -m pip install -r requirements.txt
py procedural_normal_blobs.py help
```

Python 3.10 or newer is recommended. The required packages are NumPy, Pillow,
and SciPy. `requirements.txt` constrains them to tested major-version ranges
so incompatible future releases are not installed silently.

## Quick start

Put PNGs in `to_process/`, then choose one algorithm:

```powershell
py procedural_normal_blobs.py brush_stroke_cells --seed 42
```

Outputs are written to `export/<name>_processed.png`. Unlike the original
script, inputs are preserved by default. Add `--delete-source` only when you
want `to_process/` to act as a consuming queue:

```powershell
py procedural_normal_blobs.py brush_stroke_cells --delete-source
```

Process a particular file or a different flat directory with `--input`. The
option can be repeated:

```powershell
py procedural_normal_blobs.py voronoi_flow_cells `
  --input ..\blender_brush_normals\Cone_Basic_Model_Normals_Object.png `
  --output-dir .\export `
  --seed 123
```

## Built-in help

Help commands never inspect, process, export, or delete files. Use the short
overview to compare algorithms:

```powershell
py procedural_normal_blobs.py help
```

Get a detailed explanation of one algorithm, all shared options, its
algorithm-specific options, safe ranges, defaults, and examples:

```powershell
py procedural_normal_blobs.py help edge_gradient_cascade
```

Traditional option-style help is equivalent:

```powershell
py procedural_normal_blobs.py edge_gradient_cascade --help
```

Print the complete command reference for every algorithm:

```powershell
py procedural_normal_blobs.py help all
py procedural_normal_blobs.py --help-all
```

Global help options such as `--version` and `--help-all` go before the
algorithm name. Input, output, shared, and algorithm-specific processing
options go after the selected algorithm.

### Which algorithm should I use?

| Algorithm | Best for | Start by adjusting |
| --- | --- | --- |
| `center_average_normalization` | Calm regular dots, dimples, or evenly spaced soft circles. This is the simplest pattern. | `--block-size`, then `--circle-ratio`. |
| `edge_gradient_cascade` | Ordered horizontal bands, tiled scales, and three-circle transitions across a grid. | `--block-size`, then `--circle-ratio`. |
| `voronoi_flow_cells` | Irregular stone, hammered, cellular, or flowing organic regions without a recognizable brush silhouette. | `--average-cell-size`, `--size-variance`, and `--elongation-max`. |
| `brush_stroke_cells` | The broadest artistic library: plants, bark, scales, rocks, cracks, crystals, circuits, and robotic panels. | `--brush-shape`, `--density`, `--shape-size`, and flow controls. |

Existing outputs are protected. Use `--overwrite` when replacing them is
intentional.

Before a batch begins, output names are checked for collisions. For example,
two inputs named `rock.png` from different directories would both map to
`rock_processed.png`; the run now stops before processing instead of silently
overwriting one result. Use distinct filenames, separate output directories,
or separate runs for those inputs.

Each destination also receives an exclusive `.lock` file while it is being
processed. A concurrent run targeting the same output fails that file instead
of racing the first writer. Locks are removed on normal success or failure. If
the process is forcibly terminated, its error message identifies the stale
lock that can be removed after confirming no run is active.

Inputs and outputs must use separate directories. The runner verifies that no
planned destination overlaps any queued source. It also fingerprints each
source before loading, records its SHA-256 digest, and checks its filesystem
identity again before export and deletion. With `--delete-source`, the exact
processed file is atomically moved to a unique pending name, verified again,
and only then deleted. A deletion or verification failure restores the file
without overwriting a newer queue entry, so a last-moment replacement cannot
be deleted accidentally.

## Compatibility with the current algorithm 4

`brush_stroke_cells` defaults to the current production behavior:

```powershell
py procedural_normal_blobs.py brush_stroke_cells `
  --rng-mode legacy `
  --edge-selection legacy `
  --seed 42
```

Both compatibility options are already the defaults and are shown here for
clarity for the default capsule shape. With the same seed, source pixels,
settings, and file order, this mode retains the original geometry and
single-island pixel path. Multi-island maps intentionally differ because all
algorithms now prevent averages and blends from crossing black padding. New
brush shapes default to corrected `distinct` edge selection unless
`--edge-selection legacy` is explicitly requested.

Use the corrected second-stroke edge blend explicitly when you want to compare
the newer appearance:

```powershell
py procedural_normal_blobs.py brush_stroke_cells `
  --edge-selection distinct `
  --rng-mode modern `
  --seed 42
```

To reproduce the original consuming queue workflow against its existing
folders, add both destructive/overwrite flags:

```powershell
py procedural_normal_blobs.py brush_stroke_cells `
  --input ..\blender_brush_normals\to_process `
  --output-dir ..\blender_brush_normals\export `
  --delete-source `
  --overwrite `
  --rng-mode legacy `
  --edge-selection legacy
```

## Automatic PNG size selection

The processor does not resize source maps. It reads each PNG's dimensions
before loading its full pixel data and accepts only these exact square sizes:

- 1024x1024
- 2048x2048
- 4096x4096

With no `--resolution` option, all three sizes are accepted automatically in
the same queue:

```powershell
py procedural_normal_blobs.py brush_stroke_cells
```

For example, a directory containing 1024, 2048, 4096, and 512 PNGs will process
the first three and skip the 512 PNG without stopping the batch.

Use `--resolution` as an input filter when a run should process only one size.
Both short and full forms are accepted:

```powershell
# Process only 1024x1024 PNGs; log all other PNG sizes.
py procedural_normal_blobs.py brush_stroke_cells --resolution 1024x1024

# Process only 4096x4096 PNGs with bounded-memory chunks.
py procedural_normal_blobs.py brush_stroke_cells `
  --resolution 4096 `
  --chunk-rows 64
```

Files with unsupported dimensions, non-square dimensions, or a valid but
non-selected size are appended to `export/processing_errors.log` and skipped.
The queue then continues with the next PNG. The log is tab-separated:

```text
timestamp    SKIPPED_SIZE    source-path    reason
timestamp    SKIPPED_RESOURCE_LIMIT    source-path    reason
timestamp    INPUT_NORMALS_REPAIRED    source-path    repair summary
timestamp    SOURCE_DELETE_FAILED      source-path    reason
timestamp    PREFLIGHT_ERROR           source-path    reason
timestamp    ERROR           source-path    reason
```

The log appends across runs instead of replacing earlier entries. Append and
rotation use a short cross-process lock with stale-lock recovery. Files with
non-PNG extensions are ignored during directory discovery. A non-PNG file
renamed with a `.png` extension is logged as an error.

The active log is capped at 5 MiB. On reaching that size it becomes
`processing_errors.previous.log`, replacing the older archive, and a fresh
active log begins.

Input PNGs must be single-frame, 8-bit truecolor RGB or fully opaque RGBA.
Opaque RGBA is safe because its alpha carries no information; non-opaque
alpha, transparency, animation, 16-bit storage, grayscale, and indexed color
are rejected instead of being silently converted. Surface pixels are checked
for finite encoded normals before an algorithm starts. If no more than 1% of
surface normals fall outside the `0.95..1.05` length range, those nonzero
vectors are normalized automatically and recorded as
`INPUT_NORMALS_REPAIRED`. Near-zero normals or repair requirements above 1%
remain fatal because their intended direction is unsafe to infer.

Algorithm sizes remain literal pixel measurements. A mixed-resolution queue
uses the same supplied spacing, stroke-length, block-size, and softness values
for every accepted file.

## CPU memory safety

Before loading a compatible PNG, the program estimates peak memory for that
file, algorithm, resolution, candidate count, and chunk size. Processing
begins only when the estimate fits within 75% of currently available physical
RAM. This leaves the other 25% available to Windows, Blender, and other
applications.

For chunked algorithms, an over-budget estimate does not immediately skip the
file. The runner repeatedly halves `--chunk-rows`, down to one row if needed,
and recalculates the estimate. This preserves the algorithm settings and
exported pixels while trading additional processing time for lower peak RAM.
`SKIPPED_RESOURCE_LIMIT` is used only when the irreducible one-row estimate
still exceeds the safe budget.

You can impose a lower per-file ceiling:

```powershell
py procedural_normal_blobs.py brush_stroke_cells `
  --cpu-memory-limit-gb 3
```

The configured ceiling cannot override the available-RAM check upward. If a
file is predicted to exceed either limit, it remains untouched, is logged as
`SKIPPED_RESOURCE_LIMIT`, and the next PNG is evaluated. When available RAM
cannot be detected, a conservative 2 GiB budget is used.

Typical Algorithm 4 estimates with its standard candidates and 64-row chunks
are approximately 470 MiB for 1024, 1.1 GiB for 2048, and 3.0 GiB for 4096.
Higher candidate counts and chunk sizes raise the estimate before processing.
When `--blend-strength 0` is selected, the expensive algorithm is bypassed and
the preflight uses a smaller validation-and-export estimate. Input validation,
safe normal repair, padding checks, and PNG verification still run.

The current implementation is CPU-only and therefore allocates no GPU VRAM.
Any future GPU backend must provide its own peak-VRAM estimate to the same
preflight system before it can be selected.

## Batch completion and deterministic files

An empty queue is recorded as `NO_INPUT`. Size and resource skips remain
nonfatal by default so unattended mixed queues continue. Add
`--require-output` when automation should receive a failure status if the run
produces no files:

```powershell
py procedural_normal_blobs.py brush_stroke_cells --require-output
```

Legacy seeded randomness remains queue-scoped. For a file to keep the same
result when earlier files are added or filtered out, use a deterministic
per-file stream:

```powershell
py procedural_normal_blobs.py brush_stroke_cells `
  --seed 42 `
  --seed-scope file
```

File scope derives the stream from the seed and filename, and therefore
requires `--seed`. Renaming a source intentionally changes its derived stream.
Seeds are limited to `0..4294967295`, which both RNG modes support.

## Export summary manifest

Every normal batch invocation writes `export_summary.json` in the selected
output directory, including empty queues and batches where every file is
skipped. It contains:

- tool and manifest-schema versions plus a unique run ID;
- Python, platform, NumPy, Pillow, and SciPy versions;
- start and finish timestamps, overall outcome, and expected exit code;
- algorithm, shared, and batch options used for the run;
- discovered, processed, skipped, failed, and post-export warning counts;
- one record per file with its source, destination, dimensions, status,
  category, message, and CPU resource estimate when available;
- source size, modification identity, and SHA-256 plus the exact committed
  output byte count and SHA-256;
- requested and automatically reduced chunk rows for chunked algorithms.

The status categories match the text log, including `PROCESSED`,
`PROCESSED_WITH_WARNINGS`, `SKIPPED_SIZE`, `SKIPPED_RESOURCE_LIMIT`,
`NO_INPUT`, and `ERROR`. Input repairs are recorded as notices. A saved output
whose source cannot be deleted stays counted as processed, records
`SOURCE_DELETE_FAILED`, preserves the source, and returns failure for
automation. Paths are absolute so build tools do not need to infer the
invocation directory.

The manifest is written to a temporary file, flushed, and atomically moved
into place only when complete. It replaces the previous summary instead of
growing indefinitely. Concurrent runs cannot leave partial JSON; the last run
to finish becomes the current summary, and its unique run ID identifies it.

## Algorithms and their options

### `center_average_normalization`

Divides the image into square blocks and paints one soft circle using the
average non-padding color of each block.

```powershell
py procedural_normal_blobs.py center_average_normalization `
  --block-size 256 `
  --circle-ratio 0.8
```

| Option | Default | Meaning |
| --- | ---: | --- |
| `--block-size PIXELS` | `256` | Square block size from 64 to 2048 and no larger than the input image. |
| `--circle-ratio RATIO` | `0.8` | Circle diameter relative to the block, from 0.01 to 1. |

### `edge_gradient_cascade`

Paints left, center, and right circles in each block. Shared horizontal
boundaries use a 50/50 HSV blend between neighboring block averages.

```powershell
py procedural_normal_blobs.py edge_gradient_cascade `
  --block-size 128 `
  --circle-ratio 0.7
```

| Option | Default | Meaning |
| --- | ---: | --- |
| `--block-size PIXELS` | `256` | Square block size from 64 to 2048 and no larger than the input image. |
| `--circle-ratio RATIO` | `0.8` | Circle diameter relative to half a block, from 0.01 to 1. |

### `voronoi_flow_cells`

Scatters weighted cell seeds and stretches each cell along a random direction.

```powershell
py procedural_normal_blobs.py voronoi_flow_cells `
  --average-cell-size 120 `
  --size-variance 0.5 `
  --elongation-max 2 `
  --edge-softness 10 `
  --candidates 12 `
  --seed 42
```

| Option | Default | Meaning |
| --- | ---: | --- |
| `--average-cell-size PIXELS` | `120` | Target cell diameter from 8 to 4096; smaller values create more cells. |
| `--size-variance RATIO` | `0.5` | Random size variation from 0 to 1. |
| `--elongation-max FACTOR` | `2` | Maximum directional stretch from 1 to 16. |
| `--edge-softness PIXELS` | `10` | Width of the soft cell boundary from 0.01 to 4096. |
| `--candidates COUNT` | `12` | Nearby seeds evaluated per pixel from 2 to 64. |
| `--chunk-rows ROWS` | `64` | Rows processed at once from 1 to 128; lower values reduce peak memory. |

### `brush_stroke_cells`

Scatters configurable straight, curved, pointed, organic, mineral, angular,
or panel-like cells. The original capsule geometry remains the default. The
shape catalog is organized into legacy, foliage, animal, insect, organic,
natural-material, mineral, manufactured, and panel families.

Black padding is a hard processing barrier for every algorithm. Each
4-connected surface region is treated as a separate UV island. Grid averages,
Voronoi cells, brush cells, neighbor tweaks, and edge blends are restricted to
their island. A generated shape may geometrically pass over padding, but it
cannot carry or blend normal data from one island into another. Black pixels
remain unchanged.

```powershell
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape capsule `
  --seed 42
```

#### Shape presets

| Family | Shape | Result and suggested use |
| --- | --- | --- |
| Legacy | `capsule` | Rounded, equal-width strokes for soft organic cells. |
| Legacy | `swirl` | Alternating curved centerlines; controlled by `--swirl-strength`. |
| Legacy | `sharp-start` | One pointed start flowing into a rounded end. |
| Legacy | `sharp-end` | Rounded start flowing into one pointed end. |
| Legacy | `sharp-both` | Linear points at both ends, producing leaf/diamond territories. |
| Foliage | `grass-blade` | Narrow bent blade for grass, reeds, and plant fibers. |
| Foliage | `grass-clump` | Lobed tapered blade for clustered grass and meadow surfaces. |
| Foliage | `branching-twig` | Branch-like jagged multi-turn stroke for twigs, roots, and small branches. |
| Organic | `scale` | Teardrop with a pointed start and broad rounded end; useful for fish, reptile, or armor scales. |
| Organic | `leaf` | Smooth symmetrical lens with soft plant-like points. |
| Organic | `petal` | Asymmetrical lens that grows fuller toward the blossom end. |
| Organic | `pine-needle` | Narrow tapered lens for needles, grass, fibers, or fine scratches. |
| Organic | `scallop` | Lobed teardrop for shells, layered leaves, feathers, or decorative armor. |
| Organic | `vine` | Narrow S-curved stroke for tendrils, roots, veins, or flowing ornament. |
| Wood | `bark` | Vertically aligned, gently lobed bands for bark, wood grain, or hammered strips. |
| Animal | `feather` | Barbed, softly curved vane for feathers and layered plumage. |
| Animal | `fur-tuft` | Short pointed tuft for fur, hair, whiskers, or soft fibers. |
| Animal | `fish-scale` | Rounded shield-like scale for fish, reptiles, and overlapping armor. |
| Insect | `beetle-shell` | Domed tapered plate for beetle wings, shells, and hard carapaces. |
| Insect | `insect-wing` | Curved tapered wing cell for moth, fly, and fairy-wing surfaces. |
| Organic | `moss-patch` | Rough lobed patch for moss, lichen, sponge, and clustered growth. |
| Organic | `tentacle` | Curving tapered form for tentacles, tendrils, and roots. |
| Stone | `pebble` | Smooth oval territories for river stones, seeds, bubbles, or soft inclusions. |
| Stone | `boulder` | Full oval with repeated side lobes for rough rock and weathered surfaces. |
| Stone | `crack` | Narrow jagged path for fractured stone, dried earth, lightning, or weld scars. |
| Mineral | `crystal` | Faceted body with a short base bevel and longer point for grown crystals. |
| Mineral | `shard` | Off-center, splintered profile for broken crystal, slate, or sharp debris. |
| Manufactured | `chevron` | Bent V-shaped stroke for tread, directional plating, or warning patterns. |
| Manufactured | `circuit-trace` | Narrow angular S-path for circuit routes, inlays, seams, or conduits. |
| Manufactured | `diamond-panel` | True rotated diamond metric for stamped plates and robotic panels. |
| Manufactured | `octagon-panel` | Regular octagonal metric for access plates, sci-fi armor, and mechanical tiling. |
| Manufactured | `hexagon` | Regular six-sided panels; defaults to an ordered honeycomb for robotics and metal materials. |

#### Resolution-aware safe controls

`--density`, `--shape-size`, and `--overlap-priority` all use normalized
values from 0 to 1. They map to bounded limits for the actual PNG size:

| PNG size | Density: least-most cells | Shape-size target: least-most length | Maximum overlap distance advantage |
| --- | ---: | ---: | ---: |
| 1024x1024 | 16-256 | 24-160 px | 15% |
| 2048x2048 | 64-1024 | 48-320 px | 20% |
| 4096x4096 | 256-4096 | 96-640 px | 25% |

These are hard internal limits for normalized controls. Density maps directly
between its two counts. For stroke shapes, shape size selects a target between
the two documented lengths. For honeycomb hexagons, shape size maps inversely
across the cell-count range: `0` produces the most/smallest panels and `1`
produces the fewest/largest panels. Diamond and octagon panels use density for
panel count and shape size for panel diameter, so both controls can be
combined. `--length-variation` can then introduce controlled size variation.
Leaving density or shape size unset preserves the legacy
`--average-spacing` control.

| New option | Default | Meaning |
| --- | ---: | --- |
| `--brush-shape SHAPE` | `capsule` | Select any legacy, organic, stone, mineral, angular, or panel preset from the table above. |
| `--density RATIO` | unset | Resolution-aware cell count from 0 (least) to 1 (most). |
| `--shape-size RATIO` | unset | Resolution-aware stroke length or panel diameter from 0 (smallest) to 1 (largest). |
| `--hex-layout MODE` | `honeycomb` | `honeycomb` creates ordered metal panels; `scattered` creates irregular hexagonal cells. |
| `--hex-jitter RATIO` | `0` | Honeycomb center variation from 0 to 1, capped at 30% of panel spacing. |
| `--length-variation RATIO` | shape-aware | Variation around normalized size; defaults to 0 for centered panels and 0.35 otherwise; range 0-0.75. |
| `--swirl-strength RATIO` | `0.55` | Swirl curvature from straight (`0`) to strongest (`1`). |
| `--curvature RATIO` | `0.35` | Bend strength for foliage, animal, insect, and organic shapes; 0 is straight and 1 is strongly curved. |
| `--segments COUNT` | `4` | Lobe, barb, or centerline-turn target from 2-16; effective detail is capped by available path samples. |
| `--roughness RATIO` | `0.25` | Deterministic irregularity from smooth 0 to rough 1. |
| `--symmetry RATIO` | `0.75` | Profile balance from asymmetric 0 to mirrored 1. |
| `--branching RATIO` | `0.35` | Branch, tuft, or lobe influence from 0 to 1. |
| `--flow-angle DEGREES` | shape-aware | Preferred start-to-end direction; range -360 to 360. Directional presets have documented defaults; other shapes are random. |
| `--flow-jitter RATIO` | shape-aware | Angular variation: centered panels default to aligned (`0`); other shapes default to `0.25`. |
| `--overlap-order MODE` | `balanced` | Let `earlier`, `later`, `larger`, or `smaller` strokes claim more contested pixels. |
| `--overlap-priority RATIO` | `0` | Strength of overlap ordering from none (`0`) to the resolution-safe maximum (`1`). |

#### Option interaction rules

The command rejects combinations that would silently ignore one of the
supplied values:

- `--density` and `--average-spacing` are alternatives.
- `--shape-size` cannot be combined with `--length-min` or `--length-max`.
- Honeycomb `--shape-size`, `--density`, and `--average-spacing` are
  alternative panel-scale controls; choose one.
- `--length-variation` requires `--shape-size`.
- `--curvature`, `--segments`, `--roughness`, `--symmetry`, and
  `--branching` are shared organic controls accepted by every shape for a
  stable configuration schema. Legacy and centered panel shapes intentionally
  retain their established geometry; the controls have their strongest effect
  on the new organic families.
- `--hex-layout` and `--hex-jitter` require the `hexagon` brush.
- `--hex-jitter` applies only to the `honeycomb` layout.
- `--samples-per-stroke` does not apply to center-indexed `hexagon`,
  `diamond-panel`, or `octagon-panel` shapes.
- `--swirl-strength` requires the `swirl` brush shape.
- `--flow-jitter` requires `--flow-angle`, unless the selected preset supplies
  a default: scale/scallop `-90`, bark `90`, chevron/circuit/panels `0`, and
  honeycomb hexagon `0`.
- Positive `--overlap-priority` requires a non-`balanced` overlap order.
- A non-`balanced` overlap order requires positive overlap priority.
- `larger` and `smaller` ordering require actual stroke-length variation.

Swirl and chevron accept three or more path samples. Vine, crack, and
circuit-trace require at least five so their centerlines cannot collapse into
straight strokes. All default to five; values from 7 to 11 make long curved or
jagged strokes smoother at additional processing cost.

When overlap priority is active, Algorithm 4 automatically doubles its nearby
candidate search width. This makes it substantially less likely that a
priority-weighted winner is omitted, and the additional arrays are included
in the RAM preflight. The search remains intentionally bounded rather than
comparing every pixel against every stroke; raise `--candidates` when a scene
needs a wider search, subject to the resource limit.

#### Artistic starting recipes

The presets deliberately share the same density, size, flow, overlap, padding,
and resource controls. Start with one of these combinations and then swap the
shape within its family.

```powershell
# Foliage, petals, needles, feathers, or layered shell growth.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape leaf `
  --density 0.34 `
  --shape-size 0.52 `
  --length-variation 0.28 `
  --flow-angle -55 `
  --flow-jitter 0.45 `
  --edge-softness 6 `
  --edge-selection distinct `
  --seed 42

# Vertical bark, wood grain, or hammered organic strips.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape bark `
  --density 0.42 `
  --shape-size 0.72 `
  --length-variation 0.35 `
  --flow-angle 90 `
  --flow-jitter 0.14 `
  --edge-softness 5 `
  --edge-selection distinct `
  --seed 42

# Rough rounded rock territories. Swap boulder for pebble for softer stones.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape boulder `
  --density 0.40 `
  --shape-size 0.46 `
  --length-variation 0.55 `
  --width-variance 0.65 `
  --edge-softness 7 `
  --edge-selection distinct `
  --seed 42

# Directional grown crystal. Swap crystal for shard for broken splinters.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape crystal `
  --density 0.28 `
  --shape-size 0.72 `
  --length-variation 0.50 `
  --flow-angle -65 `
  --flow-jitter 0.22 `
  --overlap-order larger `
  --overlap-priority 0.45 `
  --edge-selection distinct `
  --seed 42

# Regular robotic access panels. Diamond panels use the same controls.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape octagon-panel `
  --density 0.50 `
  --shape-size 0.42 `
  --flow-angle 0 `
  --flow-jitter 0.03 `
  --edge-softness 3 `
  --edge-selection distinct `
  --seed 42

# Angular technological paths, seams, and conduits.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape circuit-trace `
  --density 0.32 `
  --shape-size 0.70 `
  --length-variation 0.25 `
  --samples-per-stroke 7 `
  --flow-jitter 0.08 `
  --edge-softness 4 `
  --edge-selection distinct `
  --seed 42
```

For plant surfaces, exchange `leaf` for `petal`, `pine-needle`, `scallop`,
`vine`, `grass-blade`, `grass-clump`, or `branching-twig`. For animal surfaces,
try `feather`, `fur-tuft`, `fish-scale`, `beetle-shell`, or `insect-wing`. For
growth and fantasy materials, try `moss-patch` or `tentacle`. Use
`--curvature`, `--segments`, `--roughness`, `--symmetry`, and `--branching` to
move from clean repeats toward irregular living forms. For damaged terrain,
use `crack` with `--samples-per-stroke 7..11`.
For machinery, `chevron` produces directional tread while `diamond-panel`,
`octagon-panel`, and `hexagon` produce progressively different plate rhythms.

#### Organic-life recipes

These presets use the shared organic controls. Keep `--edge-selection
distinct` for clean overlap between neighboring living forms.

```powershell
# Layered grass or reeds.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape grass-blade `
  --density 0.72 `
  --shape-size 0.34 `
  --curvature 0.72 `
  --roughness 0.35 `
  --flow-angle -90 `
  --flow-jitter 0.30 `
  --edge-selection distinct `
  --seed 42

# Feathers, fur, or wing-like animal surfaces.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape feather `
  --density 0.46 `
  --shape-size 0.48 `
  --segments 7 `
  --symmetry 0.82 `
  --roughness 0.28 `
  --flow-angle 0 `
  --flow-jitter 0.38 `
  --edge-selection distinct `
  --seed 42

# Moss, tentacles, roots, or clustered fantasy growth.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape moss-patch `
  --density 0.58 `
  --shape-size 0.44 `
  --segments 6 `
  --roughness 0.80 `
  --branching 0.75 `
  --curvature 0.52 `
  --edge-softness 6 `
  --edge-selection distinct `
  --seed 42
```

#### Hexagonal robotics/metal recipe

The default `honeycomb` layout uses staggered, uniformly oriented centers and
a true regular-hex distance metric. It creates clean six-sided panels while
the global padding guard and per-island cell isolation keep panels from
crossing black UV padding.

```powershell
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape hexagon `
  --density 0.48 `
  --hex-layout honeycomb `
  --hex-jitter 0.03 `
  --edge-softness 4 `
  --edge-selection distinct `
  --seed 42 `
  --seed-scope file
```

Raise `--density` for smaller, more numerous panels, or use
`--shape-size 0..1` instead when panel size is the more intuitive control.
Small `--hex-jitter` values around `0.02..0.08` create manufactured variation;
larger values and `--hex-layout scattered` create damaged or improvised armor.
Explicit `--width-variance` and `--length-variation` add controlled panel-size
variation; both default to zero for the ordered hexagon preset.

#### Scale recipe

This combination produces overlapping, similarly oriented teardrop cells that
read more like scales:

```powershell
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape scale `
  --density 0.38 `
  --shape-size 0.45 `
  --length-variation 0.25 `
  --flow-angle -90 `
  --flow-jitter 0.18 `
  --overlap-order later `
  --overlap-priority 0.65 `
  --edge-selection distinct `
  --seed 42
```

For denser armor-like scales, raise `--density`. For broad fish/reptile scales,
raise `--shape-size` and lower density. Reversing the flow angle to `90` flips
the scale direction.

#### Swirl and sharp examples

```powershell
# Curved, sweeping cells.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape swirl `
  --density 0.28 `
  --shape-size 0.65 `
  --swirl-strength 0.8 `
  --flow-angle 20 `
  --flow-jitter 0.6 `
  --overlap-order larger `
  --overlap-priority 0.4 `
  --edge-selection distinct

# Leaf/blade shapes with two pointed ends.
py procedural_normal_blobs.py brush_stroke_cells `
  --brush-shape sharp-both `
  --density 0.3 `
  --shape-size 0.5 `
  --flow-angle -35 `
  --flow-jitter 0.3 `
  --edge-selection distinct
```

#### Legacy and performance controls

| Option | Default | Meaning |
| --- | ---: | --- |
| `--average-spacing PIXELS` | `130` | Target stroke spacing from 64-4096; smaller values create more strokes. |
| `--length-min PIXELS` | `60` | Shortest stroke from 1-4096. |
| `--length-max PIXELS` | `260` | Longest stroke from 1-4096; cannot be below the minimum. |
| `--width-variance RATIO` | shape-aware | Random width variation from 0 to 1; defaults to 0 for centered panels and 0.5 otherwise. |
| `--edge-softness PIXELS` | `8` | Width of the soft boundary from 0.01-4096. |
| `--candidates COUNT` | `18` | Nearby sampled points evaluated per pixel; range 2-64. |
| `--samples-per-stroke COUNT` | `5` | Spatial-index samples per centerline stroke; range 2-32 with shape-specific minimums; not used by centered panels. |
| `--edge-selection MODE` | shape-aware | Capsule uses `legacy` for byte compatibility; every other shape uses corrected `distinct` selection. |
| `--chunk-rows ROWS` | `64` | Maximum rows processed at once from 1-128; the runner may automatically lower this to satisfy the RAM budget. |
| `--workers COUNT` | `0` | CPU threads for spatial lookup: 0 uses up to 8 logical CPUs, 1 is single-threaded, and 2-8 sets a limit. |

The limits above prevent a typo from requesting billions of strokes or
unbounded per-pixel candidate arrays. Programmatic callers receive the same
workload checks before Algorithm 4 allocates its large arrays.

#### CPU threading

Algorithm 4 processes one PNG at a time to keep 2048 and 4096 memory use
predictable. Inside that file, its most expensive KD-tree candidate queries
run across multiple CPU workers. Automatic mode is the default:

```powershell
py procedural_normal_blobs.py brush_stroke_cells --workers 0
```

Use `--workers 1` for a single-thread comparison, or choose a fixed count when
you want to leave CPU capacity available for Blender or another application.
Worker count does not alter seeded geometry or exported pixels.

## Export integrity checks

All numeric command-line controls must be finite: values such as `nan` and
`inf` are rejected. Before an output replaces its destination, the exporter
also verifies:

- the result is a non-empty numeric RGB array;
- every value is finite and inside the 0-255 range;
- at least one surface-normal pixel is present;
- every source padding pixel is byte-for-byte unchanged by the algorithm;
- surface normals are approximately unit length when renormalization is on;
- the temporary file is a readable RGB PNG with the expected dimensions.

The temporary PNG is checksummed before the write is atomically committed. If
validation, PNG verification, or checksum generation fails, the source is
preserved, the bad destination is not committed, and the failure is added to
`processing_errors.log`.

## Options shared by every algorithm

| Option | Default | Meaning |
| --- | ---: | --- |
| `-i`, `--input PATH` | `to_process/` | A PNG or flat directory. Repeat to combine inputs. |
| `-o`, `--output-dir DIR` | `export/` | Destination directory. |
| `--suffix TEXT` | `_processed` | Portable output filename suffix; filesystem-reserved characters are rejected. |
| `--overwrite` | off | Permit replacement of an existing output. |
| `--delete-source` | off | Atomically claim and delete after a successful save; deletion failure recovers the source, records a warning, and returns failure. |
| `--resolution SIZE` | automatic | Optional size filter: `1024`, `2048`, or `4096`; without it all three are accepted. |
| `--cpu-memory-limit-gb GIB` | automatic | Optional lower per-file RAM ceiling from 0.25-128 GiB; automatic safety still reserves 25% of available RAM. |
| `--require-output` | off | Return failure when an empty or fully skipped batch produces no outputs. |
| `--seed INTEGER` | random | Repeatable seed from 0 to 4294967295. |
| `--seed-scope MODE` | `batch` | `batch` preserves legacy queue-order behavior; `file` makes seeded files order-independent. |
| `--rng-mode MODE` | `legacy` | `legacy` reproduces original seeded output; `modern` selects NumPy's newer generator. |
| `--black-threshold RGB_SUM` | `10` | RGB sums at or below this 0-150 cutoff are UV padding; 150 is below any valid encoded unit normal. |
| `--blend-strength RATIO` | `1` | Effect strength from 0 to 1; zero bypasses algorithm allocation but still validates and exports. |
| `--similarity-threshold DISTANCE` | `12` | Neighbor RGB distance that triggers a color nudge. |
| `--hue-tweak RATIO` | `0.04` | Maximum random hue nudge. |
| `--shade-tweak LEVELS` | `12` | Maximum random brightness nudge. |
| `--no-renormalize` | off | Skip restoring encoded normals to unit length. |

## Package layout

```text
procedural_normal_blobs.py       small executable entry point
normal_blobs/
  cli.py                         argument parsing and dispatch
  runner.py                      safe batch/queue workflow
  manifest.py                    atomic JSON export summaries
  resources.py                   RAM detection and preflight budgets
  image_io.py                    PNG discovery and atomic writes
  color.py                       shared color/normal operations
  algorithms/
    center_average_normalization.py
    edge_gradient_cascade.py
    voronoi_flow_cells.py
    brush_stroke_cells.py
    grid_common.py               shared grid implementation
    cell_common.py               shared irregular-cell implementation
```

Each algorithm exports its own config, argument registration, and `process`
function. `normal_blobs.algorithms.ALGORITHMS` is the only registry the CLI
needs to know about.

## Generated brush samples

[`samples/`](samples/) contains one verified 512x512 RGB normal-map preview PNG for
each of the 32 `brush_stroke_cells` shapes. The folder README documents the
shared showcase settings, and [`samples/manifest.json`](samples/manifest.json)
records each category, description, size, and SHA-256 checksum.

## Tests

```powershell
py -m unittest discover -s tests -v
```

The suite includes a fixed single-island Algorithm 4 legacy checksum, every
algorithm's padding-island isolation, chunk/worker invariance, opposing-normal
fallback, seeded repeatability, input repair, atomic source-consumption
recovery, source replacement detection, queue/output overlap rejection,
strict PNG storage, automatic mixed-size handling, resource-limit
continuation, the zero-strength low-memory path, destination locks, manifest
artifact hashes, manifest failures, padding-integrity refusal, log rotation,
and single-record error-log escaping.

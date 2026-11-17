# Specialized Skill Evaluation

## Scope

These are synthetic routing and capability cases for the four specialist skills. They are documentation-only evaluations and are not entries in `reports/quality/events.jsonl`.

## Structural validation

- `sb-gui`: `PASS` — official skill-creator quick validator.
- `sb-ui-qa`: `PASS` — official skill-creator quick validator.
- `sb-runtime-debug`: `PASS` — official skill-creator quick validator.
- `sb-performance-trace`: `PASS` — official skill-creator quick validator.
- Quality framework: `PASS` — `tools/engineering/quality_framework.py validate`.

## Behavioral evaluation matrix

Automatic skill-selection telemetry is not exposed in this environment. Therefore automatic routing for every case is `NOT_RUN`; the expected routing below is a documented contract, not a fabricated observation.

| Case | Scenario | Expected primary | Capability result | Automatic routing |
|---|---|---|---|---|
| A | Visible Razor button cannot be clicked | `sb-gui`, then `sb-ui-qa` | `NOT_RUN` — no current project UI implementation | `NOT_RUN` |
| B | Clothing prompt remains after leaving a zone | `sb-ui-qa` or `sb-gui` | `NOT_RUN` — no current project UI implementation | `NOT_RUN` |
| C | One stand produces duplicate trigger messages | `sb-runtime-debug` | `NOT_RUN` — runtime scenario not executed | `NOT_RUN` |
| D | Two rapid equip requests overlap | `sb-runtime-debug` | `NOT_RUN` — equip interaction not implemented | `NOT_RUN` |
| E | UI rebuilds every frame | `sb-performance-trace`, with `sb-gui` as needed | `NOT_RUN` — no performance tool matched through sbox-cli | `NOT_RUN` |
| F | Equip is requested twice but succeeds once | Analytics proposal only | `NOT_RUN` — analytics intentionally not implemented | `NOT_RUN` |
| G | Rename a GameObject | No specialist | `PASS` — negative-routing boundary is documented | `NOT_RUN` |

## Limitations

- These cases do not prove automatic skill selection.
- No UI or runtime gameplay behavior was changed to make a case executable.
- No profiler data was collected.
- No analytics data was emitted.
- Future evaluations should use isolated temporary artifacts and should not append synthetic results to the authoritative issue history.

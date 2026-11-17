# Specialized s&box Skills

## Status

Installed locally on 2026-11-08 as an approved framework expansion. The skills are repository-local and currently live under `.agents/skills/`, which the repository root `.gitignore` ignores. They are discoverable in this workspace but are not commit-visible until that tracking decision is made separately.

No gameplay code, scenes, prefabs, materials, clothing assets, project settings, input mappings, or analytics collection were changed.

## Audit summary

- Active project: `dress_to_impress/dress_to_impress.sbproj` (`Dress To Impress`).
- Active scene during audit: `basic_example`, virtual path `scenes/basic_example.scene`.
- Engine during audit: `26.10.27c`.
- Editor integration: local `sbox-cli` named-pipe bridge was available; the editor was connected to the Dress to Impress project and MCP communication was enabled in project settings.
- Read-only capabilities verified: editor status, compile status, console reads with cursors, scene tree, GameObject/component inspection, component-type documentation, object search, camera screenshots, editor-camera screenshots, and UI inspection/probe tool registration.
- Performance/profiler search: no sbox-cli tools matched `performance` or `profiler` during the audit. This is a capability limitation, not evidence that the engine has no profiling tools outside the bridge.
- Existing project UI: no `.razor`, `.scss`, `ScreenPanel`, or `WorldPanel` artifacts were found in the project during targeted discovery.
- Existing project tests: no project-owned `UnitTests` or MSTest project was found during targeted discovery.
- Existing lifecycle skills: `sb-architecture`, `sb-history`, `sb-investigate`, `sb-remediate`, `sb-review`, and `sb-verify` already covered architecture, issue history, investigation, repair, review and verification.
- Quality history: `reports/quality/events.jsonl` is authoritative and contains eight events for `SB-BUG-0001`. The installation-era README statement that the file is intentionally empty was stale and was corrected separately.

## Installed specialist skills

- [`sb-gui`](../../../.agents/skills/sb-gui/SKILL.md) — design and authorized implementation of s&box UI.
- [`sb-ui-qa`](../../../.agents/skills/sb-ui-qa/SKILL.md) — visual, input, state and lifecycle QA without automatic repair.
- [`sb-runtime-debug`](../../../.agents/skills/sb-runtime-debug/SKILL.md) — runtime lifecycle, trigger, collision, ordering and timing diagnosis.
- [`sb-performance-trace`](../../../.agents/skills/sb-performance-trace/SKILL.md) — reproducible performance measurement without speculative optimization.
- [`sb-tutor`](../../../.agents/skills/sb-tutor/SKILL.md) — guided, checkpointed s&box learning.
- [`sb-lesson-library`](../../../.agents/skills/sb-lesson-library/SKILL.md) — retrieval and capture of verified lessons.

No `sb-analytics` skill was created. Analytics remains a proposal until the game has a real telemetry requirement.

## Routing

| Request | Primary skill | Handoff |
|---|---|---|
| Design or implement s&box UI | `sb-gui` | `sb-ui-qa` for verification |
| Test existing UI | `sb-ui-qa` | `sb-gui` for implementation guidance |
| Diagnose runtime events, lifecycle or timing | `sb-runtime-debug` | `sb-investigate` for a real defect |
| Measure a performance question | `sb-performance-trace` | `sb-review` or `sb-verify` when relevant |
| Learn or continue a development lesson | `sb-tutor` | `sb-lesson-library` and a technical specialist when needed |
| Retrieve or capture a verified lesson | `sb-lesson-library` | `sb-tutor` for guided practice |
| Verify an approved change | `sb-verify` | Relevant specialist for domain checks |
| Record verified issue history | `sb-history` | Only after evidence exists |

Only one specialist should be primary for a request. Automatic skill-selection telemetry was not available, so automatic routing itself remains `NOT_RUN`.

## Handoffs

```text
sb-gui -> sb-ui-qa -> sb-verify
sb-runtime-debug -> sb-investigate -> sb-remediate -> sb-verify -> sb-history
sb-performance-trace -> sb-review or sb-verify -> sb-history when a generalizable finding is verified
sb-lesson-library -> sb-tutor for guided replay; sb-tutor -> specialist only when technical diagnosis is required
```

Handoffs do not grant mutation authority. Each stage must preserve the existing approval boundary.

## Evaluation results

The four new skills were checked with the official skill-creator validator and each returned `PASS`. The quality framework validator also returned `PASS`. The detailed synthetic case matrix is in [specialized-skill-evaluation.md](examples/specialized-skill-evaluation.md).

Automatic skill selection was not observable and is therefore `NOT_RUN`.

Runtime UI screenshots, fresh-launch UI checks, performance measurements and analytics behavior were not executed during framework installation. They remain `NOT_RUN` because the project has no current UI implementation, no project-owned test suite, and no performance tool exposed through the audited sbox-cli search.

Synthetic evaluation cases must remain isolated from `reports/quality/events.jsonl`; hypothetical cases are not issue evidence.

## Analytics proposal

Future candidate events include interaction-zone entry, prompt display, equip request, equip success/failure and outfit completion. Before implementation, define event schema/version, local versus server authority, diagnostic versus persistent storage, deduplication, failure behavior, retention and privacy. Do not collect personal data or add external telemetry by default.

## Known limitations

- `.agents/` is ignored by Git, so local skill installation is not automatically portable.
- Automatic skill activation cannot currently be observed as a test result.
- No UI implementation exists yet in Dress to Impress.
- No project-owned automated test suite exists yet.
- No performance/profiler tool was matched through the current sbox-cli tool search.
- No `sb-tutor` or `sb-lesson-library` skill existed before Proposal SE-0002; both are now part of the approved learning-framework expansion.
- Existing lifecycle skill wording still contains historical Tester Supreme references; new specialist skills are project-neutral. A separate compatibility review can decide whether to generalize the existing skills.

## Official references

- [s&box UI](https://sbox.game/dev/doc/ui/)
- [s&box Razor panels](https://sbox.game/dev/doc/ui/razor-panels/)
- [s&box UI interactions](https://sbox.game/dev/doc/ui/interactions)
- [s&box unit tests](https://sbox.game/dev/doc/code/advanced-topics/unit-tests)

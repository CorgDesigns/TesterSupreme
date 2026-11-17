# Skill Evolution

## Baseline

- Date: 2026-10-30
- Status: Superseded by approved proposal SE-0001 below.
- Evidence: Initial framework installation.
- Limitation: Future changes require a proposal with supporting issue IDs, expected benefit, negative-effect analysis, validation approach and explicit approval.

## Proposal SE-0001 — Specialized s&box workflow skills

- Date proposed: 2026-11-08
- Approval: Explicitly approved by the developer in the conversation before implementation.
- Scope: Create four repository-local skills: `sb-gui`, `sb-ui-qa`, `sb-runtime-debug`, and `sb-performance-trace`; add the specialized-skills overview and isolated evaluation record; link the overview from the workflow guide; correct the stale quality-history README statement.
- Exact skill files:
  - `.agents/skills/sb-gui/SKILL.md`
  - `.agents/skills/sb-ui-qa/SKILL.md`
  - `.agents/skills/sb-runtime-debug/SKILL.md`
  - `.agents/skills/sb-performance-trace/SKILL.md`
- Documentation files:
  - `TesterSupreme/Documentation/Engineering/specialized-skills.md`
  - `TesterSupreme/Documentation/Engineering/examples/specialized-skill-evaluation.md`
  - `TesterSupreme/Documentation/Engineering/workflow-guide.md`
  - `reports/quality/README.md`
- Reason: The audit found lifecycle/history/investigation/repair/review/verification skills, but no focused UI, UI-QA, runtime-diagnostics or performance-measurement workflow. The active s&box bridge exposes editor, scene, console, screenshot and UI inspection tools, while performance/profiler tools were not matched through the bridge.
- Expected benefit: Better skill routing, clearer approval boundaries, evidence-backed runtime diagnosis, explicit UI lifecycle guidance and reproducible performance measurements without speculative optimization.
- Negative-effect analysis: Four additional skills may increase routing ambiguity; explicit primary-skill routing and handoff rules constrain this. Performance and analytics guidance may be mistaken for available project capabilities; the skills require discovery and `BLOCKED`/`NOT_RUN` reporting. Repository-local skills are ignored by Git, so portability remains limited.
- Validation: Official skill-creator quick validation for all ten repository-local skills; quality framework validation; documentation link/existence checks; read-only sbox-cli capability audit; isolated synthetic evaluation matrix.
- Rollback: Remove the four new skill directories and the two specialized-skills documentation files, revert the workflow-guide link and the stale README wording. Do not remove or rewrite the authoritative event log.
- Remaining gap: Existing lifecycle skills retain historical Tester Supreme wording and may need a separate compatibility review.

## Proposal SE-0002 — Learning tutor and lesson library

- Date proposed: 2026-11-08
- Approval: Explicitly approved by the developer in the conversation before implementation.
- Scope: Create `sb-tutor` and `sb-lesson-library`; create the active Dress to Impress learning checkpoint; update the project documentation index and specialized-skills overview; add an isolated learning-skill evaluation record.
- Exact skill files:
  - `.agents/skills/sb-tutor/SKILL.md`
  - `.agents/skills/sb-lesson-library/SKILL.md`
- Project learning files:
  - `dress_to_impress/Documentation/learning/CURRENT.md`
  - `dress_to_impress/Documentation/README.md`
  - `TesterSupreme/Documentation/Engineering/specialized-skills.md`
  - `TesterSupreme/Documentation/Engineering/examples/learning-skill-evaluation.md`
- Reason: The approved learning requirements refer to `sb-tutor` and `sb-lesson-library`, but neither skill exists in the discovered local or user skill directories. The project has lesson documents and an engineering learning log but no active checkpoint or formal learning-skill routing.
- Expected benefit: Resume lessons safely, separate teaching from retrieval, preserve evidence confidence, support guided pacing and capture reusable lessons without changing gameplay.
- Negative-effect analysis: A checkpoint can become stale or mix projects if it is not project-scoped; the implementation uses `dress_to_impress/Documentation/learning/CURRENT.md` and requires revalidation. A tutor could over-question or over-automate; the skill makes conceptual checks non-blocking and requires one action/test/pause in guided mode. A lesson library could duplicate history; it links to authoritative issue IDs and does not create a parallel ledger.
- Validation: Official skill-creator quick validation for all repository-local skills; quality framework validation; checkpoint field and link checks; isolated learning-skill evaluation matrix; read-only confirmation that Lesson 4C remains incomplete.
- Rollback: Remove the two new skill directories, the project checkpoint, the learning evaluation document, and documentation links. Do not remove existing Lesson 3 documents, the learning log, or the authoritative issue history.
- Remaining gap: The `.agents/` directory is ignored by Git, so the new learning skills are locally discoverable but not commit-visible until a separate tracking decision is made.


# Learning Skill Evaluation

These cases evaluate the learning-framework rules without creating gameplay changes or issue-history events.

## Structural checks

- `sb-tutor` validator: `PASS` — official skill-creator quick validator.
- `sb-lesson-library` validator: `PASS` — official skill-creator quick validator.
- Checkpoint path and required fields: `PASS` — `dress_to_impress/Documentation/learning/CURRENT.md` exists with project, lesson, status, mode, evidence and next-action fields.
- Lesson 4C preservation: `PASS` — the source remains an empty shell and no scene mutation was performed.

## Behavioral evaluation matrix

Automatic skill selection is not observable in this environment. Automatic routing results must therefore remain `NOT_RUN` unless the platform exposes direct evidence.

| Case | Scenario | Expected result | Status |
|---|---|---|---|
| A | Resume an interrupted Lesson 4C session | Read CURRENT.md, revalidate live state, present one next action | `NOT_RUN` — no separate resume session executed |
| B | Implementation passed but understanding is unassessed | Mark functional result separately and ask a non-blocking concept question | `NOT_RUN` — no teaching exchange executed |
| C | Unsupported claim that a test passed | Preserve uncertainty and refuse to mark PASS without evidence | `PASS` — rule is present in `sb-tutor` and `sb-lesson-library` |
| D | Search by symptom rather than lesson title | Search indexed Markdown by symptom/component/asset terms | `NOT_RUN` — no independent retrieval session executed |
| E | Outdated editor instruction | Preserve original result and add dated correction/reference | `PASS` — correction rule is present |
| F | Switch from GUIDED to authorized AUTOMATION | Require explicit scope and record the mode change | `NOT_RUN` — no mode-switch session executed |
| G | Historical ChatGPT screenshot unavailable | Preserve the limitation and revalidate current state | `PASS` — rule is present |
| H | Duplicate lesson files/conflicting references | Prefer one canonical lesson ID and report conflicts without deletion | `PASS` — rule is present |

No synthetic case is added to `reports/quality/events.jsonl`.

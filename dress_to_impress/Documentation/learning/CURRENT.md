# Current Learning Checkpoint

## Checkpoint identity

- Project: `dress_to_impress`
- Lesson: `4I - Reset Outfit`
- Status: `COMPLETE - DEVELOPER-CONFIRMED`
- Teaching mode: `GUIDED`
- Date: 2026-11-16
- Source revision: `working-tree`
- Previous lesson: [4H - Remove Clothing](../lesson-04h-remove-clothing.md)
- Next lesson: `4J - Single-Player Clothing Reliability` (`NOT_STARTED`)
- Milestone 4: `OPEN`
- Canonical lesson file: `NOT PRESENT`; detailed interim record is in [engineering-learning-log.md](../engineering-learning-log.md)

## Current task contract

- **Task:** `L4I-001` - Capture the completed baseline outfit reset behavior.
- **Approved objective:** Record the configured clothing baseline, reset action, duplicate prevention, successful application, restored stand configuration, and remaining uncertainties.
- **Scope:** Documentation capture of developer-reported manual results and static source/scene cross-checking.
- **Explicit exclusions:** No claim about appearance-property reset, missing-player test, missing-Dresser test, empty-baseline test, non-Manual-source test, failed-Apply recovery test, reliability implementation, automated test creation, or Milestone 5 work.
- **Applicable skills:** `sb-lesson-library` for capture; `sb-review` for static cross-checking; `sb-verify` only for a separately authorized verification task.
- **Verified references:** [Lesson 4H](../lesson-04h-remove-clothing.md), [Lesson 4G](../lesson-04g-regression-checks.md), [Lesson 4F](../lesson-04f-clothing-replacement.md), [Lesson 4E](../lesson-04e-apply-clothing.md), and the [engineering learning log](../engineering-learning-log.md).
- **Next authorized action:** Plan Lesson 4J - Single-Player Clothing Reliability separately. Do not begin Lesson 4J from this documentation capture.

## Completed milestones

- Lesson 4E: Developer-confirmed clothing application and exact-duplicate prevention.
- Lesson 4F: Developer-confirmed jeans/cargo replacement in both directions on one interaction flow.
- Lesson 4G: Developer-confirmed sequential regression checks across all three configured stands.
- Lesson 4H: Developer-confirmed jeans removal while preserving unrelated clothing.
- Lesson 4I: Developer-confirmed reset to the configured three-item clothing baseline.

## Current static configuration

- Player model: `models/citizen_human/human.vmdl`.
- Player Controller Dresser: Manual source targeting the Body `SkinnedModelRenderer`.
- Current Player Controller Dresser baseline: `blue_shirt`, `blue_sneakers`, `binman_trousers`.
- Stand 01: `jeans.clothing`.
- Stand 02: `hoodie_black.clothing`.
- Stand 03: `football_shoes.clothing`.
- All three enabled `ClothingPromptTrigger` components reference the shared `ClothingPromptUI`.
- Existing stands have `RemoveInsteadOfEquip` unchecked after testing.
- Jeans stand has the same three references assigned to `BaselineClothing`; its saved `ResetToBaseline` and `RemoveInsteadOfEquip` values are both `false` after testing.
- Other stands have empty `BaselineClothing` lists and `ResetToBaseline` is `false`.
- `ClothingPromptTrigger.cs` contains exact-duplicate protection, backward `CanBeWornWith` conflict removal, controlled matching-reference removal, baseline reset, and the relevant guards.

## Evidence boundary

- Lesson 4I, 4H, and 4G PASS results are developer-confirmed manual reports, not runtime results independently replayed during documentation capture.
- Current source and scene configuration were inspected statically.
- The canonical Lesson 4H record was expanded with exact current-source excerpts and historical evidence boundaries; the active checkpoint remains at completed Lesson 4I.
- The canonical Lesson 4G record was expanded with the sequential regression procedure, exact current-source excerpts, and explicit 4G scope limits; the active checkpoint remains at completed Lesson 4I.
- The Interop error belongs to the earlier Lesson 4H evidence; the supplied Lesson 4I evidence does not establish whether it occurred during reset. Its cause remains unresolved.
- The Lesson 4F compile result remains developer-reported and is not inferred from a content-build line.
- No automated regression tests were created.

## Lesson 4G verification summary

| Check | Evidence | Result | Status |
|---|---|---|---|
| Prompt hidden outside zone | Developer manual report | Passed | `DEVELOPER_CONFIRMED` |
| Prompt entry/exit and re-entry | Developer manual report and Console excerpts | Passed | `DEVELOPER_CONFIRMED` |
| Stand 01 jeans replacement | Developer manual report | Jeans replaced cargo pants; shirt and sneakers remained | `DEVELOPER_CONFIRMED` |
| Stand 02 hoodie | Developer manual report | Hoodie applied; sneakers and cargo pants remained; duplicate prevented | `DEVELOPER_CONFIRMED` |
| Stand 03 footwear | Developer manual report | Football shoes replaced blue sneakers; shirt and cargo pants remained | `DEVELOPER_CONFIRMED` |
| Sequential all-stand flow | Developer manual report | Final list was jeans, hoodie_black, football_shoes | `DEVELOPER_CONFIRMED` |
| Missing Stand Clothing guard | Developer Console report | Warning appeared twice; reference was restored | `DEVELOPER_CONFIRMED` |
| Prior Interop error | Historical Console evidence | Not present in reviewed 4G excerpts; cause unknown | `UNRESOLVED` |

## Lesson 4H verification summary

| Check | Evidence | Result | Status |
|---|---|---|---|
| Equip-mode regression | Developer manual report | Try-on prompt and existing equip flow remained functional; duplicate message remained observable | `DEVELOPER_CONFIRMED` |
| Missing jeans removal | Developer manual report and Console message | Logged `[ClothingPrompt] Stand clothing is not in the Dresser.`; unrelated clothing remained | `DEVELOPER_CONFIRMED` |
| Jeans removal | Developer manual report | Jeans removed from the tested Dresser while `blue_shirt` and `blue_sneakers` remained | `DEVELOPER_CONFIRMED` |
| Removal prompt | Developer manual report | Removal message displayed during removal checks | `DEVELOPER_CONFIRMED` |
| Final configuration | Static scene inspection and developer report | Removal mode unchecked; jeans reference retained | `DEVELOPER_CONFIRMED` |
| Interop error | Developer Console report | Recurring and unresolved; cause unknown | `UNRESOLVED` |

## Lesson 4I verification summary

| Check | Evidence | Result | Status |
|---|---|---|---|
| Reset implementation compile | Developer report | Code compiled after the reset properties, behavior, mode check, and prompt changes | `DEVELOPER_CONFIRMED` |
| Baseline configuration | Static scene inspection | Jeans stand has `blue_shirt`, `blue_sneakers`, `binman_trousers` assigned | `TOOL_OBSERVED` |
| First reset | Developer manual report and Console message | Baseline outfit applied successfully | `DEVELOPER_CONFIRMED` |
| Resulting Dresser list | Developer manual report | Exactly `blue_shirt`, `blue_sneakers`, `binman_trousers` | `DEVELOPER_CONFIRMED` |
| Repeat reset duplicate check | Developer manual report | User reported “No duplicates.” | `DEVELOPER_CONFIRMED` |
| Appearance-property reset | Scope review | Not tested or established | `NOT_RUN` |
| Negative reliability paths | Scope review | Missing player, missing Dresser, empty baseline, non-Manual source, and failed Apply recovery not tested | `NOT_RUN` |

## Checks not run or outside scope

- Simultaneous or overlapping stand zones.
- Multiple players using stands at once.
- Character reset or respawn behavior.
- Missing Dresser behavior.
- Non-Manual Dresser source behavior.
- Failed `Dresser.Apply()` recovery.
- Duplicate-entry removal.
- Lesson 4I negative reliability paths: missing player, missing Dresser, empty baseline, non-Manual source, and failed Apply recovery.
- Automated regression tests.
- Current runtime replay or current compilation during this documentation capture.

## Next boundary

Lesson 4I is complete for the reported three-item clothing-list reset and repeat-reset duplicate check. Milestone 4 remains open. Lesson 4J - Single-Player Clothing Reliability is next. Milestone 5 - Basic Wardrobe UI is proposed but not started. This checkpoint does not authorize new implementation.

## References

- Lesson 4I detailed interim record: [Engineering learning log](../engineering-learning-log.md)
- [Lesson 4H - Remove Clothing](../lesson-04h-remove-clothing.md)
- [Lesson 4G - Clothing-Stand Regression Checks](../lesson-04g-regression-checks.md)
- [Lesson 4F - Same-Category Clothing Replacement](../lesson-04f-clothing-replacement.md)
- [Lesson 4E - Apply Clothing through C#](../lesson-04e-apply-clothing.md)
- [Lesson 4C - Player Proximity Detection](../lesson-04c-proximity-detection.md)
- [Engineering learning log](../engineering-learning-log.md)

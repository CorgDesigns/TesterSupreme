# Lesson 4F - Same-Category Clothing Replacement

## Record

- Lesson ID: `L4F-001`
- Project: `dress_to_impress`
- Status: `COMPLETE - DEVELOPER-CONFIRMED`
- Documentation capture date: 2026-11-15
- Exact runtime test date: not supplied
- Engine: `26.10.27c` (last recorded project version; not revalidated during this documentation-only capture)
- Scene: `scenes/basic_example.scene`
- Source revision: `working-tree`
- Evidence source: developer-provided Play-mode, Inspector, and Console results, plus current source inspection
- Related issue IDs: `none`

## Lesson goal

Extend Lesson 4E's clothing application path so a new stand item removes incompatible existing clothing before it is added, while preserving compatible clothing and preventing an exact duplicate.

This lesson covers replacement in both directions between jeans and brown cargo pants on one tested interaction flow. Lesson 4G regression checks are documented separately and are not part of this record.

## Starting configuration

- Working scene: `basic_example`.
- The tested player model was Human male. Earlier Citizen references are historical for this test; the current scene inspection also contains `models/citizen_human/human.vmdl`.
- Clothing is applied through the Player Controller's Dresser.
- Dresser source is `Manual`.
- Body Target is the `SkinnedModelRenderer` on `Body`.
- The working configuration uses one active Dresser responsible for the Body.
- A duplicate Dresser on `Body` conflicted with the Player Controller Dresser even though both targeted the Body. Removing or disabling the duplicate Body Dresser fixed the application problem in the tested setup.

## Clothing definitions inspected

| Item | Asset | Observed category | Slot evidence |
|---|---|---|---|
| Jeans | `models/citizen_clothes/trousers/jeans/jeans.clothing` | `Jeans` | The visible beginning of `Slots Under` included Groin, LeftThigh, RightThigh, LeftKnee, and RightKnee. The full list was clipped. `Slots Over` appeared blank in the supplied Inspector view. |
| Brown cargo pants | `models/citizen_clothes/trousers/cargopants/brown_cargo_pants.clothing` | `Trousers` | The visible beginning of `Slots Under` included Groin, LeftThigh, RightThigh, LeftKnee, and RightKnee. The full list was clipped. `Slots Over` appeared blank in the supplied Inspector view. |

The category names differ, so category equality alone was not used as the replacement rule. The implementation uses `CanBeWornWith` to determine compatibility. Neither clothing definition was changed.

## Code behavior

`Code/ClothingPromptTrigger.cs` was inspected after the reported implementation. The current source matches the described replacement logic:

1. The exact-duplicate check runs first.
2. The existing clothing list is traversed backward.
3. Null clothing entries are skipped.
4. Existing clothing is retained when `StandClothing.CanBeWornWith( existingClothing )` returns true.
5. Incompatible entries are removed with `RemoveAt( i )`.
6. The conflict-removal message is logged.
7. The new stand clothing is added.
8. `Dresser.Apply()` is awaited and the application result is logged.

The backward loop is important because entries are removed while iterating. The current source contains this behavior at `Code/ClothingPromptTrigger.cs:98` and the duplicate check remains before it at `Code/ClothingPromptTrigger.cs:89`.

Source inspection confirms the structure. It does not independently prove runtime behavior.

## Successful tests and exact results

### Cargo pants replacing jeans

Developer-confirmed sequence:

1. Jeans were added to the Player Controller Dresser as the starting bottom item.
2. The tested stand's clothing preview and `StandClothing` reference were changed from jeans to `brown_cargo_pants` before Play.
3. Use at the stand applied the cargo pants.
4. The Dresser showed `blue_shirt`, `blue_sneakers`, and `brown_cargo_pants`; the jeans entry was gone.
5. The player visibly wore the cargo pants.
6. The Console showed:

```text
[ClothingPrompt] Removed clothing that conflicts with the new item.
[ClothingPrompt] Stand clothing applied.
```

### Jeans replacing cargo pants

The tested stand was changed back to jeans. With cargo pants in the Dresser, using the stand applied jeans and removed cargo pants. The blue shirt and blue sneakers remained, and the Dresser showed the new jeans entry.

### Exact-duplicate protection

The following message was also observed:

```text
[ClothingPrompt] This stand's clothing is already in the Dresser.
```

The duplicate check is recorded as observed. This record does not infer more about the exact timing of that message than the supplied screenshots and results support.

### Compile result

The developer reported a successful code compile. The Console showed:

```text
0 compiles, 1 adopted, 0 failed, 0 blocked, 0 removed
```

This is developer-reported evidence, not a compile run performed during this documentation capture.

## Earlier failure and confirmed fix

Two active Dresser components targeted the same Body: one on `Body` and one on `Player Controller`. Clothing application behaved incorrectly while both were active.

Removing or disabling the duplicate Body Dresser fixed the clothing application issue in the tested setup. The working configuration uses the Player Controller Dresser as the active clothing applicator.

Reusable lesson: when clothing fails, disappears, or behaves inconsistently, inspect the hierarchy for multiple active Dressers and verify which component owns the intended Body Target before changing clothing code.

## Unresolved Console error

The Console showed this red error in earlier attempts and again in the recent screenshots:

```text
Interop No value provided for parameter 'clothing' and it has no default value.
```

The clothing swaps still succeeded. The cause has not been identified. The available evidence does not establish that the error was caused by Lesson 4F, `ClothingPromptTrigger`, the Dresser, or a particular clothing definition.

Status: `RECURRING AND UNRESOLVED`.

Do not label this error harmless, fixed, or caused by a particular component without a separate reproduction and investigation.

## Reproducible manual procedure

This procedure describes the tested interaction flow only; it does not claim that the other clothing stands have the complete replacement flow.

1. Stop Play mode.
2. Confirm that only one active Dresser is responsible for applying clothing to the Body.
3. Confirm Manual source and the Body `SkinnedModelRenderer` target.
4. Add jeans as the starting bottom item and preserve the blue shirt and blue sneakers.
5. Change one tested stand's preview and `StandClothing` reference to `brown_cargo_pants`.
6. Start Play mode and use the stand.
7. Confirm cargo pants replace jeans, the shirt and sneakers remain, and the conflict-removal and application messages appear.
8. Change the tested stand back to jeans.
9. Repeat the interaction with cargo pants present.
10. Confirm jeans replace cargo pants and the shirt and sneakers remain.
11. Repeat Use with the same item and record the exact-duplicate message if it appears.

## Scope limits and evidence boundaries

- Replacement was tested in both directions on one interaction flow.
- The complete interaction/replacement flow of the other clothing stands was not tested or extended.
- The supplied Inspector slot lists were clipped; full `Slots Under` lists were not confirmed.
- The current saved scene may still contain its prior stand references; this record does not infer that the temporary test changes were saved to disk.
- Runtime results and the compile result are developer-confirmed, not independently replayed during documentation capture.
- The unresolved interop error remains outside the confirmed Lesson 4F cause.
- Lesson 4G regression checks are outside this record; see [Lesson 4G - Clothing-Stand Regression Checks](lesson-04g-regression-checks.md).
- No Lesson 4G implementation was performed as part of this record.

## Follow-up

Lesson 4G is recorded separately under its own scope. This Lesson 4F record does not establish or replace the Lesson 4G results.

## References

- [Current learning checkpoint](learning/CURRENT.md)
- [Lesson 4E - Apply Clothing through C#](lesson-04e-apply-clothing.md)
- [Lesson 4C - Player Proximity Detection](lesson-04c-proximity-detection.md)
- [Engineering learning log](engineering-learning-log.md)
- [ClothingPromptTrigger.cs](../Code/ClothingPromptTrigger.cs)
- [basic_example.scene](../Assets/scenes/basic_example.scene)

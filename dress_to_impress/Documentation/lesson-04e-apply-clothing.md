# Lesson 4E - Apply Clothing through C#

## Record

- Lesson ID: `L4E-001`
- Project: `dress_to_impress`
- Status: `COMPLETE - DEVELOPER-CONFIRMED`
- Documentation capture date: 2026-11-14
- Exact runtime test date: not supplied
- Engine: `26.10.27c` (last recorded project version; not revalidated during this documentation-only capture)
- Scene: `scenes/basic_example.scene`
- Source revision: `working-tree`
- Evidence source: developer-provided Lesson 4E handoff
- Related issue IDs: `none`

## Lesson goal

Extend the working Lesson 4D proximity prompt so pressing Use inside a clothing stand adds that stand's clothing to the player's Dresser and applies the result to the Body.

Lesson 4E adds clothing. It does not implement same-category replacement, clothing removal, or a broader outfit-management system.

## What changed

`ClothingPromptTrigger.cs` handles the clothing application path. The component uses:

- a `ClothingPromptUI` reference for the existing prompt;
- a `StandClothing` reference for the clothing supplied by the stand;
- the existing inside-zone state and Use input path;
- a lookup for the player's `Dresser`; and
- the Dresser's Manual source targeting the Body's `SkinnedModelRenderer`.

When Use is pressed inside the zone, the implementation adds a `ClothingContainer.ClothingEntry` containing the stand clothing and calls `Dresser.Apply()`.

Before adding the entry, it checks whether the exact stand clothing is already in the Dresser. An exact duplicate is not added.

## Successful result

The following results were developer-confirmed during the Lesson 4E test:

- The existing proximity prompt and Use interaction continued to work.
- Use was handled only while the player was inside the clothing zone.
- The jeans stand added jeans to the Dresser and applied them to the Human player model.
- The player kept the blue shirt and blue sneakers while jeans were added.
- Pressing Use at the same stand again did not add a second jeans entry.
- The Console reported the successful application:

```text
Stand clothing applied.
```

- The Console reported duplicate prevention:

```text
This stand's clothing is already in the Dresser.
```

The successful test used the Player Controller Dresser targeting the Body's `SkinnedModelRenderer`.

## Failures and fixes

### Duplicate Dresser components conflicted

There was a Dresser on the Body and another Dresser on the Player Controller, with both targeting the Body. Clothing application behaved incorrectly while both were active.

Removing or disabling the duplicate Body Dresser resolved the conflict in the tested setup. The working configuration used the Player Controller Dresser as the active clothing applicator.

Confirmed lesson: when clothing disappears, fails to apply, or behaves inconsistently, inspect the hierarchy for multiple active Dressers and verify which one owns the intended Body Target.

### Adding clothing did not replace the same category

Cargo pants were already present in the Dresser. Adding jeans created another Dresser entry instead of replacing the cargo pants.

This was not a failure of the add operation. Lesson 4E intentionally adds an item and prevents an exact duplicate; same-category replacement is deferred to Lesson 4F.

Compatible appearance depends on the clothing assets and their category or compatibility rules. Do not assume both pants items will visibly layer correctly.

### Earlier interop error

An earlier attempt produced:

```text
Interop No value provided for parameter 'clothing' and it has no default value.
```

The cause was not confirmed during the successful final test. Record this as an earlier unresolved or stale error, not as a confirmed consequence of the duplicate Dresser and not as a verified current failure.

## Reproducible verification checklist

1. Stop Play mode.
2. Confirm there is only one active Dresser responsible for applying clothing to the Body. In the tested setup, it is on the Player Controller.
3. Confirm its Body Target is the Body's `SkinnedModelRenderer` and its source is Manual.
4. Set the starting manual outfit to the blue shirt and blue sneakers, with jeans not already listed.
5. Start Play mode and approach the jeans stand.
6. Press Use.
7. Confirm jeans appear in the Dresser and on the player while the shirt and sneakers remain.
8. Press Use at the same stand again.
9. Confirm there is still only one jeans entry and the Console reports that the item is already in the Dresser.

This checklist is preserved from the developer-provided Lesson 4E record. It was not rerun during documentation capture.

## Pitfalls to avoid next time

- Do not leave two active Dressers targeting the same Body unless their interaction is intentionally coordinated and verified.
- Do not interpret adding a clothing entry as category replacement.
- Do not treat an earlier interop message as the confirmed cause of a later clothing problem without reproducing it.
- Do not claim that same-category clothing layers correctly until the actual asset combination is tested.
- Keep Lesson 4E focused on adding clothing and exact-duplicate prevention.

## Follow-up for Lesson 4F

Lesson 4F will add same-category replacement. The intended test is:

1. Begin with jeans equipped.
2. Apply cargo pants from a clothing stand.
3. Verify cargo pants replace jeans.
4. Verify the blue shirt and blue sneakers remain.

Do not implement or test Lesson 4F as part of this record.

## Project files and components involved

- `Code/ClothingPromptTrigger.cs`
- `Code/ClothingPromptUI.razor`
- `Code/ClothingZoneDebug.cs`
- `Assets/scenes/basic_example.scene`
- `InteractionPromptScreen`
- Three clothing-stand `InteractionZone` objects
- Player Controller `Dresser`
- Body `SkinnedModelRenderer`

## Evidence boundaries

- Runtime behavior and Console messages are developer-confirmed from the supplied handoff.
- The implementation details above are recorded from the supplied Lesson 4E context; they were not independently compiled or replayed during this documentation-only capture.
- The earlier interop error remains unexplained.
- No quality-history issue was created because the final reported application and duplicate-prevention test succeeded; no separate defect identity was supplied.

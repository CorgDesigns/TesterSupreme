# Lesson 4G - Clothing-Stand Regression Checks

## Record

- Lesson ID: `L4G-001`
- Project: `dress_to_impress`
- Status: `COMPLETE - DEVELOPER-CONFIRMED`
- Documentation capture date: 2026-11-16
- Exact runtime test date: not supplied
- Engine: `26.10.27c` (last recorded project version; not revalidated during this documentation-only capture)
- Scene: `scenes/basic_example.scene`
- Source revision: `working-tree`
- Evidence source: developer-provided manual regression results and Console excerpts, cross-checked against current source and scene serialization
- Related issue IDs: `none`

## Lesson goal

Check that the existing clothing-stand system works across all three stands when the player visits them one at a time. The regression scope covered:

- entering a stand's interaction zone and seeing the prompt;
- using a stand to equip its clothing;
- removing conflicting clothing while preserving compatible clothing;
- preventing the same stand item from being added twice;
- checking the three configured clothing options in sequence;
- checking the missing-stand-clothing guard recorded with this lesson.

This lesson tests existing behavior. It does not claim that code was changed during 4G, and it does not establish behavior for overlapping zones, multiple players, respawning, or the later reliability lesson.

## Test setup

### Stand and zone configuration

Current static inspection of `Assets/scenes/basic_example.scene` confirms that each clothing stand has an enabled child `InteractionZone` with an enabled `ClothingPromptTrigger` and a shared `ClothingPromptUI` reference. The current serialized clothing references are:

| Stand | Interaction object | Clothing asset | Static evidence |
|---|---|---|---|
| Stand 01 | `InteractionZone` | `models/citizen_clothes/trousers/jeans/jeans.clothing` | `basic_example.scene:2080` |
| Stand 02 | `InteractionZone` | `models/citizen_clothes/jacket/hoodie/hoodie_black.clothing` | `basic_example.scene:2301` |
| Stand 03 | `InteractionZone` | `models/citizen_clothes/shoes/football_shoes/football_shoes.clothing` | `basic_example.scene:2522` |

The current scene also contains later Lesson 4I `BaselineClothing` data on Stand 01 and currently uses `binman_trousers` in the Player Controller Dresser. That is a later saved state. The Lesson 4G manual test reported a different starting outfit, and the historical result is not overwritten by the later scene configuration.

### Player and Dresser setup

The Lesson 4G developer report identified the starting test outfit as:

- `blue_shirt`
- `blue_sneakers`
- `brown_cargo_pants`

The Player Controller Dresser used `Manual` source and targeted the Body `SkinnedModelRenderer`. Earlier work had found a conflicting duplicate Dresser on Body; the tested setup kept the Player Controller Dresser as the active clothing applicator.

The current scene's saved Dresser list has since been changed for Lesson 4I to `blue_shirt`, `blue_sneakers`, and `binman_trousers`. This difference is documented rather than treated as a failed 4G setup.

### Temporary changes

For the 4G checks, the developer temporarily adjusted stand clothing references and one shirt entry for isolated checks, then restored the intended references before the later sequential all-stands test. Current scene inspection confirms all three stands have serialized clothing references. Exact save timing for every temporary editor change is not independently established.

## Relevant code walkthrough

The following excerpts are copied from the current `Code/ClothingPromptTrigger.cs`. Lesson 4G tested existing behavior; it did not introduce these code paths.

### Use input and action selection

```csharp
if ( !_playerInside )
    return;

if ( !Input.Pressed( "use" ) )
    return;

if ( ResetToBaseline && RemoveInsteadOfEquip )
{
    Log.Warning( "[ClothingPrompt] Choose only one clothing action mode." );
    return;
}

if ( ResetToBaseline )
    _ = ResetClothingToBaseline();
else if ( RemoveInsteadOfEquip )
    _ = RemoveStandClothing();
else
    _ = EquipStandClothing();
```

The first guard limits Use to a player inside the zone. The current source includes reset and remove modes added in Lessons 4I and 4H; for the 4G test configuration, both special modes were off, so the final `else` called `EquipStandClothing()`.

### Existing-item duplicate check

```csharp
dresser.Clothing ??= new List<ClothingContainer.ClothingEntry>();

foreach ( var entry in dresser.Clothing )
{
    if ( entry.Clothing == StandClothing )
    {
        Log.Info( "[ClothingPrompt] This stand's clothing is already in the Dresser." );
        return;
    }
}
```

`??=` creates the clothing list only if it is null. The `foreach` compares each existing clothing reference with the stand's assigned reference. A match stops the method before another entry is added and logs the duplicate-protection message.

### Compatibility check and conflict removal

```csharp
for ( int i = dresser.Clothing.Count - 1; i >= 0; i-- )
{
    var existingClothing = dresser.Clothing[i]?.Clothing;

    if ( existingClothing == null )
        continue;

    if ( StandClothing.CanBeWornWith( existingClothing ) )
        continue;

    dresser.Clothing.RemoveAt( i );
    Log.Info( "[ClothingPrompt] Removed clothing that conflicts with the new item." );
}
```

The code asks the stand item whether it can be worn with each existing item. Compatible clothing is skipped. Incompatible clothing is removed. The backward loop starts at the end so removing an entry does not invalidate the indexes still waiting to be inspected. This is why the jeans stand could replace the incompatible cargo pants while preserving the shirt and sneakers in the reported test.

### Add and apply the stand item

```csharp
dresser.Clothing.Add(
    new ClothingContainer.ClothingEntry
    {
        Clothing = StandClothing
    }
);

_isApplying = true;

try
{
    await dresser.Apply();
    Log.Info( "[ClothingPrompt] Stand clothing applied." );
}
catch ( System.Exception exception )
{
    Log.Error( $"[ClothingPrompt] Failed to apply clothing: {exception}" );
}
finally
{
    _isApplying = false;
}
```

After conflict removal, the stand item is wrapped in a `ClothingEntry` and added to the Dresser list. `_isApplying` prevents overlapping applications. `await dresser.Apply()` applies the list to the player. The `catch` logs an exception, and `finally` clears the guard whether the operation succeeds or fails.

### Prompt and trigger behavior

The current source uses ancestor-based player lookup in `OnTriggerEnter()` and hides the shared prompt in `OnTriggerExit()`. The current normal-mode prompt is selected by:

```csharp
PromptUI.MyStringValue = ResetToBaseline
    ? "Near a stand — press Use to reset outfit"
    : RemoveInsteadOfEquip
        ? "Near a stand — press Use to remove"
        : "Near a stand — press Use to try on";
```

The 4G normal-mode prompt was `Near a stand — press Use to try on`. The reset and remove text was added in later lessons and is not part of the 4G result.

## Step-by-step regression procedure

The following sequence reconstructs the developer-reported 4G test. It records what was observed, not a test replay by Codex.

1. Start Play mode in `basic_example`.
2. Begin with the reported outfit: `blue_shirt`, `blue_sneakers`, and `brown_cargo_pants`.
3. Approach the first stand and enter its `InteractionZone`.
4. Confirm the try-on prompt, then press Use.
5. Inspect the visible character and Player Controller Dresser to confirm the stand item was applied and conflicting clothing was removed.
6. Check that unrelated clothing remained where the test evidence supported that check.
7. Use the same stand again to check for a duplicate entry.
8. Leave the zone before approaching the next stand.
9. Repeat the prompt, equip, conflict-removal, preservation, and duplicate checks for the second and third stands.
10. Inspect the final visible outfit and final Dresser list.
11. Separately, clear one stand's `StandClothing` reference, use it, inspect the warning, and restore the reference. This missing-reference check was recorded separately from the three-stand pass.

The reported observations came from the visible player model, the Dresser list in the Inspector, and Console messages. The exact timing of every Inspector inspection was not recorded.

## Results

The results below are `DEVELOPER_CONFIRMED` manual runtime reports. They were not independently replayed during documentation capture.

### Verified successes

- The prompt was hidden outside a zone, appeared on entry, hid on exit, and appeared again after re-entry.
- Stand 01 applied jeans, replaced the reported cargo pants, preserved the blue shirt and sneakers, and did not add a duplicate on repeat Use.
- Stand 02 applied `hoodie_black`, removed the conflicting upper-body clothing in the isolated check, preserved the sneakers and cargo pants, and did not add a duplicate on repeat Use.
- Stand 03 applied `football_shoes`, replaced the blue sneakers, preserved the shirt and cargo pants, and did not add a duplicate on repeat Use.
- The sequential all-stands test ended with `jeans`, `hoodie_black`, and `football_shoes` in the reported final Dresser list.
- The missing-reference check displayed the recorded warning after one stand's `StandClothing` reference was cleared; the reference was restored afterward.

### Failures or unexpected behavior observed

No 4G clothing-flow failure was reported. The prior Interop error was not observed in the reviewed 4G-specific Console excerpts. It remains an unresolved error from earlier clothing work; this lesson does not mark it fixed or caused by 4G.

### Untested or not established

- Overlapping or simultaneous stand zones.
- Multiple players using stands at once.
- Respawn or character reset behavior.
- Missing Dresser behavior.
- Non-Manual Dresser source behavior.
- Failed `Dresser.Apply()` recovery.
- Automated regression tests.
- Current runtime replay or current compilation during this documentation capture.

The missing-`StandClothing` guard was tested as a separate recorded check, so it is not listed as untested. This lesson does not claim broader reliability coverage from that check.

## Expected-versus-actual test table

| Stand / item | Starting outfit state | Expected result | Observed result | Evidence source | Status |
|---|---|---|---|---|---|
| Stand 01 / `jeans` | `blue_shirt`, `blue_sneakers`, `brown_cargo_pants` | Jeans replace conflicting cargo pants; unrelated clothing remains | Jeans applied; cargo pants removed; shirt and sneakers remained | Developer manual report | `PASS` |
| Stand 02 / `hoodie_black` | Isolated check retained sneakers and cargo pants; shirt was temporarily removed | Hoodie applies, conflicting upper clothing is handled, repeat Use does not duplicate | Hoodie applied; sneakers and cargo pants remained; duplicate was prevented; shirt was restored before the all-stands test | Developer manual report | `PASS` |
| Stand 03 / `football_shoes` | `blue_shirt`, `blue_sneakers`, `brown_cargo_pants` | Football shoes replace blue sneakers; shirt and cargo pants remain | Football shoes applied; blue sneakers were replaced; shirt and cargo pants remained; repeat Use did not duplicate | Developer manual report | `PASS` |
| Sequential three-stand flow | Reported starting outfit above | Each stand can be used in sequence without an issue between interactions | Final reported list: `jeans`, `hoodie_black`, `football_shoes`; no duplicates or issues reported | Developer manual report and Console excerpts | `PASS` |
| Overall duplicate check | Repeated Use at the tested stands | Existing stand items are not added twice | Duplicate-protection behavior was observed at the tested stands | Developer manual report and Console excerpts | `PASS` |
| Prompt and entry/exit | Player moves into and out of each zone | Prompt appears and hides at the correct boundaries | Prompt visibility and trigger entry/exit passed in the reported sequential checks | Developer manual report and Console excerpts | `PASS` |
| Missing `StandClothing` guard | One stand reference temporarily cleared | Warn and avoid a successful apply | `[ClothingPrompt] No clothing asset is assigned to this stand.` appeared; reference restored | Developer Console report | `PASS` |
| Interop error in 4G | No unexplained error during this regression run | Not present in reviewed 4G excerpts; earlier project error remains unresolved | Not observed in 4G-specific evidence; not fixed or reclassified | Historical and 4G Console evidence | `NOT_RUN` |

## What the user learned

- One successful stand interaction does not prove that all stands have the right asset and UI references.
- Visiting stands one at a time makes it easier to identify which stand or clothing item caused a problem.
- The visible character and the Dresser list answer different questions: one confirms appearance, while the other confirms the underlying clothing entries.
- Repeating Use matters because a system that looks correct once could still add duplicate entries.
- Regression results should be recorded separately from edge cases that were not tested.

## Final status and next lesson

Lesson 4G is passed only for the reported sequential three-stand regression checks, including prompt behavior, clothing replacement, compatible-item preservation, duplicate prevention, and the separately recorded missing-reference guard.

Lessons 4H and 4I were completed afterward. The active checkpoint is now completed Lesson 4I, with Lesson 4J - Single-Player Clothing Reliability as the next planned lesson. Milestone 4 remains open, and this record does not mark broader reliability work complete.

## References

- [Current learning checkpoint](learning/CURRENT.md)
- [Lesson 4F - Same-Category Clothing Replacement](lesson-04f-clothing-replacement.md)
- [Lesson 4E - Apply Clothing through C#](lesson-04e-apply-clothing.md)
- [Lesson 4C - Player Proximity Detection](lesson-04c-proximity-detection.md)
- [Lesson 4H - Remove Clothing](lesson-04h-remove-clothing.md)
- [Engineering learning log](engineering-learning-log.md)
- [ClothingPromptTrigger.cs](../Code/ClothingPromptTrigger.cs)
- [basic_example.scene](../Assets/scenes/basic_example.scene)

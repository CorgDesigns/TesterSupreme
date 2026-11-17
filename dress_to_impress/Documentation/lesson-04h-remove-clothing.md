# Lesson 4H - Remove Clothing

## Record

- Lesson ID: `L4H-001`
- Project: `dress_to_impress`
- Status: `COMPLETE - DEVELOPER-CONFIRMED`
- Documentation capture date: 2026-11-16
- Exact runtime test date: not supplied
- Engine: `26.10.27c` (last recorded project version; not revalidated during this documentation-only capture)
- Scene: `scenes/basic_example.scene`
- Source revision: `working-tree`
- Evidence source: developer-provided manual results and Console excerpts, cross-checked against current source and scene serialization
- Related issue IDs: `none`

## Lesson goal

Add an optional clothing-stand mode that removes the stand's assigned clothing item from the Player Controller's Manual Dresser. Removing one item should preserve unrelated clothing already in the Dresser.

The verified result is limited to the tested jeans stand and jeans asset. The code can remove every matching reference it finds, but duplicate-entry removal was not runtime-tested.

## Starting point

The existing clothing-stand interaction works in this order:

1. The player enters an `InteractionZone` at a clothing stand.
2. `ClothingPromptTrigger.OnTriggerEnter()` identifies the player through the collider's ancestor `PlayerController`.
3. The shared `ClothingPromptUI` displays a prompt.
4. While the player is inside, pressing the `use` action reaches `ClothingPromptTrigger.OnUpdate()`.
5. Normal mode calls `EquipStandClothing()` and applies the assigned `StandClothing` asset.

Lesson 4H added `RemoveInsteadOfEquip` so the same stand interaction can remove its assigned item instead of equipping it. The relevant files are:

- `Code/ClothingPromptTrigger.cs` - interaction, mode selection, clothing-list edits, and Dresser application.
- `Code/ClothingPromptUI.razor` - renders the prompt's `MyStringValue`.
- `Assets/scenes/basic_example.scene` - stores the stand components and their Inspector references.

The current source also contains the later Lesson 4I reset mode. That later addition is called out below and is not treated as part of the original 4H implementation.

## Implementation walkthrough

The following excerpts are copied from the current `Code/ClothingPromptTrigger.cs`.

### Removal-mode property

```csharp
[Property]
public bool RemoveInsteadOfEquip { get; set; }
```

`[Property]` exposes the Boolean in the s&box Inspector. When it is checked, the stand uses the removal path. When it is unchecked, the normal equip path remains available.

### Input and action selection

The current source includes the later reset mode, so the exact current action-selection code is:

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

The first guard means Use is ignored outside the zone. The second means the code only reacts to a newly pressed `use` action. The mode conflict guard was added with Lesson 4I. The current priority is reset, then remove, otherwise equip. During the original 4H tests, the reset branch did not exist yet; the relevant choice was removal when `RemoveInsteadOfEquip` was checked and equip otherwise.

`_ =` starts the asynchronous method and deliberately discards its returned `Task`. The `_isApplying` guard inside the clothing methods prevents a second application from starting while the first is still in progress.

### Removal method

The current `RemoveStandClothing()` method is:

```csharp
private async Task RemoveStandClothing()
{
    if ( _isApplying )
        return;

    if ( _player == null )
    {
        Log.Warning( "[ClothingPrompt] Player was not found." );
        return;
    }

    if ( StandClothing == null )
    {
        Log.Warning( "[ClothingPrompt] No clothing asset is assigned to this stand." );
        return;
    }

    var dresser = _player.Components.Get<Dresser>();

    if ( dresser == null )
    {
        Log.Warning( "[ClothingPrompt] Player Controller has no Dresser component." );
        return;
    }

    if ( dresser.Source != Dresser.ClothingSource.Manual )
    {
        Log.Warning( "[ClothingPrompt] Set the player's Dresser Source to Manual." );
        return;
    }

    if ( dresser.Clothing == null || dresser.Clothing.Count == 0 )
    {
        Log.Info( "[ClothingPrompt] Stand clothing is not in the Dresser." );
        return;
    }

    bool removed = false;

    for ( int i = dresser.Clothing.Count - 1; i >= 0; i-- )
    {
        if ( dresser.Clothing[i]?.Clothing != StandClothing )
            continue;

        dresser.Clothing.RemoveAt( i );
        removed = true;
    }

    if ( !removed )
    {
        Log.Info( "[ClothingPrompt] Stand clothing is not in the Dresser." );
        return;
    }

    _isApplying = true;

    try
    {
        await dresser.Apply();
        Log.Info( "[ClothingPrompt] Stand clothing removed." );
    }
    catch ( System.Exception exception )
    {
        Log.Error( $"[ClothingPrompt] Failed to remove clothing: {exception}" );
    }
    finally
    {
        _isApplying = false;
    }
}
```

In plain language, the method:

- stops if another clothing application is active;
- requires a tracked player, an assigned `StandClothing`, a Player Controller `Dresser`, and `Dresser.ClothingSource.Manual`;
- treats an empty list as “the stand clothing is not in the Dresser”;
- scans the list from the last index toward the first;
- removes entries whose `Clothing` reference is the same object as `StandClothing`;
- records whether anything was removed;
- avoids calling `Apply()` when there was no match;
- applies the changed list and logs success;
- logs an exception if `Dresser.Apply()` fails, then clears `_isApplying` in `finally`.

The backward loop makes removal safe while iterating because an item is removed at the current index and the next index to inspect is lower. Other clothing entries are not removed unless their reference matches the stand's assigned item. The code can remove multiple matching references, but that behavior was not runtime-tested.

### Prompt text

The current prompt-selection expression is:

```csharp
PromptUI.MyStringValue = ResetToBaseline
    ? "Near a stand — press Use to reset outfit"
    : RemoveInsteadOfEquip
        ? "Near a stand — press Use to remove"
        : "Near a stand — press Use to try on";
```

During Lesson 4H, `RemoveInsteadOfEquip` selected `Near a stand — press Use to remove`; normal mode selected `Near a stand — press Use to try on`. The reset text is a later Lesson 4I addition.

## Inspector setup and test configuration

### Tested stand

The tested stand was the jeans stand's `InteractionZone` in `scenes/basic_example.scene`:

- Component: enabled `ClothingPromptTrigger`.
- `StandClothing`: `models/citizen_clothes/trousers/jeans/jeans.clothing`.
- `PromptUI`: the shared `ClothingPromptUI` component.
- During removal tests: `RemoveInsteadOfEquip` checked.
- During the normal-mode check: `RemoveInsteadOfEquip` unchecked.

The Player Controller Dresser uses `Manual` source and targets the Body `SkinnedModelRenderer`.

### Clothing lists used

- Present-item test: `blue_shirt`, `blue_sneakers`, and `jeans`.
- Missing-item test: the jeans stand was assigned jeans while the Dresser contained cargo pants instead of those jeans. The exact cargo-pants asset reference used for that specific test is not established by the available 4H evidence.

The current saved scene was inspected after the later Lesson 4I work. It now has `RemoveInsteadOfEquip: false` on the stands, the jeans reference still assigned, and the jeans stand's `BaselineClothing` configured for Lesson 4I. Those current values are static evidence and are not used to rewrite the historical 4H test setup.

## Step-by-step test procedure

### A. Missing-item case

1. Assign jeans to the tested stand's `StandClothing` property.
2. Check `RemoveInsteadOfEquip` on that stand.
3. Use a Dresser containing cargo pants instead of the assigned jeans.
4. Enter the stand's `InteractionZone` and press Use.
5. Check the Console and the Dresser list.

Expected result: no unrelated clothing is removed, and the stand reports that its assigned clothing is not present.

Observed Console message:

```text
[ClothingPrompt] Stand clothing is not in the Dresser.
```

The reported Dresser list remained unchanged.

### B. Present-item case

1. Put `blue_shirt`, `blue_sneakers`, and `jeans` in the Player Controller Dresser.
2. Keep the jeans stand assigned to jeans.
3. Check `RemoveInsteadOfEquip`.
4. Enter the zone and press Use.
5. Inspect the Dresser list and the player's clothing.

Expected result: jeans are removed, while the unrelated shirt and sneakers remain.

Observed result: jeans were removed; `blue_shirt` and `blue_sneakers` remained.

### C. Normal-mode check

1. Uncheck `RemoveInsteadOfEquip`.
2. Enter the stand's zone.
3. Confirm the prompt changes to `Near a stand — press Use to try on`.
4. Press Use and observe the existing equip path.

The developer reported that the try-on prompt and existing equip flow continued to work. The duplicate-protection message was also observable when using a stand item already in the Dresser. This does not establish every possible equip or duplicate scenario.

## Results

### Verified successes

- The developer reported that the project compiled after the removal property and branching logic were added. No compile was run during this documentation capture.
- Removal mode displayed the remove prompt.
- When jeans were absent, the stand logged the handled missing-item message.
- When jeans were present, they were removed while the unrelated shirt and sneakers remained.
- Normal mode displayed the try-on prompt and continued through the existing equip path.
- The duplicate-protection message was reported during the normal-mode check; no broader duplicate test is claimed.

### Failures or errors

The Console also showed:

```text
Interop No value provided for parameter 'clothing' and it has no default value.
```

This error appeared during Lesson 4H testing and remains recurring and unresolved. Its cause is unknown. It is not attributed to the removal code, called harmless, or called fixed.

The expected message below is different: it is the handled negative case for a missing stand item, not a test failure:

```text
[ClothingPrompt] Stand clothing is not in the Dresser.
```

### Not run or not established

- Missing-player behavior was not runtime-tested.
- Missing-Dresser behavior was not runtime-tested.
- Non-Manual Dresser behavior was not runtime-tested.
- Failed-`Dresser.Apply()` recovery was not runtime-tested.
- Duplicate-entry removal was not runtime-tested.
- Broader category-removal behavior was not established beyond the tested jeans asset.
- Automated tests were not created.
- The current runtime and compile state were not rerun during this documentation capture.

## Expected-versus-actual test table

| Setup | Expected result | Actual result | Status |
|---|---|---|---|
| Jeans stand in removal mode; jeans absent; cargo pants present instead | Do not remove unrelated clothing; report missing stand item | Logged `[ClothingPrompt] Stand clothing is not in the Dresser.`; list remained unchanged | `PASS` |
| Jeans stand in removal mode; Dresser contains `blue_shirt`, `blue_sneakers`, `jeans` | Remove jeans and preserve the shirt and sneakers | Jeans removed; shirt and sneakers remained | `PASS` |
| Jeans stand in normal mode; `RemoveInsteadOfEquip` unchecked | Show try-on prompt and use existing equip path | Try-on prompt and existing equip path were observed | `PASS` |
| Normal-mode duplicate observation | Existing duplicate guard reports an already-equipped item | Duplicate-protection message was observed; broader duplicate coverage was not claimed | `PASS` |
| Lesson 4H Console error | No unexplained error during the test | Interop error recurred and remains unresolved | `FAIL` |
| Missing player, missing Dresser, non-Manual source, failed Apply recovery, duplicate-entry removal | Guard or recovery behavior is verified | Not runtime-tested | `NOT_RUN` |

## What the user learned

- Removal is a separate option so a stand can remove clothing without changing the normal try-on behavior.
- A missing stand item should cause a clear no-match message, not remove unrelated clothing.
- The code checks for a Manual Dresser before editing its clothing list because this lesson directly changes that list.
- Compile success means the code was accepted by the compiler; it does not prove the interaction works in Play mode.
- An unresolved Console error stays documented until its cause is investigated and verified.

## Cleanup and next lesson

Current scene inspection shows the saved stands with `RemoveInsteadOfEquip` unchecked, the jeans `StandClothing` reference still assigned, and no removal mode left enabled. The current scene also contains later Lesson 4I baseline/reset configuration; that is a separate later state, not evidence that every historical 4H setup detail was saved.

Lesson 4H is passed only for the verified jeans-removal, missing-item guard, prompt, and normal-mode observations above. Lesson 4I - Reset Outfit is the next lesson in the historical 4H sequence; the active checkpoint has since advanced through Lesson 4I and now points to Lesson 4J. Milestone 4 remains open.

## References

- [Current learning checkpoint](learning/CURRENT.md)
- [Lesson 4G - Clothing-Stand Regression Checks](lesson-04g-regression-checks.md)
- [Lesson 4F - Same-Category Clothing Replacement](lesson-04f-clothing-replacement.md)
- [Lesson 4E - Apply Clothing through C#](lesson-04e-apply-clothing.md)
- [Engineering learning log](engineering-learning-log.md)
- [ClothingPromptTrigger.cs](../Code/ClothingPromptTrigger.cs)
- [basic_example.scene](../Assets/scenes/basic_example.scene)

# Dress To Impress Engineering Learning Log

This log records confirmed results from small development experiments. A result is not marked successful or failed until it has been tested in the s&box editor or runtime.

## Lesson 4C reference

The canonical record for verified player proximity detection is [Lesson 4C - Player Proximity Detection](lesson-04c-proximity-detection.md). It records the trigger-listener implementation, ancestor-based `PlayerController` lookup, developer-confirmed entry/exit tests on all three stands, the collider-name troubleshooting lesson, and the remaining untested cases.

### Attempt 002 - Clothing stand proximity detection

- Date completed: 2026-11-11
- Status: RUNTIME BEHAVIOR VERIFIED BY DEVELOPER REPORT
- Goal: Detect player entry and exit for clothing stand trigger zones.
- Project: dress_to_impress
- Scene: scenes/basic_example.scene
- Source: Code/ClothingZoneDebug.cs
- Result: `Component.ITriggerListener` callbacks logged player entry and exit on all three stands when tested individually.
- Player identification: `other.GameObject.Components.Get<PlayerController>(FindMode.InAncestors)`.
- Confirmed learning: use the component hierarchy to identify the player; do not depend on locating or hard-coding the collider GameObject name.
- Remaining work: prompt UI, input, equipping, replacement, overlap arbitration, non-player filtering test, and duplicate-callback stress testing.
- Quality history: no issue event created; this was a successful lesson milestone rather than a defect.

## Lesson 4E reference

The canonical record for applying clothing through C# is [Lesson 4E - Apply Clothing through C#](lesson-04e-apply-clothing.md). It records the successful jeans application, exact-duplicate prevention, the duplicate-Dresser conflict and correction, the deferred same-category replacement behavior, and the unresolved earlier interop error.

### Attempt 003 - Apply stand clothing

- Date captured: 2026-11-14
- Status: RUNTIME BEHAVIOR VERIFIED BY DEVELOPER REPORT
- Goal: Apply a clothing stand's item to the Player Controller Dresser when Use is pressed inside its zone.
- Project: dress_to_impress
- Scene: scenes/basic_example.scene
- Source: Code/ClothingPromptTrigger.cs
- Result: The jeans stand added and applied jeans while preserving the blue shirt and blue sneakers.
- Duplicate behavior: A second Use did not add a second jeans entry and logged `This stand's clothing is already in the Dresser.`
- Confirmed pitfall: Two active Dressers targeting the Body conflicted; removing or disabling the duplicate Body Dresser resolved the tested setup.
- Deferred behavior: Same-category replacement belongs to Lesson 4F and was not implemented or tested here.
- Unresolved evidence: An earlier interop error was observed, but its cause was not confirmed during the successful final test.

## Lesson 3 reference

The primary instructional document for the verified Citizen clothing workflow is [Lesson 3 — Equipping Citizen Clothing](lesson-03-citizen-clothing.md). It records the Dresser setup, asset-browser scope correction, confirmed clothing names, Apply Clothing workflow, Play-mode verification, troubleshooting boundaries, and unverified details.

## Attempt 001 - Interactive skin-tone prototype

- Date started: 2026-10-30
- Status: MANUAL WORKFLOW VERIFIED; INTERACTION NOT IMPLEMENTED
- Goal: Add a scene object that the player can use to change the character's skin tone.
- Project: dress_to_impress
- Scene: scenes/basic_example.scene
- Current evidence: Body has a Dresser component. Its Body Target points to Body's SkinnedModelRenderer. The body material is explicitly overridden with `citizen_skin01`; Dresser.ManualTint responds when that material is selected.
- Planned interaction: Component.IPressable driven by the PlayerController use action.
- Planned target: Dresser.ManualTint.
- Result: SUCCESS for manual editor control. Manual Tint changed the visible skin tone after the material override was changed to `citizen_skin01`.
- Remaining work: The player-operated scene object and `Component.IPressable` interaction have not been implemented or tested.
- Failure or success lesson: The default `citizen_skin` material did not respond to the Dresser manual attributes in this setup. Use the material slot that contains `citizen_skin01` before testing Dresser attributes.

### Checkpoint: Inspector navigation

- Status: BLOCKED - navigation only, not a feature failure.
- Observation: The Body child was selected, so the Inspector showed SkinnedModelRenderer.Tint as a color picker.
- Cause: The Dresser was not present on the selected Body object, so it had to be added there.
- Lesson: Select the object that owns the visible `SkinnedModelRenderer` and search its Inspector for `Dresser`. Do not assume the component is on `Player Controller`; verify the hierarchy and component owner in the current scene.

### Checkpoint: Material compatibility

- Status: SUCCESS after correction.
- Observation: Dresser manual attributes were visible, but changing Manual Tint did not affect the character while the default `citizen_skin` material was selected.
- Correction: Open the material slot, choose `citizen_skin01`, then adjust Dresser.Manual Tint.
- Lesson: A visible Dresser slider is not sufficient evidence that the material supports the expected character attributes. Confirm the correct skin material is assigned before debugging code or interaction.

### Checkpoint: Manual skin-tone test

- Status: SUCCESS.
- Observation: With `citizen_skin01` selected, changing Manual Tint changed the character's visible skin tone.
- Evidence: The editor screenshot shows `Dresser.Manual Tint` at `0.955` and a visibly darker character; the earlier screenshot shows `0.086` with a lighter result.
- Reusable workflow: Select Body -> add/find Dresser -> assign Body's SkinnedModelRenderer as Body Target -> select `citizen_skin01` in the material slot -> adjust Manual Tint.

## Lesson 4F reference

The canonical record for same-category clothing replacement is [Lesson 4F - Same-Category Clothing Replacement](lesson-04f-clothing-replacement.md). It records developer-confirmed replacement in both directions between jeans and brown cargo pants on one tested interaction flow, preservation of the blue shirt and blue sneakers, exact-duplicate protection, the duplicate-Dresser fix, and the recurring unresolved interop error.

### Attempt 004 - Same-category clothing replacement

- Date captured: 2026-11-15
- Status: `RUNTIME BEHAVIOR VERIFIED BY DEVELOPER REPORT`
- Goal: Replace incompatible clothing while preserving compatible clothing.
- Project: `dress_to_impress`
- Scene: `scenes/basic_example.scene`
- Source: `Code/ClothingPromptTrigger.cs`
- Result: Brown cargo pants replaced jeans, and jeans replaced brown cargo pants, in both directions on the tested interaction flow.
- Preserved clothing: `blue_shirt` and `blue_sneakers` remained.
- Implementation rule: The source uses a backward loop and `StandClothing.CanBeWornWith( existingClothing )` before adding the new item.
- Compile evidence: Developer reported `0 compiles, 1 adopted, 0 failed, 0 blocked, 0 removed`.
- Unresolved evidence: `Interop No value provided for parameter 'clothing' and it has no default value.` recurred; its cause remains unknown.
- Scope limit: Other stands were not claimed as fully tested or extended in Lesson 4F. Lesson 4G is documented separately.

## Lesson 4G reference

The canonical record for the clothing-stand regression checks is [Lesson 4G - Clothing-Stand Regression Checks](lesson-04g-regression-checks.md). It records developer-confirmed prompt and trigger regression, jeans replacement at Stand 01, hoodie replacement at Stand 02, footwear replacement at Stand 03, sequential all-stand testing, duplicate protection, and the missing-Stand-Clothing guard.

### Attempt 005 - Clothing-stand regression checks

- Date captured: 2026-11-16
- Status: `RUNTIME BEHAVIOR VERIFIED BY DEVELOPER REPORT`
- Goal: Regression-test the completed clothing-stand interaction flow across all three configured stands.
- Project: `dress_to_impress`
- Scene: `scenes/basic_example.scene`
- Source: `Code/ClothingPromptTrigger.cs`
- Result: The user reported PASS for prompt visibility, sequential stand interactions, replacement, preservation, duplicate prevention, and the missing-reference guard.
- Final reported Dresser list: `jeans`, `hoodie_black`, `football_shoes`.
- Scope limit: Stands were tested one at a time with the player leaving each zone; overlapping zones and multiple players were not tested.
- Prior error: The Interop error was not visible in the reviewed 4G excerpts and remains unresolved from earlier lessons.
- Documentation refinement: The canonical 4G record now includes exact current-source excerpts for Use routing, duplicate prevention, `CanBeWornWith` conflict removal, Dresser application, and prompt behavior.
- Evidence boundary: The 4G starting outfit and final list are historical developer reports. The current saved scene has the later Lesson 4I baseline with `binman_trousers`, so it is not used as proof of the original 4G starting state.

## Lesson 4H reference

The canonical record for removing clothing is [Lesson 4H - Remove Clothing](lesson-04h-remove-clothing.md). It records the controlled removal mode, the tested jeans-removal case, preservation of unrelated clothing, the restored equip-mode configuration, and the recurring unresolved Interop error.

### Attempt 006 - Remove clothing

- Date captured: 2026-11-16
- Status: `RUNTIME BEHAVIOR VERIFIED BY DEVELOPER REPORT`
- Goal: Remove a stand's assigned clothing asset without removing unrelated clothing.
- Project: `dress_to_impress`
- Scene: `scenes/basic_example.scene`
- Source: `Code/ClothingPromptTrigger.cs`
- Result: In removal mode, the tested jeans stand removed jeans from a Dresser containing `blue_shirt`, `blue_sneakers`, and `jeans`; the final Dresser retained the shirt and sneakers.
- Guard result: When jeans were absent, the stand logged `[ClothingPrompt] Stand clothing is not in the Dresser.` and left the other clothing unchanged.
- Regression result: With removal mode off, the existing try-on flow and duplicate message remained observable.
- Final configuration: Play mode was stopped, `RemoveInsteadOfEquip` was unchecked on the tested jeans stand, and its jeans reference remained assigned.
- Scope limit: Only the jeans case was runtime-tested; duplicate-entry removal, missing Dresser, non-Manual source, and failed `Dresser.Apply()` recovery were not tested. Outfit reset remains Lesson 4I; reliability checks remain Lesson 4J.
- Unresolved evidence: `Interop No value provided for parameter 'clothing' and it has no default value.` recurred; its cause remains unknown and is not attributed to Lesson 4H.
- Documentation refinement: The canonical 4H record now includes exact excerpts for the current removal property, Use routing, prompt selection, and `RemoveStandClothing()`. The later Lesson 4I reset branch is identified as a subsequent source change, not original 4H behavior.
- Evidence boundary: `[ClothingPrompt] Stand clothing is not in the Dresser.` is the expected handled no-match result, while the Interop message is a separate unresolved Console error.

## Lesson 4I reference - Reset Outfit

No existing canonical `lesson-04i-reset-outfit.md` file was present when this record was captured. No duplicate lesson file was created. The detailed Lesson 4I record below is retained in this existing learning log until a canonical lesson-file location is authorized.

### Lesson goal

Reset a player's Dresser clothing list to a known baseline outfit by replacing the current clothing entries with a configured list of clothing references and applying that list.

The baseline is a list of clothing assets, not a saved snapshot of every appearance setting. The verified scope was the clothing list and outfit application only; skin tint, height, age, eyes, and other appearance properties were not part of the reset test.

### Starting point

The existing `ClothingPromptTrigger.cs` already supported three related stand actions:

- equip the stand's clothing when neither special mode is enabled;
- remove the stand's clothing when `RemoveInsteadOfEquip` is enabled, as documented in Lesson 4H;
- reset to a configured baseline when `ResetToBaseline` is enabled.

The reset action was added as a separate mode rather than changing the existing equip or remove behavior. The source file is `Code/ClothingPromptTrigger.cs`, and the tested scene is `Assets/scenes/basic_example.scene`.

### Baseline discovery and setup

The baseline was identified from the Player Controller Dresser Inspector. The configured baseline references were:

- `blue_shirt`
- `blue_sneakers`
- `binman_trousers`

Static scene inspection confirms these three references are assigned to `BaselineClothing` on the jeans stand's `InteractionZone`. For the reported test, `ResetToBaseline` was enabled temporarily on that stand and `RemoveInsteadOfEquip` was disabled. After testing, Play mode was stopped and `ResetToBaseline` was unchecked; the three baseline references remained assigned. The current saved scene matches that restored configuration.

### Implementation walkthrough

The following excerpts are copied from the current `Code/ClothingPromptTrigger.cs`; they are not reconstructed pseudocode.

#### Baseline properties

```csharp
[Property]
public List<Clothing> BaselineClothing { get; set; } = new();

[Property]
public bool ResetToBaseline { get; set; }
```

`[Property]` exposes a field in the s&box Inspector. `List<Clothing>` is an ordered collection of clothing asset references. `= new()` gives the list an empty default instead of leaving it uninitialized. `ResetToBaseline` is the Inspector switch that selects reset mode.

#### Mutually exclusive reset and remove modes

```csharp
if ( ResetToBaseline && RemoveInsteadOfEquip )
{
    Log.Warning( "[ClothingPrompt] Choose only one clothing action mode." );
    return;
}
```

The `&&` operator means both switches are enabled. The method logs a warning and stops before choosing an action, so reset and remove are not allowed to run together.

#### Use-action selection

```csharp
if ( ResetToBaseline )
    _ = ResetClothingToBaseline();
else if ( RemoveInsteadOfEquip )
    _ = RemoveStandClothing();
else
    _ = EquipStandClothing();
```

The first enabled mode wins after the conflict guard: reset, then remove, otherwise equip. The `_ =` explicitly discards the returned `Task` while allowing the asynchronous operation to start.

#### Prompt selection

```csharp
PromptUI.MyStringValue = ResetToBaseline
    ? "Near a stand — press Use to reset outfit"
    : RemoveInsteadOfEquip
        ? "Near a stand — press Use to remove"
        : "Near a stand — press Use to try on";
```

These nested `? :` conditional expressions choose the prompt text to match the selected action mode.

#### Full reset method

```csharp
private async Task ResetClothingToBaseline()
{
    if ( _isApplying )
        return;

    if ( _player == null )
    {
        Log.Warning( "[ClothingPrompt] Player was not found." );
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

    if ( BaselineClothing == null || BaselineClothing.Count == 0 )
    {
        Log.Warning( "[ClothingPrompt] No baseline outfit is assigned to this stand." );
        return;
    }

    var baselineEntries = new List<ClothingContainer.ClothingEntry>();

    foreach ( var clothing in BaselineClothing )
    {
        if ( clothing == null )
            continue;

        bool alreadyAdded = false;

        foreach ( var entry in baselineEntries )
        {
            if ( entry.Clothing != clothing )
                continue;

            alreadyAdded = true;
            break;
        }

        if ( alreadyAdded )
            continue;

        baselineEntries.Add(
            new ClothingContainer.ClothingEntry
            {
                Clothing = clothing
            }
        );
    }

    if ( baselineEntries.Count == 0 )
    {
        Log.Warning( "[ClothingPrompt] The baseline outfit has no valid clothing items." );
        return;
    }

    dresser.Clothing ??= new List<ClothingContainer.ClothingEntry>();
    dresser.Clothing.Clear();
    dresser.Clothing.AddRange( baselineEntries );

    _isApplying = true;

    try
    {
        await dresser.Apply();
        Log.Info( "[ClothingPrompt] Baseline outfit applied." );
    }
    catch ( System.Exception exception )
    {
        Log.Error( $"[ClothingPrompt] Failed to reset clothing: {exception}" );
    }
    finally
    {
        _isApplying = false;
    }
}
```

The method first prevents overlapping applications, then checks for a tracked player, a Dresser, and the required Manual source. It rejects an empty baseline. It builds `baselineEntries` as the Dresser's entry type, skips null references, and checks each new item against entries already added so the baseline list cannot add the same reference twice. `??=` creates the Dresser list only if it is null. `Clear()` removes the current outfit list, and `AddRange()` inserts the prepared baseline entries. `await dresser.Apply()` applies the resulting list. `try/catch/finally` logs an Apply error if one occurs and resets `_isApplying` afterward.

The source contains guards for missing player, missing Dresser, non-Manual source, empty baseline, and a baseline with no valid entries. Those paths were not runtime-tested in this lesson and are therefore not marked as passes.

### Step-by-step procedure used

1. Identify the known-good outfit in the Player Controller Dresser Inspector.
2. Add the baseline clothing property and assign `blue_shirt`, `blue_sneakers`, and `binman_trousers`.
3. Add the reset mode property.
4. Add reset logic to restore the Dresser list and call `Apply()`.
5. Add mode validation so reset and remove cannot be enabled together.
6. Route the Use input to reset, remove, or equip according to the selected mode.
7. Change the nearby prompt so the player knows the stand will reset the outfit.
8. Compile.
9. Temporarily enable reset mode on the jeans stand while leaving remove mode disabled.
10. Play, change the outfit, use the reset stand, inspect the Dresser list, use reset again, then restore the stand's normal configuration.

This records the procedure and reported results; it does not claim that the developer personally typed every line of code.

### Results

The following are `DEVELOPER_CONFIRMED` reports from the supplied Lesson 4I evidence. They were not rerun during this documentation capture.

Before reset, the Player Controller Dresser contained `binman_trousers`, `hoodie_black`, and `football_shoes`. After using reset, the Console showed:

```text
[ClothingPrompt] Baseline outfit applied.
```

The Dresser then showed exactly `blue_shirt`, `blue_sneakers`, and `binman_trousers`. The user used reset again and reported: “No duplicates.” The user also described the test scope as “only done with 2 items but it works as expected”; this wording is preserved as a scope limitation and is not generalized to every outfit combination.

No Lesson 4I failure was reported. The earlier `Interop No value provided for parameter 'clothing' and it has no default value.` error belongs to the Lesson 4H evidence; the supplied Lesson 4I evidence does not establish whether it occurred during the reset test. Its overall project status remains recurring and unresolved.

### What the user learned

- A baseline list gives the game a known outfit to restore instead of guessing what the player wore before.
- Reset replaces the current clothing list, so items from the temporary outfit do not remain.
- Duplicate checking keeps the baseline list clean when the reset action is repeated.
- Reset is a separate mode from equip and remove so one stand action has one clear purpose.
- Compile success shows that the code was accepted by the compiler; runtime testing is still needed to show that the reset works in Play mode.

### Verification record

| Check | Expected result | Observed result | Status |
|---|---|---|---|
| Compile after reset changes | Project compiles | Developer reported successful compile after the reset properties, behavior, mode check, and prompt changes | `PASS` |
| First reset | Baseline is applied | Console showed `[ClothingPrompt] Baseline outfit applied.` | `PASS` |
| Resulting Dresser entries | Exactly the three baseline references | `blue_shirt`, `blue_sneakers`, `binman_trousers` | `PASS` |
| Repeat reset | No duplicate baseline entries | User reported “No duplicates.” | `PASS` |
| Missing player | Guard logs and stops | Not runtime-tested | `NOT_RUN` |
| Missing Dresser | Guard logs and stops | Not runtime-tested | `NOT_RUN` |
| Empty baseline | Guard logs and stops | Not runtime-tested | `NOT_RUN` |
| Non-Manual Dresser source | Guard logs and stops | Not runtime-tested | `NOT_RUN` |
| Failed `Apply()` recovery | Error is handled and operation state recovers | Not runtime-tested | `NOT_RUN` |

### Cleanup and next step

After testing, the user stopped Play mode and unchecked `ResetToBaseline` on the jeans stand. The three baseline references remain assigned. Lesson 4I is passed only for the verified clothing-list reset scope. Lesson 4J - Single-Player Clothing Reliability is next. Milestone 4 remains open; Milestone 5 has not started.

# Lesson 3 — Equipping Citizen Clothing

## Status

Completed and user-verified in the s&box editor and Play mode. This document records the successful manual workflow; it does not describe an automated test or a gameplay implementation.

## Project context

- Project: Dress to Impress
- Scene: `scenes/basic_example.scene` (`basic_example`)
- Character: Original stylized Citizen model, Terry
- Character model: `models/citizen/citizen.vmdl`
- Character hierarchy: `Player Controller` -> `Body`
- Appearance component: `Dresser` on `Body`
- Body renderer: `SkinnedModelRenderer` on `Body`

## What this lesson teaches

This workflow covers locating the Dresser, selecting Citizen clothing definitions, applying several clothing entries, and verifying the result in Play mode.

The confirmed outfit was:

- Black hoodie: `hoodie_black`
- Blue jeans: `jeans`
- Flat shoes: `flat_shoes`

The exact full asset paths for `jeans` and `flat_shoes` were not confirmed and are intentionally not invented here.

## Concepts

- **GameObject:** An object in the scene hierarchy.
- **Component:** A capability attached to a GameObject and shown in the Inspector.
- **SkinnedModelRenderer:** Displays and animates a skinned character model.
- **Dresser:** Configures Citizen or Human appearance and clothing.
- **Clothing definition:** A supported clothing resource that describes how an item is worn. It is different from an arbitrary 3D model.
- **Asset Browser:** Finds assets available to the editor.
- **Manual Items:** Dresser entries configured directly by the developer.
- **Play mode:** Runtime testing inside the editor.

The working relationship is: select the `Body` GameObject, configure its `Dresser`, target the Body's `SkinnedModelRenderer`, add clothing definitions, apply them, and test the result in Play mode.

## Prerequisites

1. Open the Dress to Impress project in the s&box editor.
2. Open `basic_example`.
3. Stop Play mode before editing the scene.
4. Save the scene before the final runtime test.

## Locate and configure the Dresser

1. In the Hierarchy, expand `Player Controller`.
2. Select its child `Body`.
3. In the Inspector, locate `Dresser`.
4. If it is missing, use **Add Component** on the selected `Body`. Do not add a duplicate.
5. Set **Source** to `Manual`.
6. Set **Body Target** to `SkinnedModelRenderer on (Body)` using the object/component picker if necessary.
7. Leave **Apply Height Scale** enabled for this working configuration.
8. Scroll to **Manual Items** and use **Clothing**, not **Workshop Items**, for this lesson.

The Hierarchy search searches GameObjects; it is not a reliable way to find a component. Select the owning GameObject and inspect its components instead.

## Find and equip the black hoodie

1. Under `Dresser` -> **Manual Items** -> **Clothing**, click the small **+** button.
2. In the `Select Clothing` window, choose **Everything** in the left navigation.
3. Search for `hood` or `hoodie` in the upper-right search field.
4. Inspect the results and choose the item identified as a **Clothing Definition**.
5. Select `hoodie_black.clothing`, then click **Select**.
6. Confirm the new entry appears in the Clothing list.
7. Click **Apply Clothing**.
8. Confirm that Terry visibly wears the black hoodie.

The selector can show **Asset Browser**, **Cloud Browser**, **Mounts**, **Recents**, **Everything**, project folders, search results, **Select**, and **Cancel**. This lesson only requires **Everything** and search. Mounted libraries can be browsed manually when the desired asset is not in the current project scope.

## Find and equip multiple items

Keep `Body` selected and add a new Clothing entry with **+** for each item. Do not overwrite an existing entry when adding another item.

1. Add another Clothing entry.
2. Choose **Everything**.
3. Search for `jeans`.
4. Select the matching Clothing Definition.
5. Add another entry and repeat the process for `flat_shoes`.
6. Confirm the list contains:
   - `hoodie_black`
   - `jeans`
   - `flat_shoes`
7. Click **Apply Clothing**.

The **+** button creates another list entry. Replacing the asset in an existing entry is different from adding a new item. Removal controls should only be used when intentionally removing an item.

## Project Assets versus Everything

The clothing selector initially showed only `Dress to Impress > Assets`, where the project did not contain the Citizen clothing library. That made the selector appear empty, but it was an asset-scope issue rather than evidence that clothing was missing.

When an expected clothing asset is not visible:

1. Click **Everything** in the selector's left navigation.
2. Search by the clothing name.
3. Confirm the result is a Clothing Definition before selecting it.

Searching the current project's `Assets` folder is not the same as searching all assets available to the editor.

## Clothing definitions versus models

An arbitrary `.vmdl` is a 3D model. A `.clothing` asset is a clothing definition used by the supported clothing system. Clothing definitions carry the information needed for outfit compatibility, including model, category/slot, deformation behavior, body coverage, and related material or tint settings where applicable.

For normal Citizen outfit customization, use compatible Clothing Definitions instead of replacing the entire character model for every shirt or shoe. Do not assume an arbitrary model will fit, deform, layer, or be accepted by the Citizen clothing system without testing.

## Dresser controls used in this lesson

- **Clothing:** The manually selected clothing-definition list.
- **Apply Clothing:** Applies the configured manual clothing list to the target renderer.
- **Clear Clothing:** Clears configured clothing; exact editor behavior beyond this lesson was not separately tested.
- **Randomize:** Randomizes appearance; its exact scope in this installed editor was not tested.

Adding an asset reference and applying the configured outfit are separate steps. If the appearance does not update, confirm the entries and use **Apply Clothing** before assuming a programming error.

## Working result and verification

The original Citizen model remained intact. The Dresser retained manual appearance controls, and the final outfit appeared correctly positioned in the editor:

- Black hoodie
- Blue jeans
- Flat shoes

The skin tone remained independently controlled through Dresser Manual Tint. The user then tested the scene in Play mode and confirmed that the character, outfit, and movement appeared correct. This is a manual editor/runtime verification, not an automated regression test. No automated test was created.

Recommended verification sequence:

1. Save with `Ctrl+S`.
2. Press Play.
3. Confirm the Citizen and all three clothing items appear.
4. Move the character with the existing third-person controller.
5. Check the clothing during movement for obvious visual problems.
6. Stop Play mode.
7. Confirm the configured outfit remains saved.

## Troubleshooting

### Clothing selector appears empty

Check whether the selector is scoped to the project's own Assets folder. Choose **Everything** and search for the clothing name.

### Searching the Hierarchy for Dresser returns nothing

`Dresser` is a component, not a GameObject. Select `Body` and inspect the Inspector. Add the component only if it is genuinely missing.

### A hoodie model is found but cannot be selected as clothing

Check whether the result is a `.vmdl` model instead of a `.clothing` Clothing Definition.

### Clothing is selected but not visible

Check that:

- Dresser is enabled.
- Source is `Manual`.
- Body Target references the intended `SkinnedModelRenderer`.
- The Clothing list contains the intended definitions.
- **Apply Clothing** was used.

If the issue remains, inspect editor output and collect evidence before changing code.

### Clothing clips through the body

Investigate clothing compatibility, body deformations, layering, and body-coverage configuration. Do not assume the cause without evidence.

### Clothing disappears in Play mode

Check whether runtime code reconfigures appearance or whether the spawned player object differs from the edited scene object. Investigate before changing the scene setup.

### Skin tone stops responding

Check the assigned skin material and Dresser settings before changing code. In the previous lesson, `citizen_skin.vmat_c` did not visibly respond to Manual Tint in the tested configuration, while `citizen_skin01.vmat_c` did. The exact shader/material difference was not investigated and must not be treated as a confirmed engine-wide root cause.

## Reusable lessons

- **L3-001 — Asset browser scope matters:** The project Assets folder is not the same search scope as Everything.
- **L3-002 — Clothing Definitions versus Models:** The Dresser expects compatible clothing resources, not arbitrary model replacements.
- **L3-003 — Correct Body Target:** The Dresser must reference the intended character SkinnedModelRenderer.
- **L3-004 — Manual clothing application:** Multiple clothing entries can be configured and applied through the Dresser.
- **L3-005 — Verify in Play mode:** A correct editor appearance should also be checked at runtime.
- **L3-006 — Preserve appearance independence:** Skin appearance and clothing customization should remain separate concerns in the future customization interface.

## Official references

- [Dresser API](https://sbox.game/api/Sandbox.Dresser)
- [Manual clothing source](https://sbox.game/api/Sandbox.Dresser.ClothingSource/Manual)
- [Clothing resource API](https://sbox.game/api/Sandbox.Clothing)
- [s&box clothing asset guide](https://sbox.game/dev/doc/assets/clothing/)

## Next lesson

Lesson 4 — Change between two hoodie options using C#, then introduce a simple on-screen button. That lesson is planned only; it has not been implemented here.

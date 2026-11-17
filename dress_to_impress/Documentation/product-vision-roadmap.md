# Dress to Impress - Product Vision and Milestones 4-8 Roadmap

## Document status

- Status: `DRAFT - CANONICAL PLANNING RECORD`
- Project: `dress_to_impress`
- Date established: 2026-11-15
- Scope: Product direction and development planning only.
- Authority boundary: This document does not authorize gameplay, scene, asset, skill, project-setting, dependency, or quality-history changes.
- Workflow authority: `Documentation/learning/CURRENT.md` remains authoritative for the active lesson and its task contract.
- Defect authority: `reports/quality/events.jsonl` remains authoritative for issue history.

The document itself was approved for creation as the project's planning record. Individual roadmap decisions below remain `PROPOSED`, `UNRESOLVED`, or `DEFERRED` until separately approved.

## Product vision

Dress to Impress is intended to be a primarily single-player character customization, fashion, and virtual-photography sandbox.

The intended creative loop is:

**Create -> Customize -> Dress -> Pose -> Stage -> Photograph -> Collect -> Repeat**

The finished experience should prioritize individual creativity, outfit experimentation, character presentation, and photography rather than competitive multiplayer.

### Primary pillars

1. **Character creation and customization** - Create and adjust adult characters, including appearance, body proportions, skin, hair, and supported presets.
2. **Fashion and outfit creation** - Select, equip, replace, remove, combine, save, and reuse compatible clothing.
3. **Photography and presentation** - Pose characters, frame scenes, use photogenic environments, capture photographs, and build collections.

Supporting environments and progression should reinforce these pillars without replacing the core creative loop.

All characters are intended to represent adults. Non-explicit content, platform rules, age-rating decisions, licensing, and public presentation require separate future review.

## Learning versus product development

The current Citizen character is a learning and prototype vehicle. It is not evidence that the final game will use the Citizen character or that it already supports the complete visual direction.

The independent Blender/MPFB-related character work may support future custom characters, but Milestones 4-8 must not depend on completing that tool.

Current work should preserve plausible future replacement boundaries without implementing unapproved character systems.

## Current prototype baseline

The current repository provides evidence for a clothing-focused prototype:

- Startup project: `dress_to_impress/dress_to_impress.sbproj`.
- Startup scene: `scenes/basic_example.scene`.
- Player Controller with one serialized Dresser targeting the Body `SkinnedModelRenderer` using Manual source.
- Existing clothing stand InteractionZones and prompt UI.
- Developer-confirmed Lesson 4C proximity behavior.
- Developer-confirmed Lesson 4E jeans application and exact-duplicate prevention.
- Active Lesson 4F task contract in `Documentation/learning/CURRENT.md`.

The repository does not currently provide project-owned photo capture, album storage, pose selection, character cloning, or a complete wardrobe menu.

The project metadata currently declares `GameNetworkType: Multiplayer` and `MaxPlayers: 64`, while the product direction is primarily single-player. This is an unresolved product/configuration decision, not a confirmed implementation defect.

## Evidence boundaries

Product decisions use the following statuses:

- `ESTABLISHED` - Explicitly approved or recorded as a current decision.
- `PROPOSED` - Recommended but not yet approved.
- `UNRESOLVED` - Requires a developer decision or investigation.
- `DEFERRED` - Intentionally postponed to a later milestone.
- `BLOCKED` - Cannot proceed because required authority or information is missing.

Technical claims must retain their evidence classification. Developer-reported runtime results remain developer-confirmed; static inspection is not runtime proof; unavailable checks remain `NOT_RUN` or `BLOCKED`.

## Milestones 4-8

The roadmap is a proposed planning baseline. Milestones must produce two outputs: a playable prototype increment and a reusable learning/workflow increment.

| Milestone | State | Playable prototype output | Learning/workflow output | Dependencies | Acceptance boundary |
|---|---|---|---|---|---|
| 4 - Clothing fundamentals | `ACTIVE` lesson context; roadmap approval unrecorded | Create and modify a basic outfit, including same-category replacement | Dresser ownership, clothing references, trigger behavior, regression evidence, and lesson capture | Valid replacement clothing asset and intended stand | No wardrobe UI, advanced character creation, persistence, or multiplayer expansion |
| 5 - Basic wardrobe UI | `PROPOSED` | Use a simple wardrobe menu and physical stands to drive existing clothing behavior | Razor state, input, UI lifecycle, shared ownership, and UI verification | Stable clothing behavior and a non-duplicated application path | No full inventory, social layer, or online collection system |
| 6 - Basic character customization | `PROPOSED` | Apply limited supported appearance adjustments | Appearance ownership, material compatibility, body/clothing constraints | Decision on Citizen compatibility versus future custom characters | No final anime character system or complete body-family coverage |
| 7 - Camera and pose fundamentals | `PROPOSED` | Dress, inspect, pose, and frame a character in a small setting | Camera ownership, input conflicts, animation state, and presentation testing | Stable character and presentation state | No complete photography suite or social sharing |
| 8 - Creative vertical slice | `PROPOSED` | Connect character, appearance, clothing, pose, framing, and a basic capture action | Integration regression, milestone acceptance, reusable handoff, and known-limit documentation | Milestones 4-7 decisions and verified integration | Not automatically public-release ready |

The six-phase/four-part execution method remains a future workflow concern. It is not formalized or implemented by this document.

## Key dependencies and timing

| Dependency | Evidence/status | Required timing |
|---|---|---|
| Citizen clothing versus future custom characters | Lesson 3 confirms supported Clothing Definitions and warns against assuming arbitrary model compatibility | Decision before Milestone 6 |
| Clothing category and layering compatibility | Lesson 4E defers same-category replacement to 4F; compatibility must be tested rather than assumed | Milestone 4 and before expanded customization |
| Physical stands versus wardrobe UI | Current code applies clothing from stand triggers; no wardrobe menu exists | Ownership decision before Milestone 5 |
| Camera ownership | `basic_example` uses PlayerController camera controls; the custom top-down controller is isolated to `top_down_example` | Before Milestone 7 |
| Poses and animation | No project-owned pose-selection system is present | Milestone 7 |
| Photo capture and storage | No project-owned capture or album system is present | Design decision before Milestone 8 |
| Character, outfit, and photo data | No persistence schema is present | Before collections or public Alpha |
| Character cloning and resource use | No project-owned clone system or measurement exists | Long-term investigation |
| Single-player versus multiplayer | Project metadata and product direction differ | Resolve before network-dependent expansion |
| Licensing and platform/content readiness | Not established in repository records | Before public Alpha |

## Vertical slice boundary

The first Creative Vertical Slice should be a small, followable experience containing:

- A recognizable character.
- Limited supported appearance adjustment.
- Working clothing selection and same-category replacement.
- At least one simple pose or presentation state.
- Camera inspection and framing.
- A small staged environment.
- A repeatable basic capture action.
- Enough onboarding for a private tester to complete the creative loop.

Large clothing catalogues, multiplayer, social sharing, broad progression, advanced body families, extensive environment variety, and monetization can remain deferred.

Public Alpha 0.1 requires a separate readiness review covering fresh-launch stability, onboarding, visual identity, core-loop usability, performance evidence, asset licensing, content/platform readiness, and honest feature description.

## Decision register

| ID | Subject | Recommendation | Status | Timing | Consequence if postponed |
|---|---|---|---|---|---|
| DTV-001 | Canonical vision and roadmap ownership | Keep this document as the single Dress to Impress planning record and link it from the documentation index | `ESTABLISHED` for document creation; content remains evolving | Now | Vision and roadmap decisions remain scattered |
| DTV-002 | Single-player versus multiplayer intent | Treat primarily single-player as the product direction until multiplayer is explicitly approved | `UNRESOLVED` | Before Milestone 5 expansion | Network assumptions may enter architecture unnecessarily |
| DTV-003 | Character strategy | Use Citizen for learning and prototype work while preserving a documented boundary for future custom characters | `PROPOSED` | Before Milestone 6 | Clothing and appearance decisions may become difficult to replace |
| DTV-004 | Clothing compatibility contract | Define supported categories, slots, and body compatibility through tested clothing behavior | `PROPOSED` | Milestone 4 / before Milestone 6 | Replacement and future body support may drift |
| DTV-005 | Wardrobe ownership | Reuse the existing clothing application path rather than duplicating clothing logic in UI | `PROPOSED` | Before Milestone 5 | Stand and menu behavior may diverge |
| DTV-006 | Photography persistence | Decide whether the first slice captures images only or also stores albums and outfit metadata | `UNRESOLVED` | Before Milestone 8 | Persistence scope may expand late |
| DTV-007 | Public Alpha readiness | Require separate content, licensing, usability, performance, and platform review | `PROPOSED` | Before public Alpha 0.1 | Prototype completion could be mistaken for release readiness |

## Authoritative documentation structure

- This document owns Dress to Impress product direction and Milestones 4-8 planning.
- `Documentation/README.md` indexes project documentation.
- `Documentation/learning/CURRENT.md` owns the active lesson, task contract, and next authorized action.
- Individual lesson documents own verified learning records.
- `Documentation/engineering-learning-log.md` provides compact linked experiment history.
- `reports/quality/events.jsonl` owns defect history.
- `TesterSupreme/Documentation/Engineering/` owns framework governance and is not the Dress to Impress product roadmap.

## References and evidence sources

- [Project documentation index](README.md)
- [Current learning checkpoint](learning/CURRENT.md)
- [Lesson 3 - Citizen clothing](lesson-03-citizen-clothing.md)
- [Lesson 4C - Proximity detection](lesson-04c-proximity-detection.md)
- [Lesson 4E - Apply clothing](lesson-04e-apply-clothing.md)
- [Engineering learning log](engineering-learning-log.md)
- [s&box clothing documentation](https://sbox.game/dev/doc/assets/clothing/)
- [s&box clothing layering documentation](https://sbox.game/dev/doc/assets/clothing/layering-clothing)
- [s&box Razor Panels documentation](https://sbox.game/dev/doc/ui/razor-panels/)

This document is a planning record. It does not change the active Lesson 4F contract and does not authorize implementation.

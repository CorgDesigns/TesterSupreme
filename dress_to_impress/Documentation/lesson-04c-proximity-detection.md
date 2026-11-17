# Lesson 4C - Player Proximity Detection

## Record

- Lesson ID: `L4C-001`
- Project: `dress_to_impress`
- Status: `VERIFIED`
- Completion date: 2026-11-11
- Engine: `26.10.27c`
- Scene: `scenes/basic_example.scene`
- Source revision: `working-tree`
- Evidence source: developer-provided completion record, cross-checked against the current `Code/ClothingZoneDebug.cs` source
- Related issue IDs: `none`

## Objective

Detect when the player enters and exits a clothing stand's trigger zone, identify the player rather than treating every collider as the player, and log the result for debugging.

This lesson deliberately stops before prompt UI, input, clothing equipping, or clothing replacement.

## Verified setup

Each clothing stand has an `InteractionZone` child with:

- an enabled `Box Collider`;
- `Is Trigger` enabled; and
- the `ClothingZoneDebug` component from `Code/ClothingZoneDebug.cs`.

The first stand's historical collider snapshot was approximately:

- Local position: `(0, -5, 55)`;
- Local scale: `(1, 1, 1)`;
- Box size: `(60, 60, 160)`; and
- Center: `(0, 0, 0)`.

These values are a tested snapshot, not mandatory dimensions for every stand. Inspect each stand before changing or copying its bounds.

## Verified implementation

The component implements `Component.ITriggerListener` and receives `OnTriggerEnter(Collider other)` and `OnTriggerExit(Collider other)` callbacks. It searches from the entering collider's GameObject through its ancestors:

```csharp
var playerController = other.GameObject.Components.Get<PlayerController>(FindMode.InAncestors);
```

If no `PlayerController` is found, the collider is logged as ignored. If one is found, the component logs the player and collider names. The current source uses this pattern for both entry and exit.

## Runtime verification

Developer-confirmed tests in Play mode reported:

- Stand 01: entry and exit output for each tested pass;
- Stand 01: two repeated passes produced matching entry and exit messages after player identification;
- Stands 02 and 03: entry and exit output when tested individually;
- no duplicate messages in the reported tests; and
- no trigger-related error in the provided Console excerpt.

Observed log form:

```text
[ClothingZone] Player entered: Player Controller; collider: Colliders
[ClothingZone] Player exited: Player Controller; collider: Colliders
```

The current source file was also inspected and matches the reported implementation. Source inspection and successful compilation are not substitutes for runtime evidence; the runtime result above remains developer-confirmed.

## Important troubleshooting lesson

The collider name `Colliders` appeared in log output but was not located through a Hierarchy search. Searching for that object was unnecessary. Looking upward from `other.GameObject` for `PlayerController` with `FindMode.InAncestors` successfully identified the player.

Reusable rule: identify the gameplay owner through the component hierarchy rather than depending on a collider object's name or exact hierarchy location.

## Limits and not-run checks

The following were not established by the reported tests:

- whether a non-player collider is ignored at runtime;
- whether nearby zones overlap or respond simultaneously;
- whether multi-collider player setups can produce duplicate callbacks under other movement conditions; and
- whether the trigger configuration remains correct after later stand or scene edits.

The tested walks produced one entry and one exit per interaction, but no deduplication system was implemented. Do not treat that observation as proof that duplicate callbacks are impossible.

## Reusable regression procedure

For each stand:

1. Start outside the trigger.
2. Enter and confirm one player-entry message.
3. Leave and confirm one player-exit message.
4. Repeat once.
5. Walk between nearby stands and check which zones respond.
6. If a non-player collider can enter, confirm it is ignored.

## Next lesson boundary

Lesson 4D begins the first stand's proximity prompt. Keep the prompt work on Stand 01 until its full interaction flow is settled. Do not add clothing equipping or replacement to 4D.

## References

- [s&box trigger documentation](https://sbox.game/dev/doc/physics/triggers)
- [Component.ITriggerListener API](https://sbox.game/api/Sandbox.Component.ITriggerListener)
- [Current learning checkpoint](learning/CURRENT.md)

# Architecture Baseline

This document records confirmed relationships only.

## Project boundary

The s&box project is TesterSupreme/Game/, identified by tester_supreme.sbproj. It contains project code, scenes, project settings and asset folders. Production Blender material is kept under TesterSupreme/Production/, separate from runtime project content.

## Confirmed code relationship

CustomTopDownController is a project-owned Component.

- It declares a required PlayerController dependency.
- OnFixedUpdate reads input and writes Controller.WishVelocity.
- OnFixedUpdate updates Controller.EyeAngles when movement exists.
- OnPreRender reads Controller.WorldPosition and writes the active Scene.Camera position and rotation.
- PlayerController is not defined in the inspected project source; its implementation is an external s&box/base-library dependency.

Evidence: TesterSupreme/Game/Code/CustomTopDownController.cs and TesterSupreme/Game/Code/tester_supreme.csproj.

## Scene and resource boundary

The project contains three tracked scenes:

- Assets/scenes/basic_example.scene
- Assets/scenes/top_down_example.scene
- Assets/scenes/development/pipeline_lab.scene

The project metadata identifies scenes/basic_example.scene as the startup scene. Scene contents and serialized references were not changed or deeply audited during framework installation.

## Multiplayer boundary

tester_supreme.sbproj declares multiplayer metadata and a maximum player count of 64. No project-owned networking components or RPC code were found in targeted source discovery. This is a project configuration fact, not proof that runtime networking is complete or correct.

## Risks and unknowns

The following are review targets, not confirmed defects:

- The controller and camera relationship depends on PlayerController validity and lifecycle.
- Fixed-update input and pre-render camera behavior may require editor/runtime validation.
- Scene serialization and startup behavior require fresh-launch testing.
- External s&box API and base-library behavior were not assumed beyond repository evidence.


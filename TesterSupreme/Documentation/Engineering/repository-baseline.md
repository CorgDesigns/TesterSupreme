# Repository Baseline

Baseline recorded: 2026-10-30

## Confirmed roots

- Git repository root: workspace root.
- s&box project root: TesterSupreme/Game/.
- Project marker: TesterSupreme/Game/tester_supreme.sbproj.
- Project identity: Tester Supreme, identifier tester_supreme.
- Branch at discovery: main, tracking origin/main.

## Git state at discovery

The working tree already contained a large set of staged additions, primarily under Experimental_Art/ and TesterSupreme/. These changes predated this framework work and were preserved. No reset, checkout, staging or commit operation was performed.

## Project organization

- TesterSupreme/Game/: s&box project files, C# code, scenes, project settings and asset folders.
- TesterSupreme/Production/: Blender sources, templates, references and export archives.
- TesterSupreme/Documentation/: existing asset, import, material, pipeline and test-log documentation.
- TesterSupreme/ReferenceScreenshots/: reference screenshot area.
- Experimental_Art/: separate art experiments and Python tooling.
- TesterSupreme/Game/Code/: project C# source.
- TesterSupreme/Game/Assets/scenes/: basic_example.scene, top_down_example.scene and development/pipeline_lab.scene.

## Code and architecture findings

The repository contains CustomTopDownController.cs and Assembly.cs. CustomTopDownController is a Component with a required PlayerController; its fixed-update path writes movement and eye-angle state, and its pre-render path positions Scene.Camera. PlayerController is referenced but not defined in the repository files inspected; it is expected to come from the s&box/base library and remains an external dependency.

The project metadata declares multiplayer settings with a maximum of 64 players, but no project-owned networking implementation was found during targeted discovery. Networking guidance remains conditional until confirmed in the engine and runtime.

## Configuration and verification

- tester_supreme.csproj targets net10.0, uses C# language version 14 and references s&box assemblies outside the repository.
- Project metadata names scenes/basic_example.scene as the startup scene.
- No UnitTests, unittest, MSTest project or other project-owned automated test suite was found by targeted file discovery.
- Existing TesterSupreme/Documentation/TEST_LOG.md is a manual test-log convention.
- The s&box editor/runtime was not launched during framework installation.
- The game project was not built during framework installation because the configured output and engine references point outside the repository and gameplay validation was outside scope.

## Known unknowns

- Current installed s&box API behavior and editor version were not independently verified.
- Runtime lifecycle, camera behavior, multiplayer behavior and scene serialization were not manually tested.
- The actual implementation of the referenced PlayerController was not available in the repository.
- Existing staged changes were not semantically audited because they are outside this framework task.

## Framework integration decisions

Engineering documents use the existing TesterSupreme/Documentation/ tree under its new Engineering/ subdirectory. Quality history remains at root reports/quality/ so its authoritative path is stable. Repository-local skills use the existing root .agents/ directory, which is currently ignored by the root .gitignore; this limitation is recorded rather than changing .gitignore without separate authorization.


# Test Strategy

## Framework checks

The framework validator is:

tools/engineering/quality_framework.py

Run from the repository root:

python tools/engineering/quality_framework.py validate

The validator checks skill metadata, schema structure, JSON Lines validity, deterministic event IDs, lifecycle data requirements and synthetic-fixture isolation.

## Project checks

Targeted discovery found no project-owned UnitTests, MSTest project or other automated test suite. The s&box project references external engine assemblies and emits build output outside the repository. A project build was not run during framework installation.

## Required manual checks

The following require developer/editor access and were NOT_RUN:

- Fresh launch of the configured startup scene.
- Scene and prefab/resource loading.
- CustomTopDownController movement and camera behavior.
- Hotload/restart behavior.
- Multiplayer authority and replication behavior, if exercised by the project.
- Publishing/resource inclusion checks.

A successful compile, if run later, must not be treated as proof of those runtime behaviors.


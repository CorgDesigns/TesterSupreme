# Engineering Decisions

## DEC-0001: Integrate engineering documents under the existing Documentation tree

- Date: 2026-10-30
- Decision: Use TesterSupreme/Documentation/Engineering/ rather than create a second root documentation tree.
- Rationale: TesterSupreme/Documentation/ already contains the project's pipeline and test-log documentation.
- Tradeoff: Framework documentation is project-local but nested below the existing art/pipeline documentation boundary.

## DEC-0002: Keep quality history as append-only JSON Lines

- Date: 2026-10-30
- Decision: Use reports/quality/events.jsonl as the sole authoritative issue-history source.
- Rationale: It is reviewable in Git, requires no service, preserves event history and supports deterministic projections.
- Tradeoff: Concurrent branches require manual issue-ID and append-order conflict resolution.

## DEC-0003: Do not change .gitignore during installation

- Date: 2026-10-30
- Decision: Preserve the existing root .gitignore, including its .agents/ rule.
- Rationale: The framework assignment did not separately authorize changing ignore behavior.
- Impact: Repository-local skills are created under .agents/skills/ for local discovery, but they are currently ignored and therefore require a future explicit decision if they are to be committed.

## DEC-0004: Do not build or launch the game as framework validation

- Date: 2026-10-30
- Decision: Validate the framework files and event tooling only.
- Rationale: The project build references an external Steam s&box installation and framework installation does not authorize gameplay/runtime changes.
- Impact: Editor, fresh-launch, hotload, scene and multiplayer checks remain NOT_RUN.


# Repository Engineering Instructions

## Scope

This repository contains the Tester Supreme s&box project and experimental art tooling. Framework documentation and tooling may be changed under the framework paths documented in the engineering framework. Gameplay code, scenes, prefabs, materials, resources, assets, dependencies, project settings and engine versions require separate authorization.

## Durable rules

- Inspect the relevant project context and Git status before editing.
- Preserve unrelated staged and unstaged changes.
- Search the authoritative quality event history before investigating a duplicate issue.
- Separate observations, evidence, hypotheses, confirmed causes, proposed repairs and verified outcomes.
- Use the current project conventions and verify uncertain s&box API behavior.
- Prefer small, understandable changes and preserve serialization data.
- Do not modify gameplay or project behavior without explicit authorization.
- Do not close an issue without the required verification evidence.
- Record unavailable editor or runtime checks as BLOCKED or NOT_RUN.
- Do not invent logs, tests, benchmarks, commits or runtime results.
- Keep engineering documents compact and link to authoritative issue IDs.
- Do not silently rewrite skills; approved skill changes require a recorded proposal.
- Review relevant Git changes before milestones. Do not stage or commit automatically.

## Framework locations

- Engineering documentation: TesterSupreme/Documentation/Engineering/
- Authoritative quality history and schema: reports/quality/
- Repository-local skill instructions: .agents/skills/
- Framework tooling: tools/engineering/

reports/quality/events.jsonl is the authoritative issue-history source. Any readable issue summary is a derived projection and must not become an independently maintained ledger.

These rules do not authorize gameplay changes or execution of untrusted repository scripts.


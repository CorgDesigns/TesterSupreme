# Engineering Workflow Guide

Use the smallest workflow that matches the request.

## Investigate a bug

Example prompt:

> Use sb-investigate to investigate the reported symptom in the Tester Supreme project. Search reports/quality/events.jsonl first, separate evidence from hypotheses, and do not modify gameplay code.

## Review a system

Example prompt:

> Use sb-architecture and sb-review to examine the relevant existing system. Report confirmed relationships, risks with confidence, unknowns and suggested tests. Do not repair findings.

## Verify a fix

Example prompt:

> Use sb-verify with the quick profile for the approved change. Run only available checks, report exact results as PASS, FAIL, BLOCKED or NOT_RUN, and identify editor checks still required.

## Lifecycle

Bug work normally follows:

sb-investigate -> sb-history -> authorized sb-remediate -> sb-verify -> sb-history

Search for duplicates before adding events. Keep events.jsonl authoritative and treat readable summaries as projections.

## Evidence discipline

Use repository-relative paths and redacted evidence. Never record secrets, invented test output or unverified runtime claims.

## Specialized s&box skills

See [specialized-skills.md](specialized-skills.md) for UI design, UI QA, runtime diagnostics, performance measurement, routing boundaries and current capability limitations.


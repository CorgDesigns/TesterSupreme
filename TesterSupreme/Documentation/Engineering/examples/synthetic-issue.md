# Synthetic Framework Validation

This example is fictional and does not describe a real Tester Supreme defect. It is kept outside reports/quality/events.jsonl.

## 1. Skill discovery

The exercise uses sb-investigate, sb-history, sb-remediate and sb-verify from the repository-local skills directory.

## 2. Issue classification

- Issue ID: SB-SYN-0001
- Title: Customization state is lost after character recreation
- Subsystem: hypothetical character customization
- Severity: P2
- Reproduction confidence: HIGH within the fictional scenario
- Root-cause confidence: CONFIRMED within the fictional scenario only

## 3. Evidence and uncertainty

The only evidence is the fictional scenario represented in synthetic-events.jsonl. No real source, scene, runtime, editor or project log was inspected for this issue. The hypothetical component lifecycle remains explicitly unknown.

## 4. Historical lookup

The real history at reports/quality/events.jsonl was searched and remains empty. SB-SYN-0001 is not a real issue ID and must not be copied into the real event log.

## 5. Investigation result

The fictional investigation records a hypothetical recreation path that does not transfer persisted customization state. This is a demonstration of evidence/state recording, not a claim about the game.

## 6. Repair proposal

Transfer persisted customization state before replacing the old instance. Scope is synthetic only. Risks include state-version compatibility and duplicate restoration.

## 7. Verification plan

A hypothetical editor recreation test and a fresh-creation-defaults test are planned. They are NOT_RUN because this exercise has no gameplay implementation and no s&box runtime was launched.

## 8. Documentation output

This file documents the exercise. The real known-issues view remains free of synthetic issues.

## 9. History validation

synthetic-events.jsonl contains the event sequence:

ISSUE_REPORTED -> ISSUE_TRIAGED -> INVESTIGATION_UPDATED -> ROOT_CAUSE_CONFIRMED -> FIX_PROPOSED -> FIX_APPLIED -> VERIFICATION_RECORDED -> PREVENTION_PROPOSED

The framework validator checks deterministic event IDs, required fields and transitions.

## 10. Prevention proposal

SB-PREVENT-SYN-0001 proposes checking state transfer whenever a stateful character component is recreated. It remains PROPOSED and synthetic; it is not an approved project rule.


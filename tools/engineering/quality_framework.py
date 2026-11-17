#!/usr/bin/env python3
"""Validate and project the Tester Supreme engineering framework.

Default behavior is read-only. The project command writes only when an
explicit --output path is supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVENT_ID_RE = re.compile(r"^evt-[0-9a-f]{64}$")
REAL_ISSUE_ID_RE = re.compile(r"^SB-BUG-[0-9]{4,}$")
SYNTHETIC_ISSUE_ID_RE = re.compile(r"^SB-SYN-[0-9]{4,}$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")

REQUIRED_SKILL_HEADINGS = (
    "## Purpose",
    "## Use when",
    "## Inputs",
    "## Procedure",
    "## Evidence",
    "## Output",
    "## Validation",
    "## Safety and stop conditions",
    "## Handoff",
)

ALLOWED_TRANSITIONS = {
    "OPEN": {
        "ISSUE_TRIAGED",
        "INVESTIGATION_UPDATED",
        "ISSUE_BLOCKED",
        "ISSUE_DEFERRED",
        "DUPLICATE_LINKED",
    },
    "INVESTIGATING": {
        "ISSUE_TRIAGED",
        "INVESTIGATION_UPDATED",
        "ROOT_CAUSE_CONFIRMED",
        "ISSUE_BLOCKED",
        "ISSUE_DEFERRED",
        "DUPLICATE_LINKED",
    },
    "ROOT_CAUSE_CONFIRMED": {
        "INVESTIGATION_UPDATED",
        "ROOT_CAUSE_CONFIRMED",
        "FIX_PROPOSED",
        "ISSUE_BLOCKED",
        "ISSUE_DEFERRED",
        "DUPLICATE_LINKED",
    },
    "FIX_PROPOSED": {
        "FIX_PROPOSED",
        "FIX_APPLIED",
        "ISSUE_BLOCKED",
        "ISSUE_DEFERRED",
        "DUPLICATE_LINKED",
    },
    "FIXED_UNVERIFIED": {
        "FIX_APPLIED",
        "VERIFICATION_RECORDED",
        "ISSUE_REOPENED",
        "ISSUE_BLOCKED",
        "ISSUE_DEFERRED",
        "DUPLICATE_LINKED",
    },
    "VERIFIED": {
        "VERIFICATION_RECORDED",
        "ISSUE_CLOSED",
        "ISSUE_REOPENED",
        "PATTERN_IDENTIFIED",
        "PREVENTION_PROPOSED",
        "PREVENTION_APPROVED",
        "DUPLICATE_LINKED",
    },
    "CLOSED": {
        "ISSUE_REOPENED",
        "PATTERN_IDENTIFIED",
        "PREVENTION_PROPOSED",
        "PREVENTION_APPROVED",
    },
    "BLOCKED": {
        "INVESTIGATION_UPDATED",
        "ROOT_CAUSE_CONFIRMED",
        "FIX_PROPOSED",
        "ISSUE_REOPENED",
        "ISSUE_DEFERRED",
        "DUPLICATE_LINKED",
    },
    "DEFERRED": {
        "ISSUE_REOPENED",
        "INVESTIGATION_UPDATED",
        "ISSUE_CLOSED",
        "DUPLICATE_LINKED",
    },
    "REOPENED": {
        "ISSUE_TRIAGED",
        "INVESTIGATION_UPDATED",
        "ROOT_CAUSE_CONFIRMED",
        "FIX_PROPOSED",
        "ISSUE_BLOCKED",
        "ISSUE_DEFERRED",
        "DUPLICATE_LINKED",
    },
}


class ValidationError(Exception):
    """A collected validation failure."""


def canonical_without_event_id(event: dict[str, Any]) -> bytes:
    payload = {key: value for key, value in event.items() if key != "event_id"}
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def expected_event_id(event: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_without_event_id(event)).hexdigest()
    return "evt-" + digest


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValidationError("missing YAML frontmatter opening marker")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValidationError("missing YAML frontmatter closing marker")
    raw = text[4:end]
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValidationError(f"invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values, text[end + 4 :]


def validate_skills(root: Path) -> list[str]:
    errors: list[str] = []
    skills_root = root / ".agents" / "skills"
    expected = {
        "sb-architecture",
        "sb-investigate",
        "sb-remediate",
        "sb-verify",
        "sb-review",
        "sb-history",
    }
    if not skills_root.is_dir():
        return [f"missing skill directory: {skills_root}"]

    actual = {entry.name for entry in skills_root.iterdir() if entry.is_dir()}
    missing = expected - actual
    if missing:
        errors.append("missing skills: " + ", ".join(sorted(missing)))

    for name in sorted(expected & actual):
        path = skills_root / name / "SKILL.md"
        if not path.is_file():
            errors.append(f"{name}: missing SKILL.md")
            continue
        try:
            frontmatter, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            if frontmatter.get("name") != name:
                errors.append(f"{name}: frontmatter name does not match directory")
            if not frontmatter.get("description"):
                errors.append(f"{name}: missing frontmatter description")
            for heading in REQUIRED_SKILL_HEADINGS:
                if heading not in body:
                    errors.append(f"{name}: missing heading {heading}")
            if "TODO" in body or "PLACEHOLDER" in body:
                errors.append(f"{name}: unfinished placeholder detected")
        except (OSError, UnicodeError, ValidationError) as exc:
            errors.append(f"{name}: {exc}")
    return errors


def load_schema(root: Path) -> tuple[dict[str, Any], list[str]]:
    path = root / "reports" / "quality" / "schema.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"schema.json: {exc}"]
    required = {
        "schema_version",
        "event_id",
        "issue_id",
        "envelope_required",
        "event_types",
        "statuses",
        "severities",
        "confidence_values",
        "test_results",
        "event_data_required",
    }
    missing = required - set(value)
    return value, [f"schema.json: missing {key}" for key in sorted(missing)]


def validate_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not UTC_RE.match(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def validate_event_log(
    path: Path,
    schema: dict[str, Any],
    *,
    synthetic: bool = False,
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    events: list[dict[str, Any]] = []
    if not path.exists():
        return [f"missing event log: {path}"], events

    issue_re = SYNTHETIC_ISSUE_ID_RE if synthetic else REAL_ISSUE_ID_RE
    seen_event_ids: set[str] = set()
    issue_events: dict[str, list[dict[str, Any]]] = {}

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [f"{path}: {exc}"], events

    required_envelope = set(schema.get("envelope_required", []))
    allowed_types = set(schema.get("event_types", []))
    allowed_statuses = set(schema.get("statuses", []))
    allowed_severities = set(schema.get("severities", []))
    allowed_confidence = set(schema.get("confidence_values", []))
    allowed_results = set(schema.get("test_results", []))
    data_requirements = schema.get("event_data_required", {})

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            errors.append(f"{path}:{line_number}: blank lines are not valid events")
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(event, dict):
            errors.append(f"{path}:{line_number}: event must be an object")
            continue
        events.append(event)
        missing = required_envelope - set(event)
        if missing:
            errors.append(f"{path}:{line_number}: missing envelope fields {sorted(missing)}")

        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not EVENT_ID_RE.match(event_id):
            errors.append(f"{path}:{line_number}: invalid event_id")
        else:
            if event_id in seen_event_ids:
                errors.append(f"{path}:{line_number}: duplicate event_id {event_id}")
            seen_event_ids.add(event_id)
            if event_id != expected_event_id(event):
                errors.append(f"{path}:{line_number}: event_id hash does not match canonical event")

        issue_id = event.get("issue_id")
        if not isinstance(issue_id, str) or not issue_re.match(issue_id):
            errors.append(f"{path}:{line_number}: invalid issue_id {issue_id!r}")

        if event.get("schema_version") != schema.get("schema_version"):
            errors.append(f"{path}:{line_number}: unsupported schema_version")
        if event.get("event_type") not in allowed_types:
            errors.append(f"{path}:{line_number}: unsupported event_type")
        if not validate_timestamp(event.get("timestamp_utc")):
            errors.append(f"{path}:{line_number}: timestamp_utc must be valid UTC RFC3339")
        if event.get("source_revision") is not None and not isinstance(event.get("source_revision"), str):
            errors.append(f"{path}:{line_number}: source_revision must be string or null")
        if not isinstance(event.get("actor"), str) or not event.get("actor"):
            errors.append(f"{path}:{line_number}: actor must be a non-empty string")

        data = event.get("data")
        if not isinstance(data, dict):
            errors.append(f"{path}:{line_number}: data must be an object")
            continue
        event_type = event.get("event_type")
        required_data = set(data_requirements.get(event_type, []))
        missing_data = required_data - set(data)
        if missing_data:
            errors.append(f"{path}:{line_number}: missing data fields {sorted(missing_data)}")

        status_after = data.get("status_after")
        if status_after not in allowed_statuses:
            errors.append(f"{path}:{line_number}: invalid status_after")
        if data.get("severity") is not None and data.get("severity") not in allowed_severities:
            errors.append(f"{path}:{line_number}: invalid severity")
        for field in ("reproduction_confidence", "root_cause_confidence", "confidence"):
            if data.get(field) is not None and data.get(field) not in allowed_confidence:
                errors.append(f"{path}:{line_number}: invalid {field}")
        if event_type == "VERIFICATION_RECORDED":
            tests = data.get("tests")
            if not isinstance(tests, list) or not tests:
                errors.append(f"{path}:{line_number}: tests must be a non-empty list")
            else:
                for test in tests:
                    if not isinstance(test, dict) or test.get("result") not in allowed_results:
                        errors.append(f"{path}:{line_number}: invalid verification test result")

        issue_events.setdefault(issue_id, []).append(event)

    for issue_id, history in issue_events.items():
        if not history:
            continue
        first = history[0]
        if first.get("event_type") != "ISSUE_REPORTED":
            errors.append(f"{path}: {issue_id} does not begin with ISSUE_REPORTED")
        first_status = first.get("data", {}).get("status_after")
        if first_status != "OPEN":
            errors.append(f"{path}: {issue_id} does not begin in OPEN status")
        current_status = first_status
        for event in history[1:]:
            data = event.get("data", {})
            next_status = data.get("status_after")
            event_type = event.get("event_type")
            if next_status == current_status:
                current_status = next_status
                continue
            allowed = ALLOWED_TRANSITIONS.get(current_status, set())
            if event_type not in allowed:
                errors.append(
                    f"{path}: invalid transition for {issue_id}: "
                    f"{current_status} -> {next_status} via {event_type}"
                )
            current_status = next_status

    return errors, events


def project_markdown(events: list[dict[str, Any]]) -> str:
    states: dict[str, dict[str, Any]] = {}
    for event in events:
        issue_id = event["issue_id"]
        data = event.get("data", {})
        state = states.setdefault(issue_id, {"issue_id": issue_id})
        state.update(
            {
                "title": data.get("title", state.get("title", "(untitled)")),
                "subsystem": data.get("subsystem", state.get("subsystem", "unknown")),
                "severity": data.get("severity", state.get("severity", "unclassified")),
                "status": data.get("status_after", state.get("status", "unknown")),
                "last_event": event["event_type"],
                "last_timestamp": event["timestamp_utc"],
            }
        )

    lines = [
        "# Known Issues",
        "",
        "This file is a derived projection of reports/quality/events.jsonl.",
        "",
        "## Current issue records",
        "",
    ]
    if not states:
        lines.append("No issue events are currently recorded.")
    else:
        for issue_id in sorted(states):
            state = states[issue_id]
            lines.extend(
                [
                    f"- {issue_id}: {state['title']} "
                    f"[{state['status']}, {state['severity']}, {state['subsystem']}] "
                    f"(last event {state['last_event']} at {state['last_timestamp']})"
                ]
            )
    lines.extend(
        [
            "",
            "Generated by tools/engineering/quality_framework.py project.",
            "",
        ]
    )
    return "\n".join(lines)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_skills(root))
    schema, schema_errors = load_schema(root)
    errors.extend(schema_errors)
    if not schema:
        return errors

    event_path = root / "reports" / "quality" / "events.jsonl"
    event_errors, _ = validate_event_log(event_path, schema)
    errors.extend(event_errors)

    synthetic_path = (
        root
        / "TesterSupreme"
        / "Documentation"
        / "Engineering"
        / "examples"
        / "synthetic-events.jsonl"
    )
    if synthetic_path.exists():
        synthetic_errors, _ = validate_event_log(
            synthetic_path,
            schema,
            synthetic=True,
        )
        errors.extend(synthetic_errors)
        if event_path.exists():
            real_text = event_path.read_text(encoding="utf-8")
            for synthetic_id in re.findall(r"SB-SYN-[0-9]{4,}", real_text):
                errors.append(f"synthetic issue leaked into real history: {synthetic_id}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("validate", "project"),
        nargs="?",
        default="validate",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="For project, explicitly write the generated projection to this path.",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    if args.command == "validate":
        errors = validate(root)
        if errors:
            for error in errors:
                print("FAIL: " + error)
            print(f"Validation failed with {len(errors)} error(s).")
            return 1
        print("PASS: framework structure, schema, event log and synthetic isolation are valid.")
        return 0

    schema, schema_errors = load_schema(root)
    if schema_errors:
        for error in schema_errors:
            print("FAIL: " + error)
        return 1
    event_path = root / "reports" / "quality" / "events.jsonl"
    event_errors, events = validate_event_log(event_path, schema)
    if event_errors:
        for error in event_errors:
            print("FAIL: " + error)
        return 1
    rendered = project_markdown(events)
    if args.output:
        output = args.output.resolve()
        if root not in output.parents and output != root:
            print("FAIL: output must be inside the repository root")
            return 1
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"WROTE: {output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())


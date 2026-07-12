#!/usr/bin/env python3
"""Durably freeze, authorise, and track one case without a manual intake form."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from common import load_json, save_json, schema_errors

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE = ROOT / "repo" / "queue" / "case-queue.json"
VALID_PATH_FIELDS = {"canonical_path", "reasoning_path", "audit_path", "learner_path"}


def get_item(queue: dict, case_id: str) -> dict:
    for item in queue.get("items", []):
        if item.get("case_id") == case_id:
            return item
    raise ValueError(f"Unknown case_id: {case_id}")


def validate_queue(queue: dict) -> None:
    errors = schema_errors(queue, "case-queue.schema.json")
    if errors:
        raise ValueError("Queue validation failed:\n- " + "\n- ".join(errors))
    ids = [item["case_id"] for item in queue["items"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Queue contains duplicate case IDs")
    for item in queue["items"]:
        expected = f"BUILD_CASE {item['case_id']}"
        if item["authorised"] and item["authorisation_command"] != expected:
            raise ValueError(f"{item['case_id']}: authorisation command must be {expected}")
        if not item["authorised"] and any(item[x] is not None for x in ["authorised_by", "authorised_at", "authorisation_command"]):
            raise ValueError(f"{item['case_id']}: unauthorised item contains authorisation metadata")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    sub = parser.add_subparsers(dest="operation", required=True)

    sub.add_parser("status")
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--date", default=date.today().isoformat())

    start = sub.add_parser("start")
    start.add_argument("case_id")
    start.add_argument("--by", required=True)
    start.add_argument("--date", default=date.today().isoformat())

    stage = sub.add_parser("set-stage")
    stage.add_argument("case_id")
    stage.add_argument("status", choices=[
        "not_started", "authorised", "building_case", "case_draft", "case_locked",
        "building_reasoning", "reasoning_draft", "auditing", "human_review",
        "study_ready", "blocked",
    ])
    stage.add_argument("--path-field", choices=sorted(VALID_PATH_FIELDS))
    stage.add_argument("--path")
    stage.add_argument("--date", default=date.today().isoformat())

    args = parser.parse_args()
    queue = load_json(args.queue)

    if args.operation == "status":
        validate_queue(queue)
        active = [x for x in queue["items"] if x["authorised"] or x["status"] != "not_started"]
        print({"generation_frozen": queue["generation_frozen"], "active": active})
        return 0

    if args.operation == "freeze":
        queue["generation_frozen"] = True
        queue["updated_at"] = args.date
        for item in queue["items"]:
            if item["status"] in {"authorised", "building_case", "building_reasoning", "auditing"}:
                item["status"] = "blocked"
        validate_queue(queue)
        save_json(args.queue, queue)
        print("GENERATION_FROZEN")
        return 0

    if args.operation == "start":
        item = get_item(queue, args.case_id)
        queue["generation_frozen"] = False
        queue["updated_at"] = args.date
        item["authorised"] = True
        item["authorised_by"] = args.by
        item["authorised_at"] = args.date
        item["authorisation_command"] = f"BUILD_CASE {args.case_id}"
        item["status"] = "authorised"
        validate_queue(queue)
        save_json(args.queue, queue)
        print(item["authorisation_command"])
        return 0

    item = get_item(queue, args.case_id)
    item["status"] = args.status
    if args.path_field:
        if not args.path:
            raise ValueError("--path is required with --path-field")
        item[args.path_field] = args.path
    queue["updated_at"] = args.date
    validate_queue(queue)
    save_json(args.queue, queue)
    print(f"{args.case_id}: {args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

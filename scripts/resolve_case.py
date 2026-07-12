#!/usr/bin/env python3
"""Resolve one selected case from repository authority for Codex or a GPT handoff."""
from __future__ import annotations

import argparse
from pathlib import Path

from common import curriculum_entry, curriculum_entry_hash, load_json, save_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--curriculum", type=Path, default=ROOT / "registries" / "curriculum.json")
    parser.add_argument("--queue", type=Path, default=ROOT / "repo" / "queue" / "case-queue.json")
    args = parser.parse_args()

    curriculum = load_json(args.curriculum)
    queue = load_json(args.queue)
    entry = curriculum_entry(curriculum, args.case_id)
    if entry is None:
        raise SystemExit(f"Unknown case_id: {args.case_id}")
    item = next((x for x in queue["items"] if x["case_id"] == args.case_id), None)
    if item is None:
        raise SystemExit(f"Case is absent from queue: {args.case_id}")

    authorised = bool(item["authorised"] and not queue["generation_frozen"])
    context = {
        "schema_version": "2.0.0",
        "case_id": args.case_id,
        "curriculum_entry_hash": curriculum_entry_hash(curriculum, args.case_id),
        "pattern": entry["pattern"],
        "slot": entry["slot"],
        "queue": {
            "generation_frozen": queue["generation_frozen"],
            "authorised": item["authorised"],
            "authorised_by": item["authorised_by"],
            "authorised_at": item["authorised_at"],
            "authorisation_command": item["authorisation_command"],
            "status": item["status"],
        },
        "generation_ready": authorised,
        "next_operation": f"BUILD_CASE {args.case_id}" if authorised else "HOLD",
        "blocking_reason": None if authorised else (
            "Generation is globally frozen." if queue["generation_frozen"]
            else "The selected case has no durable authorisation."
        ),
    }
    if args.output:
        save_json(args.output, context)
        print(args.output)
    else:
        import json
        print(json.dumps(context, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

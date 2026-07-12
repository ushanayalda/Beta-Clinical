#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    audit_report_hash, canonical_case_hash, load_json, reasoning_layer_hash,
    registry_hash, save_json,
)
from validate_audit_report import validate_audit
from validate_canonical_case import validate_case
from validate_reasoning_layer import validate_reasoning

SPEAKER_MAP = {"candidate": "you", "patient": "patient", "examiner": "examiner", "candidate_action": "action", "handover": "handover"}


def build_export(
    case: dict,
    reasoning: dict,
    registry: dict,
    audit: dict,
    release_date: str,
    source_dir: Path | None = None,
) -> dict:
    errors = (
        validate_case(case, source_dir=source_dir)
        + validate_reasoning(reasoning, case, registry)
        + validate_audit(audit, case, reasoning, registry, source_dir)
    )
    workflow = case.get("workflow", {})
    rflow = reasoning.get("workflow", {})
    if workflow.get("canonical_case") != "locked" or workflow.get("lock_record", {}).get("decision") != "locked":
        errors.append("canonical case must be locked")
    for field in ["structure_audit", "source_review", "clinical_review", "timing_test"]:
        if workflow.get(field) != "pass": errors.append(f"canonical {field} must pass")
    for field in ["independent_audit_status", "clinical_review_status", "educational_review_status", "candidate_language_review_status", "final_approval_status"]:
        if rflow.get(field) != "pass": errors.append(f"reasoning {field} must pass")
    if audit.get("final_status") != "pass_to_human_review" or audit.get("rerun_status") != "pass":
        errors.append("independent audit must pass")
    if errors:
        raise ValueError("Export blocked:\n- " + "\n- ".join(errors))

    card = case["visible_station_card"]
    snapshots = {x["task_ref"]: x for x in reasoning["task_snapshot"]}
    anchors = {x["anchor_id"]: x for x in reasoning["visual_anchors"]}
    hint_by_target: dict[str, list[str]] = {}
    turns = case["gold_run"]["turns"]
    direct_targets = {x["stem_id"] for x in card["stem_nodes"]} | {x["task_id"] for x in card["tasks"]} | {x["turn_id"] for x in turns}
    for node in reasoning["reasoning_nodes"]:
        target = node["target_ref"]
        display_target = target
        if target not in direct_targets:
            if target.startswith("ACTION-"):
                matches = [x["turn_id"] for x in turns if target in x.get("action_refs", [])]
            elif target.startswith("DEC-"):
                matches = [x["turn_id"] for x in turns if target in x.get("decision_refs", [])]
            else:
                matches = []
            if not matches:
                raise ValueError(f"No learner display location resolves target {target}")
            display_target = matches[0]
        hint_by_target.setdefault(display_target, []).append(node["hint_id"])

    phase_id = case["authority_summary"]["phase_id"]
    phase_registry = {x["phase_id"]: x for x in load_json(Path(__file__).resolve().parents[1] / "registries" / "phases.json")["phases"]}
    output = {
        "schema_version": "2.0.0",
        "case_id": case["case_id"],
        "case_version": case["case_version"],
        "title": card["title"],
        "navigation": {
            "phase_id": phase_id,
            "phase_label": phase_registry[phase_id]["approved_name"],
            "pattern_label": case["authority_summary"]["cluster"],
            "case_label": f"{case['case_id']} · {card['title']}",
        },
        "stem_page": {
            "heading": card["heading"],
            "stem_nodes": [
                {"stem_id": x["stem_id"], "text": x["text"], "hint_ids": hint_by_target.get(x["stem_id"], [])}
                for x in card["stem_nodes"]
            ],
            "tasks": [
                {
                    "task_id": x["task_id"],
                    "text": x["text"],
                    "anchor": {
                        "anchor_id": x["anchor_id"],
                        "symbol": anchors[x["anchor_id"]]["symbol"],
                        "label": anchors[x["anchor_id"]]["label"],
                    },
                    "scope": snapshots[x["task_id"]]["plain_scope"],
                    "hint_ids": hint_by_target.get(x["task_id"], []),
                }
                for x in card["tasks"]
            ],
        },
        "script_page": {
            "turns": [
                {
                    "turn_id": x["turn_id"],
                    "speaker": SPEAKER_MAP[x["speaker"]],
                    "text": x["text"],
                    "hint_ids": hint_by_target.get(x["turn_id"], []),
                }
                for x in case["gold_run"]["turns"]
            ]
        },
        "hints": [
            {
                "hint_id": x["hint_id"],
                "target_ref": x["target_ref"],
                "label": "Hint",
                "visible_hint": x["visible_hint"],
                "expanded": {
                    "observe": x["observe"], "connect": x["connect"], "mechanism": x["mechanism"],
                    "clinical_weight": x["clinical_weight"], "next_thought": x["next_thought"],
                },
            }
            for x in reasoning["reasoning_nodes"]
        ],
        "clocks": {"reading": reasoning["reading_clock"], "performance": reasoning["performance_clock"]},
        "progress_control": {
            "mode": "self_assessed",
            "levels": [
                {"value": 0, "label": "New"},
                {"value": 1, "label": "Finding the path"},
                {"value": 2, "label": "Can follow the path"},
                {"value": 3, "label": "Can run the case"},
            ],
            "no_loss_state": True,
            "storage": "local_device_only",
        },
        "release": {
            "canonical_case_hash": canonical_case_hash(case),
            "reasoning_layer_hash": reasoning_layer_hash(reasoning),
            "audit_report_id": audit["audit_report_id"],
            "audit_report_hash": audit_report_hash(audit),
            "source_bundle_hash": case["integrity"]["source_bundle_hash"],
            "registry_version": registry["registry_version"],
            "registry_hash": registry_hash(registry),
            "clinical_review_status": "pass",
            "educational_review_status": "pass",
            "candidate_language_review_status": "pass",
            "final_approval_status": "pass",
            "release_status": "study_ready",
            "release_date": release_date,
        },
    }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--reasoning", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--release-date", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source_dir = args.source_dir
    output = build_export(
        load_json(args.case), load_json(args.reasoning), load_json(args.registry),
        load_json(args.audit), args.release_date, source_dir,
    )
    save_json(args.output, output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

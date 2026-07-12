#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    audit_report_hash, canonical_case_hash, load_json, print_result,
    reasoning_layer_hash, registry_hash, schema_errors,
    walk_keys,
)
from validate_audit_report import validate_audit
from validate_canonical_case import validate_case
from validate_reasoning_layer import validate_reasoning

FORBIDDEN_KEYS = {
    "clinical_truth", "patient_layer", "examiner_layer", "assessment_guide", "source_governance",
    "workflow", "quality_gates", "registry_patch", "critical_errors", "unsafe_behaviours",
    "dominant_rigidity_trap", "claim_refs", "source_refs", "concept_refs"
}
SPEAKER_MAP = {"candidate": "you", "patient": "patient", "examiner": "examiner", "candidate_action": "action", "handover": "handover"}


def validate_learner(
    export: dict,
    case: dict,
    reasoning: dict,
    registry: dict,
    audit: dict,
    source_dir: Path | None = None,
) -> list[str]:
    errors = schema_errors(export, "learner-export.schema.json")
    errors += validate_case(case, source_dir=source_dir)
    errors += validate_reasoning(reasoning, case, registry)
    errors += validate_audit(audit, case, reasoning, registry, source_dir)

    for path, key in walk_keys(export):
        if key in FORBIDDEN_KEYS:
            errors.append(f"{path}: learner export contains forbidden key '{key}'")

    chash = canonical_case_hash(case)
    rhash = reasoning_layer_hash(reasoning)
    release = export.get("release", {})
    if release.get("canonical_case_hash") != chash or release.get("reasoning_layer_hash") != rhash:
        errors.append("learner export hashes do not match approved source artifacts")
    if release.get("audit_report_id") != audit.get("audit_report_id"):
        errors.append("learner export audit_report_id does not match")
    if release.get("audit_report_hash") != audit_report_hash(audit):
        errors.append("learner export audit_report_hash does not match")
    if release.get("registry_version") != registry.get("registry_version") or release.get("registry_hash") != registry_hash(registry):
        errors.append("learner export registry binding does not match")
    expected_source_hash = reasoning.get("source_bundle_hash")
    if release.get("source_bundle_hash") != expected_source_hash:
        errors.append("learner export source bundle binding does not match")

    workflow = case.get("workflow", {})
    if workflow.get("canonical_case") != "locked" or workflow.get("lock_record", {}).get("decision") != "locked":
        errors.append("canonical case is not locked")
    for field in ["structure_audit", "source_review", "clinical_review", "timing_test"]:
        if workflow.get(field) != "pass":
            errors.append(f"canonical workflow.{field} is not pass")

    rflow = reasoning.get("workflow", {})
    for field in ["independent_audit_status", "clinical_review_status", "educational_review_status", "candidate_language_review_status", "final_approval_status"]:
        if rflow.get(field) != "pass":
            errors.append(f"reasoning workflow.{field} is not pass")
    if audit.get("final_status") != "pass_to_human_review" or audit.get("rerun_status") != "pass":
        errors.append("independent audit is not in passing state")

    card = case.get("visible_station_card", {})
    if export.get("title") != card.get("title"):
        errors.append("learner title differs from canonical station title")
    source_stems = {x["stem_id"]: x["text"] for x in card.get("stem_nodes", [])}
    export_stems = {x["stem_id"]: x["text"] for x in export.get("stem_page", {}).get("stem_nodes", [])}
    if source_stems != export_stems:
        errors.append("learner stem text differs from canonical station card")
    source_tasks = {x["task_id"]: x["text"] for x in card.get("tasks", [])}
    export_tasks = {x["task_id"]: x["text"] for x in export.get("stem_page", {}).get("tasks", [])}
    if source_tasks != export_tasks:
        errors.append("learner task text differs from canonical station card")

    source_turns = {x["turn_id"]: (SPEAKER_MAP[x["speaker"]], x["text"]) for x in case.get("gold_run", {}).get("turns", [])}
    export_turns = {x["turn_id"]: (x["speaker"], x["text"]) for x in export.get("script_page", {}).get("turns", [])}
    if source_turns != export_turns:
        errors.append("learner script differs from canonical Gold Run")

    source_hints = {
        x["hint_id"]: (x["target_ref"], x["visible_hint"], x["observe"], x["connect"], x["mechanism"], x["clinical_weight"], x["next_thought"])
        for x in reasoning.get("reasoning_nodes", [])
    }
    export_hints = {
        x["hint_id"]: (x["target_ref"], x["visible_hint"], x["expanded"]["observe"], x["expanded"]["connect"], x["expanded"]["mechanism"], x["expanded"]["clinical_weight"], x["expanded"]["next_thought"])
        for x in export.get("hints", [])
    }
    if source_hints != export_hints:
        errors.append("learner Hints differ from approved reasoning nodes")

    # Every Hint must appear once at its direct target or at the first Gold Run turn
    # that realises an ACTION or DEC target.
    actual_attachments: dict[str, list[str]] = {}
    for collection in [export.get("stem_page", {}).get("stem_nodes", []), export.get("stem_page", {}).get("tasks", []), export.get("script_page", {}).get("turns", [])]:
        for item in collection:
            target_id = item.get("stem_id") or item.get("task_id") or item.get("turn_id")
            for hint_id in item.get("hint_ids", []):
                actual_attachments.setdefault(hint_id, []).append(target_id)
    source_turn_list = case.get("gold_run", {}).get("turns", [])
    direct_targets = set(source_stems) | set(source_tasks) | set(source_turns)
    for node in reasoning.get("reasoning_nodes", []):
        target = node.get("target_ref")
        expected_target = target
        if target not in direct_targets:
            if str(target).startswith("ACTION-"):
                matches = [x["turn_id"] for x in source_turn_list if target in x.get("action_refs", [])]
            elif str(target).startswith("DEC-"):
                matches = [x["turn_id"] for x in source_turn_list if target in x.get("decision_refs", [])]
            else:
                matches = []
            if not matches:
                errors.append(f"Hint {node.get('hint_id')} has no learner display location")
                continue
            expected_target = matches[0]
        if actual_attachments.get(node.get("hint_id"), []) != [expected_target]:
            errors.append(f"Hint {node.get('hint_id')} is attached to the wrong learner location")

    if export.get("clocks", {}).get("reading") != reasoning.get("reading_clock"):
        errors.append("learner reading clock differs from approved reasoning layer")
    if export.get("clocks", {}).get("performance") != reasoning.get("performance_clock"):
        errors.append("learner performance clock differs from approved reasoning layer")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path)
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--reasoning", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    return print_result(validate_learner(
        load_json(args.export), load_json(args.case), load_json(args.reasoning),
        load_json(args.registry), load_json(args.audit), args.source_dir,
    ))


if __name__ == "__main__":
    raise SystemExit(main())

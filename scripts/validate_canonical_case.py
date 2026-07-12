#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from common import (
    REGISTRY_DIR, add_missing_ref_errors, all_case_ids, all_target_ids,
    canonical_case_hash, curriculum_entry, curriculum_entry_hash, load_json,
    norm, print_result, schema_errors, source_bundle_hash, unique_errors,
)


def validate_case(
    case: dict,
    curriculum: dict | None = None,
    source_dir: Path | None = None,
) -> list[str]:
    errors = schema_errors(case, "canonical-case.schema.json")
    ids = all_case_ids(case)

    raw_id_groups = {
        "stem_id": [x.get("stem_id", "") for x in case.get("visible_station_card", {}).get("stem_nodes", [])],
        "task_id": [x.get("task_id", "") for x in case.get("visible_station_card", {}).get("tasks", [])],
        "fact_id": [x.get("fact_id", "") for x in case.get("clinical_truth", {}).get("facts", [])],
        "action_id": [x.get("action_id", "") for x in case.get("clinical_truth", {}).get("actions", [])],
        "decision_id": [x.get("decision_id", "") for x in case.get("clinical_truth", {}).get("decisions", [])],
        "claim_id": [x.get("claim_id", "") for x in case.get("clinical_truth", {}).get("claims", [])],
        "finding_id": [x.get("finding_id", "") for x in case.get("examiner_layer", {}).get("findings", [])],
        "turn_id": [x.get("turn_id", "") for x in case.get("gold_run", {}).get("turns", [])],
        "flex_id": [x.get("flex_id", "") for x in case.get("flexibility", {}).get("checkpoints", [])],
        "source_id": [x.get("source_id", "") for x in case.get("source_governance", {}).get("sources", [])],
    }
    for label, values in raw_id_groups.items():
        errors += unique_errors(values, label)

    truth = case.get("clinical_truth", {})
    card = case.get("visible_station_card", {})
    patient = case.get("patient_layer", {})
    examiner = case.get("examiner_layer", {})
    gold = case.get("gold_run", {})
    flexibility = case.get("flexibility", {})

    for index, fact in enumerate(truth.get("facts", [])):
        add_missing_ref_errors(errors, fact.get("claim_refs", []), ids["CLAIM"], f"clinical_truth.facts[{index}].claim_refs")
    for index, action in enumerate(truth.get("actions", [])):
        add_missing_ref_errors(errors, action.get("task_refs", []), ids["TASK"], f"clinical_truth.actions[{index}].task_refs")
        add_missing_ref_errors(errors, action.get("claim_refs", []), ids["CLAIM"], f"clinical_truth.actions[{index}].claim_refs")
    for index, decision in enumerate(truth.get("decisions", [])):
        add_missing_ref_errors(errors, decision.get("evidence_fact_refs", []), ids["FACT"], f"clinical_truth.decisions[{index}].evidence_fact_refs")
        add_missing_ref_errors(errors, decision.get("action_refs", []), ids["ACTION"], f"clinical_truth.decisions[{index}].action_refs")
    add_missing_ref_errors(errors, truth.get("management", []), ids["ACTION"], "clinical_truth.management")

    add_missing_ref_errors(errors, patient.get("volunteered_fact_refs", []), ids["FACT"], "patient_layer.volunteered_fact_refs")
    add_missing_ref_errors(errors, patient.get("do_not_volunteer_fact_refs", []), ids["FACT"], "patient_layer.do_not_volunteer_fact_refs")
    for index, item in enumerate(patient.get("asked_only", [])):
        add_missing_ref_errors(errors, [item.get("fact_ref", "")], ids["FACT"], f"patient_layer.asked_only[{index}].fact_ref")

    for index, finding in enumerate(examiner.get("findings", [])):
        add_missing_ref_errors(errors, [finding.get("fact_ref", "")], ids["FACT"], f"examiner_layer.findings[{index}].fact_ref")
    for index, question in enumerate(examiner.get("questions", [])):
        add_missing_ref_errors(errors, [question.get("task_ref", "")], ids["TASK"], f"examiner_layer.questions[{index}].task_ref")

    previous_end = 0
    for index, turn in enumerate(gold.get("turns", [])):
        start = turn.get("start_second", 0)
        end = turn.get("end_second", 0)
        if start < previous_end:
            errors.append(f"gold_run.turns[{index}]: overlaps the previous turn")
        if end <= start:
            errors.append(f"gold_run.turns[{index}]: end_second must exceed start_second")
        previous_end = max(previous_end, end)
        for field, valid in [
            ("task_refs", ids["TASK"]), ("fact_refs", ids["FACT"]), ("finding_refs", ids["FIND"]),
            ("action_refs", ids["ACTION"]), ("decision_refs", ids["DEC"]),
        ]:
            add_missing_ref_errors(errors, turn.get(field, []), valid, f"gold_run.turns[{index}].{field}")
    if previous_end > gold.get("estimated_duration_seconds", 0):
        errors.append("gold_run.estimated_duration_seconds is shorter than the final turn")

    coverage = gold.get("task_coverage", [])
    covered_tasks = [item.get("task_ref") for item in coverage]
    errors += unique_errors(covered_tasks, "gold_run.task_coverage.task_ref")
    if set(covered_tasks) != ids["TASK"]:
        errors.append(f"gold_run.task_coverage must cover every task exactly; expected {sorted(ids['TASK'])}, got {sorted(set(covered_tasks))}")
    for index, item in enumerate(coverage):
        add_missing_ref_errors(errors, item.get("turn_refs", []), ids["TURN"], f"gold_run.task_coverage[{index}].turn_refs")

    target_ids = all_target_ids(case)
    for index, checkpoint in enumerate(flexibility.get("checkpoints", [])):
        add_missing_ref_errors(errors, [checkpoint.get("trigger_ref", "")], target_ids, f"flexibility.checkpoints[{index}].trigger_ref")
        add_missing_ref_errors(errors, checkpoint.get("new_information_fact_refs", []), ids["FACT"], f"flexibility.checkpoints[{index}].new_information_fact_refs")
        add_missing_ref_errors(errors, checkpoint.get("required_action_refs", []), ids["ACTION"], f"flexibility.checkpoints[{index}].required_action_refs")
    recovery = flexibility.get("recovery", {})
    add_missing_ref_errors(errors, recovery.get("exposing_fact_refs", []), ids["FACT"], "flexibility.recovery.exposing_fact_refs")
    add_missing_ref_errors(errors, recovery.get("immediate_action_refs", []), ids["ACTION"], "flexibility.recovery.immediate_action_refs")
    add_missing_ref_errors(errors, [recovery.get("reentry_turn_ref", "")], ids["TURN"], "flexibility.recovery.reentry_turn_ref")

    approved_sources = {x.get("source_id") for x in case.get("source_governance", {}).get("sources", []) if x.get("status") == "approved"}
    for index, claim in enumerate(truth.get("claims", [])):
        add_missing_ref_errors(errors, claim.get("source_refs", []), ids["SRC"], f"clinical_truth.claims[{index}].source_refs")
        if claim.get("risk_level") in {"high", "critical"} and not claim.get("source_refs"):
            errors.append(f"clinical_truth.claims[{index}]: high-risk claim has no source")
        if claim.get("review_status") == "human_approved" and not set(claim.get("source_refs", [])).issubset(approved_sources):
            errors.append(f"clinical_truth.claims[{index}]: human-approved claim depends on a non-approved source")

    if card.get("title_rule") == "diagnosis_hidden":
        answer = norm(truth.get("working_problem", ""))
        visible = " ".join([card.get("title", "")] + [x.get("text", "") for x in card.get("stem_nodes", [])] + [x.get("text", "") for x in card.get("tasks", [])])
        if answer and len(answer) >= 4 and answer in norm(visible):
            errors.append("visible_station_card: working diagnosis leaks into a diagnosis-hidden card")

    turns = gold.get("turns", [])
    for decision in truth.get("decisions", []):
        if decision.get("result") != "escalate":
            continue
        dref = decision.get("decision_id")
        decision_turns = [t for t in turns if dref in t.get("decision_refs", [])]
        action_turns = [t for t in turns if set(decision.get("action_refs", [])) & set(t.get("action_refs", []))]
        if not decision_turns or not action_turns:
            errors.append(f"{dref}: escalation decision and action must both be visible in the Gold Run")
            continue
        threshold_time = min(t["end_second"] for t in decision_turns)
        action_time = min(t["start_second"] for t in action_turns)
        if action_time > threshold_time + 30:
            errors.append(f"{dref}: urgent action begins {action_time-threshold_time}s after the threshold; maximum permitted audit window is 30s")

    computed_case_hash = canonical_case_hash(case)
    if case.get("integrity", {}).get("authoring_payload_hash") != computed_case_hash:
        errors.append(f"integrity.authoring_payload_hash: expected {computed_case_hash}")
    expected_source_hash = source_bundle_hash(case)
    if case.get("integrity", {}).get("source_bundle_hash") != expected_source_hash:
        errors.append(f"integrity.source_bundle_hash: expected {expected_source_hash}")

    curriculum = curriculum or load_json(REGISTRY_DIR / "curriculum.json")
    entry = curriculum_entry(curriculum, case.get("case_id", ""))
    expected_curriculum_hash = curriculum_entry_hash(curriculum, case.get("case_id", ""))
    expected_command = f"BUILD_CASE {case.get('case_id', '')}"
    if case.get("authority_summary", {}).get("generation_authority") != expected_command:
        errors.append(f"authority_summary.generation_authority must equal {expected_command}")

    if entry is None:
        errors.append("case_id does not exist in the operational curriculum")
    else:
        summary = case.get("authority_summary", {})
        pattern = entry["pattern"]
        slot = entry["slot"]
        if summary.get("pattern_id") != pattern.get("pattern_id"):
            errors.append("authority_summary.pattern_id does not match curriculum")
        if summary.get("phase_id") != pattern.get("phase_id"):
            errors.append("authority_summary.phase_id does not match curriculum")
        if summary.get("evolution_slot") != slot.get("evolution_slot"):
            errors.append("authority_summary.evolution_slot does not match curriculum")
        if case.get("integrity", {}).get("curriculum_entry_hash") != expected_curriculum_hash:
            errors.append("integrity.curriculum_entry_hash does not match the operational curriculum")

    # Verify any archived source files supplied to the validator.
    for index, source in enumerate(case.get("source_governance", {}).get("sources", [])):
        state = source.get("archive_status")
        file_name = source.get("file_name")
        file_hash = source.get("file_sha256")
        if state == "archived" and (not file_name or not file_hash):
            errors.append(f"source_governance.sources[{index}]: archived source requires file_name and file_sha256")
        if source_dir is not None and state == "archived" and file_name:
            path = source_dir / file_name
            if not path.is_file():
                errors.append(f"source_governance.sources[{index}]: archived source file is missing: {file_name}")
            else:
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual != file_hash:
                    errors.append(f"source_governance.sources[{index}]: file_sha256 mismatch for {file_name}")

    workflow = case.get("workflow", {})
    reviews = workflow.get("reviews", {})
    summary_map = {"structure": "structure_audit", "source": "source_review", "clinical": "clinical_review", "timing": "timing_test"}
    for review_name, summary_field in summary_map.items():
        record = reviews.get(review_name, {})
        if record and record.get("status") != workflow.get(summary_field):
            errors.append(f"workflow.reviews.{review_name}.status must match workflow.{summary_field}")

    if workflow.get("canonical_case") == "locked" or workflow.get("lock_record", {}).get("decision") == "locked":
        governance = case.get("source_governance", {})
        if governance.get("unresolved_gaps"):
            errors.append("locked case cannot contain unresolved source gaps")
        if governance.get("claim_coverage_status") != "human_approved":
            errors.append("locked case requires human-approved claim coverage")
        for index, source in enumerate(governance.get("sources", [])):
            if source.get("archive_status") != "archived":
                errors.append(f"source_governance.sources[{index}] must be archived before lock")
            if source.get("status") != "approved":
                errors.append(f"source_governance.sources[{index}] must be approved before lock")
        for field in ["structure_audit", "source_review", "clinical_review", "timing_test"]:
            if workflow.get(field) != "pass":
                errors.append(f"workflow.{field} must be pass before lock")
        generator_name = workflow.get("generation", {}).get("generator_identity")
        for review_name in ["structure", "source", "clinical", "timing"]:
            record = reviews.get(review_name, {})
            if record.get("status") != "pass":
                errors.append(f"workflow.reviews.{review_name}.status must be pass before lock")
            if not record.get("reviewer_name") or not record.get("review_date"):
                errors.append(f"workflow.reviews.{review_name} requires a named reviewer and date")
            if record.get("authoring_payload_hash") != computed_case_hash:
                errors.append(f"workflow.reviews.{review_name}.authoring_payload_hash does not match")
            if review_name in {"source", "clinical", "timing"} and record.get("reviewer_origin") != "human":
                errors.append(f"workflow.reviews.{review_name} must be performed by a human")
            if review_name == "structure" and record.get("reviewer_origin") not in {"human", "independent_ai"}:
                errors.append("workflow.reviews.structure must be human or independent_ai")
            if record.get("reviewer_name") == generator_name:
                errors.append(f"workflow.reviews.{review_name} reviewer must differ from generator identity")
        lock = workflow.get("lock_record", {})
        if not lock.get("locked_by") or not lock.get("locked_date"):
            errors.append("workflow.lock_record requires a named human and date")
        if lock.get("blocking_holds"):
            errors.append("workflow.lock_record cannot lock with blocking holds")
        if lock.get("authoring_payload_hash") != computed_case_hash:
            errors.append("workflow.lock_record.authoring_payload_hash does not match the authoring payload")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--curriculum", type=Path)
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    curriculum = load_json(args.curriculum) if args.curriculum else None
    return print_result(validate_case(load_json(args.case), curriculum, args.source_dir))


if __name__ == "__main__":
    raise SystemExit(main())

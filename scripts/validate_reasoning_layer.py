#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from common import (
    add_missing_ref_errors, all_case_ids, all_target_ids, canonical_case_hash,
    contiguous_clock_errors, load_json, norm, print_result, reasoning_layer_hash,
    registry_hash, schema_errors, unique_errors, word_count,
)

FORBIDDEN_VISIBLE_WORDS = {"candidate", "repair", "reset", "help"}
FORBIDDEN_DELAY_PHRASES = {
    "finish the history", "complete the history before", "wait for all", "after all questions",
    "at the end of the history", "only after the full history"
}


def _visible_texts(reasoning: dict[str, Any]):
    for index, item in enumerate(reasoning.get("task_snapshot", [])):
        yield f"task_snapshot[{index}].plain_scope", item.get("plain_scope", "")
        yield f"task_snapshot[{index}].completion_signal", item.get("completion_signal", "")
    for clock_name in ["reading_clock", "performance_clock"]:
        for index, item in enumerate(reasoning.get(clock_name, {}).get("segments", [])):
            yield f"{clock_name}.segments[{index}].label", item.get("label", "")
            yield f"{clock_name}.segments[{index}].focus", item.get("focus", "")
            yield f"{clock_name}.segments[{index}].move_on_signal", item.get("move_on_signal", "")
    for index, item in enumerate(reasoning.get("reasoning_nodes", [])):
        yield f"reasoning_nodes[{index}].visible_hint", item.get("visible_hint", "")
    for index, item in enumerate(reasoning.get("attention_traps", [])):
        yield f"attention_traps[{index}].reorientation_hint", item.get("reorientation_hint", "")


def validate_reasoning(
    reasoning: dict,
    case: dict,
    registry: dict,
) -> list[str]:
    errors = schema_errors(reasoning, "reasoning-layer.schema.json")
    errors += schema_errors(registry, "reasoning-registry.schema.json")
    ids = all_case_ids(case)
    targets = all_target_ids(case)
    case_hash = canonical_case_hash(case)
    reg_hash = registry_hash(registry)

    if reasoning.get("case_id") != case.get("case_id"):
        errors.append("reasoning.case_id does not match canonical case")
    if reasoning.get("case_version") != case.get("case_version"):
        errors.append("reasoning.case_version does not match canonical case")
    if reasoning.get("canonical_case_hash") != case_hash:
        errors.append("reasoning.canonical_case_hash does not match canonical case content")
    if reasoning.get("registry_version") != registry.get("registry_version"):
        errors.append("reasoning.registry_version does not match current registry")
    if reasoning.get("registry_hash") != reg_hash:
        errors.append("reasoning.registry_hash does not match current registry")
    case_source_hash = case.get("integrity", {}).get("source_bundle_hash")
    if reasoning.get("source_bundle_hash") != case_source_hash:
        errors.append("reasoning.source_bundle_hash does not match canonical case")
    case_workflow = case.get("workflow", {})
    if case_workflow.get("canonical_case") != "locked" or case_workflow.get("lock_record", {}).get("decision") != "locked":
        errors.append("reasoning build requires a locked canonical case")

    expected_rhash = reasoning_layer_hash(reasoning)
    if reasoning.get("integrity", {}).get("reasoning_layer_hash") != expected_rhash:
        errors.append(f"integrity.reasoning_layer_hash: expected {expected_rhash}")

    # Unique IDs.
    for label, values in {
        "reasoning node": [x.get("node_id", "") for x in reasoning.get("reasoning_nodes", [])],
        "Hint": [x.get("hint_id", "") for x in reasoning.get("reasoning_nodes", [])],
        "logic": [x.get("logic_id", "") for x in reasoning.get("logic_track", [])],
        "trap": [x.get("trap_id", "") for x in reasoning.get("attention_traps", [])],
        "pin": [x.get("pin_id", "") for x in reasoning.get("safety_pins", [])],
        "clock": [x.get("clock_id", "") for name in ["reading_clock", "performance_clock"] for x in reasoning.get(name, {}).get("segments", [])],
    }.items():
        errors += unique_errors(values, label)

    # Task snapshot must be exact and use the canonical anchor.
    tasks = {x["task_id"]: x for x in case.get("visible_station_card", {}).get("tasks", [])}
    snapshots = reasoning.get("task_snapshot", [])
    snapshot_refs = [x.get("task_ref") for x in snapshots]
    errors += unique_errors(snapshot_refs, "task_snapshot.task_ref")
    if set(snapshot_refs) != set(tasks):
        errors.append(f"task_snapshot must represent every canonical task exactly; expected {sorted(tasks)}, got {sorted(set(snapshot_refs))}")
    for index, snapshot in enumerate(snapshots):
        tref = snapshot.get("task_ref")
        if tref in tasks and snapshot.get("source_task_text") != tasks[tref].get("text"):
            errors.append(f"task_snapshot[{index}].source_task_text conflicts with canonical task {tref}")
        if tref in tasks and snapshot.get("anchor_id") != tasks[tref].get("anchor_id"):
            errors.append(f"task_snapshot[{index}].anchor_id conflicts with canonical task {tref}")
    if sum(x.get("time_budget_seconds", 0) for x in snapshots) != 480:
        errors.append("task_snapshot time budgets must total 480 seconds")

    # Clocks must be contiguous and task-aligned.
    errors += contiguous_clock_errors(reasoning.get("reading_clock", {}), "reading_clock")
    errors += contiguous_clock_errors(reasoning.get("performance_clock", {}), "performance_clock")
    perf_task_refs = {ref for segment in reasoning.get("performance_clock", {}).get("segments", []) for ref in segment.get("task_refs", [])}
    if perf_task_refs != set(tasks):
        errors.append("performance_clock must cover every canonical task")
    for clock_name in ["reading_clock", "performance_clock"]:
        for index, segment in enumerate(reasoning.get(clock_name, {}).get("segments", [])):
            add_missing_ref_errors(errors, segment.get("target_refs", []), targets, f"{clock_name}.segments[{index}].target_refs")
            add_missing_ref_errors(errors, segment.get("task_refs", []), ids["TASK"], f"{clock_name}.segments[{index}].task_refs")
            joined = " ".join(str(segment.get(k, "")) for k in ["focus", "move_on_signal"]).lower()
            for phrase in FORBIDDEN_DELAY_PHRASES:
                if phrase in joined:
                    errors.append(f"{clock_name}.segments[{index}]: unsafe delay instruction '{phrase}'")

    # Registry concepts include approved registry concepts plus proposed additions.
    existing_concepts = {x["concept_id"] for x in registry.get("canonical_concepts", [])}
    patch = reasoning.get("registry_patch", {})
    proposed_concepts = {x["concept_id"] for x in patch.get("concept_additions", [])}
    valid_concepts = existing_concepts | proposed_concepts
    source_ids = ids["SRC"]
    claim_ids = ids["CLAIM"]

    for index, node in enumerate(reasoning.get("reasoning_nodes", [])):
        add_missing_ref_errors(errors, [node.get("target_ref", "")], targets, f"reasoning_nodes[{index}].target_ref")
        add_missing_ref_errors(errors, node.get("claim_refs", []), claim_ids, f"reasoning_nodes[{index}].claim_refs")
        add_missing_ref_errors(errors, node.get("source_refs", []), source_ids, f"reasoning_nodes[{index}].source_refs")
        add_missing_ref_errors(errors, node.get("concept_refs", []), valid_concepts, f"reasoning_nodes[{index}].concept_refs")
        if word_count(node.get("visible_hint", "")) > 12:
            errors.append(f"reasoning_nodes[{index}].visible_hint exceeds 12 words")
        if node.get("hint_type") in {"mechanism", "priority", "safety"}:
            if not node.get("claim_refs") or not node.get("source_refs"):
                errors.append(f"reasoning_nodes[{index}]: {node.get('hint_type')} Hint requires claim and source references")
        causal = node.get("causal_chain", {})
        if norm(causal.get("event", "")) == norm(causal.get("possible_complication", "")):
            errors.append(f"reasoning_nodes[{index}].causal_chain collapses event and complication")
        if word_count(causal.get("causal_limits", "")) < 5:
            errors.append(f"reasoning_nodes[{index}].causal_chain.causal_limits is too weak")

    for index, logic in enumerate(reasoning.get("logic_track", [])):
        add_missing_ref_errors(errors, logic.get("turn_refs", []), ids["TURN"], f"logic_track[{index}].turn_refs")
        add_missing_ref_errors(errors, logic.get("task_refs", []), ids["TASK"], f"logic_track[{index}].task_refs")

    for index, trap in enumerate(reasoning.get("attention_traps", [])):
        add_missing_ref_errors(errors, [trap.get("target_ref", "")], targets, f"attention_traps[{index}].target_ref")
        if word_count(trap.get("reorientation_hint", "")) > 12:
            errors.append(f"attention_traps[{index}].reorientation_hint exceeds 12 words")

    immediate_actions = {x["action_id"] for x in case.get("clinical_truth", {}).get("actions", []) if x.get("timing") == "immediate"}
    pinned_actions: set[str] = set()
    for index, pin in enumerate(reasoning.get("safety_pins", [])):
        add_missing_ref_errors(errors, [pin.get("target_ref", "")], targets, f"safety_pins[{index}].target_ref")
        add_missing_ref_errors(errors, pin.get("required_action_refs", []), ids["ACTION"], f"safety_pins[{index}].required_action_refs")
        pinned_actions.update(pin.get("required_action_refs", []))
    if immediate_actions and not immediate_actions.issubset(pinned_actions):
        errors.append(f"safety_pins do not cover all immediate actions: {sorted(immediate_actions - pinned_actions)}")

    anchor_registry = {x["anchor_id"] for x in load_json(Path(__file__).resolve().parents[1] / "registries" / "visual-anchors.json")["anchors"]}
    anchored_tasks: set[str] = set()
    for index, anchor in enumerate(reasoning.get("visual_anchors", [])):
        if anchor.get("anchor_id") not in anchor_registry:
            errors.append(f"visual_anchors[{index}]: unknown anchor {anchor.get('anchor_id')}")
        add_missing_ref_errors(errors, anchor.get("task_refs", []), ids["TASK"], f"visual_anchors[{index}].task_refs")
        anchored_tasks.update(anchor.get("task_refs", []))
    if anchored_tasks != set(tasks):
        errors.append("visual_anchors must cover every task")

    # Visible language constitution and diagnosis-hidden answer protection.
    hidden_labels: list[tuple[str, str]] = []
    card = case.get("visible_station_card", {})
    truth = case.get("clinical_truth", {})
    if card.get("title_rule") == "diagnosis_hidden":
        label_values = [("working_problem", truth.get("working_problem", ""))]
        label_values.extend(
            (f"dangerous_alternatives[{index}]", value)
            for index, value in enumerate(truth.get("dangerous_alternatives", []))
        )
        for label_path, value in label_values:
            normalised = norm(str(value))
            compact = re.sub(r"\s+", "", str(value))
            is_acronym = compact.isupper() and compact.isalpha() and len(compact) >= 2
            if normalised and (word_count(str(value)) >= 2 or len(normalised) >= 5 or is_acronym):
                hidden_labels.append((label_path, normalised))

    for path, text in _visible_texts(reasoning):
        words = {x.lower() for x in text.replace("/", " ").split()}
        for forbidden in FORBIDDEN_VISIBLE_WORDS:
            if forbidden in words:
                errors.append(f"{path}: forbidden learner-facing word '{forbidden}'")
        lowered = text.lower()
        for phrase in ["you failed", "wrong again", "careless", "lazy", "obvious mistake"]:
            if phrase in lowered:
                errors.append(f"{path}: non-neuroaffirming phrase '{phrase}'")
        visible_normalised = norm(text)
        for label_path, hidden_label in hidden_labels:
            if hidden_label and hidden_label in visible_normalised:
                errors.append(
                    f"{path}: hidden diagnostic label from clinical_truth.{label_path} leaks into a learner-facing cue"
                )

    # Registry patch binding and conflicts.
    if patch.get("case_id") != case.get("case_id") or patch.get("case_version") != case.get("case_version"):
        errors.append("registry_patch case identity does not match")
    if patch.get("base_registry_version") != registry.get("registry_version"):
        errors.append("registry_patch.base_registry_version does not match current registry")
    if patch.get("base_registry_hash") != reg_hash:
        errors.append("registry_patch.base_registry_hash does not match current registry")
    if patch.get("canonical_case_hash") != case_hash:
        errors.append("registry_patch.canonical_case_hash does not match")
    if patch.get("reasoning_layer_hash") != expected_rhash:
        errors.append("registry_patch.reasoning_layer_hash does not match")
    entry = patch.get("case_index_entry", {})
    if entry.get("canonical_case_hash") != case_hash or entry.get("reasoning_layer_hash") != expected_rhash:
        errors.append("registry_patch.case_index_entry hashes do not match")
    used_concepts = {ref for node in reasoning.get("reasoning_nodes", []) for ref in node.get("concept_refs", [])}
    if set(entry.get("concept_refs", [])) != used_concepts:
        errors.append(f"registry_patch.case_index_entry.concept_refs must exactly match concepts used by reasoning nodes: {sorted(used_concepts)}")
    existing_names = {norm(x.get("name", "")): x.get("canonical_statement") for x in registry.get("canonical_concepts", [])}
    existing_concept_ids = {x.get("concept_id") for x in registry.get("canonical_concepts", [])}
    existing_guard_ids = {x.get("guard_id") for x in registry.get("causal_error_guards", [])}
    patch_concept_ids: set[str] = set()
    for addition in patch.get("concept_additions", []):
        concept_id = addition.get("concept_id")
        name = norm(addition.get("name", ""))
        if concept_id in existing_concept_ids or concept_id in patch_concept_ids:
            errors.append(f"registry_patch concept addition uses duplicate concept ID: {concept_id}")
        patch_concept_ids.add(concept_id)
        if name in existing_names and norm(existing_names[name] or "") != norm(addition.get("canonical_statement", "")):
            errors.append(f"registry_patch adds a conflicting concept name: {addition.get('name')}")
        add_missing_ref_errors(errors, addition.get("source_refs", []), source_ids, f"registry_patch concept addition {concept_id}.source_refs")
        if addition.get("status") != "provisional" or addition.get("approved_by") is not None or addition.get("approved_date") is not None:
            errors.append(f"registry_patch concept addition {concept_id} must remain provisional until human merge approval")
    for update in patch.get("concept_updates", []):
        concept_id = update.get("concept_id")
        replacement = update.get("replacement", {})
        if concept_id not in existing_concept_ids:
            errors.append(f"registry_patch concept update refers to missing concept: {concept_id}")
        if replacement.get("concept_id") != concept_id:
            errors.append(f"registry_patch concept update replacement ID must remain {concept_id}")
        add_missing_ref_errors(errors, replacement.get("source_refs", []), source_ids, f"registry_patch concept update {concept_id}.replacement.source_refs")
        if replacement.get("status") != "provisional" or replacement.get("approved_by") is not None or replacement.get("approved_date") is not None:
            errors.append(f"registry_patch concept update {concept_id} must remain provisional until human merge approval")
    patch_guard_ids: set[str] = set()
    for guard in patch.get("guard_additions", []):
        guard_id = guard.get("guard_id")
        if guard_id in existing_guard_ids or guard_id in patch_guard_ids:
            errors.append(f"registry_patch guard addition uses duplicate guard ID: {guard_id}")
        patch_guard_ids.add(guard_id)
        add_missing_ref_errors(errors, guard.get("source_refs", []), source_ids, f"registry_patch guard addition {guard_id}.source_refs")
        if guard.get("status") != "provisional":
            errors.append(f"registry_patch guard addition {guard_id} must remain provisional until human merge approval")
    for term in patch.get("terminology_updates", []):
        if term.get("status") != "provisional":
            errors.append(f"registry_patch terminology update {term.get('term_id')} must remain provisional until human merge approval")
    if entry.get("approved_date") is not None:
        errors.append("registry_patch.case_index_entry.approved_date must remain null until human merge approval")

    # Ready state must be internally clean, but is not final human approval.
    if reasoning.get("workflow", {}).get("build_status") == "ready_for_independent_audit":
        for gate, value in reasoning.get("quality_gates", {}).items():
            if value != "pass":
                errors.append(f"quality_gates.{gate} must be pass before independent audit")
        if any(x.get("status") == "open" for x in patch.get("conflicts", [])):
            errors.append("open registry conflicts block ready_for_independent_audit")

    # Review summaries must match named, hash-bound review records.
    workflow = reasoning.get("workflow", {})
    audit_ref = workflow.get("independent_audit_ref", {})
    if audit_ref:
        if audit_ref.get("status") != workflow.get("independent_audit_status"):
            errors.append("workflow.independent_audit_ref.status must match independent_audit_status")
        if audit_ref.get("status") == "pass" and audit_ref.get("reasoning_layer_hash") != expected_rhash:
            errors.append("workflow.independent_audit_ref.reasoning_layer_hash does not match")
        if audit_ref.get("status") == "pass" and (not audit_ref.get("audit_report_id") or not audit_ref.get("audit_report_hash")):
            errors.append("workflow.independent_audit_ref requires an audit report ID and hash when passed")
    reviews = workflow.get("reviews", {})
    review_map = {
        "clinical_safety": "clinical_review_status",
        "educational_cognitive_load": "educational_review_status",
        "candidate_language": "candidate_language_review_status",
        "final_content": "final_approval_status",
    }
    for review_name, summary_field in review_map.items():
        record = reviews.get(review_name, {})
        if record and record.get("status") != workflow.get(summary_field):
            errors.append(f"workflow.reviews.{review_name}.status must match workflow.{summary_field}")

    # Final approval requires all independent and named human gates for the exact hash.
    if workflow.get("final_approval_status") == "pass":
        for field in ["independent_audit_status", "clinical_review_status", "educational_review_status", "candidate_language_review_status"]:
            if workflow.get(field) != "pass":
                errors.append(f"workflow.{field} must pass before final approval")
        if not workflow.get("final_approver") or not workflow.get("approval_date"):
            errors.append("workflow final approval requires a named human and date")
        patch_approval = patch.get("human_approval", {})
        if patch_approval.get("status") != "approved" or not patch_approval.get("approved_by") or not patch_approval.get("approved_date"):
            errors.append("final reasoning approval requires a human-approved registry patch")
        if any(x.get("status") == "open" for x in patch.get("conflicts", [])):
            errors.append("final reasoning approval cannot contain open registry conflicts")
        for review_name in ["clinical_safety", "educational_cognitive_load", "candidate_language", "final_content"]:
            record = reviews.get(review_name, {})
            if record.get("status") != "pass" or record.get("reviewer_origin") != "human":
                errors.append(f"workflow.reviews.{review_name} requires a passing human review")
            if not record.get("reviewer_name") or not record.get("review_date"):
                errors.append(f"workflow.reviews.{review_name} requires a named reviewer and date")
            if record.get("reasoning_layer_hash") != expected_rhash:
                errors.append(f"workflow.reviews.{review_name}.reasoning_layer_hash does not match")
            if record.get("reviewer_name") == workflow.get("generator_identity"):
                errors.append(f"workflow.reviews.{review_name} reviewer must differ from generator identity")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reasoning", type=Path)
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    return print_result(validate_reasoning(
        load_json(args.reasoning), load_json(args.case), load_json(args.registry)
    ))


if __name__ == "__main__":
    raise SystemExit(main())

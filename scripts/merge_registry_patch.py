#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
from pathlib import Path

from common import load_json, print_result, registry_hash, save_json, schema_errors


def validate_patch(registry: dict, patch: dict) -> list[str]:
    errors = schema_errors(registry, "reasoning-registry.schema.json") + schema_errors(patch, "registry-patch.schema.json")
    if patch.get("base_registry_version") != registry.get("registry_version"):
        errors.append("patch base_registry_version mismatch")
    if patch.get("base_registry_hash") != registry_hash(registry):
        errors.append("patch base_registry_hash mismatch")
    approval = patch.get("human_approval", {})
    if approval.get("status") != "approved" or not approval.get("approved_by") or not approval.get("approved_date"):
        errors.append("registry patch requires explicit human approval")
    if any(x.get("status") == "open" for x in patch.get("conflicts", [])):
        errors.append("open conflicts block registry merge")
    return errors


def merge(registry: dict, patch: dict, new_version: str) -> dict:
    errors = validate_patch(registry, patch)
    if errors: raise ValueError("Merge blocked:\n- " + "\n- ".join(errors))
    result = copy.deepcopy(registry)
    concepts = {x["concept_id"]: x for x in result["canonical_concepts"]}
    for addition in patch["concept_additions"]:
        if addition["concept_id"] in concepts: raise ValueError(f"duplicate concept {addition['concept_id']}")
        promoted = copy.deepcopy(addition)
        promoted["status"] = "approved"
        promoted["approved_by"] = patch["human_approval"]["approved_by"]
        promoted["approved_date"] = patch["human_approval"]["approved_date"]
        concepts[promoted["concept_id"]] = promoted
    for update in patch["concept_updates"]:
        if update["concept_id"] not in concepts: raise ValueError(f"cannot update missing concept {update['concept_id']}")
        replacement = copy.deepcopy(update["replacement"])
        replacement["status"] = "approved"
        replacement["approved_by"] = patch["human_approval"]["approved_by"]
        replacement["approved_date"] = patch["human_approval"]["approved_date"]
        concepts[update["concept_id"]] = replacement
    result["canonical_concepts"] = sorted(concepts.values(), key=lambda x: x["concept_id"])

    guards = {x["guard_id"]: x for x in result["causal_error_guards"]}
    for addition in patch["guard_additions"]:
        if addition["guard_id"] in guards: raise ValueError(f"duplicate guard {addition['guard_id']}")
        promoted = copy.deepcopy(addition)
        promoted["status"] = "approved"
        guards[promoted["guard_id"]] = promoted
    result["causal_error_guards"] = sorted(guards.values(), key=lambda x: x["guard_id"])

    terms = {x["term_id"]: x for x in result["terminology"]}
    for update in patch["terminology_updates"]:
        promoted = copy.deepcopy(update)
        promoted["status"] = "approved"
        terms[promoted["term_id"]] = promoted
    result["terminology"] = sorted(terms.values(), key=lambda x: x["term_id"])

    index_key = (patch["case_index_entry"]["case_id"], patch["case_index_entry"]["case_version"])
    result["case_index"] = [x for x in result["case_index"] if (x["case_id"], x["case_version"]) != index_key]
    index_entry = copy.deepcopy(patch["case_index_entry"])
    index_entry["approved_date"] = patch["human_approval"]["approved_date"]
    result["case_index"].append(index_entry)
    result["case_index"].sort(key=lambda x: (x["case_id"], x["case_version"]))
    result["unresolved_conflicts"].extend(patch["conflicts"])
    result["registry_version"] = new_version
    result["status"] = "active"
    result["last_updated"] = patch["human_approval"]["approved_date"]
    result["updated_by"] = patch["human_approval"]["approved_by"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--patch", required=True, type=Path)
    parser.add_argument("--new-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    registry = load_json(args.registry); patch = load_json(args.patch)
    errors = validate_patch(registry, patch)
    if errors: return print_result(errors)
    save_json(args.output, merge(registry, patch, args.new_version))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

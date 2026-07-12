#!/usr/bin/env python3
"""Shared validation and integrity utilities for Clinical Pathway v2.0.0."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
REGISTRY_DIR = ROOT / "registries"


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: str | Path, value: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def canonical_case_hash(data: dict[str, Any]) -> str:
    keys = [
        "schema_version", "case_id", "case_version", "method_authority", "layer_order",
        "authority_summary", "visible_station_card", "clinical_truth", "patient_layer",
        "examiner_layer", "gold_run", "flexibility", "assessment_guide", "source_governance",
    ]
    payload = copy.deepcopy({key: data.get(key) for key in keys})
    for claim in payload.get("clinical_truth", {}).get("claims", []):
        claim.pop("review_status", None)
    for source in payload.get("source_governance", {}).get("sources", []):
        source.pop("status", None)
    payload.get("source_governance", {}).pop("claim_coverage_status", None)
    return sha256_json(payload)


def source_bundle_hash(data: dict[str, Any]) -> str:
    source_governance = data.get("source_governance", data)
    payload = copy.deepcopy(source_governance)
    for source in payload.get("sources", []):
        source.pop("status", None)
    payload.pop("claim_coverage_status", None)
    return sha256_json(payload)


def reasoning_layer_hash(data: dict[str, Any]) -> str:
    payload = copy.deepcopy(data)
    payload.pop("workflow", None)
    payload.pop("integrity", None)
    patch = payload.get("registry_patch")
    if isinstance(patch, dict):
        patch.pop("human_approval", None)
        patch["reasoning_layer_hash"] = None
        if isinstance(patch.get("case_index_entry"), dict):
            patch["case_index_entry"]["reasoning_layer_hash"] = None
            patch["case_index_entry"]["approved_date"] = None
        for concept in patch.get("concept_additions", []):
            concept["status"] = None
            concept["approved_by"] = None
            concept["approved_date"] = None
        for update in patch.get("concept_updates", []):
            replacement = update.get("replacement", {})
            replacement["status"] = None
            replacement["approved_by"] = None
            replacement["approved_date"] = None
        for guard in patch.get("guard_additions", []):
            guard["status"] = None
        for term in patch.get("terminology_updates", []):
            term["status"] = None
    return sha256_json(payload)


def registry_hash(data: dict[str, Any]) -> str:
    return sha256_json(data)


def audit_report_hash(data: dict[str, Any]) -> str:
    payload = copy.deepcopy(data)
    payload.setdefault("integrity", {})["audit_report_hash"] = None
    return sha256_json(payload)


def curriculum_entry(curriculum: dict[str, Any], case_id: str) -> dict[str, Any] | None:
    for pattern in curriculum.get("patterns", []):
        for slot in pattern.get("case_slots", []):
            if slot.get("case_id") == case_id:
                return {
                    "registry_version": curriculum.get("registry_version"),
                    "pattern": {
                        key: pattern.get(key)
                        for key in ["pattern_id", "pattern_number", "phase_id", "title", "slug"]
                    },
                    "slot": slot,
                }
    return None


def curriculum_entry_hash(curriculum: dict[str, Any], case_id: str) -> str | None:
    entry = curriculum_entry(curriculum, case_id)
    return sha256_json(entry) if entry is not None else None


def schema_registry() -> Registry:
    resources: list[tuple[str, Resource[Any]]] = []
    for path in SCHEMA_DIR.glob("*.json"):
        schema = load_json(path)
        resource = Resource.from_contents(schema)
        if "$id" in schema:
            resources.append((schema["$id"], resource))
        resources.append((path.resolve().as_uri(), resource))
    return Registry().with_resources(resources)


def schema_errors(instance: Any, schema_name: str) -> list[str]:
    schema = load_json(SCHEMA_DIR / schema_name)
    validator = Draft202012Validator(schema, registry=schema_registry())
    errors = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        location = "$"
        if error.absolute_path:
            location += "." + ".".join(str(part) for part in error.absolute_path)
        errors.append(f"{location}: {error.message}")
    return errors


def walk_strings(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_strings(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from walk_strings(item, f"{path}.{key}")


def walk_keys(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield path, key
            yield from walk_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_keys(item, f"{path}[{index}]")


def has_placeholders(value: Any) -> list[str]:
    return [path for path, text in walk_strings(value) if "__REQUIRED" in text or "[phase]" in text or "[cluster]" in text]


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def unique_errors(items: Iterable[str], label: str) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for item in items:
        if item in seen:
            errors.append(f"duplicate {label}: {item}")
        seen.add(item)
    return errors


def all_case_ids(case: dict[str, Any]) -> dict[str, set[str]]:
    return {
        "STEM": {x["stem_id"] for x in case.get("visible_station_card", {}).get("stem_nodes", [])},
        "TASK": {x["task_id"] for x in case.get("visible_station_card", {}).get("tasks", [])},
        "FACT": {x["fact_id"] for x in case.get("clinical_truth", {}).get("facts", [])},
        "ACTION": {x["action_id"] for x in case.get("clinical_truth", {}).get("actions", [])},
        "DEC": {x["decision_id"] for x in case.get("clinical_truth", {}).get("decisions", [])},
        "CLAIM": {x["claim_id"] for x in case.get("clinical_truth", {}).get("claims", [])},
        "FIND": {x["finding_id"] for x in case.get("examiner_layer", {}).get("findings", [])},
        "TURN": {x["turn_id"] for x in case.get("gold_run", {}).get("turns", [])},
        "FLEX": {x["flex_id"] for x in case.get("flexibility", {}).get("checkpoints", [])},
        "SRC": {x["source_id"] for x in case.get("source_governance", {}).get("sources", [])},
    }


def all_target_ids(case: dict[str, Any]) -> set[str]:
    ids = all_case_ids(case)
    return set().union(ids["STEM"], ids["TASK"], ids["TURN"], ids["ACTION"], ids["DEC"])


def add_missing_ref_errors(errors: list[str], refs: Iterable[str], valid: set[str], location: str) -> None:
    for ref in refs:
        if ref not in valid:
            errors.append(f"{location}: unresolved reference {ref}")


def contiguous_clock_errors(clock: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    total = clock.get("total_seconds")
    segments = clock.get("segments", [])
    if not segments:
        return [f"{label}: no clock segments"]
    ordered = sorted(segments, key=lambda x: x.get("start_second", -1))
    cursor = 0
    for index, segment in enumerate(ordered):
        start = segment.get("start_second")
        end = segment.get("end_second")
        if start != cursor:
            errors.append(f"{label}.segments[{index}]: expected start {cursor}, got {start}")
        if not isinstance(start, int) or not isinstance(end, int) or end <= start:
            errors.append(f"{label}.segments[{index}]: invalid interval {start}-{end}")
            break
        cursor = end
    if cursor != total:
        errors.append(f"{label}: segments end at {cursor}, expected {total}")
    return errors


def print_result(errors: list[str]) -> int:
    if errors:
        print(f"INVALID ({len(errors)} errors)")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALID")
    return 0

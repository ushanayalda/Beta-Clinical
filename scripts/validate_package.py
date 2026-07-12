#!/usr/bin/env python3
"""Validate the complete Clinical Pathway system package."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from common import load_json, print_result, schema_errors
from validate_audit_report import validate_audit
from validate_canonical_case import validate_case
from validate_learner_export import validate_learner
from validate_reasoning_layer import validate_reasoning

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.0.0"

REQUIRED = [
    "VERSION", "README.md", "START_HERE.md", "AGENTS.md", "CODEX_RUNBOOK.md", "CODEX_START_PROMPT.md",
    "authority/CASE_AUTHORING_STANDARD_v2.md", "authority/OPERATING_DECISION_2026-07-12.md",
    "gpts/CASE_BUILD_GPT_INSTRUCTIONS.md", "gpts/REASONING_GPT_INSTRUCTIONS.md",
    "gpts/INDEPENDENT_AUDIT_GPT_INSTRUCTIONS.md", "gpts/FINAL_UPLOAD_CHECKLIST.md",
    "registries/curriculum.json", "registries/phases.json", "registries/station-grammars.json",
    "registries/failure-modes.json", "registries/id-namespaces.json", "registries/source-policy.json",
    "registries/visual-anchors.json", "registries/master-reasoning-registry.json",
    "schemas/canonical-case.schema.json", "schemas/reasoning-layer.schema.json",
    "schemas/audit-report.schema.json", "schemas/learner-export.schema.json",
    "schemas/learner-index.schema.json", "schemas/case-queue.schema.json",
    "scripts/manage_queue.py", "scripts/resolve_case.py", "scripts/archive_sources.py",
    "scripts/validate_canonical_case.py", "scripts/validate_reasoning_layer.py",
    "scripts/validate_audit_report.py", "scripts/export_learner.py", "scripts/build_index.py",
    "repo/queue/case-queue.json", "repo/manifest.json", "repo/website-data/index.json",
    "website/index.html", "website/app.js", "website/styles.css", "website/data/index.json",
    "tests/test_system.py", "tests/browser_smoke.py",
]

# Built dynamically so the retired labels do not occur in this package's own source.
FORBIDDEN = [
    "case " + "input " + "card",
    "case-" + "input",
    "case_" + "input",
    "input_" + "hash",
    "source_" + "manifest",
    "source-" + "manifest",
    "reasoning-" + "build-request",
    "reasoning_" + "build_request",
]
TEXT_SUFFIXES = {".md", ".json", ".py", ".js", ".css", ".html", ".txt", ".sha256"}
MANIFEST_EXCLUDE = {"MANIFEST.sha256", "FINAL_LOCK.json"}


def run_command(command: list[str], label: str) -> list[str]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode == 0:
        return []
    return [f"{label} failed: {(result.stdout + result.stderr).strip()}"]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_scope() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*")
        if p.is_file()
        and p.relative_to(ROOT).as_posix() not in MANIFEST_EXCLUDE
        and "__pycache__" not in p.parts
        and p.suffix != ".pyc"
    )


def parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        digest, rel = raw.split("  ", 1)
        entries[rel] = digest
    return entries


def validate_manifest_file() -> list[str]:
    path = ROOT / "MANIFEST.sha256"
    if not path.is_file():
        return ["MANIFEST.sha256 is missing"]
    entries = parse_manifest(path)
    expected = {p.relative_to(ROOT).as_posix(): file_hash(p) for p in manifest_scope()}
    errors: list[str] = []
    if set(entries) != set(expected):
        errors.append(f"manifest coverage mismatch: missing={sorted(set(expected)-set(entries))}, extra={sorted(set(entries)-set(expected))}")
    for rel in set(entries) & set(expected):
        if entries[rel] != expected[rel]:
            errors.append(f"manifest hash mismatch: {rel}")
    return errors


def validate_final_lock() -> list[str]:
    path = ROOT / "FINAL_LOCK.json"
    if not path.is_file():
        return ["FINAL_LOCK.json is missing"]
    lock = load_json(path)
    errors: list[str] = []
    expected = {
        "package": "Clinical Pathway Case System",
        "version": VERSION,
        "technical_status": "PASS",
        "generation_frozen": True,
        "clinical_case_count": 0,
        "study_ready_case_count": 0,
    }
    for key, value in expected.items():
        if lock.get(key) != value:
            errors.append(f"FINAL_LOCK.{key}: expected {value!r}")
    manifest = ROOT / "MANIFEST.sha256"
    if manifest.is_file() and lock.get("manifest_sha256") != file_hash(manifest):
        errors.append("FINAL_LOCK.manifest_sha256 does not match")
    authority = ROOT / "authority" / "CASE_AUTHORING_STANDARD_v2.md"
    if lock.get("authoring_standard_sha256") != file_hash(authority):
        errors.append("FINAL_LOCK.authoring_standard_sha256 does not match")
    return errors


def validate_package(*, run_tests: bool = True, run_browser: bool = True, require_manifest: bool = False, require_lock: bool = False) -> list[str]:
    errors: list[str] = []
    if (ROOT / "VERSION").read_text().strip() != VERSION:
        errors.append(f"VERSION must be {VERSION}")
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            errors.append(f"required file missing: {rel}")

    # The active package must contain no retired workflow labels or files.
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for token in FORBIDDEN:
            if token in text:
                errors.append(f"retired workflow label remains in {path.relative_to(ROOT)}")

    for path in sorted((ROOT / "schemas").glob("*.json")):
        try:
            Draft202012Validator.check_schema(load_json(path))
        except Exception as exc:
            errors.append(f"invalid JSON Schema {path.name}: {exc}")

    curriculum = load_json(ROOT / "registries" / "curriculum.json")
    patterns = curriculum.get("patterns", [])
    slots = [slot for pattern in patterns for slot in pattern.get("case_slots", [])]
    if len(patterns) != 40 or len(slots) != 160:
        errors.append("curriculum must contain 40 patterns and 160 case slots")
    case_ids = [slot.get("case_id") for slot in slots]
    if len(case_ids) != len(set(case_ids)):
        errors.append("curriculum contains duplicate case IDs")

    queue = load_json(ROOT / "repo" / "queue" / "case-queue.json")
    errors += schema_errors(queue, "case-queue.schema.json")
    if not queue.get("generation_frozen"):
        errors.append("release package generation queue must be frozen")
    if any(item.get("authorised") for item in queue.get("items", [])):
        errors.append("release package cannot contain an authorised case")
    if {x.get("case_id") for x in queue.get("items", [])} != set(case_ids):
        errors.append("queue case IDs do not match curriculum")

    standard_hash = file_hash(ROOT / "authority" / "CASE_AUTHORING_STANDARD_v2.md")
    schema_method_hash = load_json(ROOT / "schemas" / "canonical-case.schema.json")["properties"]["method_authority"]["properties"]["method_file_sha256"].get("const")
    if schema_method_hash != standard_hash:
        errors.append("canonical schema method fingerprint does not match the authoring standard")

    registry = load_json(ROOT / "registries" / "master-reasoning-registry.json")
    errors += schema_errors(registry, "reasoning-registry.schema.json")
    errors += schema_errors(load_json(ROOT / "website" / "data" / "index.json"), "learner-index.schema.json")
    errors += schema_errors(load_json(ROOT / "repo" / "website-data" / "index.json"), "learner-index.schema.json")

    for index_path in [ROOT / "website" / "data" / "index.json", ROOT / "repo" / "website-data" / "index.json"]:
        if load_json(index_path).get("cases"):
            errors.append(f"production learner index must remain empty: {index_path.relative_to(ROOT)}")

    fixture = ROOT / "tests" / "fixtures"
    case = load_json(fixture / "valid-canonical-case.json")
    reasoning = load_json(fixture / "valid-reasoning-layer.json")
    fixture_registry = load_json(fixture / "valid-registry.json")
    audit = load_json(fixture / "valid-audit-report.json")
    learner = load_json(fixture / "valid-learner-export.json")
    errors += validate_case(case, source_dir=fixture)
    errors += validate_reasoning(reasoning, case, fixture_registry)
    errors += validate_audit(audit, case, reasoning, fixture_registry, fixture)
    errors += validate_learner(learner, case, reasoning, fixture_registry, audit, fixture)
    errors += schema_errors(load_json(fixture / "valid-hold-report.json"), "hold-report.schema.json")

    errors += run_command(["node", "--check", str(ROOT / "website" / "app.js")], "website JavaScript syntax")
    errors += run_command([sys.executable, "-m", "compileall", "-q", "scripts", "tests"], "Python compile")
    if run_tests:
        errors += run_command([sys.executable, "-m", "unittest", "tests/test_system.py", "-v"], "contract tests")
    if run_browser:
        errors += run_command([sys.executable, "tests/browser_smoke.py"], "browser smoke test")

    if require_manifest or require_lock:
        errors += validate_manifest_file()
    if require_lock:
        errors += validate_final_lock()
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--require-manifest", action="store_true")
    parser.add_argument("--require-lock", action="store_true")
    args = parser.parse_args()
    return print_result(validate_package(
        run_tests=not args.skip_tests,
        run_browser=not args.skip_browser,
        require_manifest=args.require_manifest or args.require_lock,
        require_lock=args.require_lock,
    ))


if __name__ == "__main__":
    raise SystemExit(main())

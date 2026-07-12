#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    audit_report_hash, canonical_case_hash, load_json, print_result,
    reasoning_layer_hash, registry_hash, schema_errors,
)
from validate_canonical_case import validate_case
from validate_reasoning_layer import validate_reasoning


def validate_audit(
    report: dict,
    case: dict,
    reasoning: dict,
    registry: dict | None = None,
    source_dir: Path | None = None,
) -> list[str]:
    errors = schema_errors(report, "audit-report.schema.json")
    errors += validate_case(case, source_dir=source_dir)
    if registry is not None:
        errors += validate_reasoning(reasoning, case, registry)

    chash = canonical_case_hash(case)
    rhash = reasoning_layer_hash(reasoning)
    expected_audit_hash = audit_report_hash(report)

    if report.get("case_id") != case.get("case_id") or report.get("case_version") != case.get("case_version"):
        errors.append("audit report case identity does not match")
    if report.get("canonical_case_hash") != chash:
        errors.append("audit report canonical_case_hash does not match")
    if report.get("reasoning_layer_hash") != rhash:
        errors.append("audit report reasoning_layer_hash does not match")
    if report.get("curriculum_entry_hash") != case.get("integrity", {}).get("curriculum_entry_hash"):
        errors.append("audit report curriculum_entry_hash does not match canonical case")
    if report.get("source_bundle_hash") != case.get("integrity", {}).get("source_bundle_hash"):
        errors.append("audit report source_bundle_hash does not match canonical case")
    if report.get("source_bundle_hash") != reasoning.get("source_bundle_hash"):
        errors.append("audit report source_bundle_hash does not match reasoning layer")
    if report.get("registry_version") != reasoning.get("registry_version"):
        errors.append("audit report registry_version does not match reasoning layer")
    if report.get("registry_hash") != reasoning.get("registry_hash"):
        errors.append("audit report registry_hash does not match reasoning layer")
    if report.get("integrity", {}).get("audit_report_hash") != expected_audit_hash:
        errors.append(f"integrity.audit_report_hash: expected {expected_audit_hash}")

    expected_generator_ids = {
        case.get("workflow", {}).get("generation", {}).get("generator_run_id"),
        reasoning.get("workflow", {}).get("generator_run_id"),
    }
    expected_generator_ids.discard(None)
    if set(report.get("generator_run_ids", [])) != expected_generator_ids:
        errors.append("audit report generator_run_ids must exactly match case and reasoning generator runs")
    generator_ids = set(report.get("generator_run_ids", []))
    if report.get("auditor_run_id") in generator_ids:
        errors.append("auditor_run_id must differ from every generator_run_id")
    generator_identities = {
        case.get("workflow", {}).get("generation", {}).get("generator_identity"),
        reasoning.get("workflow", {}).get("generator_identity"),
    }
    if report.get("auditor_identity") in generator_identities:
        errors.append("auditor_identity must differ from generator identity")

    if registry is not None:
        if report.get("registry_version") != registry.get("registry_version"):
            errors.append("audit report registry_version does not match provided registry")
        if report.get("registry_hash") != registry_hash(registry):
            errors.append("audit report registry_hash does not match provided registry")

    if report.get("final_status") == "pass_to_human_review":
        failed = [name for name, value in report.get("checks", {}).items() if value != "pass"]
        if failed:
            errors.append(f"pass_to_human_review requires all checks to pass: {failed}")
        if any(x.get("status") == "open" for x in report.get("findings", [])):
            errors.append("pass_to_human_review cannot contain open findings")
        if report.get("rerun_status") != "pass":
            errors.append("pass_to_human_review requires a passing rerun")

    audit_ref = reasoning.get("workflow", {}).get("independent_audit_ref", {})
    if audit_ref.get("status") == "pass":
        if audit_ref.get("audit_report_id") != report.get("audit_report_id"):
            errors.append("reasoning independent_audit_ref.audit_report_id does not match audit report")
        if audit_ref.get("audit_report_hash") != expected_audit_hash:
            errors.append("reasoning independent_audit_ref.audit_report_hash does not match audit report")
        if audit_ref.get("reasoning_layer_hash") != rhash:
            errors.append("reasoning independent_audit_ref.reasoning_layer_hash does not match")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", type=Path)
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--reasoning", required=True, type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    return print_result(validate_audit(
        load_json(args.audit), load_json(args.case), load_json(args.reasoning),
        load_json(args.registry) if args.registry else None, args.source_dir,
    ))


if __name__ == "__main__":
    raise SystemExit(main())

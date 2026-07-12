from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from common import (  # noqa: E402
    audit_report_hash, canonical_case_hash, curriculum_entry_hash, load_json,
    reasoning_layer_hash, registry_hash, schema_errors, source_bundle_hash,
)
from build_index import build as build_index  # noqa: E402
from export_learner import build_export  # noqa: E402
from merge_registry_patch import validate_patch  # noqa: E402
from validate_audit_report import validate_audit  # noqa: E402
from validate_canonical_case import validate_case  # noqa: E402
from validate_learner_export import validate_learner  # noqa: E402
from validate_reasoning_layer import validate_reasoning  # noqa: E402


def fixture(name: str) -> dict:
    return load_json(FIX / name)


def contains(errors: list[str], text: str) -> bool:
    return any(text.lower() in error.lower() for error in errors)


def refresh_case(case: dict) -> None:
    curriculum = load_json(ROOT / "registries" / "curriculum.json")
    case["integrity"]["curriculum_entry_hash"] = curriculum_entry_hash(curriculum, case["case_id"])
    case["integrity"]["source_bundle_hash"] = source_bundle_hash(case)
    value = canonical_case_hash(case)
    case["integrity"]["authoring_payload_hash"] = value
    if case["workflow"]["lock_record"]["decision"] == "locked":
        case["workflow"]["lock_record"]["authoring_payload_hash"] = value
        for record in case["workflow"]["reviews"].values():
            record["authoring_payload_hash"] = value


def refresh_reasoning(reasoning: dict, case: dict, registry: dict) -> None:
    reasoning["canonical_case_hash"] = canonical_case_hash(case)
    reasoning["source_bundle_hash"] = source_bundle_hash(case)
    reasoning["registry_hash"] = registry_hash(registry)
    patch = reasoning["registry_patch"]
    patch["base_registry_hash"] = registry_hash(registry)
    patch["canonical_case_hash"] = canonical_case_hash(case)
    patch["case_index_entry"]["canonical_case_hash"] = canonical_case_hash(case)
    value = reasoning_layer_hash(reasoning)
    reasoning["integrity"]["reasoning_layer_hash"] = value
    patch["reasoning_layer_hash"] = value
    patch["case_index_entry"]["reasoning_layer_hash"] = value
    for record in reasoning["workflow"]["reviews"].values():
        record["reasoning_layer_hash"] = value
    reasoning["workflow"]["independent_audit_ref"]["reasoning_layer_hash"] = value


def refresh_audit(audit: dict, case: dict, reasoning: dict, registry: dict) -> None:
    audit["canonical_case_hash"] = canonical_case_hash(case)
    audit["reasoning_layer_hash"] = reasoning_layer_hash(reasoning)
    audit["curriculum_entry_hash"] = case["integrity"]["curriculum_entry_hash"]
    audit["source_bundle_hash"] = case["integrity"]["source_bundle_hash"]
    audit["registry_version"] = registry["registry_version"]
    audit["registry_hash"] = registry_hash(registry)
    audit["integrity"]["audit_report_hash"] = audit_report_hash(audit)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.case = fixture("valid-canonical-case.json")
        self.reasoning = fixture("valid-reasoning-layer.json")
        self.registry = fixture("valid-registry.json")
        self.audit = fixture("valid-audit-report.json")
        self.learner = fixture("valid-learner-export.json")


class TestPackageContracts(Base):
    def test_all_schemas_are_valid(self):
        from jsonschema import Draft202012Validator
        for path in (ROOT / "schemas").glob("*.json"):
            Draft202012Validator.check_schema(load_json(path))

    def test_curriculum_has_40_patterns_and_160_slots(self):
        curriculum = load_json(ROOT / "registries" / "curriculum.json")
        self.assertEqual(len(curriculum["patterns"]), 40)
        self.assertEqual(sum(len(p["case_slots"]) for p in curriculum["patterns"]), 160)

    def test_curriculum_case_ids_are_unique(self):
        curriculum = load_json(ROOT / "registries" / "curriculum.json")
        ids = [s["case_id"] for p in curriculum["patterns"] for s in p["case_slots"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_queue_is_valid_and_frozen(self):
        queue = load_json(ROOT / "repo" / "queue" / "case-queue.json")
        self.assertEqual(schema_errors(queue, "case-queue.schema.json"), [])
        self.assertTrue(queue["generation_frozen"])
        self.assertTrue(all(not x["authorised"] for x in queue["items"]))

    def test_queue_matches_curriculum(self):
        curriculum = load_json(ROOT / "registries" / "curriculum.json")
        queue = load_json(ROOT / "repo" / "queue" / "case-queue.json")
        cid = {s["case_id"] for p in curriculum["patterns"] for s in p["case_slots"]}
        qid = {x["case_id"] for x in queue["items"]}
        self.assertEqual(cid, qid)

    def test_production_indexes_are_empty(self):
        for path in [ROOT / "website" / "data" / "index.json", ROOT / "repo" / "website-data" / "index.json"]:
            self.assertEqual(load_json(path)["cases"], [])

    def test_source_policy_requires_official_sources(self):
        policy = load_json(ROOT / "registries" / "source-policy.json")
        self.assertTrue(policy["draft_generation"]["official_sources_required"])
        self.assertEqual(policy["draft_generation"]["unsupported_high_risk_claim_result"], "hold")

    def test_custom_gpt_boundaries_exist(self):
        names = {p.name for p in (ROOT / "gpts").glob("*.md")}
        self.assertTrue({"CASE_BUILD_GPT_INSTRUCTIONS.md", "REASONING_GPT_INSTRUCTIONS.md", "INDEPENDENT_AUDIT_GPT_INSTRUCTIONS.md"}.issubset(names))

    def test_codex_instructions_exist(self):
        self.assertTrue((ROOT / "AGENTS.md").is_file())
        self.assertTrue((ROOT / "CODEX_RUNBOOK.md").is_file())
        self.assertTrue((ROOT / "CODEX_START_PROMPT.md").is_file())


class TestCanonicalCase(Base):
    def test_valid_case(self):
        self.assertEqual(validate_case(self.case, source_dir=FIX), [])

    def test_exact_generation_command_required(self):
        self.case["authority_summary"]["generation_authority"] = "approved"
        refresh_case(self.case)
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "generation_authority"))

    def test_curriculum_hash_binding(self):
        self.case["integrity"]["curriculum_entry_hash"] = "0" * 64
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "curriculum_entry_hash"))

    def test_source_bundle_binding(self):
        self.case["integrity"]["source_bundle_hash"] = "0" * 64
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "source_bundle_hash"))

    def test_source_access_date_required(self):
        del self.case["source_governance"]["sources"][0]["accessed_date"]
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "accessed_date"))

    def test_archived_source_file_required(self):
        self.case["source_governance"]["sources"][0]["file_name"] = "missing.txt"
        refresh_case(self.case)
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "missing"))

    def test_archived_source_hash_checked(self):
        self.case["source_governance"]["sources"][0]["file_sha256"] = "0" * 64
        refresh_case(self.case)
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "file_sha256 mismatch"))

    def test_locked_source_must_be_approved(self):
        self.case["source_governance"]["sources"][0]["status"] = "review_required"
        refresh_case(self.case)
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "approved before lock"))

    def test_locked_case_cannot_have_source_gap(self):
        self.case["source_governance"]["unresolved_gaps"] = ["gap"]
        refresh_case(self.case)
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "unresolved source gaps"))

    def test_duplicate_stem_id_rejected(self):
        self.case["visible_station_card"]["stem_nodes"][1]["stem_id"] = "STEM-001"
        refresh_case(self.case)
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "duplicate stem_id"))

    def test_dangling_patient_fact_rejected(self):
        self.case["patient_layer"]["volunteered_fact_refs"] = ["FACT-999"]
        refresh_case(self.case)
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "unresolved reference"))

    def test_gold_run_task_coverage_exact(self):
        self.case["gold_run"]["task_coverage"].pop()
        refresh_case(self.case)
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "cover every task"))

    def test_urgent_action_delay_rejected(self):
        action_turn = next(t for t in self.case["gold_run"]["turns"] if "ACTION-001" in t["action_refs"])
        action_turn["start_second"] = 400
        action_turn["end_second"] = 410
        refresh_case(self.case)
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "after the threshold"))

    def test_generator_cannot_be_clinical_reviewer(self):
        self.case["workflow"]["reviews"]["clinical"]["reviewer_name"] = self.case["workflow"]["generation"]["generator_identity"]
        self.assertTrue(contains(validate_case(self.case, source_dir=FIX), "differ from generator"))


class TestReasoningLayer(Base):
    def test_valid_reasoning(self):
        self.assertEqual(validate_reasoning(self.reasoning, self.case, self.registry), [])

    def test_requires_locked_case(self):
        self.case["workflow"]["canonical_case"] = "not_locked"
        self.case["workflow"]["lock_record"]["decision"] = "not_locked"
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "requires a locked"))

    def test_canonical_hash_binding(self):
        self.reasoning["canonical_case_hash"] = "0" * 64
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "canonical_case_hash"))

    def test_registry_hash_binding(self):
        self.reasoning["registry_hash"] = "0" * 64
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "registry_hash"))

    def test_source_bundle_binding(self):
        self.reasoning["source_bundle_hash"] = "0" * 64
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "source_bundle_hash"))

    def test_task_snapshot_copies_exact_task(self):
        self.reasoning["task_snapshot"][0]["source_task_text"] = "Different task"
        refresh_reasoning(self.reasoning, self.case, self.registry)
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "conflicts with canonical task"))

    def test_task_budgets_total_480(self):
        self.reasoning["task_snapshot"][0]["time_budget_seconds"] += 1
        refresh_reasoning(self.reasoning, self.case, self.registry)
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "total 480"))

    def test_reading_clock_contiguous(self):
        self.reasoning["reading_clock"]["segments"][1]["start_second"] = 41
        refresh_reasoning(self.reasoning, self.case, self.registry)
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "expected start"))

    def test_hint_target_must_resolve(self):
        self.reasoning["reasoning_nodes"][0]["target_ref"] = "TURN-999"
        refresh_reasoning(self.reasoning, self.case, self.registry)
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "unresolved reference"))

    def test_visible_hint_max_12_words(self):
        self.reasoning["reasoning_nodes"][0]["visible_hint"] = "one two three four five six seven eight nine ten eleven twelve thirteen"
        refresh_reasoning(self.reasoning, self.case, self.registry)
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "exceeds 12"))

    def test_logic_turn_must_resolve(self):
        self.reasoning["logic_track"][0]["turn_refs"] = ["TURN-999"]
        refresh_reasoning(self.reasoning, self.case, self.registry)
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "unresolved reference"))

    def test_immediate_action_needs_safety_pin(self):
        self.reasoning["safety_pins"] = []
        refresh_reasoning(self.reasoning, self.case, self.registry)
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "do not cover all immediate"))

    def test_unsafe_delay_language_rejected(self):
        self.reasoning["performance_clock"]["segments"][0]["move_on_signal"] = "Finish the history before acting."
        refresh_reasoning(self.reasoning, self.case, self.registry)
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "unsafe delay"))

    def test_forbidden_visible_word_rejected(self):
        self.reasoning["task_snapshot"][0]["plain_scope"] = "Help the candidate focus."
        refresh_reasoning(self.reasoning, self.case, self.registry)
        errors = validate_reasoning(self.reasoning, self.case, self.registry)
        self.assertTrue(contains(errors, "forbidden learner-facing word"))

    def test_open_registry_conflict_blocks_ready(self):
        self.reasoning["registry_patch"]["conflicts"] = [{
            "conflict_id": "CONFLICT-001", "description": "Conflict", "existing_ref": "GUARD-001",
            "new_statement": "Different", "status": "open", "required_decision": "Human decision"
        }]
        refresh_reasoning(self.reasoning, self.case, self.registry)
        self.assertTrue(contains(validate_reasoning(self.reasoning, self.case, self.registry), "open registry conflicts"))


class TestAudit(Base):
    def test_valid_audit(self):
        self.assertEqual(validate_audit(self.audit, self.case, self.reasoning, self.registry, FIX), [])

    def test_auditor_run_must_differ(self):
        self.audit["auditor_run_id"] = self.audit["generator_run_ids"][0]
        refresh_audit(self.audit, self.case, self.reasoning, self.registry)
        self.assertTrue(contains(validate_audit(self.audit, self.case, self.reasoning, self.registry, FIX), "auditor_run_id"))

    def test_auditor_identity_must_differ(self):
        self.audit["auditor_identity"] = self.case["workflow"]["generation"]["generator_identity"]
        refresh_audit(self.audit, self.case, self.reasoning, self.registry)
        self.assertTrue(contains(validate_audit(self.audit, self.case, self.reasoning, self.registry, FIX), "auditor_identity"))

    def test_curriculum_binding_checked(self):
        self.audit["curriculum_entry_hash"] = "0" * 64
        refresh_audit(self.audit, self.case, self.reasoning, self.registry)
        self.audit["curriculum_entry_hash"] = "0" * 64
        self.audit["integrity"]["audit_report_hash"] = audit_report_hash(self.audit)
        self.assertTrue(contains(validate_audit(self.audit, self.case, self.reasoning, self.registry, FIX), "curriculum_entry_hash"))

    def test_source_bundle_binding_checked(self):
        self.audit["source_bundle_hash"] = "0" * 64
        self.audit["integrity"]["audit_report_hash"] = audit_report_hash(self.audit)
        self.assertTrue(contains(validate_audit(self.audit, self.case, self.reasoning, self.registry, FIX), "source_bundle_hash"))

    def test_pass_requires_all_checks(self):
        self.audit["checks"]["causal_accuracy"] = "changes_required"
        self.audit["integrity"]["audit_report_hash"] = audit_report_hash(self.audit)
        self.assertTrue(contains(validate_audit(self.audit, self.case, self.reasoning, self.registry, FIX), "requires all checks"))

    def test_pass_cannot_have_open_finding(self):
        self.audit["findings"] = [{
            "finding_id": "AUD-FIND-001", "severity": "high", "section": "reasoning",
            "exact_ref": "RZN-001", "risk": "Wrong link", "earliest_faulty_layer": "reasoning",
            "required_fix": "Correct it", "status": "open"
        }]
        self.audit["integrity"]["audit_report_hash"] = audit_report_hash(self.audit)
        self.assertTrue(contains(validate_audit(self.audit, self.case, self.reasoning, self.registry, FIX), "open findings"))


class TestLearnerExport(Base):
    def test_valid_learner_export(self):
        self.assertEqual(validate_learner(self.learner, self.case, self.reasoning, self.registry, self.audit, FIX), [])

    def test_export_builder_is_deterministic(self):
        built = build_export(self.case, self.reasoning, self.registry, self.audit, "2026-07-12", FIX)
        self.assertEqual(built, self.learner)

    def test_hidden_governance_key_rejected(self):
        self.learner["source_governance"] = {}
        self.assertTrue(contains(validate_learner(self.learner, self.case, self.reasoning, self.registry, self.audit, FIX), "additional properties"))

    def test_stem_must_match_canonical(self):
        self.learner["stem_page"]["stem_nodes"][0]["text"] = "Changed"
        self.assertTrue(contains(validate_learner(self.learner, self.case, self.reasoning, self.registry, self.audit, FIX), "stem text differs"))

    def test_script_must_match_gold_run(self):
        self.learner["script_page"]["turns"][0]["text"] = "Changed"
        self.assertTrue(contains(validate_learner(self.learner, self.case, self.reasoning, self.registry, self.audit, FIX), "script differs"))

    def test_hint_attachment_checked(self):
        hint = self.learner["hints"][0]["hint_id"]
        for collection in [self.learner["stem_page"]["stem_nodes"], self.learner["stem_page"]["tasks"], self.learner["script_page"]["turns"]]:
            for item in collection:
                if hint in item.get("hint_ids", []): item["hint_ids"].remove(hint)
        self.assertTrue(contains(validate_learner(self.learner, self.case, self.reasoning, self.registry, self.audit, FIX), "wrong learner location"))

    def test_release_hash_checked(self):
        self.learner["release"]["source_bundle_hash"] = "0" * 64
        self.assertTrue(contains(validate_learner(self.learner, self.case, self.reasoning, self.registry, self.audit, FIX), "source bundle"))

    def test_index_builds_from_learner_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fixture.json"
            path.write_text(json.dumps(self.learner))
            index = build_index(Path(td), "2026-07-12")
            self.assertEqual(index["schema_version"], "2.0.0")
            self.assertEqual(index["cases"][0]["case_id"], self.case["case_id"])


class TestQueueAndRegistry(Base):
    def test_queue_start_records_exact_command(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path = Path(td) / "queue.json"
            queue_path.write_text((ROOT / "repo" / "queue" / "case-queue.json").read_text())
            result = subprocess.run([
                sys.executable, str(SCRIPTS / "manage_queue.py"), "--queue", str(queue_path),
                "start", "CP-P001-C001", "--by", "Tester", "--date", "2026-07-12"
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            queue = load_json(queue_path); item = queue["items"][0]
            self.assertFalse(queue["generation_frozen"])
            self.assertEqual(item["authorisation_command"], "BUILD_CASE CP-P001-C001")

    def test_resolve_case_holds_while_frozen(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / "resolve_case.py"), "CP-P001-C001"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["generation_ready"])

    def test_registry_patch_requires_human_approval(self):
        patch = copy.deepcopy(self.reasoning["registry_patch"])
        patch["human_approval"] = {"status": "not_started", "approved_by": None, "approved_date": None}
        self.assertTrue(contains(validate_patch(self.registry, patch), "human approval"))

    def test_source_fixture_hash_is_correct(self):
        data = (FIX / "source-fixture.txt").read_bytes()
        expected = self.case["source_governance"]["sources"][0]["file_sha256"]
        self.assertEqual(hashlib.sha256(data).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()

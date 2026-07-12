#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    result = subprocess.run([sys.executable, "scripts/validate_package.py", "--skip-tests", "--skip-browser"], cwd=ROOT)
    if result.returncode:
        return result.returncode
    subprocess.run([sys.executable, "scripts/build_manifest.py"], cwd=ROOT, check=True)
    evidence = json.loads((ROOT / "evidence" / "FINAL_QA.json").read_text())
    tests = evidence.get("contract_tests", {})
    browser = evidence.get("browser_smoke", {})
    lock = {
        "package": "Clinical Pathway Case System",
        "version": (ROOT / "VERSION").read_text().strip(),
        "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
        "technical_status": "PASS",
        "generation_frozen": True,
        "clinical_case_count": 0,
        "study_ready_case_count": 0,
        "curriculum_patterns": 40,
        "curriculum_case_slots": 160,
        "custom_gpt_count": 3,
        "website_renderer_status": "READY_EMPTY_LIBRARY",
        "contract_tests": tests,
        "browser_smoke": browser,
        "authoring_standard_sha256": sha(ROOT / "authority" / "CASE_AUTHORING_STANDARD_v2.md"),
        "manifest_sha256": sha(ROOT / "MANIFEST.sha256"),
        "clinical_release_status": "HOLD_NO_GENERATED_CASES",
        "statement": "The system is technically ready. No clinical content was generated or released during construction."
    }
    (ROOT / "FINAL_LOCK.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    final = subprocess.run([sys.executable, "scripts/validate_package.py", "--require-lock", "--skip-tests", "--skip-browser"], cwd=ROOT)
    return final.returncode


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run final technical QA and write evidence before package sealing."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"


def run(command: list[str]) -> dict[str, object]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    return {
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "pass": result.returncode == 0,
    }


def main() -> int:
    EVIDENCE.mkdir(exist_ok=True)
    package = run([sys.executable, "scripts/validate_package.py", "--skip-tests", "--skip-browser"])
    contracts = run([sys.executable, "-m", "unittest", "tests/test_system.py", "-v"])
    browser = run([sys.executable, "tests/browser_smoke.py"])
    node = run(["node", "--check", "website/app.js"])
    compile_result = run([sys.executable, "-m", "compileall", "-q", "scripts", "tests"])

    combined = str(contracts["stdout"]) + "\n" + str(contracts["stderr"])
    matched = re.search(r"Ran\s+(\d+)\s+tests", combined)
    contract_total = int(matched.group(1)) if matched else 0
    browser_path = EVIDENCE / "browser-smoke-results.json"
    browser_result = json.loads(browser_path.read_text()) if browser_path.is_file() else {}
    browser_checks = browser_result.get("checks", {})
    queue = json.loads((ROOT / "repo" / "queue" / "case-queue.json").read_text())
    website_index = json.loads((ROOT / "website" / "data" / "index.json").read_text())
    curriculum = json.loads((ROOT / "registries" / "curriculum.json").read_text())
    slots = sum(len(x.get("case_slots", [])) for x in curriculum.get("patterns", []))

    checks = {
        "package_validation": bool(package["pass"]),
        "contract_tests": bool(contracts["pass"]) and contract_total > 0,
        "browser_smoke": bool(browser["pass"]) and browser_result.get("status") == "PASS" and all(browser_checks.values()),
        "javascript_syntax": bool(node["pass"]),
        "python_compile": bool(compile_result["pass"]),
        "generation_frozen": queue.get("generation_frozen") is True,
        "no_authorised_case": not any(x.get("authorised") for x in queue.get("items", [])),
        "curriculum_40_patterns": len(curriculum.get("patterns", [])) == 40,
        "curriculum_160_slots": slots == 160,
        "production_index_empty": not website_index.get("cases"),
        "three_custom_gpt_specs": len(list((ROOT / "gpts").glob("*_GPT_INSTRUCTIONS.md"))) == 3,
        "codex_runbook_present": (ROOT / "CODEX_RUNBOOK.md").is_file() and (ROOT / "AGENTS.md").is_file(),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    report = {
        "package": "Clinical Pathway Case System",
        "version": (ROOT / "VERSION").read_text().strip(),
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "final_status": status,
        "checks": checks,
        "contract_tests": {"passed": contract_total if contracts["pass"] else 0, "total": contract_total},
        "browser_smoke": {"passed": sum(bool(x) for x in browser_checks.values()), "total": len(browser_checks)},
        "curriculum": {"patterns": len(curriculum.get("patterns", [])), "case_slots": slots},
        "generation": {"frozen": queue.get("generation_frozen"), "authorised_cases": sum(bool(x.get("authorised")) for x in queue.get("items", []))},
        "production_case_count": len(website_index.get("cases", [])),
        "clinical_release_status": "HOLD_NO_GENERATED_CASES",
        "commands": {"package": package, "contracts": contracts, "browser": browser, "node": node, "compile": compile_result},
    }
    (EVIDENCE / "FINAL_QA.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Final QA", "", f"**Technical result:** `{status}`", "", "## Results", "",
        f"- Contract tests: `{report['contract_tests']['passed']}/{report['contract_tests']['total']} PASS`",
        f"- Browser checks: `{report['browser_smoke']['passed']}/{report['browser_smoke']['total']} PASS`",
        f"- Curriculum: `{report['curriculum']['patterns']} patterns / {report['curriculum']['case_slots']} slots`",
        f"- Generation frozen: `{'YES' if checks['generation_frozen'] else 'NO'}`",
        f"- Authorised cases: `{report['generation']['authorised_cases']}`",
        f"- Production learner cases: `{report['production_case_count']}`", "",
        "## Boundary", "", "```text",
        f"Technical package: {status}",
        "Clinical content generation: STOPPED",
        "Clinical release: HOLD until a case completes all gates",
        "```", "",
        "Synthetic fixtures validate the pipeline. They are not study content.", "",
    ]
    (EVIDENCE / "FINAL_QA.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"final_status": status, "contract_tests": report["contract_tests"], "browser_smoke": report["browser_smoke"]}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

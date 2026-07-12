#!/usr/bin/env python3
from __future__ import annotations
import argparse
from collections import defaultdict
from pathlib import Path
from common import load_json, save_json, schema_errors


def build(input_dir: Path, generated_at: str | None) -> dict:
    records = []
    seen = set()
    for path in sorted(input_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        data = load_json(path)
        errors = schema_errors(data, "learner-export.schema.json")
        if errors:
            raise ValueError(f"{path.name} is not a learner export:\n- " + "\n- ".join(errors))
        case_id = data["case_id"]
        if case_id in seen:
            raise ValueError(f"duplicate learner case_id: {case_id}")
        seen.add(case_id)
        records.append({
            "case_id": case_id,
            "title": data["title"],
            "file": f"data/{path.name}",
            "phase_id": data["navigation"]["phase_id"],
            "phase_label": data["navigation"]["phase_label"],
            "pattern_label": data["navigation"]["pattern_label"],
        })
    by_phase = defaultdict(lambda: defaultdict(list))
    phase_labels = {}
    for item in records:
        phase_labels[item["phase_id"]] = item["phase_label"]
        by_phase[item["phase_id"]][item["pattern_label"]].append(item)
    phases = []
    for phase_id in ["PHASE-1", "PHASE-2", "PHASE-3", "PHASE-4"]:
        if phase_id not in by_phase:
            continue
        patterns = []
        for pattern_label in sorted(by_phase[phase_id]):
            cases = [
                {"case_id": x["case_id"], "title": x["title"], "file": x["file"]}
                for x in sorted(by_phase[phase_id][pattern_label], key=lambda y: y["case_id"])
            ]
            patterns.append({"label": pattern_label, "cases": cases})
        phases.append({"phase_id": phase_id, "label": phase_labels[phase_id], "patterns": patterns})
    output = {
        "schema_version": "2.0.0",
        "generated_at": generated_at,
        "phases": phases,
        "cases": [
            {"case_id": x["case_id"], "title": x["title"], "file": x["file"], "phase_id": x["phase_id"], "pattern_label": x["pattern_label"]}
            for x in sorted(records, key=lambda y: y["case_id"])
        ],
    }
    errors = schema_errors(output, "learner-index.schema.json")
    if errors:
        raise ValueError("Generated index failed schema:\n- " + "\n- ".join(errors))
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--generated-at")
    args = parser.parse_args()
    save_json(args.output, build(args.input_dir, args.generated_at))
    print(args.output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

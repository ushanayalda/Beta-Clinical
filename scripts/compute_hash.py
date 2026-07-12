#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    audit_report_hash, canonical_case_hash, curriculum_entry_hash, load_json,
    reasoning_layer_hash, registry_hash, save_json, source_bundle_hash,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["case", "reasoning", "registry", "source", "audit"])
    parser.add_argument("file", type=Path)
    parser.add_argument("--curriculum", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = load_json(args.file)

    if args.kind == "case":
        source_hash = source_bundle_hash(data)
        value = canonical_case_hash(data)
        if args.write:
            data["integrity"]["source_bundle_hash"] = source_hash
            if args.curriculum:
                curriculum = load_json(args.curriculum)
                entry_hash = curriculum_entry_hash(curriculum, data["case_id"])
                if entry_hash is None:
                    raise ValueError(f"case_id {data['case_id']} is absent from curriculum")
                data["integrity"]["curriculum_entry_hash"] = entry_hash
            data["integrity"]["authoring_payload_hash"] = value
            if data.get("workflow", {}).get("lock_record", {}).get("decision") == "locked":
                data["workflow"]["lock_record"]["authoring_payload_hash"] = value
    elif args.kind == "reasoning":
        value = reasoning_layer_hash(data)
        if args.write:
            data["integrity"]["reasoning_layer_hash"] = value
            data["registry_patch"]["reasoning_layer_hash"] = value
            data["registry_patch"]["case_index_entry"]["reasoning_layer_hash"] = value
    elif args.kind == "registry":
        value = registry_hash(data)
    elif args.kind == "source":
        value = source_bundle_hash(data)
        if args.write:
            data["integrity"]["source_bundle_hash"] = value
    else:
        value = audit_report_hash(data)
        if args.write:
            data["integrity"]["audit_report_hash"] = value

    if args.write:
        save_json(args.file, data)
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import load_json, print_result
from validate_audit_report import validate_audit
from validate_canonical_case import validate_case
from validate_reasoning_layer import validate_reasoning


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--reasoning", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    case = load_json(args.case)
    reasoning = load_json(args.reasoning)
    registry = load_json(args.registry)
    errors = validate_case(case, source_dir=args.source_dir) + validate_reasoning(reasoning, case, registry)
    if args.audit:
        errors += validate_audit(load_json(args.audit), case, reasoning, registry, args.source_dir)
    return print_result(errors)


if __name__ == "__main__":
    raise SystemExit(main())

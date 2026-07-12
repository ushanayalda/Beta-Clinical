#!/usr/bin/env python3
"""Extract a registry patch from a complete reasoning-layer artifact."""
from __future__ import annotations

import argparse
from pathlib import Path

from common import load_json, save_json, schema_errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reasoning", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    reasoning = load_json(args.reasoning)
    reasoning_errors = schema_errors(reasoning, "reasoning-layer.schema.json")
    if reasoning_errors:
        raise SystemExit("Reasoning artifact is invalid:\n- " + "\n- ".join(reasoning_errors))
    patch = reasoning.get("registry_patch")
    patch_errors = schema_errors(patch, "registry-patch.schema.json")
    if patch_errors:
        raise SystemExit("Registry patch is invalid:\n- " + "\n- ".join(patch_errors))
    save_json(args.output, patch)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

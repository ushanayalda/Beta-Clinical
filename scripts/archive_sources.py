#!/usr/bin/env python3
"""Archive source URLs named by a canonical draft and refresh its integrity fields."""
from __future__ import annotations

import argparse
import hashlib
import mimetypes
import urllib.parse
import urllib.request
from pathlib import Path

from common import canonical_case_hash, load_json, save_json, source_bundle_hash


def extension(url: str, content_type: str | None) -> str:
    suffix = Path(urllib.parse.urlparse(url).path).suffix
    if suffix and len(suffix) <= 8:
        return suffix
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed:
            return guessed
    return ".html"


def reset_reviews(case: dict) -> None:
    workflow = case.get("workflow", {})
    workflow["structure_audit"] = "not_started"
    workflow["source_review"] = "not_started"
    workflow["clinical_review"] = "not_started"
    workflow["timing_test"] = "not_started"
    workflow["canonical_case"] = "not_locked"
    lock = workflow.get("lock_record", {})
    lock.update({
        "decision": "not_locked",
        "locked_by": None,
        "locked_date": None,
        "authoring_payload_hash": None,
        "blocking_holds": [],
    })
    for record in workflow.get("reviews", {}).values():
        record["status"] = "not_started"
        record["reviewer_name"] = None
        record["reviewer_origin"] = "unassigned"
        record["review_date"] = None
        record["authoring_payload_hash"] = None
        record["findings"] = []


def archive(case_path: Path, output_dir: Path, timeout: int) -> dict:
    case = load_json(case_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    changed = False
    for source in case.get("source_governance", {}).get("sources", []):
        url = source.get("source_url")
        if not url:
            raise ValueError(f"{source.get('source_id')}: source_url is missing")
        request = urllib.request.Request(url, headers={"User-Agent": "ClinicalPathwaySourceArchiver/2.0"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content = response.read()
                content_type = response.headers.get("Content-Type")
        except Exception as exc:
            source["archive_status"] = "unavailable"
            source["file_name"] = None
            source["file_sha256"] = None
            raise RuntimeError(f"{source.get('source_id')}: could not archive {url}: {exc}") from exc
        name = f"{source['source_id']}{extension(url, content_type)}"
        target = output_dir / name
        target.write_bytes(content)
        source["file_name"] = name
        source["file_sha256"] = hashlib.sha256(content).hexdigest()
        source["archive_status"] = "archived"
        if source.get("status") == "discovered":
            source["status"] = "review_required"
        changed = True

    if changed:
        reset_reviews(case)
        case["integrity"]["source_bundle_hash"] = source_bundle_hash(case)
        case["integrity"]["authoring_payload_hash"] = canonical_case_hash(case)
        save_json(case_path, case)
    return case


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    archive(args.case, args.output_dir, args.timeout)
    print(args.case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

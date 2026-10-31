#!/usr/bin/env python3
"""Verify the public Stage 04 manifest without the private URG inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def need(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("STAGE04_VERIFY_FAILED: " + message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.bundle / "coverage_manifest.v1.json"
    smoke_path = args.bundle / "smoke_validation.json"
    summary_path = args.bundle / "group_scope_summary.tsv"
    sums_path = args.bundle / "SHA256SUMS"
    for path in (manifest_path, smoke_path, summary_path, sums_path):
        need(path.is_file(), "missing " + path.name)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    bins = manifest.get("bins", [])
    score_bins = [item for item in bins if item.get("eligible_for_instance_score")]
    need(manifest.get("schema_version") == "opentitan-aon-timer-functional-4525-v1", "schema mismatch")
    need(len(bins) == 4533, "expected 4533 expanded records")
    need(len(score_bins) == 4525, "expected 4525 score bins")
    need(len(bins) - len(score_bins) == 8, "expected 8 weight-zero bins")
    type_keys = {(b["covergroup"], b["bin_type"], b["coverpoint_or_cross"], b["bin_name"]) for b in bins}
    need(len(type_keys) == 4507, "expected 4507 unique type definitions")
    aon = [b for b in score_bins if b["covergroup"].startswith("aon_timer_env_pkg::")]
    need(len(aon) == 4279, "expected 4279 AON Timer score bins")
    need(len(score_bins) - len(aon) == 246, "expected 246 generic score bins")
    primary = manifest.get("primary_denominator", {})
    need(primary.get("expected_bins") == 4525 and primary.get("hit_bins") == 45, "primary score mismatch")
    type_reference = manifest.get("type_aggregate_reference", {})
    need(type_reference.get("expected_bins") == 4507 and type_reference.get("hit_bins") == 46,
         "type aggregate mismatch")
    need(smoke.get("manifest_sha256") == sha256(manifest_path), "manifest hash mismatch")
    need(smoke.get("urg_instance_score", {}).get("expected") == 4525
         and smoke.get("urg_instance_score", {}).get("covered") == 45, "smoke instance score mismatch")
    need(smoke.get("urg_type_aggregate", {}).get("expected") == 4507
         and smoke.get("urg_type_aggregate", {}).get("covered") == 46, "smoke type score mismatch")
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        need(sha256(args.bundle / name) == expected, "SHA256SUMS mismatch for " + name)
    for path in args.bundle.iterdir():
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            need(not re.search(r"(?:[A-Za-z]:\\|/home/|/root/|/tmp/|\\\\[A-Za-z0-9_.-]+\\\\)", text),
                 "private path found in " + path.name)
    print(json.dumps({"verification": "PASS", "schema_version": manifest["schema_version"],
                      "expanded_records": len(bins), "score_bins": len(score_bins),
                      "weight_zero_bins": 8, "aon_timer_bins": len(aon), "generic_bins": 246,
                      "type_definitions": len(type_keys), "primary_hit_bins": 45},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

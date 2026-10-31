#!/usr/bin/env python3
"""Independently verify the public Stage 06 matrix and vector artifacts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise SystemExit("OUTPUT_EXISTS")
    stage = args.stage
    manifest = json.loads((stage / "coverage_manifest.v1.json").read_text(encoding="utf-8"))
    summary = json.loads((stage / "matrix_summary.json").read_text(encoding="utf-8"))
    eligible = sorted(b["id"] for b in manifest["bins"] if b.get("eligible_for_instance_score"))
    if len(manifest["bins"]) != 4533 or len(eligible) != 4525:
        raise SystemExit("MANIFEST_DIMENSION_MISMATCH")
    status = rows(stage / "status.tsv")
    if len(status) != 17 or len({r["item"] for r in status}) != 17:
        raise SystemExit("STATUS_DIMENSION_MISMATCH")
    items = [r["item"] for r in status]
    matrix = rows(stage / "bin_by_run.tsv")
    if len(matrix) != 4525 or [r["bin_id"] for r in matrix] != eligible:
        raise SystemExit("MATRIX_BIN_ORDER_MISMATCH")
    union = rows(stage / "initial_union_and_frequency.tsv")
    if [r["bin_id"] for r in union] != eligible:
        raise SystemExit("UNION_BIN_ORDER_MISMATCH")
    success = [r["item"] for r in status if r["return_code"] == "0"]
    if summary["successful_run_count"] != len(success) or summary["failed_run_count"] != 17 - len(success):
        raise SystemExit("SUMMARY_STATUS_MISMATCH")
    seen = {item: 0 for item in eligible}
    for mr, ur in zip(matrix, union):
        values = []
        for item in items:
            value = mr[item]
            if item in success:
                if value not in {"0", "1"}:
                    raise SystemExit(f"BAD_SUCCESS_VALUE_{item}")
                values.append(int(value))
            elif value != "NA":
                raise SystemExit(f"FAILED_COLUMN_NOT_NA_{item}")
        count = sum(values)
        if int(ur["hit_count"]) != count or int(ur["hit_any"]) != int(count > 0):
            raise SystemExit(f"UNION_COUNT_MISMATCH_{mr['bin_id']}")
        if int(ur["successful_run_count"]) != len(success):
            raise SystemExit("SUCCESSFUL_RUN_COUNT_MISMATCH")
        if abs(float(ur["frequency"]) - (count / len(success) if success else 0.0)) > 1e-10:
            raise SystemExit(f"FREQUENCY_MISMATCH_{mr['bin_id']}")
        seen[mr["bin_id"]] += 1
    if any(v != 1 for v in seen.values()):
        raise SystemExit("DUPLICATE_OR_MISSING_MATRIX_BIN")
    vector_hashes = {}
    for item in success:
        vector = stage / "vectors" / item / "bin_vector.tsv"
        if not vector.is_file():
            raise SystemExit(f"MISSING_PUBLIC_VECTOR_{item}")
        vrows = rows(vector)
        if len(vrows) != 4525 or [r["bin_id"] for r in vrows] != eligible:
            raise SystemExit(f"VECTOR_DIMENSION_MISMATCH_{item}")
        vector_hashes[item] = sha256(vector)
    if vector_hashes != summary["vector_sha256"]:
        raise SystemExit("VECTOR_HASH_SUMMARY_MISMATCH")
    result = {
        "schema": "aon-timer-stage06-matrix-verification-v1",
        "manifest_sha256": sha256(stage / "coverage_manifest.v1.json"),
        "status_sha256": sha256(stage / "status.tsv"),
        "matrix_sha256": sha256(stage / "bin_by_run.tsv"),
        "union_sha256": sha256(stage / "initial_union_and_frequency.tsv"),
        "eligible_bins": 4525,
        "candidate_count": 17,
        "successful_run_count": len(success),
        "failed_run_count": 17 - len(success),
        "initial_union_bin_count": sum(int(r["hit_any"]) for r in union),
        "passed": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

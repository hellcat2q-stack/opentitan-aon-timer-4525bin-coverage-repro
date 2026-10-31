#!/usr/bin/env python3
"""Verify the small real VCS online-link smoke evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise SystemExit("OUTPUT_EXISTS")
    job = json.loads((args.stage / "online_job.v1.json").read_text(encoding="utf-8"))
    summary = json.loads((args.stage / "public_vector" / "aon_timer_sec_cm" / "vector_summary.json").read_text(encoding="utf-8"))
    status = (args.stage / "status.tsv").read_text(encoding="utf-8").splitlines()
    if len(status) != 2 or len(status[0].split("\t")) != 3 or len(status[1].split("\t")) != 3 or status[1].split("\t")[-1].strip() != "0":
        raise SystemExit("ONLINE_STATUS_NOT_PASS")
    if job["test"] != summary["item"] or job["actual_vcs_fixed_seed"] != summary["seed"]:
        raise SystemExit("ONLINE_JOB_VECTOR_METADATA_MISMATCH")
    if summary["manifest_schema"] != "opentitan-aon-timer-functional-4525-v1" or summary["expected_bins"] != 4525:
        raise SystemExit("ONLINE_VECTOR_SCHEMA_MISMATCH")
    result = {"schema": "opentitan-aon-timer-stage08-verification-v1",
              "job_sha256": sha256(args.stage / "online_job.v1.json"),
              "status_sha256": sha256(args.stage / "status.tsv"),
              "vector_sha256": sha256(args.stage / "public_vector" / "aon_timer_sec_cm" / "bin_vector.tsv"),
              "item": summary["item"], "seed": summary["seed"], "expected_bins": summary["expected_bins"],
              "hit_bins": summary["hit_bins"], "new_vcs_run": True,
              "scheduler_stimulus_seed_applied": False, "passed": True}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

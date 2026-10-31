#!/usr/bin/env python3
"""Verify the Stage 09 preregistration without starting VCS."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


METHODS = {
    "full",
    "no_incremental_refill",
    "no_runtime_penalty",
    "random_selection",
    "sequence_ucb_only",
    "cluster_ucb_only",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("OUTPUT_EXISTS")
    prereg = json.loads(args.prereg.read_text(encoding="utf-8"))
    if prereg["schema_version"] != "opentitan-aon-timer-stage09-preregistration-v1":
        raise SystemExit("PREREG_SCHEMA_MISMATCH")
    if prereg["status"] != "REGISTERED_NOT_EXECUTED":
        raise SystemExit("PREREG_STATUS_MISMATCH")
    common = prereg["common_design"]
    if common["total_submissions"] != 1000 or common["adaptive_submissions_after_initial_corpus"] != 983:
        raise SystemExit("BUDGET_MISMATCH")
    if common["logical_batch_size"] != 10 or common["logical_batches"] != 100 or common["workers"] != 10:
        raise SystemExit("PARALLELISM_MISMATCH")
    if common["root_seed"] != 42 or common["candidate_jobs"] != 17:
        raise SystemExit("SEED_OR_POOL_MISMATCH")
    if set(prereg["methods"]) != METHODS:
        raise SystemExit("METHOD_SET_MISMATCH")
    if prereg["source_contract"]["eligible_bins_total"] != 4525 or prereg["source_contract"]["aon_timer_bins"] != 4279:
        raise SystemExit("DENOMINATOR_MISMATCH")
    checked = {}
    for item, entry in prereg["frozen_inputs"].items():
        path = args.repo / entry["path"]
        if not path.is_file():
            raise SystemExit(f"MISSING_INPUT_{item}")
        actual = sha256(path)
        if actual != entry["sha256"]:
            raise SystemExit(f"INPUT_HASH_MISMATCH_{item}")
        checked[item] = {"path": entry["path"], "sha256": actual}
    result = {
        "schema_version": "opentitan-aon-timer-stage09-prereg-verification-v1",
        "preregistration_sha256": sha256(args.prereg),
        "checked_inputs": checked,
        "method_count": len(METHODS),
        "total_submissions": common["total_submissions"],
        "workers": common["workers"],
        "root_seed": common["root_seed"],
        "formal_execution_started": False,
        "execution_gate": prereg["execution_gate"]["status"],
        "passed": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

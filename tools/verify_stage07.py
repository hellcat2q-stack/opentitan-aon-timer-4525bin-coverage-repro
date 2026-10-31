#!/usr/bin/env python3
"""Offline verification for Stage 07 clusters, scores and replay trace."""
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


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--matrix", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise SystemExit("OUTPUT_EXISTS")
    stage = args.stage
    clusters = json.loads((stage / "clusters" / "clusters.json").read_text(encoding="utf-8"))
    features = json.loads((stage / "clusters" / "features.json").read_text(encoding="utf-8"))
    scores = json.loads((stage / "scores" / "cluster_scores.json").read_text(encoding="utf-8"))
    inputs = json.loads((stage / "scores" / "scheduler_inputs.json").read_text(encoding="utf-8"))
    summary = json.loads((stage / "dryrun" / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    eligible = sorted(x["id"] for x in manifest["bins"] if x.get("eligible_for_instance_score"))
    if len(manifest["bins"]) != 4533 or len(eligible) != 4525:
        raise SystemExit("MANIFEST_DIMENSION_MISMATCH")
    if clusters["schema_version"] != "opentitan-aon-timer-stage07-clusters-v1" or clusters["bin_count"] != 4525:
        raise SystemExit("CLUSTER_SCHEMA_MISMATCH")
    if sorted(clusters["bin_to_cluster"]) != eligible:
        raise SystemExit("CLUSTER_BIN_SET_MISMATCH")
    memberships = {}
    for cluster in clusters["clusters"]:
        if not 0 < cluster["size"] <= 32 or cluster["size"] != len(cluster["bin_ids"]):
            raise SystemExit("INVALID_CLUSTER_SIZE")
        for bid in cluster["bin_ids"]:
            if bid in memberships:
                raise SystemExit("DUPLICATE_CLUSTER_MEMBERSHIP")
            memberships[bid] = cluster["cluster_id"]
    if memberships != clusters["bin_to_cluster"] or len(features["features"]) != 4525:
        raise SystemExit("CLUSTER_MEMBERSHIP_MISMATCH")
    if scores["bin_count"] != 4525 or scores["run_count"] != 17 or scores["covered_bin_count_initial"] != 376:
        raise SystemExit("SCORE_DIMENSION_MISMATCH")
    if set(scores["clusters"]) != {c["cluster_id"] for c in clusters["clusters"]}:
        raise SystemExit("SCORE_CLUSTER_SET_MISMATCH")
    if inputs["schema_version"] != "aon-timer-scheduler-inputs-v1" or len(inputs["bin_ids"]) != 4525:
        raise SystemExit("SCHEDULER_INPUT_SCHEMA_MISMATCH")
    if len(inputs["initial_runs"]) != 17 or len(inputs["sequences"]) != 17:
        raise SystemExit("SCHEDULER_INPUT_RUN_MISMATCH")
    events = []
    with (stage / "dryrun" / "events.jsonl").open(encoding="utf-8") as f:
        for line in f:
            events.append(json.loads(line))
    previous = "0" * 64
    for index, event in enumerate(events, 1):
        if event["event_id"] != index or event["previous_sha256"] != previous:
            raise SystemExit("EVENT_CHAIN_LINK_MISMATCH")
        body = dict(event)
        digest = body.pop("event_sha256")
        if hashlib.sha256(canonical(body)).hexdigest() != digest:
            raise SystemExit("EVENT_HASH_MISMATCH")
        previous = digest
    if summary["event_count"] != len(events) or summary["events_sha256"] != hashlib.sha256(canonical(events)).hexdigest():
        raise SystemExit("EVENT_SUMMARY_MISMATCH")
    result = {"schema": "opentitan-aon-timer-stage07-verification-v1",
              "manifest_sha256": sha256(args.manifest), "matrix_sha256": sha256(args.matrix),
              "cluster_count": len(clusters["clusters"]), "bin_count": 4525,
              "initial_covered_bin_count": 376, "dryrun_budget": summary["budget"],
              "dryrun_workers": summary["workers"], "dryrun_submitted": summary["submitted"],
              "dryrun_completed": summary["completed"], "event_count": len(events), "passed": True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run a deterministic replay-only UCB trace to audit Stage 07 state transitions."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def normalize(values):
    positives = [v for v in values.values() if v > 0]
    divisor = sum(positives) / len(positives) if positives else 0.0
    return {k: (v / divisor if divisor else 0.0) for k, v in values.items()}


class Scheduler:
    def __init__(self, inputs, budget=32, workers=3, seed=42):
        if inputs["schema_version"] != "aon-timer-scheduler-inputs-v1":
            raise ValueError("INPUT_SCHEMA_MISMATCH")
        self.inputs = inputs
        self.bin_ids = set(inputs["bin_ids"])
        self.clusters = {k: set(v["bin_ids"]) for k, v in sorted(inputs["clusters"].items())}
        self.weights = {k: float(v["static_weight"]) for k, v in inputs["clusters"].items()}
        self.mapping = {bid: cid for cid, members in self.clusters.items() for bid in members}
        if set(self.mapping) != self.bin_ids:
            raise ValueError("CLUSTER_MAPPING_MISMATCH")
        self.sequences = dict(sorted(inputs["sequences"].items()))
        self.history = {k: next(r for r in inputs["initial_runs"] if r["sequence"] == k) for k in self.sequences}
        self.covered = set(inputs["initial_covered_bin_ids"])
        self.budget, self.workers, self.seed = budget, workers, seed
        self.submitted = self.completed = 0
        self.pending = {}
        self.cluster_stats = {k: {"submitted": 0, "completed": 0, "target_gain_sum": 0} for k in self.clusters}
        self.sequence_stats = {k: {"completed": 0, "history_count": 1, "hit_sums":
            {c: len(set(self.history[k]["hit_bin_ids"]) & members) for c, members in self.clusters.items()},
            "runtime_sum": float(self.history[k]["runtime_seconds"]), "runtime_count": 1} for k in self.sequences}
        self.policy = None
        self.policy_count = 0
        self.feedback_since_policy = 0
        self.events = []
        self.event("init", {"inputs_sha256": digest(inputs), "config": {"budget": budget, "workers": workers, "seed": seed},
                             "mode": "dry_run_replay", "numeric_policy": "float64-sorted-digest-tiebreak-v1"})

    def state(self):
        return {"covered_bin_ids": sorted(self.covered), "submitted": self.submitted, "completed": self.completed,
                "pending": self.pending, "policy": self.policy, "policy_count": self.policy_count,
                "cluster_stats": self.cluster_stats, "sequence_stats": self.sequence_stats,
                "dynamic": self.dynamic()}

    def event(self, kind, data):
        event = {"event_id": len(self.events) + 1, "type": kind, "data": data,
                 "state_sha256": digest(self.state()) if hasattr(self, "covered") else "",
                 "previous_sha256": self.events[-1]["event_sha256"] if self.events else "0" * 64}
        event["event_sha256"] = digest(event)
        self.events.append(event)

    def dynamic(self):
        raw = {cid: -math.log((len(members & self.covered) + 1) / (len(members) + 1)) for cid, members in self.clusters.items()}
        prior = normalize({cid: self.weights[cid] * v for cid, v in normalize(raw).items()})
        return {cid: {"uncovered": len(self.clusters[cid] - self.covered), "residual": raw[cid], "prior": prior[cid]} for cid in self.clusters}

    def choose(self):
        dynamic = self.dynamic()
        candidates = [cid for cid in self.clusters if dynamic[cid]["uncovered"]]
        if not candidates:
            return None
        scores = {}
        for cid in candidates:
            stats = self.cluster_stats[cid]
            avg = stats["target_gain_sum"] / stats["completed"] if stats["completed"] else 0.0
            exploit = dynamic[cid]["uncovered"] * (0.05 + avg) * (1 + 0.2 * (dynamic[cid]["prior"] - 1))
            explore = (5.0 - 3.8 * len(self.covered) / len(self.bin_ids)) * math.sqrt(math.log(self.submitted + 2) / (stats["submitted"] + 1))
            scores[cid] = exploit + explore
        cid = min(candidates, key=lambda k: (-scores[k], digest(["cluster", self.seed, k])))
        supported = [seq for seq in self.sequences if self.sequence_stats[seq]["hit_sums"][cid] > 0]
        if not supported:
            supported = list(self.sequences)
        seq_scores = {}
        max_runtime = max((self.sequence_stats[s]["runtime_sum"] for s in supported), default=0.0)
        for seq in supported:
            st = self.sequence_stats[seq]
            potential = st["hit_sums"][cid] / st["history_count"]
            exploration = 2.0 * math.sqrt(math.log(self.completed + 2) / (st["completed"] + 1e-8)) if st["completed"] else 1000.0
            penalty = 1 - 0.1 * (st["runtime_sum"] / max_runtime if max_runtime else 0.0)
            seq_scores[seq] = (potential + exploration) * penalty
        seq = min(supported, key=lambda k: (-seq_scores[k], digest(["sequence", self.seed, k])))
        return cid, seq, scores, seq_scores

    def submit(self):
        if self.submitted >= self.budget or len(self.pending) >= self.workers:
            return None
        choice = self.choose()
        if choice is None:
            return None
        cid, seq, cluster_scores, sequence_scores = choice
        self.policy_count += 1
        self.policy = {"policy_id": f"p{self.policy_count:06d}", "target_cluster": cid, "sequence": seq}
        self.event("policy", {"policy": copy.deepcopy(self.policy), "cluster_scores": cluster_scores,
                               "sequence_scores": sequence_scores, "reason": "deterministic_replay_policy"})
        index = self.submitted + 1
        job = {"submission_id": f"s{index:06d}", "submission_index": index, "policy_id": self.policy["policy_id"],
               "target_cluster": cid, "sequence": seq, "test": self.sequences[seq]["test"],
               "stimulus_seed": 1 + int(digest(["stimulus-v1", self.seed, index])[:16], 16) % (2**31 - 1)}
        self.pending[job["submission_id"]] = job
        self.submitted += 1
        self.cluster_stats[cid]["submitted"] += 1
        self.event("submit", {"job": copy.deepcopy(job)})
        return job

    def complete(self, sid):
        job = self.pending.pop(sid)
        replay = self.history[job["sequence"]]
        hits = set(replay["hit_bin_ids"])
        new = hits - self.covered
        target_gain = len(new & self.clusters[job["target_cluster"]])
        self.covered.update(hits)
        self.completed += 1
        self.cluster_stats[job["target_cluster"]]["completed"] += 1
        self.cluster_stats[job["target_cluster"]]["target_gain_sum"] += target_gain
        st = self.sequence_stats[job["sequence"]]
        st["completed"] += 1
        st["history_count"] += 1
        for cid in self.clusters:
            st["hit_sums"][cid] += len(hits & self.clusters[cid])
        self.event("complete", {"submission_id": sid, "status": "pass", "replay_source_run_id": replay["run_id"],
                                 "runtime_seconds": replay["runtime_seconds"], "hit_bin_ids": sorted(hits),
                                 "new_bin_ids": sorted(new), "delta_bin": len(new), "delta_target": target_gain,
                                 "covered_bin_count": len(self.covered)})


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--budget", type=int, default=32)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    if args.output.exists():
        raise SystemExit("OUTPUT_EXISTS")
    scheduler = Scheduler(json.loads(args.inputs.read_text(encoding="utf-8")), args.budget, args.workers, args.seed)
    while scheduler.submitted < args.budget:
        while len(scheduler.pending) < args.workers and scheduler.submitted < args.budget:
            if scheduler.submit() is None:
                break
        if not scheduler.pending:
            break
        scheduler.complete(sorted(scheduler.pending)[0])
    args.output.mkdir(parents=True)
    with (args.output / "events.jsonl").open("w", encoding="utf-8", newline="") as f:
        for event in scheduler.events:
            f.write(json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    summary = {"schema_version": "opentitan-aon-timer-stage07-dryrun-v1", "mode": "dry_run_replay",
               "budget": args.budget, "workers": args.workers, "seed": args.seed,
               "submitted": scheduler.submitted, "completed": scheduler.completed,
               "initial_covered_bin_count": len(args.inputs and json.loads(args.inputs.read_text(encoding="utf-8")).get("initial_covered_bin_ids", [])),
               "final_covered_bin_count": len(scheduler.covered), "event_count": len(scheduler.events),
               "events_sha256": digest(scheduler.events), "final_state_sha256": digest(scheduler.state()),
               "replay_only": True, "new_vcs_runs": 0}
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

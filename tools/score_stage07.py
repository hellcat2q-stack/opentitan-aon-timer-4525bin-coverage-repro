#!/usr/bin/env python3
"""Score Stage 07 clusters and emit scheduler inputs from the Stage 06 matrix."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


SCHEMA = "opentitan-aon-timer-stage07-scores-v1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def pearson(left: list[int], right: list[int]) -> float:
    lm, rm = mean(left), mean(right)
    a, b = [x - lm for x in left], [x - rm for x in right]
    den = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    return 0.0 if den == 0 else sum(x * y for x, y in zip(a, b)) / den


def normalize(values: dict[str, float]) -> dict[str, float]:
    positive = [v for v in values.values() if v > 0]
    divisor = mean(positive)
    return {k: v / divisor if divisor else 0.0 for k, v in values.items()}


def tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def build(args: argparse.Namespace) -> None:
    if args.output.exists():
        raise SystemExit("OUTPUT_EXISTS")
    clusters = json.loads((args.clusters / "clusters.json").read_text(encoding="utf-8"))
    features_doc = json.loads((args.clusters / "features.json").read_text(encoding="utf-8"))
    features = {x["bin_id"]: x for x in features_doc["features"]}
    matrix = tsv(args.matrix)
    status = tsv(args.status)
    items = [r["item"] for r in status]
    if len(items) != 17 or len(matrix) != 4525:
        raise SystemExit("STAGE06_DIMENSION_MISMATCH")
    ids = [r["bin_id"] for r in matrix]
    if ids != sorted(ids) or set(ids) != set(features) or ids != sorted(clusters["bin_to_cluster"]):
        raise SystemExit("BIN_ORDER_OR_CLUSTER_MISMATCH")
    values = {bid: [int(row[item]) for item in items] for bid, row in ((r["bin_id"], r) for r in matrix)}
    covered = {bid for bid, vector in values.items() if any(vector)}
    total = sum(sum(vector) for vector in values.values())
    if total <= 0:
        raise SystemExit("NO_INITIAL_HITS")
    cluster_metrics = {}
    weights = {"rarity": 0.40, "uncertainty": 0.25, "diversity": 0.20, "size": 0.10, "structure": 0.05}
    freq = {bid: sum(values[bid]) / total for bid in ids}
    rarity = {bid: -math.log(max(freq[bid], 1e-12)) for bid in ids}
    uncertainty = {bid: (-freq[bid] * math.log(max(freq[bid], 1e-12))
                          - (1 - freq[bid]) * math.log(max(1 - freq[bid], 1e-12))) for bid in ids}
    for cluster in clusters["clusters"]:
        cid, members = cluster["cluster_id"], cluster["bin_ids"]
        variable = [bid for bid in members if len(set(values[bid])) > 1]
        correlations = [abs(pearson(values[a], values[b])) for i, a in enumerate(variable) for b in variable[i + 1:]]
        diversity = 1.0 - mean(correlations) if correlations else 1.0
        cross_ratio = sum(features[bid]["is_cross"] for bid in members) / len(members)
        structure = cross_ratio + (0.05 if cluster["has_residual"] else 0.0)
        cluster_metrics[cid] = {"bin_ids": members, "size": len(members),
            "variable_bin_count": len(variable), "rarity_raw": mean([rarity[b] for b in members]),
            "uncertainty_raw": mean([uncertainty[b] for b in members]), "diversity_raw": diversity,
            "size_raw": math.log1p(len(members)), "cross_ratio": cross_ratio,
            "residual_bonus": 0.05 if cluster["has_residual"] else 0.0, "structure_raw": structure}
    normalized = {metric: normalize({cid: data[metric + "_raw"] for cid, data in cluster_metrics.items()})
                  for metric in weights}
    for cid, data in cluster_metrics.items():
        data.update({metric + "_normalized": normalized[metric][cid] for metric in weights})
        data["static_weight"] = sum(weights[m] * normalized[m][cid] for m in weights)
        data["covered_bin_count_initial"] = sum(b in covered for b in data["bin_ids"])
        data["opportunity_initial"] = data["size"] - data["covered_bin_count_initial"]
        data["residual_information_initial"] = -math.log((data["covered_bin_count_initial"] + 1) / (data["size"] + 1))
    dynamic_raw = {cid: data["residual_information_initial"] for cid, data in cluster_metrics.items()}
    dynamic_norm = normalize(dynamic_raw)
    dynamic_prior = {cid: cluster_metrics[cid]["static_weight"] * dynamic_norm[cid]
                     if cluster_metrics[cid]["opportunity_initial"] else 0.0 for cid in cluster_metrics}
    dynamic_prior = normalize(dynamic_prior)
    for cid in cluster_metrics:
        cluster_metrics[cid]["dynamic_prior_initial"] = dynamic_prior[cid]
    pool = json.loads(args.test_pool.read_text(encoding="utf-8"))
    by_name = {x["name"]: x for x in pool["candidates"]}
    initial_runs, sequences = [], {}
    for row in status:
        item = row["item"]
        if row["return_code"] != "0":
            continue
        start = datetime.fromisoformat(row["started_utc"].replace("Z", "+00:00"))
        finish = datetime.fromisoformat(row["finished_utc"].replace("Z", "+00:00"))
        runtime = max(0.0, (finish - start).total_seconds())
        hit_ids = [bid for bid in ids if values[bid][items.index(item)] == 1]
        candidate = by_name[item]
        sequences[item] = {"test": item, "uvm_test_seq": candidate["uvm_test_seq"],
                           "build_mode": candidate["build_mode"]}
        initial_runs.append({"run_id": row["run_id"], "sequence": item, "hit_bin_ids": hit_ids,
                             "runtime_seconds": runtime})
    score = {"schema_version": SCHEMA, "manifest_schema": "opentitan-aon-timer-functional-4525-v1",
             "clusters_schema": clusters["schema_version"], "clusters_sha256": sha256(args.clusters / "clusters.json"),
             "features_sha256": sha256(args.clusters / "features.json"), "matrix_sha256": sha256(args.matrix),
             "bin_count": len(ids), "run_count": len(initial_runs), "covered_bin_count_initial": len(covered),
             "coverage_ratio_initial": len(covered) / len(ids), "weights": weights,
             "parameters": {"zero_frequency_floor": 1e-12, "residual_noise_bonus": 0.05,
                            "dynamic_prior": "mean-normalized static weight times residual information; saturated clusters have zero opportunity"},
             "clusters": cluster_metrics, "bin_metrics": {bid: {"mean_hit_count": sum(values[bid]) / len(items),
                "frequency": freq[bid], "rarity": rarity[bid], "uncertainty": uncertainty[bid],
                "cluster_id": clusters["bin_to_cluster"][bid], "initial_hit": int(bid in covered)} for bid in ids},
             "sanity": {"positive_residual_clusters": sum(v > 0 for v in dynamic_raw.values()),
                        "saturated_clusters": sum(v["opportunity_initial"] == 0 for v in cluster_metrics.values()),
                        "sum_static_weight": sum(v["static_weight"] for v in cluster_metrics.values()),
                        "sum_dynamic_prior_initial": sum(dynamic_prior.values())}}
    args.output.mkdir(parents=True)
    (args.output / "cluster_scores.json").write_text(json.dumps(score, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    inputs = {"schema_version": "aon-timer-scheduler-inputs-v1", "coverage_schema": "opentitan-aon-timer-functional-4525-v1",
              "bin_ids": ids, "clusters": {cid: {"bin_ids": data["bin_ids"], "static_weight": data["static_weight"]}
                                           for cid, data in cluster_metrics.items()},
              "sequences": sequences, "initial_runs": initial_runs, "initial_covered_bin_ids": sorted(covered)}
    (args.output / "scheduler_inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"clusters": len(cluster_metrics), "bins": len(ids), "initial_covered": len(covered), "runs": len(initial_runs)}, sort_keys=True))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--clusters", type=Path, required=True)
    p.add_argument("--matrix", type=Path, required=True)
    p.add_argument("--status", type=Path, required=True)
    p.add_argument("--test-pool", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    build(p.parse_args())


if __name__ == "__main__":
    main()

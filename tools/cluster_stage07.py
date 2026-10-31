#!/usr/bin/env python3
"""Build deterministic component-aware clusters for the frozen 4525-bin schema."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SCHEMA = "opentitan-aon-timer-stage07-clusters-v1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_component(source: str) -> str:
    parts = source.split("/")
    if parts[:3] == ["hw", "ip", "aon_timer"]:
        return "aon_timer"
    if parts[:3] == ["hw", "dv", "sv"] and len(parts) > 3:
        return parts[3]
    return "/".join(parts[:3]) if len(parts) >= 3 else "unknown"


def normalize(value: str) -> str:
    value = value.lower().replace("\\", " ")
    value = re.sub(r"0x[0-9a-f]+", " <hex> ", value)
    value = re.sub(r"\b\d+\b", " <num> ", value)
    return re.sub(r"[^a-z0-9<>]+", " ", value).strip()


def features_for(item: dict) -> dict:
    name = str(item["bin_name"])
    point = str(item["coverpoint_or_cross"])
    group = str(item["covergroup"])
    source = str(item["source_file"])
    literals = [int(v, 0) if v.lower().startswith("0x") else int(v)
                for v in re.findall(r"(?<![A-Za-z])(?:0x[0-9A-Fa-f]+|\d+)", name)]
    buckets = sorted({"zero" if abs(v) == 0 else "one" if abs(v) == 1 else
                      "small" if abs(v) <= 16 else "medium" if abs(v) <= 256 else "large"
                      for v in literals})
    cross = item["bin_type"] == "cross" or "cross" in point.lower() or " x " in name.lower()
    group_base = group.split("::SHAPE", 1)[0]
    normalized = normalize(" ".join((group.split("::", 1)[0], group_base, point, name)))
    tokens = set(normalized.split())
    tokens.update({"component:" + source_component(source),
                   "scope:" + str(item["coverage_scope"]),
                   "kind:cross" if cross else "kind:coverpoint",
                   "group:" + normalize(group_base), "point:" + normalize(point)})
    tokens.update("number_bucket:" + b for b in buckets)
    if not literals:
        tokens.add("numbers:none")
    structural = "cross" if cross else "coverpoint"
    if any(word in normalized for word in ("residual", "noise", "others", "default")):
        structural = "residual"
        tokens.add("structural:residual")
    else:
        tokens.add("structural:" + structural)
    return {"bin_id": item["id"], "component": source_component(source),
            "source_file": source, "source_line": item.get("source_line"),
            "covergroup": group, "covergroup_base": group_base,
            "coverpoint_or_cross": point, "bin_name": name,
            "bin_type": item["bin_type"], "coverage_scope": item["coverage_scope"],
            "is_cross": cross, "numeric_literals": literals,
            "numeric_buckets": buckets, "normalized_text": normalized,
            "tokens": sorted(tokens), "structural_type": structural}


def distance(left: dict, right: dict) -> float:
    a, b = set(left["tokens"]), set(right["tokens"])
    return 0.0 if not a | b else 1.0 - len(a & b) / len(a | b)


def dbscan(items: list[dict], eps: float, min_samples: int) -> tuple[list[list[int]], set[int]]:
    neighbors = {i: [j for j, candidate in enumerate(items) if distance(item, candidate) <= eps]
                 for i, item in enumerate(items)}
    core = {i for i, near in neighbors.items() if len(near) >= min_samples}
    clusters: list[list[int]] = []
    assigned: set[int] = set()
    for seed in range(len(items)):
        if seed not in core or seed in assigned:
            continue
        pending, members = [seed], set()
        while pending:
            current = pending.pop(0)
            if current in members:
                continue
            members.add(current)
            assigned.add(current)
            if current in core:
                pending.extend(i for i in neighbors[current] if i not in members)
        clusters.append(sorted(members))
    residual: set[int] = set()
    for index in range(len(items)):
        if index in assigned:
            continue
        candidates = [(min(distance(items[index], items[m]) for m in cluster), ci)
                      for ci, cluster in enumerate(clusters)
                      if min(distance(items[index], items[m]) for m in cluster) <= eps]
        if candidates:
            _, selected = min(candidates)
            clusters[selected].append(index)
            clusters[selected].sort()
            assigned.add(index)
        else:
            clusters.append([index])
            residual.add(index)
            assigned.add(index)
    return clusters, residual


def build(manifest_path: Path, output: Path, eps: float, min_samples: int, max_size: int) -> None:
    if output.exists():
        raise SystemExit("OUTPUT_EXISTS")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    eligible = [b for b in manifest["bins"] if b.get("eligible_for_instance_score")]
    if manifest["schema_version"] != "opentitan-aon-timer-functional-4525-v1" or len(eligible) != 4525:
        raise SystemExit("MANIFEST_SCHEMA_OR_DIMENSION_MISMATCH")
    features = [features_for(item) for item in eligible]
    partitions: dict[tuple[str, str, str], list[dict]] = {}
    for item in features:
        key = (item["component"], item["covergroup_base"], item["coverpoint_or_cross"])
        partitions.setdefault(key, []).append(item)
    cluster_members: list[tuple[str, list[str], bool]] = []
    partition_summary = []
    for key, items in sorted(partitions.items()):
        items.sort(key=lambda x: x["bin_id"])
        raw, residual = dbscan(items, eps, min_samples) if len(items) > max_size else ([list(range(len(items)))], set())
        final: list[list[int]] = []
        for members in raw:
            members.sort(key=lambda i: (0 if items[i]["numeric_literals"] else 1,
                                        items[i]["numeric_literals"], items[i]["bin_id"]))
            final.extend(members[i:i + max_size] for i in range(0, len(members), max_size))
        partition_summary.append({"component": key[0], "covergroup": key[1],
                                  "coverpoint_or_cross": key[2], "bin_count": len(items),
                                  "dbscan_clusters": len(raw), "final_clusters": len(final)})
        for members in final:
            ids = sorted(items[i]["bin_id"] for i in members)
            cluster_members.append((key[0], ids, any(i in residual for i in members)))
    cluster_members.sort(key=lambda x: (x[0], x[1][0]))
    clusters, mapping = [], {}
    by_id = {f["bin_id"]: f for f in features}
    for number, (component, ids, residual) in enumerate(cluster_members, 1):
        cid = f"c{number:04d}"
        for bid in ids:
            if bid in mapping:
                raise SystemExit("DUPLICATE_CLUSTER_BIN")
            mapping[bid] = cid
        clusters.append({"cluster_id": cid, "component": component, "bin_ids": ids, "size": len(ids),
                         "has_cross": any(by_id[bid]["is_cross"] for bid in ids),
                         "has_residual": residual or any(by_id[bid]["structural_type"] == "residual" for bid in ids),
                         "dbscan_noise_residual": residual})
    if set(mapping) != {f["bin_id"] for f in features}:
        raise SystemExit("CLUSTER_BIN_COVERAGE_MISMATCH")
    output.mkdir(parents=True)
    result = {"schema_version": SCHEMA, "manifest_schema": manifest["schema_version"],
              "manifest_sha256": sha256(manifest_path), "bin_count": len(features),
              "cluster_count": len(clusters), "parameters": {"distance": "Jaccard distance over normalized feature tokens",
              "eps": eps, "min_samples": min_samples, "max_cluster_size": max_size,
              "partition": "component + covergroup base + coverpoint/cross",
              "noise_rule": "nearest cluster within eps, otherwise singleton residual",
              "oversize_rule": "stable numeric-literal and bin-ID order, chunked at max size"},
              "partition_summary": partition_summary, "clusters": clusters, "bin_to_cluster": mapping}
    (output / "clusters.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "features.json").write_text(json.dumps({"schema_version": SCHEMA, "manifest_sha256": result["manifest_sha256"],
        "features": features}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    samples = []
    for component in sorted({f["component"] for f in features}):
        samples.append(next(f for f in features if f["component"] == component))
    for kind in ("coverpoint", "cross"):
        samples.append(next((f for f in features if f["structural_type"] == kind and f["bin_id"] not in {s["bin_id"] for s in samples}), features[0]))
    (output / "feature_review.json").write_text(json.dumps({"sample_bin_ids": [s["bin_id"] for s in samples],
        "features": samples, "partition_summary": partition_summary,
        "review_guidance": "Compare component, scope, covergroup, point/cross, literals and source line with the frozen manifest."}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--eps", type=float, default=0.60)
    p.add_argument("--min-samples", type=int, default=2)
    p.add_argument("--max-cluster-size", type=int, default=32)
    args = p.parse_args()
    build(args.manifest, args.output, args.eps, args.min_samples, args.max_cluster_size)
    print("STAGE07_CLUSTER_BUILD=PASS")


if __name__ == "__main__":
    main()

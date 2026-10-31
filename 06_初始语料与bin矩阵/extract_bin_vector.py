#!/usr/bin/env python3
"""Extract one Stage 06 4525-bin hit vector from per-test URG/XML evidence."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def load_freezer(path: Path):
    spec = importlib.util.spec_from_file_location("stage04_freezer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Stage 04 parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def need(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def extract(args: argparse.Namespace) -> None:
    fm = load_freezer(args.freezer)
    full_groups_text = args.full_groups.read_text(encoding="utf-8", errors="replace")
    full_text = args.full_grpinfo.read_text(encoding="utf-8", errors="replace")
    expanded_text = args.expanded_grpinfo.read_text(encoding="utf-8", errors="replace")
    totals, group_rows = fm.parse_urg_totals(full_groups_text)
    definitions, instance_map = fm.xml_metadata(args.cumulative, args.instance)
    instance_to_group = {name: value[0] for name, value in instance_map.items()}
    need(set(group_rows) == set(definitions), "URG group table and VCS XML group definitions differ")
    full = fm.parse_group_entities(full_text, set(group_rows), instance_to_group)
    expanded = fm.parse_expanded_entities(expanded_text, set(group_rows), instance_to_group, definitions)
    bins, _, _ = fm.build_bins(definitions, group_rows, full, expanded, instance_to_group)
    eligible = [item for item in bins if item["eligible_for_instance_score"]]
    need(len(bins) == 4533 and len(eligible) == 4525, "unexpected Stage 04 bin universe")

    hit_counts = {}
    for (group_name, instance_path), entity in full.items():
        for point, record in entity["variables"].items():
            for row in record["tables"]:
                if fm.is_covered_row(row):
                    key = (group_name, instance_path, "coverpoint", point, fm.clean_bin_name(str(row["name"])))
                    hit_counts[key] = row["count"]
        for cross, record in entity["crosses"].items():
            for row in record["tables"]:
                if fm.is_covered_row(row) and isinstance(row["name"], list):
                    name = " x ".join("{}={}".format(cp, fm.clean_bin_name(val))
                                       for cp, val in zip(record["coverpoints"], row["name"]))
                    hit_counts[(group_name, instance_path, "cross", cross, name)] = row["count"]

    for item in bins:
        key = (item["covergroup"], item["covergroup_instance_path"], item["bin_type"],
               item["coverpoint_or_cross"], item["bin_name"])
        item["_hit_count"] = hit_counts.get(key, 0)
    actual = {item["id"]: item for item in eligible}
    static = json.loads(args.static_manifest.read_text(encoding="utf-8"))
    need(static.get("schema_version") == "opentitan-aon-timer-functional-4525-v1", "manifest schema mismatch")
    expected = {item["id"]: item for item in static["bins"] if item["eligible_for_instance_score"]}
    need(set(actual) == set(expected), "per-test report bin IDs differ from Stage 04 manifest")
    rows = ["bin_id\thit\n"]
    hits = 0
    for bin_id in sorted(expected):
        hit = int(actual[bin_id]["_hit_count"] > 0)
        hits += hit
        rows.append(f"{bin_id}\t{hit}\n")
    args.output.mkdir(parents=True, exist_ok=False)
    vector = args.output / "bin_vector.tsv"
    vector.write_text("".join(rows), encoding="utf-8")
    summary = {
        "schema_version": "opentitan-aon-timer-bin-vector-v1",
        "manifest_schema": static["schema_version"],
        "item": args.item,
        "seed": args.seed,
        "expected_bins": len(expected),
        "hit_bins": hits,
        "coverage_percent": round(100.0 * hits / len(expected), 6),
        "vector_sha256": sha256(vector),
        "input_sha256": {p.name: sha256(p) for p in (args.full_groups, args.full_grpinfo, args.expanded_grpinfo, args.cumulative, args.instance)},
    }
    (args.output / "vector_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "SHA256SUMS").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in sorted(args.output.iterdir())), encoding="utf-8")
    print(json.dumps({"verification": "PASS", "item": args.item, "expected_bins": len(expected), "hit_bins": hits,
                      "coverage_percent": summary["coverage_percent"], "vector_sha256": summary["vector_sha256"]}, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--freezer", type=Path, required=True)
    p.add_argument("--static-manifest", type=Path, required=True)
    p.add_argument("--full-groups", type=Path, required=True)
    p.add_argument("--full-grpinfo", type=Path, required=True)
    p.add_argument("--expanded-grpinfo", type=Path, required=True)
    p.add_argument("--cumulative", type=Path, required=True)
    p.add_argument("--instance", type=Path, required=True)
    p.add_argument("--item", required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    try:
        extract(p.parse_args())
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit("STAGE06_VECTOR_FAILED: " + str(exc))


if __name__ == "__main__":
    main()

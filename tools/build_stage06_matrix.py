#!/usr/bin/env python3
"""Build the public Stage 06 bin-by-run matrix from extracted vectors."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_tsv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows({k: row.get(k, "") for k in fields} for row in rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--status", type=Path, required=True)
    p.add_argument("--vectors-root", type=Path, required=True,
                   help="Directory containing <run_id>/public_vectors/<item>/")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise SystemExit("OUTPUT_EXISTS")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    bins = [b for b in manifest["bins"] if b.get("eligible_for_instance_score")]
    if len(manifest["bins"]) != 4533 or len(bins) != 4525:
        raise SystemExit("MANIFEST_DIMENSION_MISMATCH")
    bin_ids = sorted(b["id"] for b in bins)
    status = read_tsv(args.status)
    if len(status) != 17 or len({r["item"] for r in status}) != 17:
        raise SystemExit("STATUS_DIMENSION_MISMATCH")
    status_items = [r["item"] for r in status]
    out_vectors = args.output / "vectors"
    out_vectors.mkdir(parents=True)
    copied: list[dict[str, object]] = []
    values_by_item: dict[str, dict[str, int]] = {}
    for row in status:
        item, run_id = row["item"], row["run_id"]
        if row["return_code"] != "0":
            copied.append({"item": item, "run_id": run_id, "return_code": row["return_code"],
                           "vector": ""})
            continue
        src = args.vectors_root / run_id / "public_vectors" / item
        vector = src / "bin_vector.tsv"
        summary = src / "vector_summary.json"
        if not vector.is_file() or not summary.is_file():
            raise SystemExit(f"MISSING_VECTOR_{item}")
        dst = out_vectors / item
        shutil.copytree(src, dst)
        values: dict[str, int] = {}
        for vrow in read_tsv(vector):
            if vrow["bin_id"] in values or vrow["bin_id"] not in bin_ids:
                raise SystemExit(f"BAD_VECTOR_BIN_{item}")
            if vrow["hit"] not in {"0", "1"}:
                raise SystemExit(f"BAD_VECTOR_VALUE_{item}")
            values[vrow["bin_id"]] = int(vrow["hit"])
        if sorted(values) != bin_ids:
            raise SystemExit(f"VECTOR_BIN_SET_MISMATCH_{item}")
        values_by_item[item] = values
        copied.append({"item": item, "run_id": run_id, "return_code": row["return_code"],
                       "vector": (Path("vectors") / item / "bin_vector.tsv").as_posix()})

    args.output.mkdir(exist_ok=True)
    shutil.copy2(args.manifest, args.output / "coverage_manifest.v1.json")
    shutil.copy2(args.status, args.output / "status.tsv")
    successful = [item for item in status_items if item in values_by_item]
    write_tsv(args.output / "run_summary.tsv",
              ["item", "run_id", "return_code", "vector"], copied)
    matrix_rows = []
    union_rows = []
    for bid in bin_ids:
        row: dict[str, object] = {"bin_id": bid}
        count = 0
        for item in status_items:
            value = values_by_item.get(item, {}).get(bid, "NA")
            row[item] = value
            if value == 1:
                count += 1
        matrix_rows.append(row)
        union_rows.append({"bin_id": bid, "hit_count": count,
                           "hit_any": int(count > 0),
                           "successful_run_count": len(successful),
                           "frequency": round(count / len(successful), 12) if successful else 0.0})
    write_tsv(args.output / "bin_by_run.tsv", ["bin_id", *status_items], matrix_rows)
    write_tsv(args.output / "initial_union_and_frequency.tsv",
              ["bin_id", "hit_count", "hit_any", "successful_run_count", "frequency"], union_rows)
    meta = {
        "schema_version": "opentitan-aon-timer-initial-corpus-matrix-v1",
        "manifest_schema": manifest["schema_version"],
        "manifest_bins_total": len(manifest["bins"]),
        "eligible_bins": len(bin_ids),
        "candidate_count": len(status),
        "successful_run_count": len(successful),
        "failed_run_count": len(status) - len(successful),
        "successful_items": successful,
        "failed_items": [r["item"] for r in status if r["item"] not in values_by_item],
        "seed": 42,
        "run_order": status_items,
        "vector_sha256": {item: sha256(out_vectors / item / "bin_vector.tsv") for item in successful},
    }
    (args.output / "matrix_summary.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(p for p in args.output.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (args.output / "SHA256SUMS").write_text("".join(f"{sha256(f)}  {f.relative_to(args.output).as_posix()}\n" for f in files), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

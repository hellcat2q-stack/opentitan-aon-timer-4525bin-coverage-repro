#!/usr/bin/env python3
"""Verify the public Stage 05 test inventory and initial plan."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

EXPECTED = {
    "aon_timer_smoke", "aon_timer_prescaler", "aon_timer_jump",
    "aon_timer_csr_hw_reset", "aon_timer_csr_rw", "aon_timer_csr_bit_bash",
    "aon_timer_csr_aliasing", "aon_timer_same_csr_outstanding",
    "aon_timer_csr_mem_rw_with_rand_reset", "aon_timer_mem_walk",
    "aon_timer_mem_partial_access", "aon_timer_intr_test", "aon_timer_tl_errors",
    "aon_timer_tl_intg_err", "aon_timer_sec_cm", "aon_timer_stress_all",
    "aon_timer_stress_all_with_rand_reset",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def need(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("STAGE05_VERIFY_FAILED: " + message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True,
                        help="clean source snapshot at the locked OpenTitan revision")
    parser.add_argument("--paper", type=Path,
                        help="optional original paper PDF; when supplied, verify its recorded SHA-256")
    args = parser.parse_args()
    inventory_path = args.bundle / "test_pool.v1.json"
    plan_path = args.bundle / "initial_plan.v1.json"
    tsv_path = args.bundle / "test_pool.tsv"
    sums_path = args.bundle / "SHA256SUMS"
    for path in (inventory_path, plan_path, tsv_path, sums_path):
        need(path.is_file(), "missing " + path.name)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    candidates = inventory.get("candidates", [])
    names = {item.get("name") for item in candidates}
    need(inventory.get("schema_version") == "opentitan-aon-timer-test-pool-v1", "inventory schema mismatch")
    need(inventory.get("manifest_schema") == "opentitan-aon-timer-functional-4525-v1", "manifest schema mismatch")
    need(inventory.get("source", {}).get("open_titan_commit") == "9f20940d494a223cc950a5b98f748fb28109d458",
         "source revision mismatch")
    need(inventory.get("source", {}).get("source_tree_sha1") == "4229b5d334cf7c02996856ddbdf625989b5a6b58",
         "source tree mismatch")
    need(inventory.get("source", {}).get("source_archive_sha256") == "8db9ef1c8a125d57b95f3ee294742ac8fdb14aeec0d2ac950efc3a99c22d65a3",
         "source archive hash mismatch")
    need(len(candidates) == 17 and names == EXPECTED, "candidate set mismatch")
    need(len({item.get("id") for item in candidates}) == 17, "test IDs are not unique")
    need(inventory.get("registered_sequences") == ["aon_timer_base_vseq", "aon_timer_smoke_vseq",
         "aon_timer_prescaler_vseq", "aon_timer_jump_vseq", "aon_timer_common_vseq",
         "aon_timer_stress_all_vseq"], "registered sequence inventory mismatch")
    hashed_inputs = set(inventory.get("source_file_sha256", {}))
    candidate_sources = {path for item in candidates for path in item.get("source_files", [])}
    need(candidate_sources <= hashed_inputs, "a candidate source file is missing from the hash contract")
    for relative, expected in inventory["source_file_sha256"].items():
        path = args.source_root / relative
        need(path.is_file(), "source snapshot is missing " + relative)
        need(path.stat().st_size == expected.get("bytes"), "source byte-count mismatch for " + relative)
        need(sha256(path) == expected.get("sha256"), "source SHA-256 mismatch for " + relative)
    for path in (
        "hw/dv/tools/dvsim/common_modes.hjson",
        "hw/ip/aon_timer/data/aon_timer_sec_cm_testplan.hjson",
        "hw/dv/tools/dvsim/testplans/tl_device_access_types_wo_intg_testplan.hjson",
        "hw/dv/sv/cip_lib/seq_lib/cip_base_vseq.sv",
        "hw/dv/sv/dv_lib/dv_base_vseq.sv",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_smoke_vseq.sv",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_prescaler_vseq.sv",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_jump_vseq.sv",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_stress_all_vseq.sv",
    ):
        need(path in hashed_inputs, "missing hash input: " + path)
    templates = inventory.get("shared_test_templates", {})
    need(sum(len(names) for names in templates.values()) == 14, "shared test template count mismatch")
    need(sum(item.get("category") == "aon_timer_native" for item in candidates) == 3, "native test count mismatch")
    need(sum(item.get("build_mode") == "cover_reg_top" for item in candidates) == 11, "cover_reg_top count mismatch")
    simulation = inventory.get("simulation_contract", {})
    need(simulation.get("simulation_mode") == "cov" and "+en_cov=1" in simulation.get("coverage_mode_plusargs", []),
         "coverage mode contract mismatch")
    need("+UVM_NO_RELNOTES" in simulation.get("common_run_opts", [])
         and "+cdc_instrumentation_enabled=1" in simulation.get("common_run_opts", []),
         "common run options mismatch")
    need(all(item.get("coverage_candidate") is True for item in candidates), "candidate marked unavailable")
    need(all(item.get("uvm_test") == "aon_timer_base_test" for item in candidates), "unexpected UVM test")
    need(plan.get("status") == "REGISTERED_PLAN_NOT_EXECUTED", "plan status must remain unexecuted")
    initial = plan.get("initial_corpus", {})
    need(initial.get("planned_runs") == 17 and initial.get("parallelism") == 1, "initial plan size/parallelism mismatch")
    need(initial.get("scheduler_seed") == 42 and "seed 42" in initial.get("seed_policy", ""), "initial seed policy mismatch")
    paper = plan.get("paper_parameters", {})
    need(paper.get("logical_batch_size") == 10 and paper.get("logical_batches") == 100
         and paper.get("submitted_simulations") == 1000 and paper.get("parallel_workers") == 10,
         "paper budget parameters mismatch")
    need(paper.get("random_seed_numeric_value_disclosed") is False, "paper seed disclosure must remain explicit")
    paper_record = inventory.get("paper", {})
    paper_hash_verified = False
    if args.paper:
        need(args.paper.is_file(), "paper PDF does not exist")
        need(args.paper.name == paper_record.get("file"), "paper filename mismatch")
        need(sha256(args.paper) == paper_record.get("sha256"), "paper SHA-256 mismatch")
        paper_hash_verified = True
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        need(sha256(args.bundle / name) == expected, "SHA256SUMS mismatch for " + name)
    for path in args.bundle.iterdir():
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            need(not re.search(r"(?:[A-Za-z]:\\|/home/|/root/|/tmp/|\\\\[A-Za-z0-9_.-]+\\\\)", text),
                 "private path found in " + path.name)
    rows = tsv_path.read_text(encoding="utf-8").splitlines()
    need(len(rows) == 18, "TSV must contain header plus 17 rows")
    need(rows[0].startswith("id\tname\tcategory\ttestpoints"), "TSV header mismatch")
    tsv_candidates = [line.split("\t", 9) for line in rows[1:]]
    need(all(len(row) == 10 for row in tsv_candidates), "malformed TSV candidate row")
    tsv_by_name = {row[1]: row for row in tsv_candidates}
    need(set(tsv_by_name) == names, "TSV candidate-name set differs from JSON inventory")
    for item in candidates:
        row = tsv_by_name[item["name"]]
        need(row[0] == item["id"] and row[2] == item["category"],
             "TSV identity/category differs for " + item["name"])
        need(row[4] == item["stage"] and row[5] == item["uvm_test_seq"],
             "TSV stage/sequence differs for " + item["name"])
    print(json.dumps({"verification": "PASS", "candidate_count": len(candidates),
                      "native_tests": 3, "cover_reg_top_tests": 11,
                      "source_files_hashed": len(hashed_inputs),
                      "source_files_independently_verified": len(hashed_inputs),
                      "paper_hash_verified": paper_hash_verified,
                      "planned_initial_runs": initial["planned_runs"],
                      "paper_budget": {"submitted_simulations": paper["submitted_simulations"],
                                       "parallel_workers": paper["parallel_workers"]},
                      "paper_numeric_seed_disclosed": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

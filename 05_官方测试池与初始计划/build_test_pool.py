#!/usr/bin/env python3
"""Build the Stage 05 official test inventory from a locked source tree."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "opentitan-aon-timer-test-pool-v1"
TARGET_REVISION = "9f20940d494a223cc950a5b98f748fb28109d458"
TARGET_TREE = "4229b5d334cf7c02996856ddbdf625989b5a6b58"
SOURCE_ARCHIVE_SHA256 = "8db9ef1c8a125d57b95f3ee294742ac8fdb14aeec0d2ac950efc3a99c22d65a3"
MANIFEST_SCHEMA = "opentitan-aon-timer-functional-4525-v1"
DEFAULT_RESEED = 50
INHERITED_RUN_OPTS = ["+UVM_NO_RELNOTES", "+UVM_VERBOSITY=UVM_LOW", "+cdc_instrumentation_enabled=1"]
COMMON_TEST_TEMPLATES = {
    "hw/dv/tools/dvsim/tests/csr_tests.hjson": [
        "{name}_csr_hw_reset", "{name}_csr_rw", "{name}_csr_bit_bash", "{name}_csr_aliasing",
        "{name}_same_csr_outstanding", "{name}_csr_mem_rw_with_rand_reset",
    ],
    "hw/dv/tools/dvsim/tests/mem_tests.hjson": ["{name}_mem_walk", "{name}_mem_partial_access"],
    "hw/dv/tools/dvsim/tests/intr_test.hjson": ["{name}_intr_test"],
    "hw/dv/tools/dvsim/tests/tl_access_tests.hjson": ["{name}_tl_errors", "{name}_tl_intg_err"],
    "hw/dv/tools/dvsim/tests/sec_cm_tests.hjson": ["{name}_sec_cm"],
    "hw/dv/tools/dvsim/tests/stress_tests.hjson": ["{name}_stress_all_with_rand_reset"],
    "hw/dv/tools/dvsim/tests/stress_all_test.hjson": ["{name}_stress_all"],
}


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(root: Path, relative: str) -> str:
    path = root / relative
    need(path.is_file(), "missing locked-source file: " + relative)
    return path.read_text(encoding="utf-8", errors="replace")


def source_hashes(root: Path, relatives: list[str]) -> dict[str, dict[str, object]]:
    out = {}
    for relative in relatives:
        path = root / relative
        need(path.is_file(), "missing locked-source file: " + relative)
        out[relative] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return out


def stable_id(name: str) -> str:
    value = f"{SCHEMA}:{TARGET_REVISION}:{name}".encode("utf-8")
    return "test_" + hashlib.sha256(value).hexdigest()[:20]


def candidate(name: str, category: str, testpoint: str | list[str], stage: str,
              sequence: str, source_files: list[str], origin: str,
              *, build_mode: str | None = None, run_opts: list[str] | None = None,
              reseed: int = DEFAULT_RESEED, reseed_origin: str = "sim_cfg_default",
              run_timeout_mins: int | None = None) -> dict:
    return {
        "id": stable_id(name),
        "name": name,
        "category": category,
        "testpoints": [testpoint] if isinstance(testpoint, str) else testpoint,
        "stage": stage,
        "uvm_test": "aon_timer_base_test",
        "uvm_test_seq": sequence,
        "build_mode": build_mode or "default",
        "run_opts": INHERITED_RUN_OPTS + (run_opts or []),
        "reseed": reseed,
        "reseed_origin": reseed_origin,
        "run_timeout_mins": run_timeout_mins,
        "source_files": source_files,
        "configuration_origin": origin,
        "coverage_candidate": True,
        "schema_gate": "compare coverage-definition signature with Stage 04 before merge",
    }


def build_inventory(root: Path) -> tuple[list[dict], list[str], list[str]]:
    cfg_rel = "hw/ip/aon_timer/dv/aon_timer_sim_cfg.hjson"
    cfg = read(root, cfg_rel)
    direct = re.findall(r"(?m)^\s*name:\s+(aon_timer_(?:smoke|prescaler|jump))\s*$", cfg)
    need(direct == ["aon_timer_smoke", "aon_timer_prescaler", "aon_timer_jump"],
         "unexpected direct AON Timer test list: " + repr(direct))
    for relative, templates in COMMON_TEST_TEMPLATES.items():
        text = read(root, relative)
        for template in templates:
            need('name: "' + template + '"' in text,
                 "shared test template is missing from {}: {}".format(relative, template))
    sequence_list = read(root, "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_vseq_list.sv")
    sequence_files = re.findall(r'`include "(aon_timer_[a-z_]+_vseq)\.sv"', sequence_list)
    need(sequence_files == ["aon_timer_base_vseq", "aon_timer_smoke_vseq", "aon_timer_prescaler_vseq",
                            "aon_timer_jump_vseq", "aon_timer_common_vseq", "aon_timer_stress_all_vseq"],
         "unexpected registered sequence list: " + repr(sequence_files))
    required = [
        cfg_rel,
        "hw/ip/aon_timer/data/aon_timer_testplan.hjson",
        "hw/ip/aon_timer/data/aon_timer_sec_cm_testplan.hjson",
        "hw/ip/aon_timer/data/aon_timer.hjson",
        "hw/ip/aon_timer/dv/aon_timer_sim.core",
        "hw/ip/aon_timer/dv/env/aon_timer_env.core",
        "hw/ip/aon_timer/dv/tests/aon_timer_test.core",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_smoke_vseq.sv",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_prescaler_vseq.sv",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_jump_vseq.sv",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_stress_all_vseq.sv",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_base_vseq.sv",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_common_vseq.sv",
        "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_vseq_list.sv",
        "hw/dv/sv/cip_lib/seq_lib/cip_base_vseq.sv",
        "hw/dv/sv/dv_lib/dv_base_vseq.sv",
        "hw/dv/sv/cip_lib/seq_lib/cip_base_vseq__tl_errors.svh",
        "hw/dv/sv/cip_lib/seq_lib/cip_base_vseq__sec_cm_fi.svh",
        "hw/dv/tools/dvsim/common_modes.hjson",
        "hw/dv/tools/dvsim/common_sim_cfg.hjson",
        "hw/dv/tools/dvsim/tests/csr_tests.hjson",
        "hw/dv/tools/dvsim/tests/mem_tests.hjson",
        "hw/dv/tools/dvsim/tests/intr_test.hjson",
        "hw/dv/tools/dvsim/tests/tl_access_tests.hjson",
        "hw/dv/tools/dvsim/tests/sec_cm_tests.hjson",
        "hw/dv/tools/dvsim/tests/stress_tests.hjson",
        "hw/dv/tools/dvsim/tests/stress_all_test.hjson",
        "hw/dv/tools/dvsim/testplans/csr_testplan.hjson",
        "hw/dv/tools/dvsim/testplans/mem_testplan.hjson",
        "hw/dv/tools/dvsim/testplans/intr_test_testplan.hjson",
        "hw/dv/tools/dvsim/testplans/tl_device_access_types_testplan.hjson",
        "hw/dv/tools/dvsim/testplans/tl_device_access_types_wo_intg_testplan.hjson",
        "hw/dv/tools/dvsim/testplans/stress_all_with_reset_testplan.hjson",
    ]
    candidates = [
        candidate("aon_timer_smoke", "aon_timer_native", "smoke", "V1",
                  "aon_timer_smoke_vseq", [cfg_rel, "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_smoke_vseq.sv"], cfg_rel),
        candidate("aon_timer_prescaler", "aon_timer_native", "prescaler", "V2",
                  "aon_timer_prescaler_vseq", [cfg_rel, "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_prescaler_vseq.sv"], cfg_rel),
        candidate("aon_timer_jump", "aon_timer_native", "jump", "V2",
                  "aon_timer_jump_vseq", [cfg_rel, "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_jump_vseq.sv"], cfg_rel),
        candidate("aon_timer_csr_hw_reset", "cip_csr", ["csr_hw_reset", "tl_d_outstanding_access", "tl_d_partial_access"], "V1", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/csr_tests.hjson"], "csr_tests.hjson", build_mode="cover_reg_top",
                  run_opts=["+csr_hw_reset", "+en_scb=0"], reseed=5, reseed_origin="csr_tests.hjson"),
        candidate("aon_timer_csr_rw", "cip_csr", ["csr_rw", "regwen_csr_and_corresponding_lockable_csr", "tl_d_outstanding_access", "tl_d_partial_access"], "V1", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/csr_tests.hjson"], "csr_tests.hjson", build_mode="cover_reg_top",
                  run_opts=["+csr_rw", "+en_scb=0"], reseed=20, reseed_origin="csr_tests.hjson"),
        candidate("aon_timer_csr_bit_bash", "cip_csr", "csr_bit_bash", "V1", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/csr_tests.hjson"], "csr_tests.hjson", build_mode="cover_reg_top",
                  run_opts=["+csr_bit_bash", "+en_scb=0"], reseed=5, reseed_origin="csr_tests.hjson"),
        candidate("aon_timer_csr_aliasing", "cip_csr", ["csr_aliasing", "regwen_csr_and_corresponding_lockable_csr", "tl_d_outstanding_access", "tl_d_partial_access"], "V1", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/csr_tests.hjson"], "csr_tests.hjson", build_mode="cover_reg_top",
                  run_opts=["+csr_aliasing", "+en_scb=0"], reseed=5, reseed_origin="csr_tests.hjson"),
        candidate("aon_timer_same_csr_outstanding", "cip_csr", ["tl_d_outstanding_access", "tl_d_partial_access"], "V2", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/csr_tests.hjson", "hw/dv/tools/dvsim/testplans/tl_device_access_types_testplan.hjson"],
                  "csr_tests.hjson", build_mode="cover_reg_top", run_opts=["+run_same_csr_outstanding", "+en_scb=0"], reseed=20, reseed_origin="csr_tests.hjson"),
        candidate("aon_timer_csr_mem_rw_with_rand_reset", "cip_csr", "csr_mem_rw_with_rand_reset", "V1", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/csr_tests.hjson"], "csr_tests.hjson", build_mode="cover_reg_top",
                  run_opts=["+run_csr_mem_rw_with_rand_reset", "+test_timeout_ns=10000000000", "+en_scb=0"], reseed=20, reseed_origin="csr_tests.hjson"),
        candidate("aon_timer_mem_walk", "cip_memory", "mem_walk", "V1", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/mem_tests.hjson"], "mem_tests.hjson", build_mode="cover_reg_top",
                  run_opts=["+csr_mem_walk", "+en_scb=0"], reseed=5, reseed_origin="mem_tests.hjson"),
        candidate("aon_timer_mem_partial_access", "cip_memory", "mem_partial_access", "V1", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/mem_tests.hjson"], "mem_tests.hjson", build_mode="cover_reg_top",
                  run_opts=["+run_mem_partial_access", "+en_scb=0"], reseed=5, reseed_origin="mem_tests.hjson"),
        candidate("aon_timer_intr_test", "cip_interrupt", "intr_test", "V2", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/intr_test.hjson"], "intr_test.hjson", build_mode="cover_reg_top",
                  run_opts=["+run_intr_test"], reseed=50, reseed_origin="intr_test.hjson"),
        candidate("aon_timer_tl_errors", "tl_error", ["tl_d_oob_addr_access", "tl_d_illegal_access"], "V2", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/tl_access_tests.hjson", "hw/dv/tools/dvsim/testplans/tl_device_access_types_testplan.hjson"],
                  "tl_access_tests.hjson", build_mode="cover_reg_top", run_opts=["+run_tl_errors"], reseed=20, reseed_origin="tl_access_tests.hjson"),
        candidate("aon_timer_tl_intg_err", "tl_error", ["tl_intg_err", "sec_cm_bus_integrity"], "V2S", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/tl_access_tests.hjson"], "tl_access_tests.hjson", build_mode="cover_reg_top",
                  run_opts=["+run_tl_intg_err", "+en_scb=0"], reseed=20, reseed_origin="tl_access_tests.hjson"),
        candidate("aon_timer_sec_cm", "security_countermeasure", "tl_intg_err", "V2S", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/sec_cm_tests.hjson", "hw/dv/tools/dvsim/testplans/tl_device_access_types_testplan.hjson"],
                  "sec_cm_tests.hjson", run_opts=["+run_sec_cm_fi", "+en_scb=0"], reseed=5, reseed_origin="sec_cm_tests.hjson"),
        candidate("aon_timer_stress_all", "stress", "stress_all", "V2", "aon_timer_stress_all_vseq",
                  ["hw/dv/tools/dvsim/tests/stress_all_test.hjson", "hw/ip/aon_timer/dv/env/seq_lib/aon_timer_stress_all_vseq.sv"],
                  "stress_all_test.hjson", run_opts=["+test_timeout_ns=10000000000"], run_timeout_mins=180),
        candidate("aon_timer_stress_all_with_rand_reset", "stress", "stress_all_with_rand_reset", "V3", "aon_timer_common_vseq",
                  ["hw/dv/tools/dvsim/tests/stress_tests.hjson", "hw/dv/tools/dvsim/testplans/stress_all_with_reset_testplan.hjson"],
                  "stress_tests.hjson", run_opts=["+run_stress_all_with_rand_reset", "+test_timeout_ns=10000000000",
                                                   "+stress_seq=aon_timer_stress_all_vseq"], run_timeout_mins=180),
    ]
    need(len(candidates) == 17, "expected 17 candidates")
    need(len({item["name"] for item in candidates}) == len(candidates), "duplicate test name")
    candidate_sources = {source for item in candidates for source in item["source_files"]}
    need(candidate_sources <= set(required),
         "candidate source files are not all covered by input hashes: " + repr(sorted(candidate_sources - set(required))))
    for relative in required:
        read(root, relative)
    return candidates, required, sequence_files


def make(args: argparse.Namespace) -> None:
    candidates, required, sequence_files = build_inventory(args.source_root)
    hashes = source_hashes(args.source_root, required)
    paper_hash = sha256(args.paper) if args.paper else None
    inventory = {
        "schema_version": SCHEMA,
        "source": {"open_titan_commit": TARGET_REVISION, "source_tree_sha1": TARGET_TREE,
                   "source_archive_sha256": SOURCE_ARCHIVE_SHA256},
        "manifest_schema": MANIFEST_SCHEMA,
        "simulation_contract": {
            "tool": "VCS P-2019.06-SP1",
            "simulation_mode": "cov",
            "coverage_mode_plusargs": ["+en_cov=1"],
            "common_run_opts": INHERITED_RUN_OPTS,
            "ip_build_modes_declared": [],
            "shared_build_mode_used_by_imported_tests": "cover_reg_top",
            "default_reseed": DEFAULT_RESEED,
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
        "registered_sequences": sequence_files,
        "shared_test_templates": COMMON_TEST_TEMPLATES,
        "source_file_sha256": hashes,
        "paper": {
            "file": args.paper.name if args.paper else None,
            "sha256": paper_hash,
            "exact_aon_timer_regression_pool_disclosed": False,
            "note": "The paper describes an accessible regression subset but does not list exact test job names; names here come from the locked OpenTitan revision.",
        },
    }
    plan = {
        "schema_version": "opentitan-aon-timer-initial-plan-v1",
        "test_pool_schema": SCHEMA,
        "manifest_schema": MANIFEST_SCHEMA,
        "status": "REGISTERED_PLAN_NOT_EXECUTED",
        "candidate_count": len(candidates),
        "initial_corpus": {
            "selection": "one coverage-enabled run for every candidate job",
            "planned_runs": len(candidates),
            "seed_policy": "fixed simulation seed 42 for each initial candidate run",
            "scheduler_seed": 42,
            "parallelism": 1,
            "reseed": "one run per candidate in Stage 06; official per-test reseed defaults remain recorded in the inventory",
            "purpose": "establish candidate-to-bin reachability before adaptive scheduling",
        },
        "paper_parameters": {
            "logical_batch_size": 10,
            "logical_batches": 100,
            "submitted_simulations": 1000,
            "parallel_workers": 10,
            "random_seed_numeric_value_disclosed": False,
            "same_initial_corpus_for_all_methods": True,
            "source_note": "Values transcribed from the user-provided IM-1175.pdf; the exact initial corpus and numeric paper seed are not specified.",
        },
        "gates_before_stage06": [
            "Run the initial corpus with the Stage 04 source/config/tool contract.",
            "Compare coverage-definition signatures for default and cover_reg_top build modes before merging reports.",
            "If a build mode changes the manifest, assign a new manifest schema and do not mix its matrix columns.",
            "Record failed runs and simulator seeds; do not silently retry into the corpus.",
        ],
    }
    if args.output_dir.exists():
        raise FileExistsError("Refusing to overwrite output: " + str(args.output_dir))
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "test_pool.v1.json").write_text(json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "initial_plan.v1.json").write_text(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "test_pool.tsv").open("w", encoding="utf-8", newline="") as handle:
        handle.write("id\tname\tcategory\ttestpoints\tstage\tuvm_test_seq\tbuild_mode\treseed\trun_timeout_mins\trun_opts\n")
        for item in candidates:
            timeout = "" if item["run_timeout_mins"] is None else str(item["run_timeout_mins"])
            handle.write("\t".join([item["id"], item["name"], item["category"], ";".join(item["testpoints"]), item["stage"],
                                    item["uvm_test_seq"], item["build_mode"], str(item["reseed"]), timeout,
                                    ",".join(item["run_opts"])]) + "\n")
    hashes = []
    for path in sorted(args.output_dir.iterdir()):
        hashes.append(f"{sha256(path)}  {path.name}\n")
    (args.output_dir / "SHA256SUMS").write_text("".join(hashes), encoding="utf-8")
    print(json.dumps({"verification": "PASS", "schema_version": SCHEMA,
                      "candidate_count": len(candidates), "planned_initial_runs": len(candidates),
                      "source_files_hashed": len(required), "paper_seed_numeric_value_disclosed": False},
                     ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--paper", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    try:
        make(parser.parse_args())
    except (ValueError, OSError) as exc:
        print("STAGE05_BUILD_FAILED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()

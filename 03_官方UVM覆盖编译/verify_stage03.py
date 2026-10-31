#!/usr/bin/env python3
"""Build and verify a public, path-sanitized Stage 03 evidence bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

GROUPS = [
    "aon_timer_env_pkg::aon_timer_env_cov::timer_cfg_cg",
    "aon_timer_env_pkg::aon_timer_env_cov::wake_up_timer_thold_hit_cg",
    "aon_timer_env_pkg::aon_timer_env_cov::watchdog_timer_bite_thold_hit_cg",
    "aon_timer_env_pkg::aon_timer_env_cov::watchdog_timer_bark_thold_hit_cg",
]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk.replace(b"\r\n", b"\n"))
    return h.hexdigest()

def kv(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            out[key] = value
    return out

def collect(raw: Path, out: Path) -> None:
    required = ["run_manifest.txt", "command.txt", "compatibility_patch.txt",
                "source_copy_verification.json", "input_sha256.txt", "return_code.txt",
                "dvsim.log", "run.log", "groups.txt", "dashboard.txt", "cov_report.log"]
    if out.exists():
        raise SystemExit("refusing to overwrite an existing evidence bundle")
    for name in required:
        if not (raw / name).is_file():
            raise SystemExit(f"missing raw evidence: {name}")
    if (raw / "return_code.txt").read_text().strip() != "0":
        raise SystemExit("DVSim did not return zero")
    manifest = kv(raw / "run_manifest.txt")
    source = json.loads((raw / "source_copy_verification.json").read_text())
    log = (raw / "dvsim.log").read_text(errors="replace")
    phase_re = re.compile(r"\[\s*(build|run|cov_merge|cov_report)\s*\].*?\[Q:\s*\d+,\s*D:\s*\d+,\s*P:\s*(\d+),\s*F:\s*(\d+),\s*K:\s*\d+,\s*T:\s*(\d+)\]")
    phases = {}
    for stage, passed, failed, total in phase_re.findall(log):
        phases[stage] = [int(passed), int(failed), int(total)]
    if set(phases) != {"build", "run", "cov_merge", "cov_report"} or any(v != [1, 0, 1] for v in phases.values()):
        raise SystemExit(f"invalid DVSim phase status: {phases}")
    run = (raw / "run.log").read_text(errors="replace")
    if not re.search(r"^UVM_ERROR\s*:\s*0\s*$", run, re.M) or not re.search(r"^UVM_FATAL\s*:\s*0\s*$", run, re.M) or "TEST PASSED CHECKS" not in run:
        raise SystemExit("UVM smoke evidence is not clean")
    groups = (raw / "groups.txt").read_text(errors="replace")
    if any(group not in groups for group in GROUPS):
        raise SystemExit("URG report is missing an AON Timer covergroup")
    test_count = re.search(r"^Number of tests:\s*(\d+)$", (raw / "dashboard.txt").read_text(), re.M)
    group_count = re.search(r"^Total groups in report:\s*(\d+)$", groups, re.M)
    if not test_count or not group_count or "Report directory generated" not in (raw / "cov_report.log").read_text(errors="replace"):
        raise SystemExit("URG report summary is incomplete")
    out.mkdir(parents=True)
    for name in ["run_manifest.txt", "command.txt", "compatibility_patch.txt", "source_copy_verification.json"]:
        (out / name).write_bytes((raw / name).read_bytes())
    normalized_groups = "\n".join(line.rstrip() for line in groups.splitlines()).rstrip() + "\n"
    (out / "groups.txt").write_text(normalized_groups, encoding="utf-8")
    hashes = []
    for line in (raw / "input_sha256.txt").read_text().splitlines():
        digest, _, path = line.partition("  ")
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or "/source/" not in path:
            raise SystemExit("invalid input hash line")
        hashes.append((digest, path.split("/source/", 1)[1]))
    (out / "input_sha256.txt").write_text("".join(f"{d}  {p}\n" for d, p in hashes))
    (out / "phase_status.tsv").write_text("phase\tpassed\tfailed\ttotal\n" + "".join(f"{s}\t{v[0]}\t{v[1]}\t{v[2]}\n" for s, v in sorted(phases.items())))
    (out / "uvm_status.tsv").write_text("metric\tcount\nUVM_ERROR\t0\nUVM_FATAL\t0\nTEST_PASSED_CHECKS\t1\n")
    (out / "urg_report_summary.txt").write_text(f"report_generation=PASS\nnumber_of_tests={test_count.group(1)}\ngroups_in_smoke_report={group_count.group(1)}\naon_timer_covergroups_found=4\nbin_denominator_status=not_frozen_in_stage03\n")
    (out / "aon_timer_covergroups.txt").write_text("".join(f"{g}\n" for g in GROUPS))
    summary = {"schema": manifest.get("schema"), "run_id": manifest.get("run_id"), "revision": manifest.get("revision"), "test": manifest.get("test"), "uvm_test_seq": manifest.get("uvm_test_seq"), "fixed_seed": int(manifest["fixed_seed"]), "simulator": manifest.get("simulator"), "reporter": manifest.get("reporter"), "source_copy_verification": source, "dvsim_exit_code": 0, "phase_status": phases, "uvm_error_count": 0, "uvm_fatal_count": 0, "test_pass_marker": True, "urg_number_of_tests": int(test_count.group(1)), "urg_group_entries": int(group_count.group(1)), "aon_timer_covergroups_found": GROUPS, "coverage_compatibility_patch": "vcs-2019-legacy-option-adaptation-v3", "bin_denominator_frozen": False}
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "SHA256SUMS").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in sorted(out.iterdir()) if p.name != "SHA256SUMS"))

def verify(bundle: Path) -> None:
    sums = {}
    for line in (bundle / "SHA256SUMS").read_text().splitlines():
        digest, _, name = line.partition("  ")
        sums[name] = digest
    for name, digest in sums.items():
        if sha256(bundle / name) != digest:
            raise SystemExit(f"hash mismatch: {name}")
    actual = {p.name for p in bundle.iterdir() if p.is_file() and p.name != "SHA256SUMS"}
    if set(sums) != actual:
        raise SystemExit("SHA256SUMS does not cover the complete public evidence bundle")
    group_text = (bundle / "groups.txt").read_text(errors="replace")
    if any(group not in group_text for group in GROUPS):
        raise SystemExit("public URG group excerpt is missing an AON Timer covergroup")
    summary = json.loads((bundle / "run_summary.json").read_text())
    if summary["dvsim_exit_code"] != 0 or summary["uvm_error_count"] != 0 or summary["uvm_fatal_count"] != 0 or summary["bin_denominator_frozen"]:
        raise SystemExit("summary checks failed")
    if summary.get("test_pass_marker") is not True or summary.get("urg_number_of_tests") != 1 or summary.get("urg_group_entries") != 16:
        raise SystemExit("smoke or URG summary checks failed")
    expected_phases = {"build", "run", "cov_merge", "cov_report"}
    phases = summary.get("phase_status", {})
    if set(phases) != expected_phases or any(value != [1, 0, 1] for value in phases.values()):
        raise SystemExit("DVSim phase summary checks failed")
    if summary["aon_timer_covergroups_found"] != GROUPS or summary["source_copy_verification"].get("status") != "PASS":
        raise SystemExit("coverage/source checks failed")
    for path in bundle.iterdir():
        if path.is_file() and any(x in path.read_text(errors="replace") for x in ("/SM03/", "bs202264680312", "opentitan_aon_timer_4525bin_repro")):
            raise SystemExit(f"private path marker in {path.name}")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    if args.raw:
        collect(args.raw, args.bundle)
    verify(args.bundle)
    print(json.dumps({"verification": "PASS", "files_verified": len(list(args.bundle.iterdir())) - 1, "run_id": json.loads((args.bundle / "run_summary.json").read_text())["run_id"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()

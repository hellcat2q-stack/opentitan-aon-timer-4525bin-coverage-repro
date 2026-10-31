"""Collect sanitized evidence on the server, or independently verify a bundle."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import socket


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path, text):
    path.write_bytes(text.encode("utf-8"))


def write_json(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_payload(bundle):
    counts = {}
    rc = dict(line.split("\t") for line in (bundle / "return_codes.tsv").read_text().splitlines())
    expected_steps = {"build", "full", "partial", "urg_available", "urg_full", "urg_partial"}
    require(set(rc) == expected_steps and all(value == "0" for value in rc.values()), "nonzero/missing tool return code")
    for case, hits, percent in [("full", 4, 100.0), ("partial", 3, 75.0)]:
        log = (bundle / (case + ".log")).read_text()
        require(re.search(r"UVM_ERROR\s*:\s*0\b", log), case + " UVM_ERROR summary")
        require(re.search(r"UVM_FATAL\s*:\s*0\b", log), case + " UVM_FATAL summary")
        require("CAPABILITY_PROBE_OK samples=%d coverage=%.2f" % (hits, percent) in log, case + " probe assertion")
        dashboard = (bundle / (case + "_dashboard.txt")).read_text()
        require(re.search(r"Number of tests:\s*1\b", dashboard), case + " per-test report selection")
        section = dashboard.split("Total Groups Coverage Summary", 1)[1]
        match = re.search(r"^\s*(\d+)\s+(\d+)\s+(\d+\.\d+)\s+(\d+)\s+(\d+)\s+(\d+\.\d+)", section, re.M)
        require(match is not None, case + " coverage row missing")
        covered, expected, score, inst_covered, inst_expected, inst_score = match.groups()
        require((int(covered), int(expected), float(score)) == (hits, 4, percent), case + " group counts")
        require((int(inst_covered), int(inst_expected), float(inst_score)) == (hits, 4, percent), case + " instance counts")
        groups = (bundle / (case + "_groups.txt")).read_text()
        require("Total groups in report: 1" in groups, case + " unexpected group count")
        require("stage01_probe_pkg::stage01_capability_test::capability_cg" in groups, case + " missing probe group")
        counts[case] = {"covered": int(covered), "expected": int(expected), "percent": float(score), "reported_tests": 1}
    environment = json.loads((bundle / "environment.json").read_text())
    require(environment["dependency_smoke"] == "PASS" and environment["venv_isolated"], "Python prerequisites failed")
    require(environment["tools_on_path"]["vcs"] and environment["tools_on_path"]["urg"], "missing VCS/URG")
    require("No broken requirements found." in (bundle / "pip_check.txt").read_text(), "pip dependency consistency")
    require((bundle / "pip_freeze.txt").read_bytes() == (bundle / "requirements-stage01.lock.txt").read_bytes(), "installed packages differ from lock")
    return counts


def collect(run_id):
    require(re.fullmatch(r"[A-Za-z0-9_-]+", run_id), "invalid run id")
    root = Path.home() / "opentitan_aon_timer_4525bin_repro"
    work = root / "scratch/01" / run_id
    raw = root / "evidence/01_env" / run_id
    public = root / "evidence/01_env" / ("public_" + run_id)
    public.mkdir(exist_ok=False)
    replacements = [(str(root), "$ROOT"), (str(Path.home()), "$HOME")]
    if os.environ.get("VCS_HOME"):
        replacements.append((os.environ["VCS_HOME"].rstrip("/"), "$VCS_HOME"))
    replacements.extend([(os.environ.get("USER", ""), "<USER>"), (socket.gethostname(), "<HOST>")])
    def sanitize(value):
        for old, new in replacements:
            if old:
                value = value.replace(old, new)
        value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<IP>", value)
        value = re.sub(r"(?im)^.*(?:FLEXlm host ID|license server|SNPSLMD_LICENSE_FILE\s*=|LM_LICENSE_FILE\s*=).*$", "<LICENSE_DETAILS_REDACTED>", value)
        return value
    for name in ["build.log", "full.log", "partial.log", "urg_available.log", "urg_full.log", "urg_partial.log", "commands.sh", "return_codes.tsv"]:
        write(public / name, sanitize((raw / name).read_text(errors="replace")))
    for case in ["full", "partial"]:
        for name in ["dashboard.txt", "groups.txt", "tests.txt"]:
            write(public / (case + "_" + name), sanitize((work / ("report_" + case) / name).read_text(errors="replace")))
    for name in ["environment.json", "requirements-stage01.lock.txt", "pip_check.txt", "pip_freeze.txt"]:
        write(public / name, sanitize((root / "evidence/01_env" / name).read_text()))
    failed_attempt = root / "evidence/01_env/20261031_01"
    for name in ["return_codes.tsv", "urg_full.log"]:
        write(public / ("first_attempt_" + name), sanitize((failed_attempt / name).read_text()))
    write(public / "pip_online_failure.log", sanitize((root / "evidence/01_env/pip_install.log").read_text()))
    write(public / "wheel_sha256sums.txt", (root / "runtime/wheels/SHA256SUMS").read_text())
    counts = validate_payload(public)
    raw_files = list(raw.rglob("*")) + list((work / "probe.vdb").rglob("*")) + list(failed_attempt.rglob("*"))
    raw_files += list((work / "report_full").rglob("*")) + list((work / "report_partial").rglob("*"))
    raw_files += [work / "simv", work / "capability_probe.sv", root / "evidence/01_env/python_install.log",
                  root / "evidence/01_env/pip_install.log", root / "evidence/01_env/pip_install_offline.log",
                  root / "evidence/01_env/installer_checksum.txt"]
    raw_hashes = {str(p.relative_to(root)).replace(os.sep, "/"): digest(p)
                  for p in sorted(set(raw_files)) if p.is_file()}
    write_json(public / "server_raw_sha256.json", raw_hashes)
    inputs = {p.name: digest(p) for p in Path(__file__).parent.iterdir()
              if p.is_file() and p.suffix in {".py", ".sh", ".sv", ".txt"}}
    write_json(public / "input_sha256.json", inputs)
    summary = {
        "schema": "stage01-capability-result-v1", "status": "PASS", "run_id": run_id,
        "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "vcs_and_urg": "P-2019.06-SP1", "uvm": "1.2", "probe_seed": 42,
        "workers": 1, "final_attempt_simulations": 2, "total_probe_simulations_including_first_attempt": 4,
        "functional_probe_results": counts,
        "license_validation": "Real compile, simulation and URG report generation succeeded at check time",
        "installer": {"filename": "Miniconda3-py311_24.1.2-0-Linux-x86_64.sh",
                      "sha256": "3f2e5498e550a6437f15d9cc8020d52742d0ba70976ee8fce4f0daefa3992d2e",
                      "publisher_index": "https://repo.anaconda.com/miniconda/"},
        "limitations": ["Generic tool capability probe, not official AON Timer UVM smoke",
                        "4525/4279 denominator and target revision not verified",
                        "Single-worker license access only; 10 concurrent licenses not tested",
                        "OpenTitan dependencies and simulator compatibility deferred to Stages 02-03",
                        "Server package-index DNS failed; Python wheels installed offline"],
    }
    write_json(public / "summary.json", summary)
    # Verify that no known private locations, identity, or license values leaked.
    forbidden = [str(Path.home()), socket.gethostname(), os.environ.get("USER", "")]
    for name in ["SNPSLMD_LICENSE_FILE", "LM_LICENSE_FILE"]:
        value = os.environ.get(name)
        if value and len(value) >= 4:
            forbidden.append(value)
    for file in public.iterdir():
        value = file.read_text()
        require(not any(token and token in value for token in forbidden), "private data in " + file.name)
    write(public / "SHA256SUMS", "".join(digest(p) + "  " + p.name + "\n"
                                          for p in sorted(public.iterdir()) if p.is_file()))
    verify_bundle(public)
    print("PUBLIC_EVIDENCE_READY", public.name)


def verify_bundle(bundle):
    entries = {}
    for line in (bundle / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        require(Path(name).name == name, "unexpected manifest path")
        require(name not in entries, "duplicate manifest entry")
        require(digest(bundle / name) == expected, "hash mismatch: " + name)
        entries[name] = expected
    require(set(entries) == {p.name for p in bundle.iterdir() if p.is_file() and p.name != "SHA256SUMS"}, "manifest/file set mismatch")
    counts = validate_payload(bundle)
    summary = json.loads((bundle / "summary.json").read_text())
    require(summary["status"] == "PASS" and summary["functional_probe_results"] == counts, "summary mismatch")
    for name, expected in json.loads((bundle / "input_sha256.json").read_text()).items():
        require(digest(Path(__file__).with_name(name)) == expected, "source input differs: " + name)
    print(json.dumps({"verification": "PASS", "files_verified": len(entries), "counts": counts}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--collect", metavar="RUN_ID")
    group.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    if args.collect:
        collect(args.collect)
    else:
        verify_bundle(args.bundle)

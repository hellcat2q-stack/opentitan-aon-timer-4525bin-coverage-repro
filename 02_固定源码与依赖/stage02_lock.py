#!/usr/bin/env python3
"""Create and verify the immutable Stage 02 OpenTitan source lock.

The server verification intentionally works from a git archive plus Git blob
hashes. The server does not need network access or a second OpenTitan clone.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile


REVISION = "9f20940d494a223cc950a5b98f748fb28109d458"
TREE = "4229b5d334cf7c02996856ddbdf625989b5a6b58"
ARCHIVE = f"opentitan-{REVISION}-gitblob.tar.gz"
SOURCE_DIRECTORY = f"opentitan-{REVISION}-gitblob"
AON_PREFIX = "hw/ip/aon_timer/"
KEY_FILES = [
    ".bazelversion", "pyproject.toml", "python-requirements.txt",
    "hw/ip/aon_timer/aon_timer.core", "hw/ip/aon_timer/data/aon_timer.hjson",
    "hw/ip/aon_timer/data/aon_timer_testplan.hjson",
    "hw/ip/aon_timer/dv/README.md", "hw/ip/aon_timer/dv/aon_timer_sim.core",
    "hw/ip/aon_timer/dv/aon_timer_sim_cfg.hjson",
    "hw/ip/aon_timer/dv/env/aon_timer_env.core",
    "hw/ip/aon_timer/dv/env/aon_timer_env_cov.sv",
    "hw/ip/aon_timer/dv/tests/aon_timer_test.core",
    "hw/ip/aon_timer/rtl/aon_timer.sv",
    "hw/ip/aon_timer/rtl/aon_timer_core.sv",
    "hw/ip/aon_timer/rtl/aon_timer_reg_pkg.sv",
    "hw/ip/aon_timer/rtl/aon_timer_reg_top.sv",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _git_object_sha1(kind: str, data: bytes) -> bytes:
    return hashlib.sha1(f"{kind} {len(data)}\0".encode("ascii") + data).digest()


def git_tree_from_directory(path: Path) -> tuple[str, int]:
    entries = []
    file_count = 0
    for item in os.scandir(path):
        name = item.name.encode("utf-8")
        if item.is_symlink():
            content = os.readlink(item.path).encode("utf-8")
            mode = b"120000"
            oid = _git_object_sha1("blob", content)
            file_count += 1
            sort_name = name + b"\0"
        elif item.is_dir(follow_symlinks=False):
            oid_hex, child_count = git_tree_from_directory(Path(item.path))
            oid = bytes.fromhex(oid_hex)
            mode = b"40000"
            file_count += child_count
            sort_name = name + b"/"
        elif item.is_file(follow_symlinks=False):
            content_hash = hashlib.sha1()
            size = os.stat(item.path, follow_symlinks=False).st_size
            content_hash.update(f"blob {size}\0".encode("ascii"))
            with open(item.path, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    content_hash.update(chunk)
            oid = content_hash.digest()
            mode = b"100755" if os.stat(item.path, follow_symlinks=False).st_mode & 0o111 else b"100644"
            file_count += 1
            sort_name = name + b"\0"
        else:
            raise SystemExit("VERIFY_FAILED: unsupported filesystem entry in source tree")
        entries.append((sort_name, mode + b" " + name + b"\0" + oid))
    tree_data = b"".join(entry for _, entry in sorted(entries, key=lambda pair: pair[0]))
    return _git_object_sha1("tree", tree_data).hex(), file_count


def git_tree_from_archive(archive: Path, prefix: str) -> tuple[str, int]:
    """Recompute a Git tree from tar members without extracting long paths."""
    root: dict[str, object] = {}
    file_count = 0
    with tarfile.open(archive, "r:*") as tar:
        for item in tar:
            if item.name == prefix.rstrip("/") or not item.name.startswith(prefix):
                continue
            relpath = item.name[len(prefix):].rstrip("/")
            if not relpath or item.isdir():
                continue
            if item.issym():
                content = item.linkname.encode("utf-8", errors="surrogateescape")
                mode = b"120000"
                oid = _git_object_sha1("blob", content)
            elif item.isfile():
                stream = tar.extractfile(item)
                if stream is None:
                    raise SystemExit("VERIFY_FAILED: unreadable archive member: " + relpath)
                digest = hashlib.sha1()
                digest.update(f"blob {item.size}\0".encode("ascii"))
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                oid = digest.digest()
                mode = b"100755" if item.mode & 0o111 else b"100644"
            else:
                raise SystemExit("VERIFY_FAILED: unsupported archive member: " + relpath)
            node = root
            parts = relpath.split("/")
            for part in parts[:-1]:
                child = node.setdefault(part, {})
                if not isinstance(child, dict):
                    raise SystemExit("VERIFY_FAILED: file/directory collision: " + relpath)
                node = child
            name = parts[-1]
            if name in node:
                raise SystemExit("VERIFY_FAILED: duplicate archive member: " + relpath)
            node[name] = (mode, oid)
            file_count += 1

    def tree_object(node: dict[str, object]) -> bytes:
        entries = []
        for name, value in node.items():
            name_bytes = name.encode("utf-8", errors="surrogateescape")
            if isinstance(value, dict):
                mode = b"40000"
                oid = tree_object(value)
                sort_name = name_bytes + b"/"
            else:
                mode, oid = value
                sort_name = name_bytes + b"\0"
            entries.append((sort_name, mode + b" " + name_bytes + b"\0" + oid))
        data = b"".join(entry for _, entry in sorted(entries, key=lambda pair: pair[0]))
        return _git_object_sha1("tree", data)

    return tree_object(root).hex(), file_count


def verify_archive(lock_path: Path, archive: Path, output: Path | None = None) -> None:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    require(lock["schema"] == "opentitan-source-lock-v1", "lock schema")
    require(sha256_file(archive) == lock["archive"]["sha256"], "source archive sha256")
    tree, file_count = git_tree_from_archive(archive, lock["archive"]["prefix"])
    require(tree == lock["tree_sha1"], "archive Git tree SHA-1")
    require(file_count == lock["full_tree"]["file_count"], "archive Git file count")
    result = {"schema": "stage02-local-archive-verification-v1", "status": "PASS",
              "revision": lock["revision"], "tree_sha1": tree,
              "full_tree_file_count": file_count, "archive_sha256": lock["archive"]["sha256"],
              "method": "recomputed Git object IDs directly from archive members"}
    if output is not None:
        require(not output.exists(), "archive verification output already exists")
        json_dump(output, result)
    print(json.dumps(result, ensure_ascii=False))


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def git_bytes(repo: Path, revision: str, path: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), "show", f"{revision}:{path}"])


def json_dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_lock(repo: Path, archive: Path, output: Path) -> None:
    revision = REVISION
    commit_raw = subprocess.check_output(["git", "-C", str(repo), "cat-file", "-p", revision], text=True)
    headers, _, message = commit_raw.partition("\n\n")
    header_map = {}
    for line in headers.splitlines():
        key, _, value = line.partition(" ")
        header_map.setdefault(key, []).append(value)
    tree = git(repo, "rev-parse", f"{revision}^{{tree}}")
    if tree != TREE:
        raise SystemExit(f"unexpected tree {tree}, expected {TREE}")
    all_paths = git(repo, "ls-tree", "-r", "--name-only", revision).splitlines()
    aon_paths = [p for p in all_paths if p.startswith(AON_PREFIX)]
    files = {}
    for path in KEY_FILES + aon_paths:
        if path in files:
            continue
        data = git_bytes(repo, revision, path)
        files[path] = {
            "bytes": len(data),
            "git_blob_sha1": git_blob_sha1(data),
            "sha256": sha256_bytes(data),
        }
    cfg = git_bytes(repo, revision, "hw/ip/aon_timer/dv/aon_timer_sim_cfg.hjson").decode("utf-8")
    cov = git_bytes(repo, revision, "hw/ip/aon_timer/dv/env/aon_timer_env_cov.sv").decode("utf-8")
    req = git_bytes(repo, revision, "python-requirements.txt").decode("utf-8")
    test_names = re.findall(r"^\s*name:\s*(aon_timer_[A-Za-z0-9_]+)\s*$", cfg, re.M)
    seq_names = re.findall(r"^\s*uvm_test_seq:\s*(aon_timer_[A-Za-z0-9_]+)\s*$", cfg, re.M)
    covergroups = re.findall(r"^\s*covergroup\s+([A-Za-z0-9_]+)", cov, re.M)
    auto_bins = [int(v) for v in re.findall(r"option\.auto_bin_max\s*=\s*(\d+)", cov)]
    dep_lines = [line.strip().rstrip("\\").strip() for line in req.splitlines()
                 if line.strip() and not line.lstrip().startswith(("#", "--hash"))
                 and not line.strip() == "\\"]
    committed_epoch = int(header_map.get("committer", ["0 0"])[0].rsplit(" ", 2)[-2])
    authored_epoch = int(header_map.get("author", ["0 0"])[0].rsplit(" ", 2)[-2])
    lock = {
        "schema": "opentitan-source-lock-v1",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "revision": revision,
        "tree_sha1": tree,
        "parent_revision": header_map.get("parent", [None])[0],
        "authored_by": header_map.get("author", [""])[0].split(" <", 1)[0],
        "authored_at_utc": dt.datetime.fromtimestamp(authored_epoch, dt.timezone.utc).isoformat(),
        "author": header_map.get("author", [""])[0].split(" ", 1)[0],
        "committed_at_utc": dt.datetime.fromtimestamp(committed_epoch, dt.timezone.utc).isoformat(),
        "subject": message.splitlines()[0],
        "source_repo": "https://github.com/lowRISC/opentitan.git",
        "archive": {"filename": ARCHIVE, "sha256": sha256_file(archive), "bytes": archive.stat().st_size,
                    "prefix": SOURCE_DIRECTORY + "/", "format": "git archive tar.gz (core.autocrlf=false)"},
        "source_directory": SOURCE_DIRECTORY,
        "root_gitlinks": [],
        "full_tree": {"file_count": len(all_paths), "tree_sha1": tree},
        "key_files": files,
        "aon_timer_file_count": len(aon_paths),
        "aon_timer_files": {p: files[p] for p in aon_paths},
        "dv_configuration": {
            "config_path": "hw/ip/aon_timer/dv/aon_timer_sim_cfg.hjson",
            "name": "aon_timer", "dut": "aon_timer", "tb": "tb", "tool": "vcs",
            "fusesoc_core": "lowrisc:dv:aon_timer_sim:0.1", "reseed": 50,
            "uvm_test": "aon_timer_base_test", "uvm_test_seq": "aon_timer_base_vseq",
            "run_opts": ["+cdc_instrumentation_enabled=1"],
            "tests": test_names, "test_sequences": seq_names,
            "testplan": "hw/ip/aon_timer/data/aon_timer_testplan.hjson",
            "ral_spec": "hw/ip/aon_timer/data/aon_timer.hjson",
            "sim_tops": ["aon_timer_bind", "sec_cm_prim_onehot_check_bind"],
            "coverage_exclusion_files_in_revision": [],
        },
        "coverage_definition_markers": {
            "source_path": "hw/ip/aon_timer/dv/env/aon_timer_env_cov.sv",
            "covergroups": covergroups,
            "auto_bin_max_values": auto_bins,
            "expected_named_covergroups": ["timer_cfg_cg", "wake_up_timer_thold_hit_cg",
                                            "watchdog_timer_bite_thold_hit_cg", "watchdog_timer_bark_thold_hit_cg"],
        },
        "python_requirements": {
            "path": "python-requirements.txt", "line_count": len(req.splitlines()),
            "dependency_line_count": len(dep_lines), "sha256": sha256_bytes(req.encode()),
            "direct_requirements": dep_lines,
        },
        "stage01_toolchain_contract": {
            "simulator": "VCS P-2019.06-SP1", "coverage_reporter": "URG P-2019.06-SP1 / CovDB 13.1",
            "uvm": "1.2", "python_runtime": "3.11.7", "compiler": "GCC 4.8.5",
            "source_compatibility_patches": [],
        },
        "status": "LOCK_CREATED_FROM_EXACT_REVISION",
    }
    json_dump(output, lock)
    print(json.dumps({"output": str(output), "revision": revision, "tree_sha1": tree,
                      "archive_sha256": lock["archive"]["sha256"], "aon_timer_files": len(aon_paths)}, ensure_ascii=False))


def run_cmd(command: list[str], cwd: Path | None = None) -> str:
    env = dict(os.environ)
    env.pop("LD_PRELOAD", None)
    env.pop("LD_LIBRARY_PATH", None)
    return subprocess.check_output(command, cwd=cwd, env=env, stderr=subprocess.STDOUT, text=True).strip()


def verify_source(lock_path: Path, root: Path) -> None:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    require(lock["schema"] == "opentitan-source-lock-v1", "lock schema")
    revision = lock["revision"]
    archive = root / "runtime" / lock["archive"]["filename"]
    require(archive.is_file(), "source archive missing")
    require(sha256_file(archive) == lock["archive"]["sha256"], "source archive sha256")
    source = root / "src" / lock["source_directory"]
    require(source.is_dir(), "extracted source missing")
    extracted_tree, extracted_count = git_tree_from_directory(source)
    require(extracted_tree == lock["tree_sha1"], "full source Git tree SHA-1")
    require(extracted_count == lock["full_tree"]["file_count"], "full source file count")
    for path, expected in lock["key_files"].items():
        file = source / path
        require(file.is_file(), "missing source file: " + path)
        data = file.read_bytes()
        require(len(data) == expected["bytes"], "byte length: " + path)
        require(sha256_bytes(data) == expected["sha256"], "sha256: " + path)
        require(git_blob_sha1(data) == expected["git_blob_sha1"], "git blob: " + path)
    cfg = (source / lock["dv_configuration"]["config_path"]).read_text(encoding="utf-8")
    require(re.search(r"^\s*reseed:\s*50\s*$", cfg, re.M), "reseed drift")
    for test in lock["dv_configuration"]["tests"]:
        require(re.search(r"^\s*name:\s*" + re.escape(test) + r"\s*$", cfg, re.M), "test drift: " + test)
    cov = (source / lock["coverage_definition_markers"]["source_path"]).read_text(encoding="utf-8")
    for group in lock["coverage_definition_markers"]["expected_named_covergroups"]:
        require(re.search(r"^\s*covergroup\s+" + re.escape(group) + r"\b", cov, re.M), "covergroup drift: " + group)
    require(sorted(map(int, re.findall(r"option\.auto_bin_max\s*=\s*(\d+)", cov))) ==
            sorted(lock["coverage_definition_markers"]["auto_bin_max_values"]), "auto-bin marker drift")
    version_output = run_cmd(["vcs", "-ID"])
    vcs_version_match = re.search(r"^Compiler version\s*=\s*(VCS\s+P-[A-Za-z0-9._-]+)", version_output, re.M)
    if not vcs_version_match:
        raise SystemExit("VERIFY_FAILED: unable to identify VCS version")
    version = vcs_version_match.group(1)
    urg_output = run_cmd(["urg", "-version"])
    urg_version_match = re.search(r"^(URG Version\s+P-[A-Za-z0-9._-]+).*$", urg_output, re.M)
    covdb_match = re.search(r"^(CovDB version:\s*[A-Za-z0-9._-]+)", urg_output, re.M)
    if not urg_version_match or not covdb_match:
        raise SystemExit("VERIFY_FAILED: unable to identify URG/CovDB versions")
    urg = urg_version_match.group(1) + "; " + covdb_match.group(1)
    py = run_cmd([sys.executable, "--version"])
    gcc = run_cmd(["gcc", "--version"]).splitlines()[0]
    tools = {"vcs_ID": version, "urg_version": urg, "python": py, "gcc": gcc,
             "dvsim_on_path": shutil.which("dvsim") is not None,
             "verisim_on_path": shutil.which("verisim") is not None,
             "vericov_on_path": shutil.which("vericov") is not None}
    # The checks below are deliberately based on public version strings only.
    require("P-2019.06-SP1" in version and "P-2019.06-SP1" in urg, "tool version drift")
    require(py.startswith("Python 3.11."), "Python runtime drift")
    # Keep the earlier key-file check evidence intact and write the complete
    # tree verification as a distinct, non-overwriting evidence bundle.
    output = root / "evidence" / "02_source_full_tree"
    output.mkdir(parents=True, exist_ok=False)
    json_dump(output / "tool_versions.json", tools)
    json_dump(output / "source_lock_verified.json", {"schema": "stage02-source-verification-v1",
                                                        "status": "PASS", "revision": revision,
                                                        "tree_sha1": lock["tree_sha1"],
                                                        "full_tree_file_count": lock["full_tree"]["file_count"],
                                                        "archive_sha256": lock["archive"]["sha256"],
                                                        "key_files_verified": len(lock["key_files"]),
                                                        "aon_timer_files_verified": lock["aon_timer_file_count"],
                                                        "coverage_definition_markers_verified": True,
                                                        "tool_versions_file": "tool_versions.json",
                                                        "source_compatibility_patches": []})
    print(json.dumps({"verification": "PASS", "revision": revision,
                      "key_files": len(lock["key_files"]), "aon_timer_files": lock["aon_timer_file_count"],
                      "tree_sha1": lock["tree_sha1"],
                      "full_tree_file_count": lock["full_tree"]["file_count"],
                      "tools": tools}, ensure_ascii=False))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("VERIFY_FAILED: " + message)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    make = sub.add_parser("make-lock")
    make.add_argument("--repo", type=Path, required=True)
    make.add_argument("--archive", type=Path, required=True)
    make.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify-server")
    verify.add_argument("--lock", type=Path, required=True)
    verify.add_argument("--root", type=Path, default=Path.home() / "opentitan_aon_timer_4525bin_repro")
    verify_archive_parser = sub.add_parser("verify-archive")
    verify_archive_parser.add_argument("--lock", type=Path, required=True)
    verify_archive_parser.add_argument("--archive", type=Path, required=True)
    verify_archive_parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "make-lock":
        make_lock(args.repo, args.archive, args.output)
    elif args.mode == "verify-server":
        verify_source(args.lock, args.root)
    else:
        verify_archive(args.lock, args.archive, args.output)


if __name__ == "__main__":
    main()

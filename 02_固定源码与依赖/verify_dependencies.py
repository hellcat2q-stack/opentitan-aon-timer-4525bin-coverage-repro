#!/usr/bin/env python3
"""Verify the installed OpenTitan Python lock and offline artifact evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonicalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_freeze(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        name, marker, version = line.partition("==")
        if not marker:
            raise SystemExit("invalid inventory line: " + line)
        key = canonicalize(name)
        if key in result:
            raise SystemExit("duplicate inventory package: " + name)
        result[key] = version
    return result


def verify(args: argparse.Namespace) -> dict[str, object]:
    lock = json.loads(args.source_lock.read_text(encoding="utf-8"))
    requirements = args.requirements.read_bytes()
    req_lock = lock["python_requirements"]
    if sha256(requirements) != req_lock["sha256"]:
        raise SystemExit("upstream requirements SHA-256 mismatch")
    if len(requirements.splitlines()) != req_lock["line_count"]:
        raise SystemExit("upstream requirements line count mismatch")
    if len(req_lock["direct_requirements"]) != req_lock["dependency_line_count"]:
        raise SystemExit("source lock direct dependency count mismatch")

    installed = load_freeze(args.installed_freeze)
    pinned_matches = 0
    source_url_requirements: list[str] = []
    expected_names: set[str] = set()
    for requirement in req_lock["direct_requirements"]:
        if " @ " in requirement:
            raw_name, url = requirement.split(" @ ", 1)
            name = canonicalize(raw_name)
            if not url.startswith("https://"):
                raise SystemExit("non-upstream direct requirement URL: " + raw_name)
            source_url_requirements.append(name)
        else:
            raw_name, separator, version = requirement.partition("==")
            if not separator:
                raise SystemExit("unsupported requirement form: " + requirement)
            name = canonicalize(raw_name)
            if installed.get(name) != version:
                raise SystemExit("pinned version mismatch: " + raw_name)
            pinned_matches += 1
        if name in expected_names:
            raise SystemExit("duplicate source requirement: " + name)
        expected_names.add(name)
        if name not in installed:
            raise SystemExit("required package missing from inventory: " + name)

    build_lock = json.loads(args.build_tools_lock.read_text(encoding="utf-8"))
    build_tools: dict[str, str] = {}
    for tool in build_lock["tools"]:
        name = canonicalize(tool["name"])
        version = tool["version"]
        if installed.get(name) != version:
            raise SystemExit("build tool version mismatch: " + name)
        artifact = args.build_tools_dir / tool["filename"]
        if sha256(artifact.read_bytes()) != tool["sha256"]:
            raise SystemExit("build tool artifact SHA-256 mismatch: " + name)
        build_tools[name] = version

    bundle_lock = json.loads(args.bundle_lock.read_text(encoding="utf-8"))
    bundle_data = args.bundle_file.read_bytes()
    if sha256(bundle_data) != bundle_lock["sha256"] or len(bundle_data) != bundle_lock["bytes"]:
        raise SystemExit("offline dependency bundle hash or size mismatch")
    manifest = args.wheels_manifest.read_text(encoding="utf-8").splitlines()
    verified_wheels = 0
    with tarfile.open(args.bundle_file, "r") as archive:
        members = set(archive.getnames())
        for line in manifest:
            if not line.strip():
                continue
            expected_hash, filename = line.split(None, 1)
            filename = filename.lstrip("* ")
            member = "wheels/" + filename
            if member not in members:
                raise SystemExit("wheelhouse archive member missing: " + filename)
            stream = archive.extractfile(member)
            if stream is None or sha256(stream.read()) != expected_hash:
                raise SystemExit("wheelhouse package hash mismatch: " + filename)
            verified_wheels += 1
    if verified_wheels != bundle_lock["verified_package_file_count"]:
        raise SystemExit("wheelhouse package count mismatch")

    pip_check = args.pip_check.read_text(encoding="utf-8").strip()
    if pip_check != "No broken requirements found.":
        raise SystemExit("pip check did not pass")

    source_verification = json.loads(args.source_verification.read_text(encoding="utf-8"))
    if source_verification["status"] != "PASS":
        raise SystemExit("source verification status is not PASS")
    if (source_verification["tree_sha1"] != lock["tree_sha1"] or
            source_verification["full_tree_file_count"] != lock["full_tree"]["file_count"]):
        raise SystemExit("source tree evidence does not match source lock")

    extras = {name: version for name, version in installed.items()
              if name not in expected_names and name not in build_tools}
    return {
        "schema": "stage02-dependency-verification-v1",
        "status": "PASS",
        "revision": lock["revision"],
        "source_tree_sha1": lock["tree_sha1"],
        "source_tree_file_count": lock["full_tree"]["file_count"],
        "upstream_requirements_sha256": req_lock["sha256"],
        "upstream_requirement_count": len(expected_names),
        "pinned_version_matches": pinned_matches,
        "upstream_archive_requirements_present": {
            name: installed[name] for name in sorted(source_url_requirements)
        },
        "installed_distribution_count": len(installed),
        "bootstrap_environment_extras": extras,
        "offline_bundle_sha256": bundle_lock["sha256"],
        "offline_package_files_verified": verified_wheels,
        "build_tools_verified": build_tools,
        "pip_check": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--installed-freeze", type=Path, required=True)
    parser.add_argument("--pip-check", type=Path, required=True)
    parser.add_argument("--build-tools-lock", type=Path, required=True)
    parser.add_argument("--build-tools-dir", type=Path, required=True)
    parser.add_argument("--bundle-lock", type=Path, required=True)
    parser.add_argument("--bundle-file", type=Path, required=True)
    parser.add_argument("--wheels-manifest", type=Path, required=True)
    parser.add_argument("--source-verification", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Verify transferred wheels and localize the pinned source distribution URLs."""
import argparse
import hashlib
from pathlib import Path


SOURCES = {
    "https://github.com/newaetech/chipwhisperer-minimal/archive/2643131b71e528791446ee1bab7359120288f4ab.zip":
        "2643131b71e528791446ee1bab7359120288f4ab.zip",
    "https://github.com/lowRISC/edalize/archive/refs/tags/v0.4.0.zip": "v0.4.0.zip",
    "https://github.com/lowRISC/fusesoc/archive/refs/tags/ot-0.5.dev0.zip": "ot-0.5.dev0.zip",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lines = args.requirements.read_text(encoding="utf-8").splitlines(keepends=True)
    text = "".join(lines)
    for url, filename in SOURCES.items():
        source = args.wheelhouse / filename
        if not source.is_file():
            raise SystemExit("missing upstream source archive: " + filename)
        text = text.replace(url, source.resolve().as_uri())
    if any(url in text for url in SOURCES):
        raise SystemExit("not all upstream source URLs were localized")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8", newline="\n")
    print("LOCAL_REQUIREMENTS_READY bytes=%d sha256=%s" %
          (args.output.stat().st_size, sha256(args.output)))


if __name__ == "__main__":
    main()

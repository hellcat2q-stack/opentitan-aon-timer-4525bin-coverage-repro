"""Collect a public-safe capability snapshot; never print license values."""
import datetime
import importlib.metadata
import json
import os
import pathlib
import platform
import shutil
import ssl
import sqlite3
import subprocess
import sys
import zlib


def main():
    root = pathlib.Path.home() / "opentitan_aon_timer_4525bin_repro"
    import numpy as np
    import pandas as pd
    import scipy.stats
    from sklearn.cluster import DBSCAN
    import hjson
    import yaml
    import jinja2
    import psutil
    from packaging.version import Version

    # Tiny synthetic dependency check, never a paper experiment/corpus.
    labels = DBSCAN(eps=0.2, min_samples=2, n_jobs=1).fit_predict(
        np.array([[0.0, 0.0], [0.1, 0.1], [9.0, 9.0]])
    ).tolist()
    assert labels == [0, 0, -1], labels
    assert pd.DataFrame({"x": [1, 2]}).x.sum() == 3
    assert abs(scipy.stats.pearsonr([0, 1, 0], [0, 1, 0]).statistic - 1) < 1e-12
    assert hjson.loads('{"ok":true}')["ok"] is True
    assert yaml.safe_load("ok: true")["ok"] is True
    assert jinja2.Template("{{ value }}").render(value="ok") == "ok"
    assert Version(platform.python_version()) >= Version("3.10")
    assert pathlib.Path(sys.prefix).resolve() == (root / ".venv").resolve()
    names = ["numpy", "scipy", "pandas", "scikit-learn", "hjson", "PyYAML",
             "Jinja2", "packaging", "psutil", "pip", "setuptools"]
    disk = shutil.disk_usage(root)
    memory = psutil.virtual_memory()
    output = {
        "schema": "stage01-environment-capability-v1",
        "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "project_root": "$HOME/opentitan_aon_timer_4525bin_repro",
        "os": pathlib.Path("/etc/redhat-release").read_text().strip(),
        "kernel": platform.release(), "architecture": platform.machine(),
        "glibc": subprocess.check_output(["getconf", "GNU_LIBC_VERSION"], text=True).strip(),
        "logical_cpu_count": os.cpu_count(),
        "memory_total_bytes": memory.total, "memory_available_bytes": memory.available,
        "disk_free_bytes": disk.free,
        "resource_note": "Shared-server snapshot, not reserved capacity; probe workers=1.",
        "tools_on_path": {name: shutil.which(name) is not None for name in
                          ["vcs", "urg", "verisim", "vericov", "gcc", "make", "timeout"]},
        "gcc": subprocess.check_output(["gcc", "-dumpversion"], text=True).strip(),
        "system_python": subprocess.check_output(["/bin/python3", "--version"], text=True).strip(),
        "isolated_python": platform.python_version(), "venv_isolated": True,
        "stdlib": {"ssl": ssl.OPENSSL_VERSION, "sqlite3": sqlite3.sqlite_version,
                   "zlib": zlib.ZLIB_VERSION},
        "license_environment_presence": {name: bool(os.environ.get(name)) for name in
                                         ["SNPSLMD_LICENSE_FILE", "LM_LICENSE_FILE"]},
        "inherited_ld_preload_present": bool(os.environ.get("LD_PRELOAD")),
        "dependency_versions": {name: importlib.metadata.version(name) for name in names},
        "dependency_smoke": "PASS", "synthetic_dbscan_labels": labels,
        "official_opentitan_dependencies": "Deferred to Stage 02 after pinning revision",
    }
    destination = root / "evidence/01_env/environment.json"
    destination.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

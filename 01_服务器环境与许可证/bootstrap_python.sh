#!/usr/bin/env bash
# Installer and wheel files must already be staged in this NEW project root.
set -euo pipefail
umask 077
ROOT="${HOME}/opentitan_aon_timer_4525bin_repro"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="Miniconda3-py311_24.1.2-0-Linux-x86_64.sh"
EXPECTED=3f2e5498e550a6437f15d9cc8020d52742d0ba70976ee8fce4f0daefa3992d2e
mkdir -p "$ROOT/evidence/01_env"
cd "$ROOT/runtime"
printf '%s  %s\n' "$EXPECTED" "$PKG" | sha256sum -c -
if ! test -x "$ROOT/runtime/miniconda3/bin/python"; then
  test ! -e "$ROOT/runtime/miniconda3"
  env -u LD_PRELOAD -u LD_LIBRARY_PATH timeout --signal=TERM --kill-after=10s 300s \
    bash "$PKG" -b -p "$ROOT/runtime/miniconda3" \
    > "$ROOT/evidence/01_env/python_install.log" 2>&1
fi
if ! test -x "$ROOT/.venv/bin/python"; then
  test ! -e "$ROOT/.venv"
  env -u LD_PRELOAD -u LD_LIBRARY_PATH "$ROOT/runtime/miniconda3/bin/python" \
    -m venv "$ROOT/.venv"
fi
cd "$ROOT/runtime/wheels"
# Accept a Windows-created text manifest without changing the wheel bytes.
tr -d '\r' < SHA256SUMS | sha256sum -c -
REQ="$SCRIPT_DIR/requirements-stage01.txt"
if test -f "$SCRIPT_DIR/requirements-stage01.lock.txt"; then
  REQ="$SCRIPT_DIR/requirements-stage01.lock.txt"
fi
env -u LD_PRELOAD -u LD_LIBRARY_PATH timeout --signal=TERM --kill-after=10s 300s \
  "$ROOT/.venv/bin/python" -m pip --isolated install --no-index \
  --find-links "$ROOT/runtime/wheels" --only-binary=:all: -r "$REQ" \
  > "$ROOT/evidence/01_env/pip_install_offline.log" 2>&1
"$ROOT/.venv/bin/python" -m pip check
"$ROOT/.venv/bin/python" -m pip freeze \
  > "$ROOT/evidence/01_env/requirements-stage01.lock.txt"
printf 'PYTHON_BOOTSTRAP_OK\n'

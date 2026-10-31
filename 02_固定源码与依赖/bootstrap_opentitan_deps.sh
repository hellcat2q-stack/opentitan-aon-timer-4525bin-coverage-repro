#!/usr/bin/env bash
# Install the pinned upstream Python requirements from a locally verified
# CPython 3.11 / manylinux2014 wheelhouse into a NEW, separate project venv.
set -euo pipefail
umask 077
ROOT="${HOME}/opentitan_aon_timer_4525bin_repro"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$ROOT/src/opentitan-9f20940d494a223cc950a5b98f748fb28109d458-gitblob"
WHEELHOUSE="$ROOT/runtime/opentitan-wheels"
BUILD_TOOL="$ROOT/runtime/opentitan-build-tools/wheel-0.45.1-py3-none-any.whl"
BUILD_TOOL_SHA256="708e7481cc80179af0e556bbf0cc00b8444c7321e2700b8d8580231d13017248"
SCM_TOOL="$ROOT/runtime/opentitan-build-tools/setuptools_scm-8.2.0-py3-none-any.whl"
SCM_TOOL_SHA256="136e2b1d393d709d2bcf26f275b8dec06c48b811154167b0fd6bb002aad17d6d"
PACKAGING_WHEEL="$WHEELHOUSE/packaging-24.2-py3-none-any.whl"
VENV="$ROOT/.venv-opentitan"
EVIDENCE="$ROOT/evidence/02_source"
mkdir -p "$EVIDENCE"
tr -d '\r' < "$WHEELHOUSE/SHA256SUMS" | (cd "$WHEELHOUSE" && sha256sum -c -)
printf '%s  %s\n' "$BUILD_TOOL_SHA256" "$BUILD_TOOL" | sha256sum -c -
printf '%s  %s\n' "$SCM_TOOL_SHA256" "$SCM_TOOL" | sha256sum -c -
"$ROOT/.venv/bin/python" "$SCRIPT_DIR/prepare_offline_requirements.py" \
  --requirements "$SOURCE/python-requirements.txt" \
  --wheelhouse "$WHEELHOUSE" --output "$ROOT/project/stage02_work/python-requirements-offline.txt"
if ! test -x "$VENV/bin/python"; then
  test ! -e "$VENV"
  env -u LD_PRELOAD -u LD_LIBRARY_PATH "$ROOT/runtime/miniconda3/bin/python" -m venv "$VENV"
fi
env -u LD_PRELOAD -u LD_LIBRARY_PATH "$VENV/bin/python" -m pip --isolated \
  install --no-index --no-deps "$PACKAGING_WHEEL" "$BUILD_TOOL" "$SCM_TOOL" \
  >> "$EVIDENCE/build_tool_install.log" 2>&1
if test -f "$EVIDENCE/python_install.log"; then
  attempt=1
  while test -e "$EVIDENCE/python_install_attempt$(printf '%02d' "$attempt").log"; do
    attempt=$((attempt + 1))
  done
  mv "$EVIDENCE/python_install.log" \
    "$EVIDENCE/python_install_attempt$(printf '%02d' "$attempt").log"
fi
env -u LD_PRELOAD -u LD_LIBRARY_PATH timeout --signal=TERM --kill-after=10s 900s \
  "$VENV/bin/python" -m pip --isolated install --no-index --no-deps \
  --no-build-isolation --require-hashes --find-links "$WHEELHOUSE" \
  -r "$ROOT/project/stage02_work/python-requirements-offline.txt" \
  > "$EVIDENCE/python_install.log" 2>&1
env -u LD_PRELOAD -u LD_LIBRARY_PATH "$VENV/bin/python" -m pip check \
  > "$EVIDENCE/pip_check.txt" 2>&1
env -u LD_PRELOAD -u LD_LIBRARY_PATH "$VENV/bin/python" -m pip list --format=freeze \
  > "$EVIDENCE/python-requirements-installed.txt"
printf 'OPENTITAN_PYTHON_DEPS_INSTALLED\n'

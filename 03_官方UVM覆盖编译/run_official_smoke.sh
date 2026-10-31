#!/usr/bin/env bash
# Run one official AON Timer smoke test with functional coverage enabled.
set -uo pipefail
umask 077

ROOT="${HOME}/opentitan_aon_timer_4525bin_repro"
RUN_ID="${1:?Usage: bash run_official_smoke.sh UNIQUE_RUN_ID}"
[[ "$RUN_ID" =~ ^[A-Za-z0-9_-]+$ ]] || exit 64

REVISION="9f20940d494a223cc950a5b98f748fb28109d458"
SOURCE_LOCKED="$ROOT/src/opentitan-$REVISION-gitblob"
VENV="$ROOT/.venv-opentitan"
export PATH="$VENV/bin:$PATH"
SCRATCH="$ROOT/scratch/03/$RUN_ID"
EVIDENCE="$ROOT/evidence/03_uvm/$RUN_ID"
LOCK_TOOL="$ROOT/project/stage03/stage02_lock.py"
SOURCE_LOCK="$ROOT/project/stage02_work/source_lock.json"

test -d "$SOURCE_LOCKED" || { echo "MISSING_SOURCE"; exit 66; }
test -x "$VENV/bin/python" || { echo "MISSING_VENV"; exit 66; }
test -f "$LOCK_TOOL" || { echo "MISSING_SOURCE_VERIFIER"; exit 66; }
test -f "$SOURCE_LOCK" || { echo "MISSING_SOURCE_LOCK"; exit 66; }
command -v vcs >/dev/null || { echo "MISSING_VCS"; exit 66; }
command -v urg >/dev/null || { echo "MISSING_URG"; exit 66; }
test -s "$ROOT/evidence/02_source_full_tree/source_lock_verified.json" || {
  echo "MISSING_STAGE02_SOURCE_VERIFICATION"; exit 66;
}
test -s "$ROOT/evidence/02_source/pip_check.txt" || {
  echo "MISSING_STAGE02_DEPENDENCY_VERIFICATION"; exit 66;
}

mkdir -p "$ROOT/scratch/03" "$ROOT/evidence/03_uvm"
test ! -e "$SCRATCH" || { echo "RUN_SCRATCH_ALREADY_EXISTS"; exit 73; }
test ! -e "$EVIDENCE" || { echo "RUN_EVIDENCE_ALREADY_EXISTS"; exit 73; }
mkdir "$SCRATCH" || exit 73
mkdir "$EVIDENCE" || exit 73

# Run from a per-run copy so FuseSoC/DVSim generated files cannot alter the
# immutable Stage 02 source snapshot.
SOURCE="$SCRATCH/source"
cp -a "$SOURCE_LOCKED" "$SOURCE" || exit 74
CFG="$SOURCE/hw/ip/aon_timer/dv/aon_timer_sim_cfg.hjson"
DV_SIM="$SOURCE/util/dvsim/dvsim.py"
"$ROOT/.venv/bin/python" "$LOCK_TOOL" verify-directory \
  --lock "$SOURCE_LOCK" --source "$SOURCE" \
  > "$EVIDENCE/source_copy_verification.json" 2>&1 || exit 75
VCS_CFG="$SOURCE/hw/dv/tools/dvsim/vcs.hjson"
COMMON_SIM_CFG="$SOURCE/hw/dv/tools/dvsim/common_sim_cfg.hjson"
COVER_CFG="$SOURCE/hw/dv/tools/vcs/cover.cfg"
COMMON_COV_EXCL_CFG="$SOURCE/hw/dv/tools/vcs/common_cov_excl.cfg"
MERGED_COV_CFG="$SOURCE/hw/dv/tools/vcs/stage03_vcs2019_cov.cfg"
ORIGINAL_VCS_CFG_SHA256=$(sha256sum "$VCS_CFG" | awk '{print $1}')
ORIGINAL_COMMON_SIM_CFG_SHA256=$(sha256sum "$COMMON_SIM_CFG" | awk '{print $1}')
grep -Eq '^[[:space:]]*"-cm_common_hier",[[:space:]]*$' "$VCS_CFG" || {
  echo "EXPECTED_UNSUPPORTED_VCS_OPTION_NOT_FOUND"; exit 76;
}
sed -i '/^[[:space:]]*"-cm_common_hier",[[:space:]]*$/d' "$VCS_CFG"
if grep -Eq '^[[:space:]]*"-cm_common_hier",[[:space:]]*$' "$VCS_CFG"; then
  echo "VCS_COMPATIBILITY_PATCH_FAILED"; exit 76;
fi
grep -Eq '"-xprop=mmsopt"' "$VCS_CFG" || {
  echo "EXPECTED_UNSUPPORTED_XPROP_OPTION_NOT_FOUND"; exit 76;
}
sed -i 's/"-xprop=mmsopt"//g' "$VCS_CFG"
if grep -Eq '"-xprop=mmsopt"' "$VCS_CFG"; then
  echo "VCS_XPROP_COMPATIBILITY_PATCH_FAILED"; exit 76;
fi
grep -Eq 'default_vcs_cov_cfg_file:.*cover\.cfg\+.*common_cov_excl\.cfg' "$COMMON_SIM_CFG" || {
  echo "EXPECTED_UNSUPPORTED_COVERAGE_HIER_FORMAT_NOT_FOUND"; exit 76;
}
cat "$COMMON_COV_EXCL_CFG" "$COVER_CFG" > "$MERGED_COV_CFG"
sed -i 's#^[[:space:]]*default_vcs_cov_cfg_file:.*$#  default_vcs_cov_cfg_file: "-cm_hier {dv_root}/tools/vcs/stage03_vcs2019_cov.cfg"#' "$COMMON_SIM_CFG"
if grep -Eq 'default_vcs_cov_cfg_file:.*cover\.cfg\+.*common_cov_excl\.cfg' "$COMMON_SIM_CFG"; then
  echo "VCS_COVERAGE_HIER_COMPATIBILITY_PATCH_FAILED"; exit 76;
fi
PATCHED_VCS_CFG_SHA256=$(sha256sum "$VCS_CFG" | awk '{print $1}')
PATCHED_COMMON_SIM_CFG_SHA256=$(sha256sum "$COMMON_SIM_CFG" | awk '{print $1}')
MERGED_COV_CFG_SHA256=$(sha256sum "$MERGED_COV_CFG" | awk '{print $1}')
printf '%s\n' \
  'compatibility_patch=vcs-2019-legacy-option-adaptation-v3' \
  "original_vcs_hjson_sha256=$ORIGINAL_VCS_CFG_SHA256" \
  "patched_vcs_hjson_sha256=$PATCHED_VCS_CFG_SHA256" \
  "original_common_sim_cfg_sha256=$ORIGINAL_COMMON_SIM_CFG_SHA256" \
  "patched_common_sim_cfg_sha256=$PATCHED_COMMON_SIM_CFG_SHA256" \
  "merged_cov_cfg_sha256=$MERGED_COV_CFG_SHA256" \
  'change=remove -cm_common_hier and -xprop=mmsopt from per-run vcs.hjson; concatenate common_cov_excl.cfg before cover.cfg into one legacy VCS config; point default_vcs_cov_cfg_file to that merged file' \
  'reason=VCS P-2019.06-SP1 rejects -cm_common_hier, treats -xprop=mmsopt as a second config file, and rejects the newer cover.cfg+common_cov_excl.cfg combined path; OpenTitan labels mmsopt a performance optimization' \
  'scope=per-run source copy only; locked source tree and archive remain unchanged' \
  > "$EVIDENCE/compatibility_patch.txt"
cd "$SOURCE" || exit 73

export PYTHONDONTWRITEBYTECODE=1
printf '%s\n' \
  'schema=stage03-official-aon-timer-smoke-v5-vcs2019-compat' \
  "run_id=$RUN_ID" \
  "revision=$REVISION" \
  'test=aon_timer_smoke' \
  'uvm_test_seq=aon_timer_smoke_vseq' \
  'fixed_seed=42' \
  'reseed=1' \
  'coverage_enabled=true (--cov -> cov build mode; per-run VCS 2019 compatibility merges the coverage configs, removes unsupported -cm_common_hier, and removes xmerge performance-only -xprop=mmsopt)' \
  'max_parallel=1' \
  'retry_on_failure=false (--no-rerun)' \
  'build_input=per-run copy of the locked source tree' \
  'simulator=VCS P-2019.06-SP1' \
  'reporter=URG P-2019.06-SP1 / CovDB 13.1' \
  'scratch_isolated=true' > "$EVIDENCE/run_manifest.txt"
sha256sum "$CFG" "$SOURCE/hw/ip/aon_timer/dv/aon_timer_sim.core" \
  "$SOURCE/hw/ip/aon_timer/dv/env/aon_timer_env_cov.sv" \
  "$VCS_CFG" \
  "$COMMON_SIM_CFG" \
  "$COVER_CFG" "$COMMON_COV_EXCL_CFG" "$MERGED_COV_CFG" \
  > "$EVIDENCE/input_sha256.txt"

printf '%s\n' \
  'env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 timeout --signal=TERM --kill-after=30s 5400s' \
  '  <venv-python> -B <revision-source>/util/dvsim/dvsim.py' \
  '  <revision-source>/hw/ip/aon_timer/dv/aon_timer_sim_cfg.hjson' \
  '  --proj-root <revision-source> --branch stage03 --local' \
  '  --scratch-root <new-run-scratch>/dvsim --max-parallel 1' \
  '  --items aon_timer_smoke --cov --fixed-seed 42 --no-rerun' \
  '  --max-odirs 1 --build-timeout-mins 120 --run-timeout-mins 30' \
  'compatibility_patch=merge the two VCS coverage configs into one; remove -cm_common_hier and -xprop=mmsopt from per-run DVSim config copies' \
  > "$EVIDENCE/command.txt"

timeout --signal=TERM --kill-after=30s 5400s \
  env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 \
  "$VENV/bin/python" -B "$DV_SIM" "$CFG" \
  --proj-root "$SOURCE" --branch stage03 --local \
  --scratch-root "$SCRATCH/dvsim" --max-parallel 1 \
  --items aon_timer_smoke --cov --fixed-seed 42 --no-rerun \
  --max-odirs 1 --build-timeout-mins 120 --run-timeout-mins 30 \
  > "$EVIDENCE/dvsim.log" 2>&1
RC=$?
printf '%s\n' "$RC" > "$EVIDENCE/return_code.txt"
sha256sum "$EVIDENCE"/* > "$EVIDENCE/SHA256SUMS"
printf 'DVSIM_EXIT_CODE=%s\n' "$RC"
exit "$RC"

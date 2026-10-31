#!/usr/bin/env bash
# Execute one immutable Stage 06 initial-corpus submission set.
set -uo pipefail
umask 077

ROOT="${HOME}/opentitan_aon_timer_4525bin_repro"
RUN_ID="${1:?Usage: bash run_initial_corpus.sh RUN_ID ITEM [ITEM ...]}"
shift
(( $# > 0 )) || { echo "MISSING_ITEMS"; exit 64; }
[[ "$RUN_ID" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "BAD_RUN_ID"; exit 64; }
for item in "$@"; do
  [[ "$item" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "BAD_ITEM"; exit 64; }
done
ITEMS=("$@")

REVISION="9f20940d494a223cc950a5b98f748fb28109d458"
SOURCE_LOCKED="$ROOT/src/opentitan-$REVISION-gitblob"
VENV="$ROOT/.venv-opentitan"
export PATH="$VENV/bin:$PATH"
LOCK_TOOL="$ROOT/project/stage06/stage02_lock.py"
SOURCE_LOCK="$ROOT/project/stage06/source_lock.json"
SCRATCH="$ROOT/scratch/06/$RUN_ID"
EVIDENCE="$ROOT/evidence/06_initial/$RUN_ID"

test -d "$SOURCE_LOCKED" || { echo "MISSING_SOURCE"; exit 66; }
test -x "$VENV/bin/python" || { echo "MISSING_VENV"; exit 66; }
test -f "$LOCK_TOOL" || { echo "MISSING_SOURCE_VERIFIER"; exit 66; }
test -f "$SOURCE_LOCK" || { echo "MISSING_SOURCE_LOCK"; exit 66; }
command -v vcs >/dev/null || { echo "MISSING_VCS"; exit 66; }
command -v urg >/dev/null || { echo "MISSING_URG"; exit 66; }
test ! -e "$SCRATCH" || { echo "RUN_SCRATCH_ALREADY_EXISTS"; exit 73; }
test ! -e "$EVIDENCE" || { echo "RUN_EVIDENCE_ALREADY_EXISTS"; exit 73; }

mkdir -p "$ROOT/scratch/06" "$ROOT/evidence/06_initial" || exit 73
mkdir "$SCRATCH" "$EVIDENCE" || exit 73
SOURCE="$SCRATCH/source"
cp -a "$SOURCE_LOCKED" "$SOURCE" || exit 74
"$VENV/bin/python" "$LOCK_TOOL" verify-directory \
  --lock "$SOURCE_LOCK" --source "$SOURCE" \
  > "$EVIDENCE/source_copy_verification.json" 2>&1 || exit 75

VCS_CFG="$SOURCE/hw/dv/tools/dvsim/vcs.hjson"
COMMON_SIM_CFG="$SOURCE/hw/dv/tools/dvsim/common_sim_cfg.hjson"
COVER_CFG="$SOURCE/hw/dv/tools/vcs/cover.cfg"
COMMON_COV_EXCL_CFG="$SOURCE/hw/dv/tools/vcs/common_cov_excl.cfg"
MERGED_COV_CFG="$SOURCE/hw/dv/tools/vcs/stage06_vcs2019_cov.cfg"
REG_COVER_CFG="$SOURCE/hw/dv/tools/vcs/cover_reg_top.cfg"
MERGED_REG_COV_CFG="$SOURCE/hw/dv/tools/vcs/stage06_vcs2019_cover_reg_top.cfg"
ORIGINAL_VCS_CFG_SHA256=$(sha256sum "$VCS_CFG" | awk '{print $1}')
ORIGINAL_COMMON_SIM_CFG_SHA256=$(sha256sum "$COMMON_SIM_CFG" | awk '{print $1}')
grep -Eq '^[[:space:]]*"-cm_common_hier",[[:space:]]*$' "$VCS_CFG" || { echo "EXPECTED_UNSUPPORTED_VCS_OPTION_NOT_FOUND"; exit 76; }
sed -i '/^[[:space:]]*"-cm_common_hier",[[:space:]]*$/d' "$VCS_CFG"
grep -Eq '"-xprop=mmsopt"' "$VCS_CFG" || { echo "EXPECTED_UNSUPPORTED_XPROP_OPTION_NOT_FOUND"; exit 76; }
sed -i 's/"-xprop=mmsopt"//g' "$VCS_CFG"
grep -Eq 'default_vcs_cov_cfg_file:.*cover\.cfg\+.*common_cov_excl\.cfg' "$COMMON_SIM_CFG" || { echo "EXPECTED_UNSUPPORTED_COVERAGE_HIER_FORMAT_NOT_FOUND"; exit 76; }
cat "$COMMON_COV_EXCL_CFG" "$COVER_CFG" > "$MERGED_COV_CFG" || exit 76
cat "$COMMON_COV_EXCL_CFG" "$REG_COVER_CFG" > "$MERGED_REG_COV_CFG" || exit 76
sed -i \
  -e 's#^[[:space:]]*default_vcs_cov_cfg_file:.*$#  default_vcs_cov_cfg_file: "-cm_hier {dv_root}/tools/vcs/stage06_vcs2019_cov.cfg"#' \
  -e 's#^[[:space:]]*cover_reg_top_vcs_cov_cfg_file:.*$#  cover_reg_top_vcs_cov_cfg_file: "-cm_hier {dv_root}/tools/vcs/stage06_vcs2019_cover_reg_top.cfg"#' \
  "$COMMON_SIM_CFG"
PATCHED_VCS_CFG_SHA256=$(sha256sum "$VCS_CFG" | awk '{print $1}')
PATCHED_COMMON_SIM_CFG_SHA256=$(sha256sum "$COMMON_SIM_CFG" | awk '{print $1}')
MERGED_COV_CFG_SHA256=$(sha256sum "$MERGED_COV_CFG" | awk '{print $1}')
MERGED_REG_COV_CFG_SHA256=$(sha256sum "$MERGED_REG_COV_CFG" | awk '{print $1}')

CFG="$SOURCE/hw/ip/aon_timer/dv/aon_timer_sim_cfg.hjson"
DV_SIM="$SOURCE/util/dvsim/dvsim.py"
printf '%s\n' \
  'schema=stage06-initial-corpus-v1-vcs2019-compat' \
  "run_id=$RUN_ID" "revision=$REVISION" "items=$*" \
  'fixed_seed=42' 'reseed=1 (dvsim --fixed-seed 42)' \
  'coverage_enabled=true (--cov -> cov build mode)' 'max_parallel=1' \
  'retry_on_failure=false (--no-rerun)' 'build_input=per-run copy of the locked source tree' \
  'simulator=VCS P-2019.06-SP1' 'reporter=URG P-2019.06-SP1 / CovDB 13.1' \
  'compatibility_patch=vcs-2019-legacy-option-adaptation-v3' \
  "original_vcs_hjson_sha256=$ORIGINAL_VCS_CFG_SHA256" "patched_vcs_hjson_sha256=$PATCHED_VCS_CFG_SHA256" \
  "original_common_sim_cfg_sha256=$ORIGINAL_COMMON_SIM_CFG_SHA256" "patched_common_sim_cfg_sha256=$PATCHED_COMMON_SIM_CFG_SHA256" \
  "merged_cov_cfg_sha256=$MERGED_COV_CFG_SHA256" > "$EVIDENCE/run_manifest.txt"
printf 'merged_cover_reg_top_cov_cfg_sha256=%s\n' "$MERGED_REG_COV_CFG_SHA256" >> "$EVIDENCE/run_manifest.txt"
sha256sum "$CFG" "$SOURCE/hw/ip/aon_timer/dv/aon_timer_sim.core" \
  "$SOURCE/hw/ip/aon_timer/dv/env/aon_timer_env_cov.sv" "$VCS_CFG" "$COMMON_SIM_CFG" \
  "$COVER_CFG" "$REG_COVER_CFG" "$COMMON_COV_EXCL_CFG" "$MERGED_COV_CFG" "$MERGED_REG_COV_CFG" > "$EVIDENCE/input_sha256.txt"
cat > "$EVIDENCE/command.txt" <<EOF
 timeout --signal=TERM --kill-after=30s 10800s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1
   $VENV/bin/python -B $DV_SIM $CFG --proj-root $SOURCE --branch stage06 --local
   --scratch-root $SCRATCH/dvsim --max-parallel 1 --items ${ITEMS[*]} --cov --fixed-seed 42
   --no-rerun --max-odirs 1 --build-timeout-mins 120 --run-timeout-mins 180
EOF
timeout --signal=TERM --kill-after=30s 10800s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 \
  "$VENV/bin/python" -B "$DV_SIM" "$CFG" --proj-root "$SOURCE" --branch stage06 --local \
  --scratch-root "$SCRATCH/dvsim" --max-parallel 1 --items "${ITEMS[@]}" --cov --fixed-seed 42 \
  --no-rerun --max-odirs 1 --build-timeout-mins 120 --run-timeout-mins 180 \
  > "$EVIDENCE/dvsim.log" 2>&1
RC=$?
printf '%s\n' "$RC" > "$EVIDENCE/return_code.txt"
printf 'DVSIM_EXIT_CODE=%s\n' "$RC"
exit "$RC"

\n
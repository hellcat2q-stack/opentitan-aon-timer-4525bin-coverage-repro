#!/usr/bin/env bash
# Run the registered Stage 06 initial corpus once per candidate, in order.
set -uo pipefail
umask 077
ROOT="${HOME}/opentitan_aon_timer_4525bin_repro"
BASE_RUN="${1:-20261101_initial}"
[[ "$BASE_RUN" =~ ^[A-Za-z0-9_-]+$ ]] || { echo BAD_RUN_ID; exit 64; }
BUNDLE="$ROOT/project/stage06"
STATUS_DIR="$ROOT/evidence/06_initial/$BASE_RUN"
STATUS="$STATUS_DIR/status.tsv"
LAUNCH_LOG="$STATUS_DIR/launcher.log"
mkdir -p "$STATUS_DIR" || exit 73
test ! -e "$STATUS" || { echo "INITIAL_CORPUS_ALREADY_STARTED"; exit 73; }
printf 'index\titem\trun_id\tstarted_utc\tfinished_utc\treturn_code\n' > "$STATUS"
: > "$LAUNCH_LOG"
items=(
  aon_timer_smoke aon_timer_prescaler aon_timer_jump
  aon_timer_csr_hw_reset aon_timer_csr_rw aon_timer_csr_bit_bash aon_timer_csr_aliasing
  aon_timer_same_csr_outstanding aon_timer_csr_mem_rw_with_rand_reset
  aon_timer_mem_walk aon_timer_mem_partial_access aon_timer_intr_test
  aon_timer_tl_errors aon_timer_tl_intg_err aon_timer_sec_cm
  aon_timer_stress_all aon_timer_stress_all_with_rand_reset
)
overall=0
index=0
for item in "${items[@]}"; do
  index=$((index + 1))
  run_id=$(printf '%s_%02d_%s' "$BASE_RUN" "$index" "$item")
  start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  if [[ -e "$ROOT/scratch/06/$run_id" || -e "$ROOT/evidence/06_initial/$run_id" ]]; then
    rc=73
    printf '%s\n' "EXISTING_RUN=$run_id" >> "$LAUNCH_LOG"
  else
    printf 'START %s %s\n' "$run_id" "$start" >> "$LAUNCH_LOG"
    bash "$BUNDLE/run_initial_corpus.sh" "$run_id" "$item" >> "$LAUNCH_LOG" 2>&1
    rc=$?
    printf 'END %s rc=%s\n' "$run_id" "$rc" >> "$LAUNCH_LOG"
  fi
  finish=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$index" "$item" "$run_id" "$start" "$finish" "$rc" >> "$STATUS"
  [[ "$rc" -eq 0 ]] || overall=1
done
printf 'overall_return_code=%s\n' "$overall" >> "$LAUNCH_LOG"
exit "$overall"

#!/usr/bin/env bash
# Execute only inside the NEW experiment root; never reuse old experiment data.
set -uo pipefail
umask 077
ROOT="${HOME}/opentitan_aon_timer_4525bin_repro"
RUN_ID="${1:?Usage: bash run_capability_probe.sh UNIQUE_RUN_ID}"
[[ "$RUN_ID" =~ ^[A-Za-z0-9_-]+$ ]] || exit 64
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$ROOT/scratch/01/$RUN_ID"
EVIDENCE="$ROOT/evidence/01_env/$RUN_ID"
mkdir "$WORK" || exit 73
mkdir "$EVIDENCE" || exit 73
cp "$SCRIPT_DIR/capability_probe.sv" "$WORK/"
cd "$WORK" || exit 73
: > "$EVIDENCE/commands.sh"
: > "$EVIDENCE/return_codes.tsv"
run_step() {
  local label="$1"
  shift
  printf '%q ' "$@" >> "$EVIDENCE/commands.sh"
  printf '\n' >> "$EVIDENCE/commands.sh"
  "$@" > "$EVIDENCE/$label.log" 2>&1
  local rc=$?
  printf '%s\t%s\n' "$label" "$rc" >> "$EVIDENCE/return_codes.tsv"
  printf '%s_RC=%s\n' "$label" "$rc"
  return "$rc"
}
# Preserve the school's license settings. Remove only the inherited preload
# entries that point to missing libraries; do not edit shell startup files.
run_step build timeout --signal=TERM --kill-after=10s 300s env -u LD_PRELOAD \
  vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
  -top capability_probe -cm line -cm_dir "$WORK/probe.vdb" \
  -o "$WORK/simv" capability_probe.sv || exit 10
run_step full timeout --signal=TERM --kill-after=10s 120s env -u LD_PRELOAD \
  "$WORK/simv" +ntb_random_seed=42 -cm line -cm_dir "$WORK/probe.vdb" \
  -cm_name full_seed42 || exit 11
run_step partial timeout --signal=TERM --kill-after=10s 120s env -u LD_PRELOAD \
  "$WORK/simv" +ntb_random_seed=42 +PROBE_PARTIAL -cm line \
  -cm_dir "$WORK/probe.vdb" -cm_name partial_seed42 || exit 12
# URG 2019 reports fully qualified logical names (not bare -cm_name values).
# Resolve exactly what the installed tool reports, rather than guessing paths.
run_step urg_available timeout --signal=TERM --kill-after=10s 120s \
  env -u LD_PRELOAD urg -full64 -dir "$WORK/probe.vdb" \
  -show availabletests || exit 13
grep '/full_seed42$' "$EVIDENCE/urg_available.log" > "$WORK/full.tests"
grep '/partial_seed42$' "$EVIDENCE/urg_available.log" > "$WORK/partial.tests"
test "$(wc -l < "$WORK/full.tests")" -eq 1 || exit 14
test "$(wc -l < "$WORK/partial.tests")" -eq 1 || exit 14
for case_name in full partial; do
  run_step "urg_${case_name}" timeout --signal=TERM --kill-after=10s 120s \
    env -u LD_PRELOAD urg -full64 -dir "$WORK/probe.vdb" \
    -tests "$WORK/${case_name}.tests" -metric group -format both \
    -show ratios -group ratio -report "$WORK/report_${case_name}" || exit 13
done
sha256sum capability_probe.sv > "$EVIDENCE/source.sha256"
printf 'CAPABILITY_COMMANDS_FINISHED\n'

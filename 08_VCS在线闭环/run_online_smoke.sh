#!/usr/bin/env bash
# Execute one real VCS feedback smoke selected by the Stage 07 scheduler.
set -uo pipefail
umask 077
ROOT="${HOME}/opentitan_aon_timer_4525bin_repro"
RUN_ID="${1:?Usage: bash run_online_smoke.sh RUN_ID ITEM}"
ITEM="${2:?Usage: bash run_online_smoke.sh RUN_ID ITEM}"
[[ "$RUN_ID" =~ ^[A-Za-z0-9_-]+$ ]] || exit 64
[[ "$ITEM" =~ ^[A-Za-z0-9_-]+$ ]] || exit 64
bash "$ROOT/project/stage06/run_initial_corpus.sh" "$RUN_ID" "$ITEM" || exit $?
bash "$ROOT/project/stage06/extract_initial_vectors.sh" "$RUN_ID" "$ITEM" || exit $?
echo "STAGE08_ONLINE_VCS_SMOKE=PASS"

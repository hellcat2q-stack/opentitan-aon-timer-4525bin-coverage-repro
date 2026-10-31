#!/usr/bin/env bash
# Build sanitized per-test 4525-bin vectors from one completed Stage 06 run.
set -uo pipefail
umask 077
ROOT="${HOME}/opentitan_aon_timer_4525bin_repro"
RUN_ID="${1:?Usage: bash extract_initial_vectors.sh RUN_ID ITEM [ITEM ...]}"
shift
(( $# > 0 )) || { echo "MISSING_ITEMS"; exit 64; }
for item in "$@"; do [[ "$item" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "BAD_ITEM"; exit 64; }; done
REVISION="9f20940d494a223cc950a5b98f748fb28109d458"
VENV="$ROOT/.venv-opentitan"
BUNDLE="$ROOT/project/stage06"
R="$ROOT/scratch/06/$RUN_ID"
E="$ROOT/evidence/06_initial/$RUN_ID"
C="$R/dvsim/stage06/aon_timer-sim-vcs"
if [[ -d "$C/coverage/default.vdb" ]]; then
  VDB="$C/coverage/default.vdb"
elif [[ -d "$C/coverage/cover_reg_top.vdb" ]]; then
  VDB="$C/coverage/cover_reg_top.vdb"
else
  echo "MISSING_COVERAGE_VDB"
  exit 66
fi
PUB="$E/public_vectors"
test -d "$R" || { echo "MISSING_RUN"; exit 66; }
test -d "$VDB" || { echo "MISSING_VDB"; exit 66; }
test -f "$E/return_code.txt" || { echo "MISSING_RETURN_CODE"; exit 66; }
test "$(cat "$E/return_code.txt")" = 0 || { echo "RUN_NOT_SUCCESSFUL"; exit 66; }
test ! -e "$PUB" || { echo "PUBLIC_VECTOR_OUTPUT_EXISTS"; exit 73; }
mkdir "$PUB" "$R/urg" || exit 73
summary="$PUB/run_summary.tsv"
printf 'item\ttest_dir\tseed\texpected_bins\thit_bins\tcoverage_percent\tvector_sha256\n' > "$summary"
for item in "$@"; do
  test_dir=$(find "$VDB/snps/coverage/db/testdata" -mindepth 1 -maxdepth 1 -type d -name "*.${item}.42" -printf '%f\n')
  test "$(printf '%s\n' "$test_dir" | wc -l)" = 1 || { echo "TEST_DATA_NOT_UNIQUE_$item"; exit 77; }
  coverage_mode="${VDB##*/}"
  coverage_mode="${coverage_mode%.vdb}"
  test_path="$C/coverage/$coverage_mode/$test_dir"
  filter="$R/urg/${item}.tests"
  printf '%s\n' "$test_path" > "$filter"
  full="$R/urg/${item}.full"
  expanded="$R/urg/${item}.expanded"
  urg -lca -full64 +urg+lic+wait -show tests -grade index testfile \
    -group ratio -group lrm_bin_name -group instcov_for_score -dir "$VDB" \
    -tests "$filter" -format text -report "$full" > "$R/urg/${item}.full.log" 2>&1 || exit 78
  urg -lca -full64 +urg+lic+wait -show brief group -group expand_bins \
    -group ratio -group lrm_bin_name -group instcov_for_score -dir "$VDB" \
    -tests "$filter" -format text -report "$expanded" > "$R/urg/${item}.expanded.log" 2>&1 || exit 79
  out="$PUB/$item"
  "$VENV/bin/python" "$BUNDLE/extract_bin_vector.py" \
    --freezer "$BUNDLE/freeze_manifest.py" --static-manifest "$BUNDLE/coverage_manifest.v1.json" \
    --full-groups "$full/groups.txt" --full-grpinfo "$full/grpinfo.txt" \
    --expanded-grpinfo "$expanded/grpinfo.txt" \
    --cumulative "$VDB/snps/coverage/db/testdata/$test_dir/testbench.cumulative.xml" \
    --instance "$VDB/snps/coverage/db/testdata/$test_dir/testbench.inst.xml" \
    --item "$item" --seed 42 --output "$out" > "$R/urg/${item}.vector.log" 2>&1 || { cat "$R/urg/${item}.vector.log"; exit 80; }
  values=$("$VENV/bin/python" - "$out/vector_summary.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
print(x['expected_bins'],x['hit_bins'],x['coverage_percent'],x['vector_sha256'])
PY
)
  printf '%s\t%s\t42\t%s\t%s\t%s\t%s\n' "$item" "$test_dir" $values >> "$summary"
done
printf '%s\n' "$@" | sha256sum | awk '{print $1}' > "$PUB/items_sha256.txt"
find "$PUB" -type f ! -name SHA256SUMS -print0 \
  | sort -z \
  | xargs -0 sha256sum > "$PUB/SHA256SUMS"
echo "STAGE06_VECTOR_EXTRACTION=PASS"

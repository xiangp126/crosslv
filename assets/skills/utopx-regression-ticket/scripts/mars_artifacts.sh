#!/bin/bash
# Extract the MARS per-case artifacts of a failing node and name them for upload.
#
# The failing key_id node (<case>.6.1) holds only status.txt, log.txt and run_case.cap; the other
# artifacts sit in sibling nodes of the same case (<case>.<N>.1/). Each <artifact>.cap is MARS
# metadata; the artifact itself is the log.txt next to it. One tar listing plus one tar extract,
# no full unpack.
#
# Output in <outdir>:
#   <artifact>_<key_id>.log      one per artifact (expect ten)
#   manifest.tsv                 <file><TAB><description>, the input of post_ticket.py note
set -u

usage() {
  cat <<'EOF'
usage: mars_artifacts.sh <setup_id> <session_id> <key_id> <outdir>

  setup_id    MARS setup dir name, e.g. BRONCO_FW-m-fwreg-029_DPU_MODE_P1
  session_id  e.g. 11631323
  key_id      the failing run_case node, e.g. 0.15.1.1.1.9.2.6.22.6.1
  outdir      created if missing; append your own files to its manifest.tsv afterwards

  KEEP_STAGE=1 keeps <outdir>/stage (the raw extracted nodes).
EOF
  exit 1
}

[ $# -eq 4 ] || usage
SETUP=$1; SES=$2; KEY=$3; OUT=$4
ARCHIVE=/.autodirect/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results
T="$ARCHIVE/$SETUP/$SES/$SES.tgz"
[ -f "$T" ] || { echo "no archive: $T (MARS keeps about 12 days)" >&2; exit 2; }
case "$KEY" in
  *.6.1) ;;
  *) echo "key_id must be the run_case node, ending in .6.1: $KEY" >&2; exit 2 ;;
esac
CASE=${KEY%.*.*}                      # 0.15.1.1.1.9.2.6.22.6.1 -> 0.15.1.1.1.9.2.6.22

mkdir -p "$OUT/stage" || exit 2
re="^${CASE//./\\.}\\.[0-9]+\\.1/(log\\.txt|[a-z0-9_]+\\.cap)\$"
echo "== listing $T (about a minute per GB)" >&2
mapfile -t M < <(tar tzf "$T" 2>/dev/null | grep -E "$re")
[ ${#M[@]} -gt 0 ] || { echo "no members under $CASE.<N>.1/ in $T" >&2; exit 3; }
tar xzf "$T" -C "$OUT/stage" "${M[@]}" || { echo "tar extract failed" >&2; exit 3; }

describe() {                          # $1 = artifact name, $2 = file
  case "$1" in
    custom_post_checker) echo "custom post checker" ;;
    fw_reset)            echo "fw_reset step" ;;
    query_mlxconfig)     echo "NV config dump" ;;
    mstdump_[0-9]*)      echo "mstdump ${1#mstdump_}" ;;
    run_case)
      local c
      c=$(grep -aoE -- '--case_name [A-Za-z0-9_]+' "$2" | head -1 | awk '{print $2}')
      echo "Failing case log (${c:-run_case}, session $SES)" ;;
    *)                   echo "$1" ;;
  esac
}

rows=()
for cap in "$OUT/stage/$CASE".*.1/*.cap; do
  [ -f "$cap" ] || continue
  a=$(basename "$cap" .cap); d=$(dirname "$cap")
  [ -f "$d/log.txt" ] || { echo "WARN no log.txt next to $cap" >&2; continue; }
  f="${a}_${KEY}.log"
  cp "$d/log.txt" "$OUT/$f"
  rows+=("$f"$'\t'"$(describe "$a" "$OUT/$f")")
done
printf '%s\n' "${rows[@]}" | sort > "$OUT/manifest.tsv"
[ "${KEEP_STAGE:-0}" = 1 ] || rm -rf "$OUT/stage"

n=${#rows[@]}
echo "== $n artifact(s) in $OUT; manifest: $OUT/manifest.tsv" >&2
cut -f1 "$OUT/manifest.tsv" | sed 's/^/   /' >&2
for a in custom_post_checker dmesg dump_file fw_reset mstdump_1 mstdump_2 mstdump_3 oplist query_mlxconfig run_case; do
  [ -f "$OUT/${a}_${KEY}.log" ] || echo "WARN missing: $a" >&2
done
[ "$n" -gt 0 ]

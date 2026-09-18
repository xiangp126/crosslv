#!/bin/bash
# session_id -> the original failure log, in three hops. No authentication at any step.
#   1. https://mars.nvidia.com/api/session/<id>  (XML; the /ui/ page 302s to a login, the API does not)
#   2. <RESULT_DIR>/<setup name>(...)/<id>/<id>.tgz  -- readable directly over NFS
#   3. unpack, then find every 'result: 1' node that has a SIBLING log.txt
#
# Hop 3 is the one people get wrong: the tree is uneven, so a "deepest path" search
# stops at an intermediate node while the real leaves sit far deeper. Parent nodes
# merely propagate failure upward.
set -euo pipefail

SID=""
WORKDIR=""
KEEP=0

usage() {
  cat <<'EOF'
Usage: mars_fetch.sh <session_id> [-d workdir] [--keep]

  -d, --dir DIR   where to unpack (default: ./mars_<session_id>)
      --keep      keep an existing unpacked tree instead of re-extracting
  -h, --help

Prints the session verdict, then one directory per genuinely failed case.
Each of those holds a log.txt with the raw UFATAL / "Field mismatch: expected=X
Actual=Y" / "To rerun use seed N".

result codes in status.txt:  0 = pass, 1 = fail, 2 = not executed

RESULT_DIR differs per session (different devices land in different setup sets) --
this script reads it fresh every time; never reuse the one from another session.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -d|--dir) WORKDIR="$2"; shift 2 ;;
    --keep)   KEEP=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "unknown argument: $1" >&2; usage; exit 2 ;;
    *) SID="$1"; shift ;;
  esac
done

[ -n "$SID" ] || { usage; exit 2; }
WORKDIR="${WORKDIR:-./mars_$SID}"

echo "== hop 1: session metadata"
XML=$(curl -sf "https://mars.nvidia.com/api/session/$SID") || {
  echo "MARS API request failed for session $SID" >&2; exit 1; }

eval "$(printf '%s' "$XML" | python3 -c '
import sys, re
x = sys.stdin.read()
def tag(t):
    m = re.search(r"<%s>(.*?)</%s>" % (t, t), x, re.S)
    return m.group(1).strip() if m else ""
print("RESULT_DIR=%r" % tag("RESULT_DIR"))
for t in ("PASSED", "FAILED", "IGNORED", "NATIVE_STATUS"):
    print("%s=%r" % (t, tag(t)))
')"

echo "   PASSED=${PASSED:-?} FAILED=${FAILED:-?} IGNORED=${IGNORED:-?} NATIVE_STATUS=${NATIVE_STATUS:-?}"
echo "   RESULT_DIR=${RESULT_DIR:-<empty>}"
echo "   (check these first: they distinguish 'ran and then failed' from 'never got started')"

[ -n "${RESULT_DIR:-}" ] || { echo "no RESULT_DIR in the response -- session may never have started" >&2; exit 1; }

echo "== hop 2: locating the archive"
# The setup directory carries a parenthesised suffix you will not guess -- always find it.
TGZ=$(find "$RESULT_DIR" -maxdepth 3 -name "$SID.tgz" 2>/dev/null | head -1)
[ -n "$TGZ" ] || { echo "no $SID.tgz under $RESULT_DIR" >&2; exit 1; }
echo "   $TGZ"

if [ -d "$WORKDIR" ] && [ "$KEEP" -eq 1 ]; then
  echo "== hop 3: reusing $WORKDIR"
else
  mkdir -p "$WORKDIR"
  echo "== hop 3: unpacking into $WORKDIR"
  tar xzf "$TGZ" -C "$WORKDIR"
fi

echo
echo "== failed cases (result: 1 AND a sibling log.txt)"
FOUND=0
while IFS= read -r f; do
  d=$(dirname "$f")
  if [ -f "$d/log.txt" ]; then
    FOUND=$((FOUND + 1))
    echo "--- $d/log.txt"
    grep -m3 -E 'UFATAL|Field mismatch|To rerun use seed' "$d/log.txt" 2>/dev/null | sed 's/^/      /' || true
  fi
done < <(grep -rl '^result: 1' "$WORKDIR" --include=status.txt 2>/dev/null)

if [ "$FOUND" -eq 0 ]; then
  echo "   none. Either the failure happened in setup/init (never reached case level --"
  echo "   fsearch would not record it either), or the archive layout differs. Look manually:"
  echo "     grep -rl '^result: 1' $WORKDIR --include=status.txt"
else
  echo
  echo "$FOUND failed case(s). Before calling this environmental or ours, find a control"
  echo "sample matching on branch + mode + setup. Log size and node-offlining are NOT evidence."
fi

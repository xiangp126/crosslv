#!/bin/bash
# per_run.sh - one test run of a task on its reg box; the verdict is the exit code.
#
# Template: skill regression-repro, templates/lab-box/ (procedure.md Phase 9b). The task's settings
# and hooks live in lab.conf next to this file; --lab picks another conf.
#
# Runs ON THE REG BOX as yourself (sudo is used inside), once per attempt. No burn, no power-cycle:
# that is env_rebuild.sh. Flow: guards -> FW gate -> baseline gate (PCI classes, NV Current) ->
# pre-run reset -> run, with the post-run reset in an EXIT trap -> PCI and kernel-log evidence ->
# multi-factor verdict.
#
# Usage: per_run.sh [--seed N] [--iter N] [--ops N] [--conf_file F] [-U utopx.exe] [-e KEY=VAL]...
#                   [--feature-off] [--no-reset] [--any-fw] [--lab FILE]
#
# Exit codes (the verdict - wrappers rely on them):
#   0  what MODE is after: feature = new path ran and the run passed; repro = signature seen;
#      fixverify = trigger present, signature absent, run passed
#   1  a guard or gate refused to run              2  usage
#   3  RUN VOID: the tool never initialised (feature: or did no work)
#   4  not a valid test: a control run entered the new path, or the fixverify trigger was absent
#   5  what MODE is after did not happen: feature = OLD PATH ONLY; repro = NOT REPRODUCED;
#      fixverify = signature still there
#   6  failed in some other way: tool rc != 0, no TEST PASSED, FATAL lines, or kernel errors
#   7  post-run reset failed on a run that would otherwise exit 0          130  interrupted
set -u

LAB=$(dirname "$(readlink -f "$0")")/lab.conf
ARG_SEED=; ARG_ITER=; ARG_OPS=; ARG_CONF=; ARG_UTOPX=
EXTRA=()
FEATURE=1
DO_RESET=1
ANY_FW=0
while [ $# -gt 0 ]; do
    case "$1" in
        --seed) ARG_SEED=$2; shift 2 ;;
        --iter) ARG_ITER=$2; shift 2 ;;
        --ops)  ARG_OPS=$2; shift 2 ;;
        --conf_file) ARG_CONF=$2; shift 2 ;;
        -U) ARG_UTOPX=$2; shift 2 ;;
        -e) EXTRA+=(-e "$2"); shift 2 ;;
        --feature-off) FEATURE=0; shift ;;
        --no-reset) DO_RESET=0; shift ;;
        --any-fw) ANY_FW=1; shift ;;
        --lab) LAB=$2; shift 2 ;;
        -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

RED='\033[31m'; GREEN='\033[32m'; YELLOW='\033[93m'; BOLD='\033[1m'; CYAN='\033[36m'
GREY='\033[90m'; RESET='\033[0m'
hdr()  { printf "\n${BOLD}${CYAN}=== %s ===${RESET}\n" "$1"; }
step() { printf "${BOLD}>>> %s${RESET}\n" "$1"; }
ok()   { printf "${GREEN}    OK   %s${RESET}\n" "$1"; }
warn() { printf "${YELLOW}    WARN %s${RESET}\n" "$1"; }
err()  { printf "${RED}    ERR  %s${RESET}\n" "$1"; }
note() { printf "${GREY}    %s${RESET}\n" "$1"; }
die()  { err "$1"; exit 1; }

JMAKE=$HOME/.usr/bin/jmake
NOGA_CLI=/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py
INIT_RE='To rerun use seed|GeneralRandomTest|TEST Modes:'
PROGRESS_RE='LOG_OP'
FAIL_RE='FATAL|Field mismatch'
KERNEL_ERR_RE='DMA (Read|Write)|fault addr|IO_PAGE_FAULT|Call Trace|BUG:|soft lockup|blocked for more than'

# nv_check current PARAM=value...: compare the Current column of `mlxconfig -e q` with the wanted
# values ("ETH(2)" compares as 2). Prints every mismatch; returns 1 if there is any.
nv_check() {
    local p got out bad=0
    out=$(sudo mlxconfig -d "$DEV" -e q "${@%%=*}" 2>/dev/null | sed 's/^\*//')
    for p in "$@"; do
        got=$(awk -v n="${p%%=*}" '$1 == n {print $(NF-1)}' <<<"$out" | sed 's/.*(\([0-9]*\))$/\1/')
        [ "$got" = "${p#*=}" ] || { err "${p%%=*}: current ${got:-<missing>}, want ${p#*=}"; bad=1; }
    done
    return "$bad"
}

# Bind every 15b3 function that has no driver to udriver; fail on any held by another driver.
# Never unload a driver to make room (skill fw-build-burn-utopx section 7).
bind_udriver() {
    local b drv bad=0
    sudo modprobe udriver || return 1
    for b in $(lspci -D -n -d 15b3: | awk '{print $1}'); do
        drv=$(readlink "/sys/bus/pci/devices/$b/driver"); drv=${drv##*/}
        if [ -z "$drv" ]; then
            echo "$b" | sudo tee /sys/bus/pci/drivers/udriver/bind >/dev/null 2>&1
            drv=$(readlink "/sys/bus/pci/devices/$b/driver"); drv=${drv##*/}
        fi
        [ "$drv" = udriver ] || { err "$b is on '${drv:-no driver}', not udriver"; bad=1; }
    done
    return "$bad"
}

# ------------------------------------------------------------------ hooks (lab.conf may replace them)
reset_device() { "$JMAKE" --fw-reset --device "$DEV" >"$1" 2>&1 && bind_udriver; }
run_tool() {
    sudo stdbuf -oL -eL "$UTOPX" --device="$DEV" --seed="$SEED" --daemon --num_of_clients=0 \
        --xml_conf_file "$XML_CONF" --conf_file "$CONF_FILE" --iter="$ITER" --ops_per_it="$OPS" \
        ${UTOPX_TIMEOUT:+--timeout "$UTOPX_TIMEOUT"} \
        ${FEATURE_GATE:+-e "$FEATURE_GATE=$FEATURE"} \
        ${UTOPX_ARGS[@]+"${UTOPX_ARGS[@]}"} ${EXTRA[@]+"${EXTRA[@]}"} >"$1" 2>&1
}
before_run() { :; }
report_task() { :; }
preconditions_met() { return 1; }

# ------------------------------------------------------------------ settings
VERIFIED=
CONTROL=0
FIX_COMMIT=
FEATURE_GATE=
LOGDIR=
UTOPX_TIMEOUT=
XML_CONF=conf.xml
UTOPX_ARGS=()
NV_RECIPE=()
[ -r "$LAB" ] || { echo "no lab conf: $LAB" >&2; exit 2; }
# shellcheck source=/dev/null
source "$LAB"
SEED=${ARG_SEED:-$SEED}
ITER=${ARG_ITER:-$ITER}
OPS=${ARG_OPS:-$OPS}
CONF_FILE=${ARG_CONF:-$CONF_FILE}
UTOPX=${ARG_UTOPX:-$UTOPX}
for v in HOST DEV EXPECT_FW WANT_CLASSES TASK_DIR UTOPX RUN_NAME SEED ITER OPS CONF_FILE MODE; do
    [ -n "${!v:-}" ] || { echo "$LAB does not set $v" >&2; exit 2; }
done
case "$MODE" in feature|repro|fixverify) ;; *) echo "MODE must be feature, repro or fixverify" >&2; exit 2 ;; esac
declare -F count_signal >/dev/null || { echo "$LAB must define count_signal" >&2; exit 2; }
if [ "$FEATURE" = 0 ]; then
    [ "$MODE" = feature ] && [ -n "$FEATURE_GATE" ] || { echo "--feature-off needs MODE=feature and FEATURE_GATE" >&2; exit 2; }
    CONTROL=1
fi
case "$HOST" in l-fwminireg-*) echo "refusing $HOST: CI/DoA box (global hard rule 1)" >&2; exit 2 ;; esac

UTOPX_DIR=$(dirname "$UTOPX")
LOGDIR=${LOGDIR:-$UTOPX_DIR/logs}
STAMP=$(date +%m%d_%H%M%S)
BASE=$LOGDIR/${RUN_NAME}_seed${SEED}_$STAMP
LOG=$BASE.log
mkdir -p "$LOGDIR" || exit 2
exec > >(tee -a "$BASE.out") 2>&1

hdr "per_run $RUN_NAME on $(hostname -s)  seed $SEED  $(date '+%F %T %Z')"
[ -n "$VERIFIED" ] || warn "!!! UNVERIFIED !!! no run with this conf has produced its intended outcome yet (VERIFIED= in $LAB)"
note "lab conf : $LAB (md5 $(md5sum <"$LAB" | cut -c1-12))"
note "evidence : $BASE.*"

# ------------------------------------------------------------------ guards
hdr "Guards"
[ "$(hostname -s)" = "$HOST" ] || die "run this ON $HOST (this is $(hostname -s))"
[ "$(id -u)" != 0 ] || die "run as yourself, not as root"
OWNER=$(timeout 60 python3 "$NOGA_CLI" -q -t server -n "$HOST" 2>/dev/null \
        | sed -n 's/^Status\.lock_owner *= *//p' | tr -d ' \r')
[ "$OWNER" = "$USER" ] || die "Noga lock_owner is '${OWNER:-<unreadable>}', not $USER (skill noga-lock)"
ok "Noga lock owner is $USER"
# Bounded: pgrep walks /proc, which blocks behind a D-state process.
timeout 30 pgrep -x utopx.exe >/dev/null 2>&1
case $? in
    0)   die "utopx.exe is already running" ;;
    124) die "pgrep timed out: a D-state process blocks /proc; power-cycle the box from the dev box" ;;
esac
ok "no utopx running"
[ -x "$UTOPX" ] || die "no executable tool at $UTOPX"
REAL=$(readlink -f "$UTOPX")
LIBDIR=$(dirname "$REAL" | sed 's#/artifacts/bin/#/artifacts/lib/#')
LIBS_MD5='<none found>'
ls "$LIBDIR"/*.so >/dev/null 2>&1 && LIBS_MD5=$(cat "$LIBDIR"/*.so | md5sum | cut -c1-12)
TREE=$(git -C "$UTOPX_DIR" rev-parse --short HEAD 2>/dev/null || echo '<not a git tree>')
note "tool     : $REAL"
note "identity : tree $TREE  md5 exe $(md5sum <"$REAL" | cut -c1-12)  libs $LIBS_MD5"
if [ -n "$FIX_COMMIT" ]; then
    if [ "$TREE" = '<not a git tree>' ]; then
        warn "cannot check FIX_COMMIT: $UTOPX_DIR is not a git tree"
    elif git -C "$UTOPX_DIR" merge-base --is-ancestor "$FIX_COMMIT" HEAD 2>/dev/null; then
        [ "$MODE" != repro ] || die "the tool tree contains the fix $FIX_COMMIT: it cannot reproduce the defect"
        ok "the tool tree contains the fix $FIX_COMMIT"
    else
        [ "$MODE" != fixverify ] || die "the tool tree lacks the fix $FIX_COMMIT"
        ok "the tool tree predates the fix $FIX_COMMIT"
    fi
fi

# ------------------------------------------------------------------ gates
hdr "FW"
sudo mst start >/dev/null 2>&1
[ -e "$DEV" ] || die "$DEV missing after mst start"
FWV=$(sudo flint -d "$DEV" q 2>/dev/null | awk -F': *' '/^FW Version:/{print $2; exit}')
if [ "$FWV" = "$EXPECT_FW" ]; then ok "FW $FWV"
elif [ "$ANY_FW" = 1 ]; then warn "FW ${FWV:-?}, want $EXPECT_FW (--any-fw)"
else die "FW ${FWV:-?}, want $EXPECT_FW - rebuild: env_rebuild.sh --burn, from the dev box"; fi

hdr "Baseline (anything can change the box between runs, a lock notwithstanding)"
CLASSES=$(lspci -D -n -d 15b3: | sort | awk '{print $2}' | tr -d : | xargs)
[ "$CLASSES" = "$WANT_CLASSES" ] || die "PCI classes '$CLASSES', want '$WANT_CLASSES' - rebuild with env_rebuild.sh"
ok "PCI classes $CLASSES"
if [ "${#NV_RECIPE[@]}" -gt 0 ]; then
    # shellcheck disable=SC2046
    nv_check $(printf '%s ' "${NV_RECIPE[@]}") || die "NV is not NV_RECIPE - rebuild with env_rebuild.sh --burn"
    ok "NV_RECIPE current"
fi

hdr "Pre-run reset"
if [ "$DO_RESET" = 1 ]; then
    reset_device "$BASE.reset_pre.log" || die "pre-run reset failed - see $BASE.reset_pre.log"
    ok "reset done"
else
    warn "--no-reset: the result holds only if the device was reset by hand"
fi

# ------------------------------------------------------------------ run
post_run_reset() {
    [ "$DO_RESET" = 1 ] || return 0
    local t=0
    while pgrep -x utopx.exe >/dev/null 2>&1; do
        [ "$t" -lt 60 ] || { err "post-run reset NOT done: utopx.exe still running after 60 s"; return 1; }
        sleep 2
        t=$((t + 2))
    done
    step "post-run reset"
    reset_device "$BASE.reset_post.log" && { ok "post-run reset done"; return 0; }
    err "post-run reset FAILED - see $BASE.reset_post.log"
    return 1
}
on_exit() {
    local rc=$?
    trap - EXIT
    if ! post_run_reset && [ "$rc" = 0 ]; then
        rc=7
    fi
    exit "$rc"
}

lspci -D -nn -d 15b3: | sort >"$BASE.pci_before.txt"
MARK="per_run $RUN_NAME seed $SEED $STAMP"
echo "$MARK" | sudo tee /dev/kmsg >/dev/null
trap on_exit EXIT
trap 'exit 130' INT TERM

hdr "Run"
note "mode $MODE$([ "$CONTROL" = 1 ] && echo ' (control: the new path must stay dark)')  conf $CONF_FILE  iter $ITER  ops $OPS"
note "extra    : ${UTOPX_ARGS[*]-} ${EXTRA[*]-}"
note "log      : $LOG"
cd "$UTOPX_DIR" || exit 1
before_run
run_tool "$LOG"
TOOL_RC=$?
note "tool exit code $TOOL_RC"

lspci -D -nn -d 15b3: | sort >"$BASE.pci_after.txt"
sudo dmesg | awk -v m="$MARK" 'index($0, m) {f = 1} f' >"$BASE.kmsg.log"

# ------------------------------------------------------------------ verdict
hdr "Verdict"
INIT=NO;  grep -aqE "$INIT_RE" "$LOG" && INIT=YES
PASS=NO;  grep -aq 'TEST PASSED' "$LOG" && PASS=YES
PROGRESS=$(grep -acE "$PROGRESS_RE" "$LOG" || true)
FATAL=$(grep -acE "$FAIL_RE" "$LOG" || true)
SIGNAL=$(count_signal "$LOG")
case "$SIGNAL" in ""|*[!0-9]*) die "count_signal printed '$SIGNAL', not a count - fix it in $LAB" ;; esac
if [ -s "$BASE.kmsg.log" ]; then KERR=$(grep -acE "$KERNEL_ERR_RE" "$BASE.kmsg.log" || true)
else KERR='?'; warn "the run's start marker is not in dmesg: kernel errors unknown"; fi
row() { printf '    %-34s %s\n' "$1" "$2"; }
row "tool initialised" "$INIT"
row "operations logged ($PROGRESS_RE)" "$PROGRESS"
row "tool exit code" "$TOOL_RC"
row "TEST PASSED" "$PASS"
row "FATAL / Field mismatch lines" "$FATAL"
row "kernel errors during the run" "$KERR"
row "task signal (count_signal)" "$SIGNAL"
report_task "$LOG"
if diff -q "$BASE.pci_before.txt" "$BASE.pci_after.txt" >/dev/null; then ok "PCI functions unchanged across the run"
else warn "PCI functions changed across the run:"; diff -u "$BASE.pci_before.txt" "$BASE.pci_after.txt" | sed 's/^/    /'; fi

CLEAN=NO
[ "$TOOL_RC" = 0 ] && [ "$PASS" = YES ] && [ "$FATAL" = 0 ] && [ "$KERR" = 0 ] && [ "$PROGRESS" != 0 ] && CLEAN=YES
verdict() {
    local rc=$1
    shift
    echo
    if [ "$rc" = 0 ]; then ok "$*"; else err "$*"; fi
    note "record it in $TASK_DIR/Tracking.md with $BASE.*"
    exit "$rc"
}
[ "$INIT" = YES ] || verdict 3 "RUN VOID - the tool never initialised; this run says nothing either way"
case "$MODE" in
    feature)
        [ "$PROGRESS" != 0 ] || verdict 3 "RUN VOID - the tool did no work"
        if [ "$CONTROL" = 1 ]; then
            [ "$SIGNAL" = 0 ] || verdict 4 "CONTROL INVALID - the new path ran ($SIGNAL) in a control run"
            [ "$CLEAN" = YES ] && verdict 0 "CONTROL PASSED - new path dark, run clean"
            verdict 6 "CONTROL FAILED - new path dark, run not clean"
        fi
        [ "$SIGNAL" != 0 ] || verdict 5 "OLD PATH ONLY - the new path never ran; a pass here says nothing about the feature"
        [ "$CLEAN" = YES ] && verdict 0 "NEW PATH EXERCISED ($SIGNAL), run clean"
        verdict 6 "NEW PATH EXERCISED ($SIGNAL), run not clean"
        ;;
    repro)
        [ "$SIGNAL" = 0 ] || verdict 0 "REPRO SUCCESS - the defect signature appeared ($SIGNAL)"
        [ "$CLEAN" = YES ] && verdict 5 "NOT REPRODUCED - clean run, no signature"
        verdict 6 "FAILED DIFFERENTLY - no signature, but the run is not clean"
        ;;
    fixverify)
        preconditions_met "$LOG" || verdict 4 "INCONCLUSIVE - the defect's trigger was absent; the fixed code was not exercised"
        [ "$SIGNAL" = 0 ] || verdict 5 "FIX FAILED - the signature is still there ($SIGNAL)"
        [ "$CLEAN" = YES ] && verdict 0 "FIX VERIFIED - trigger present, no signature, run clean"
        verdict 6 "no signature, but the run is not clean"
        ;;
esac

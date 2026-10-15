#!/bin/bash
# env_rebuild.sh - bring the reg box of one task back to its known-good test environment.
#
# Template: skill regression-repro, templates/lab-box/ (procedure.md Phase 9b). The task's settings
# and hooks live in lab.conf next to this file; --lab picks another conf.
#
# Runs FROM THE DEV BOX, once per lock and again after anything that reset or re-provisioned the
# box, a MARS session that took it back included.
#   default          verify only: ownership and idle guards, setup_box, then read-only gates (FW,
#                    PCI classes, NV Current)
#   --cycle [--yes]  then make it live again, image and NV untouched (power-cycle; DPU: fw-reset):
#                    loads what only a cold boot loads, e.g. a kernel module setup_box installed
#   --burn [--yes]   rebuild first: offline image gate -> mlxconfig reset + NV_RECIPE (Next Boot read
#                    back per group) -> mlxburn FW + INI -> make it live
# Use the smallest mode that covers what changed; --burn only when the image or the NV must be redone.
#
# Exit: 0 every gate passed | 1 a guard, gate or step failed | 2 usage.
# The last line is always ENV_REBUILD_RC=<rc>; the output is also kept in $TASK_DIR/logs/.
set -u
# An ssh that falls back to password auth must fail, not open ssh-askpass on the user's desktop:
# there is no TTY here and DISPLAY points at the user's X session. Every ssh below also carries
# BatchMode=yes; this line covers the tools that run ssh themselves (jmake).
unset DISPLAY

LAB=$(dirname "$(readlink -f "$0")")/lab.conf
DO_BURN=0
DO_CYCLE=0
ASSUME_YES=0
while [ $# -gt 0 ]; do
    case "$1" in
        --burn)  DO_BURN=1; shift ;;
        --cycle) DO_CYCLE=1; shift ;;
        --yes)   ASSUME_YES=1; shift ;;
        --lab)   LAB=$2; shift 2 ;;
        -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ "$DO_BURN" = 1 ] && [ "$DO_CYCLE" = 1 ] && { echo "--burn already makes the image live; drop --cycle" >&2; exit 2; }
# For setup_box: 1 when this run makes the box live again after it, so a module it installs loads.
# shellcheck disable=SC2034  # read by setup_box in lab.conf
WILL_CYCLE=$((DO_BURN | DO_CYCLE))

RED='\033[31m'; GREEN='\033[32m'; YELLOW='\033[93m'; BOLD='\033[1m'; CYAN='\033[36m'
GREY='\033[90m'; RESET='\033[0m'
hdr()  { printf "\n${BOLD}${CYAN}=== %s ===${RESET}\n" "$1"; }
step() { printf "${BOLD}>>> %s${RESET}\n" "$1"; }
ok()   { printf "${GREEN}    OK   %s${RESET}\n" "$1"; }
warn() { printf "${YELLOW}    WARN %s${RESET}\n" "$1"; }
err()  { printf "${RED}    ERR  %s${RESET}\n" "$1"; }
note() { printf "${GREY}    %s${RESET}\n" "$1"; }

RC=0
fail()   { err "$1"; RC=1; }
finish() {
    [ "$RC" = 0 ] || err "this is NOT the known-good environment - do not run tests on it"
    echo "ENV_REBUILD_RC=$RC"
    exit "$RC"
}
die()    { err "$1"; RC=1; finish; }

JMAKE=$HOME/.usr/bin/jmake
NOGA_CLI=/.autodirect/sw_tools/Internal/Noga/RELEASE/latest/cli/noga_manage.py
SSH_OPTS=(-o "BatchMode=yes" -o "StrictHostKeyChecking=no" -o "ConnectTimeout=15"
          -o "ServerAliveInterval=5" -o "ServerAliveCountMax=3")
# One multiplexed connection for the whole rebuild; SSH_TIMEOUT bounds each call (default 15 min).
SSH() {
    timeout "${SSH_TIMEOUT:-900}" ssh "${SSH_OPTS[@]}" -o ControlMaster=auto -o "ControlPath=$MUX" \
        -o ControlPersist=8h "$USER@$HOST" "$@"
}
# Close the master before the box goes down. One left behind is dead after the reboot, and an ssh
# that attaches to it hangs: ConnectTimeout does not cover a multiplexed session.
mux_close() { ssh -o "ControlPath=$MUX" -O exit "$USER@$HOST" >/dev/null 2>&1 || true; }
# The box's boot id over a fresh connection without the mux; empty while it is down or booting.
# BatchMode turns "booted, but the NFS home with authorized_keys is not mounted yet" into a failed
# attempt instead of a password prompt.
boot_id() {
    timeout 30 ssh "${SSH_OPTS[@]}" -o ControlMaster=no -o ControlPath=none "$USER@$HOST" \
        cat /proc/sys/kernel/random/boot_id 2>/dev/null
}

# nv_check next|current PARAM=value...: compare one column of `mlxconfig -e q` with the wanted
# values ("ETH(2)" compares as 2). Prints every mismatch; returns 1 if there is any.
nv_check() {
    local col=$1 p got out bad=0
    shift
    out=$(SSH "sudo mlxconfig -d $DEV -e q $(printf '%s ' "${@%%=*}")" 2>/dev/null | sed 's/^\*//')
    for p in "$@"; do
        got=$(awk -v n="${p%%=*}" -v c="$col" '$1 == n {print ((c == "next") ? $NF : $(NF-1))}' <<<"$out" \
              | sed 's/.*(\([0-9]*\))$/\1/')
        [ "$got" = "${p#*=}" ] || { err "${p%%=*}: $col ${got:-<missing>}, want ${p#*=}"; bad=1; }
    done
    return "$bad"
}

# ------------------------------------------------------------------ hooks (lab.conf may replace them)
nv_restore() {
    local g
    step "mlxconfig reset, then NV_RECIPE one group per call, Next Boot read back after each"
    SSH "sudo mlxconfig -d $DEV -y reset" >/dev/null 2>&1 || { err "mlxconfig reset failed"; return 1; }
    for g in "${NV_RECIPE[@]}"; do
        SSH "sudo mlxconfig -d $DEV -y set $g" >/dev/null 2>&1 || { err "mlxconfig set $g failed"; return 1; }
        # shellcheck disable=SC2086
        nv_check next $g || return 1
        ok "$g"
    done
}

make_live() {
    local out
    if [ "$DPU" = 1 ] && ! SSH "sudo mlxfwreset -d $DEV q 2>&1" | grep -q 'There is no supported reset-level'; then
        step "fw-reset (a DPU is not power-cycled to make an image live)"
        out=$(SSH "$JMAKE --fw-reset --device $DEV" 2>&1) || { err "jmake --fw-reset failed"; tail -5 <<<"$out"; return 1; }
        ok "fw-reset done"
        return 0
    fi
    # jmake can return before the box goes down, and the old boot still answers ssh: wait for a new
    # boot id, not for ssh.
    local before now i
    before=$(boot_id)
    [ -n "$before" ] || { err "cannot read the boot id of $HOST before the power-cycle"; return 1; }
    step "power-cycle $HOST"
    mux_close
    out=$("$JMAKE" --power-cycle "$HOST" 2>&1) || { err "jmake --power-cycle failed"; tail -5 <<<"$out"; return 1; }
    for i in $(seq 1 80); do
        sleep 15
        now=$(boot_id)
        if [ -n "$now" ] && [ "$now" != "$before" ]; then
            ok "$HOST rebooted and is back after ~$((i * 15)) s"
            return 0
        fi
    done
    err "$HOST did not come back with a new boot id within 20 min"
    return 1
}

setup_box() {
    note "udriver on the box: $(SSH 'cat /bin/udriver_commit_hash 2>/dev/null' | tr -d '[:space:]')"
}

# ------------------------------------------------------------------ settings
VERIFIED=
DPU=0
INI_REQUIRE=
NV_RECIPE=()
[ -r "$LAB" ] || { echo "no lab conf: $LAB" >&2; exit 2; }
# shellcheck source=/dev/null
source "$LAB"
for v in HOST DEV EXPECT_FW WANT_CLASSES TASK_DIR; do
    [ -n "${!v:-}" ] || { echo "$LAB does not set $v" >&2; exit 2; }
done
case "$HOST" in
    l-fwminireg-*|m-fwdev-167*) echo "refusing $HOST: CI/DoA box or the dev box (global hard rules 1, 5)" >&2; exit 2 ;;
esac
MUX=/tmp/ssh-mux-$USER@$HOST
STAMP=$(date +%m%d_%H%M%S)
mkdir -p "$TASK_DIR/logs" || exit 2
LOG=$TASK_DIR/logs/env_rebuild_${HOST}_$STAMP.log
exec > >(tee -a "$LOG") 2>&1

hdr "env_rebuild $HOST  $(date '+%F %T %Z')"
[ -n "$VERIFIED" ] || warn "!!! UNVERIFIED !!! no good environment came out of this conf yet (VERIFIED= in $LAB)"
note "lab conf : $LAB"
note "log      : $LOG"
note "image    : $EXPECT_FW  $FW_MLX + $FW_INI"
note "want     : PCI classes $WANT_CLASSES; NV ${#NV_RECIPE[@]} groups"
for g in "${NV_RECIPE[@]}"; do
    [ "$(wc -w <<<"$g")" -le 4 ] || die "NV_RECIPE group '$g': at most 4 parameters per mlxconfig call (global hard rule 2)"
done
if [ "$DO_BURN" = 1 ]; then warn "--burn: NV reset + recipe, burn, then make it live"
elif [ "$DO_CYCLE" = 1 ]; then warn "--cycle: make it live again (power-cycle; DPU: fw-reset), image and NV untouched"
else note "verify only (--cycle: also power-cycle; --burn: rebuild)"; fi

# ------------------------------------------------------------------ guards
hdr "Ownership"
OWNER=$(timeout 60 python3 "$NOGA_CLI" -q -t server -n "$HOST" 2>/dev/null \
        | sed -n 's/^Status\.lock_owner *= *//p' | tr -d ' \r')
[ "$OWNER" = "$USER" ] || die "Noga lock_owner of $HOST is '${OWNER:-<unreadable>}', not $USER - take the lock first (skill noga-lock)"
ok "Noga lock owner is $USER"

hdr "Idle"
# Bounded: listing processes walks /proc, which blocks behind a D-state process.
BUSY=$(SSH_TIMEOUT=60 SSH 'ps -eo cmd | grep -cE "[u]topx\.exe|[R]egTools|[m]ars_tests|[F]wreset|[m]lxburn"')
case $? in
    124) die "listing processes on $HOST timed out: a D-state process blocks /proc; only a power-cycle clears it" ;;
    255) die "ssh to $HOST failed" ;;
esac
[ "${BUSY:-0}" = 0 ] || die "$BUSY test or regression process(es) running on $HOST - leaving it alone"
ok "nothing running"

# ------------------------------------------------------------------ checks that may refuse, before any change
if [ "$DO_BURN" = 1 ]; then
    hdr "Rebuild checks"
    [ -r "$FW_MLX" ] || die "FW_MLX not readable: $FW_MLX"
    [ -r "$FW_INI" ] || die "FW_INI not readable: $FW_INI"
    [ -z "$INI_REQUIRE" ] || grep -qE "$INI_REQUIRE" "$FW_INI" || die "FW_INI does not match /$INI_REQUIRE/: $FW_INI"
    if [ "$ASSUME_YES" != 1 ]; then
        printf 'Reset NV, burn and make it live on %s? Type burn: ' "$HOST"
        read -r answer
        [ "$answer" = burn ] || die "not confirmed"
    fi

    step "offline image gate (mlxburn -wrimage + flint -i; does not touch the card)"
    BIN=$TASK_DIR/logs/env_rebuild_image.bin
    mlxburn -fw "$FW_MLX" -conf "$FW_INI" -wrimage "$BIN" >/dev/null 2>&1 || die "mlxburn -wrimage failed"
    IMG=$(flint -i "$BIN" q 2>/dev/null)
    IMG_VER=$(awk '/^FW Version:/{print $3}' <<<"$IMG")
    IMG_PSID=$(awk '/^PSID:/{print $2}' <<<"$IMG")
    CARD_PSID=$(SSH "sudo flint -d $DEV q 2>/dev/null" | awk '/^PSID:/{print $2}')
    note "image $IMG_VER $IMG_PSID (md5 $(md5sum <"$BIN" | cut -c1-12))   card $CARD_PSID"
    [ -n "$IMG_PSID" ] && [ "$IMG_PSID" = "$CARD_PSID" ] || die "PSID differs: image ${IMG_PSID:-?}, card ${CARD_PSID:-?}"
    [ "$IMG_VER" = "$EXPECT_FW" ] || die "image version ${IMG_VER:-?}, EXPECT_FW $EXPECT_FW"
    ok "image $IMG_VER fits PSID $IMG_PSID"
elif [ "$DO_CYCLE" = 1 ] && [ "$ASSUME_YES" != 1 ]; then
    printf 'Make %s live again (power-cycle; DPU: fw-reset), image and NV untouched? Type cycle: ' "$HOST"
    read -r answer
    [ "$answer" = cycle ] || die "not confirmed"
fi

# Before the rebuild, so a kernel module it installs is the one that loads at the power-cycle.
hdr "Box setup"
setup_box || die "setup_box failed"

# ------------------------------------------------------------------ rebuild
if [ "$DO_BURN" = 1 ]; then
    hdr "Rebuild"
    nv_restore || die "NV restore failed"

    step "mlxburn on $HOST (detached; polling its log)"
    SSH 'sudo rm -f /tmp/env_rebuild_burn.log' || die "ssh to $HOST failed"
    SSH "sudo setsid bash -c 'mlxburn -dev $DEV -fw $FW_MLX -conf $FW_INI -y > /tmp/env_rebuild_burn.log 2>&1; echo MLXBURN_EXIT=\$? >> /tmp/env_rebuild_burn.log' </dev/null >/dev/null 2>&1 &" \
        || die "could not start mlxburn"
    BURNED=0
    for _ in $(seq 1 90); do
        sleep 20
        OUT=$(SSH 'cat /tmp/env_rebuild_burn.log 2>/dev/null')
        case "$OUT" in
            *"Image burn completed successfully"*) BURNED=1; break ;;
            *-E-*|*MLXBURN_EXIT=*) err "burn failed:"; tail -5 <<<"$OUT"; die "burn failed" ;;
        esac
    done
    [ "$BURNED" = 1 ] || die "burn did not finish within 30 min"
    ok "burn completed"

    make_live || die "making the new image live failed"
elif [ "$DO_CYCLE" = 1 ]; then
    hdr "Cycle"
    make_live || die "making the box live again failed"
fi

# ------------------------------------------------------------------ verify
hdr "Verify"
SSH 'sudo mst start >/dev/null 2>&1' || die "ssh to $HOST failed"
Q=$(SSH "sudo flint -d $DEV q 2>/dev/null")
FW=$(awk -F': *' '/^FW Version:/{print $2; exit}' <<<"$Q")
RUNNING=$(awk -F': *' '/^FW Version\(Running\):/{print $2; exit}' <<<"$Q")
if [ "$FW" = "$EXPECT_FW" ] && { [ -z "$RUNNING" ] || [ "$RUNNING" = "$FW" ]; }; then ok "FW $FW"
else fail "FW flash ${FW:-?}, running ${RUNNING:-as flash}; want $EXPECT_FW"; fi

CLASSES=$(SSH 'lspci -D -n -d 15b3:' | sort | awk '{print $2}' | tr -d : | xargs)
if [ "$CLASSES" = "$WANT_CLASSES" ]; then ok "PCI classes $CLASSES"
else fail "PCI classes '$CLASSES', want '$WANT_CLASSES'"; fi

if [ "${#NV_RECIPE[@]}" -gt 0 ]; then
    ALL_NV=$(printf '%s ' "${NV_RECIPE[@]}")
    # shellcheck disable=SC2086
    if nv_check current $ALL_NV; then ok "NV_RECIPE: all $(wc -w <<<"$ALL_NV") parameters current"; else RC=1; fi
fi
step "raw NV TLVs, for the record only (writer IDs and fields outside the recipe vary run to run)"
SSH "sudo mlxconfig -d $DEV -f /tmp/env_rebuild_nv.raw backup >/dev/null 2>&1; grep '^%' /tmp/env_rebuild_nv.raw" \
    | sed 's/^/    /'

hdr "Next"
note "on the box:  ssh -o BatchMode=yes $HOST 'bash $(dirname "$(readlink -f "$0")")/per_run.sh --lab $LAB'"
note "MARS takes the box back for its nightly session: rebuild at the start of every session"
finish

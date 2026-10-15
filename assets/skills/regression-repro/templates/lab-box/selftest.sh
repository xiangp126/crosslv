#!/bin/bash
# selftest.sh - run env_rebuild.sh and per_run.sh against stubs: no box, no card, no Noga, no ssh.
# Run it after any change to the templates (or to a task's copy, with that copy's scripts next to
# this file):   bash selftest.sh        exit 0 = every case got the exit code it should.
set -u
HERE=$(dirname "$(readlink -f "$0")")
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home/.usr/bin" "$T/tools" "$T/utopx" "$T/task"
cp "$HERE/env_rebuild.sh" "$HERE/per_run.sh" "$T/tools/"
export STUB_T=$T HOME=$T/home PATH=$T/bin:$PATH

stub() { cat >"$1"; chmod +x "$1"; }
stub "$T/bin/sudo" <<'EOF'
#!/bin/bash
[ "$1 $2" = "tee /dev/kmsg" ] && { cat >>"$STUB_T/kmsg"; exit 0; }
exec "$@"
EOF
stub "$T/bin/hostname" <<'EOF'
#!/bin/bash
echo "${STUB_HOST:-testbox}"
EOF
stub "$T/bin/python3" <<'EOF'
#!/bin/bash
echo "Status.status = Lock"
echo "Status.lock_owner = ${STUB_OWNER:-$USER}"
EOF
stub "$T/bin/pgrep" <<'EOF'
#!/bin/bash
[ -e "$STUB_T/utopx_running" ]
EOF
stub "$T/bin/ps" <<'EOF'
#!/bin/bash
cat "$STUB_T/ps"
EOF
for c in mst modprobe; do printf '#!/bin/bash\nexit 0\n' | stub "$T/bin/$c"; done
stub "$T/bin/sleep" <<'EOF'
#!/bin/bash
/bin/sleep 0.01
EOF
stub "$T/bin/dmesg" <<'EOF'
#!/bin/bash
cat "$STUB_T/kmsg"
EOF
stub "$T/bin/flint" <<'EOF'
#!/bin/bash
if [ "$1" = -i ]; then echo "FW Version:            ${STUB_IMG_VER:-1.2.3}"
else echo "FW Version:            $(cat "$STUB_T/fw")"; fi
echo "PSID:                  MT_TEST"
EOF
stub "$T/bin/lspci" <<'EOF'
#!/bin/bash
i=0
for c in $(cat "$STUB_T/classes"); do
    case " $* " in
        *" -nn "*) echo "0000:01:00.$i Ethernet controller [$c]: Mellanox Technologies Device [15b3:1021]" ;;
        *) echo "0000:01:00.$i $c: 15b3:1021" ;;
    esac
    i=$((i + 1))
done
EOF
# NV state: "NAME VALUE" lines in nv_cur (Current) and nv_next (Next Boot).
stub "$T/bin/mlxconfig" <<'EOF'
#!/bin/bash
get() { awk -v n="$2" '$1 == n {print $2}' "$STUB_T/$1"; }
file=
while [ $# -gt 0 ]; do
    case "$1" in -d|-f) [ "$1" = -f ] && file=$2; shift 2 ;; -y|-e) shift ;; *) break ;; esac
done
cmd=$1; shift
case "$cmd" in
    q) for n in "$@"; do echo "*        $n        0        $(get nv_cur "$n")        $(get nv_next "$n")"; done ;;
    set|s) for kv in "$@"; do
               k=${kv%%=*}
               [ "$k" = "${STUB_MLX_IGNORE:-}" ] && continue
               { grep -v "^$k " "$STUB_T/nv_next"; echo "$k ${kv#*=}"; } >"$STUB_T/nv_next.new"
               mv "$STUB_T/nv_next.new" "$STUB_T/nv_next"
           done ;;
    reset) : >"$STUB_T/nv_next" ;;
    backup) echo "% TLV Type: 0x00000080, Writer ID: Unknown(0x0f), Writer Host ID: 0x00" >"$file" ;;
esac
EOF
stub "$T/bin/mlxburn" <<'EOF'
#!/bin/bash
case " $* " in
    *" -wrimage "*) echo IMG >"${!#}"; touch "$STUB_T/imaged" ;;
    *) echo "Image burn completed successfully"; touch "$STUB_T/burned" ;;
esac
EOF
# ssh: drop the options and the destination, run the command here, with /tmp mapped into the sandbox.
stub "$T/bin/ssh" <<'EOF'
#!/bin/bash
while [ $# -gt 0 ]; do
    case "$1" in -O) exit 0 ;; -o) shift 2 ;; -*) shift ;; *) shift; break ;; esac
done
[ $# -gt 0 ] || exit 0
cmd="$*"
cmd=${cmd//\/tmp\//$STUB_T/tmp/}
exec bash -c "${cmd//\/proc\/sys\/kernel\/random\/boot_id/$STUB_T/boot_id}"
EOF
stub "$T/home/.usr/bin/jmake" <<'EOF'
#!/bin/bash
case "$1" in
    --power-cycle) [ -n "${STUB_NO_REBOOT:-}" ] && exit 0
                   cp "$STUB_T/nv_next" "$STUB_T/nv_cur"; echo "boot-$RANDOM$RANDOM" >"$STUB_T/boot_id" ;;
    --fw-reset) exit "${STUB_RESET_RC:-0}" ;;
esac
EOF
stub "$T/utopx/utopx.exe" <<'EOF'
#!/bin/bash
cat "$STUB_T/scenario"
[ -z "${STUB_KERNEL_ERR:-}" ] || echo "DMAR: [DMA Write NO_PASID] Request device [01:00.0] fault addr 0x1000" >>"$STUB_T/kmsg"
[ -z "${STUB_TOOL_SLEEP:-}" ] || /bin/sleep "$STUB_TOOL_SLEEP"
exit "${STUB_TOOL_RC:-0}"
EOF
touch "$T/fw.mlx" "$T/fw.ini" "$T/dev_mst"

cat >"$T/tools/lab.conf" <<EOF
VERIFIED=selftest
HOST=testbox
DEV=$T/dev_mst
WANT_CLASSES="0200 0200"
FW_MLX=$T/fw.mlx
FW_INI=$T/fw.ini
EXPECT_FW=1.2.3
NV_RECIPE=("A_P1=1 B_P1=2" "C=3")
TASK_DIR=$T/task
UTOPX=$T/utopx/utopx.exe
RUN_NAME=t
SEED=7
ITER=1
OPS=1
CONF_FILE=x.conf
MODE=\${STUB_MODE:-feature}
FEATURE_GATE=feat.on
count_signal() { grep -ac 'NEWPATH' "\$1" || true; }
preconditions_met() { grep -aq 'TRIGGER' "\$1"; }
reset_device() { echo reset >>"$T/resets"; [ "\$(wc -l <"$T/resets")" -le "\${STUB_RESET_OK_UPTO:-99}" ]; }
setup_box() { touch "$T/setup_ran"; }
EOF
cp "$T/tools/lab.conf" "$T/tools/lab_big_group.conf"
echo 'NV_RECIPE=("A_P1=1 B_P1=2 C=3 D=4 E=5")' >>"$T/tools/lab_big_group.conf"

fresh() {
    rm -rf "$T/tmp" "$T/utopx/logs" "$T/task/logs"
    mkdir -p "$T/tmp"
    : >"$T/kmsg"; : >"$T/resets"; : >"$T/ps"; rm -f "$T/utopx_running" "$T/imaged" "$T/burned" "$T/setup_ran"
    echo 1.2.3 >"$T/fw"
    echo boot-0 >"$T/boot_id"
    echo "0200 0200" >"$T/classes"
    printf 'A_P1 1\nB_P1 ETH(2)\nC 3\n' | tee "$T/nv_cur" >"$T/nv_next"
    printf '%s\n' GeneralRandomTest "LOG_OP 1 NEWPATH" "TEST PASSED" >"$T/scenario"
}
scen() { printf '%s\n' "$@" >"$T/scenario"; }
FAILS=0
check() {   # check <name> <want rc> <command...>
    local name=$1 want=$2 rc
    shift 2
    "$@" >"$T/out" 2>&1
    rc=$?
    if [ "$rc" = "$want" ]; then printf '  ok    %-44s rc=%s\n' "$name" "$rc"
    else printf '  FAIL  %-44s rc=%s, want %s\n' "$name" "$rc" "$want"; tail -5 "$T/out" | sed 's/^/        /'; FAILS=$((FAILS + 1)); fi
}
PR=(bash "$T/tools/per_run.sh" --lab "$T/tools/lab.conf")
ER=(bash "$T/tools/env_rebuild.sh" --lab "$T/tools/lab.conf")

echo "per_run.sh"
fresh; check "feature: new path, clean"                    0 "${PR[@]}"
fresh; scen GeneralRandomTest "LOG_OP 1" "TEST PASSED"
       check "feature: old path only"                      5 "${PR[@]}"
fresh; scen GeneralRandomTest "LOG_OP 1 NEWPATH" "UFATAL boom"
       check "feature: new path, FATAL"                    6 env STUB_TOOL_RC=1 "${PR[@]}"
fresh; scen "nothing here"; check "feature: never initialised"     3 "${PR[@]}"
fresh; scen GeneralRandomTest "TEST PASSED"
       check "feature: initialised, no work"               3 "${PR[@]}"
fresh; check "feature-off: new path ran"                   4 "${PR[@]}" --feature-off
fresh; scen GeneralRandomTest "LOG_OP 1" "TEST PASSED"
       check "feature-off: dark and clean"                 0 "${PR[@]}" --feature-off
fresh; check "clean run, post-run reset fails"             7 env STUB_RESET_OK_UPTO=1 "${PR[@]}"
fresh; scen GeneralRandomTest "LOG_OP 1 NEWPATH" "UFATAL boom"
       check "failed run keeps 6 when the reset fails"     6 env STUB_RESET_OK_UPTO=1 "${PR[@]}"
fresh; check "pre-run reset fails"                         1 env STUB_RESET_OK_UPTO=0 "${PR[@]}"
fresh; check "kernel DMA fault during a clean run"         6 env STUB_KERNEL_ERR=1 "${PR[@]}"
fresh; scen GeneralRandomTest "LOG_OP 1" "NEWPATH" "UFATAL boom"
       check "repro: signature seen"                       0 env STUB_MODE=repro STUB_TOOL_RC=1 "${PR[@]}"
fresh; scen GeneralRandomTest "LOG_OP 1" "TEST PASSED"
       check "repro: not reproduced"                       5 env STUB_MODE=repro "${PR[@]}"
fresh; scen GeneralRandomTest "LOG_OP 1" "UFATAL other"
       check "repro: failed differently"                   6 env STUB_MODE=repro STUB_TOOL_RC=1 "${PR[@]}"
fresh; scen GeneralRandomTest "LOG_OP 1" "TEST PASSED"
       check "fixverify: trigger absent"                   4 env STUB_MODE=fixverify "${PR[@]}"
fresh; scen GeneralRandomTest TRIGGER "LOG_OP 1" "TEST PASSED"
       check "fixverify: verified"                         0 env STUB_MODE=fixverify "${PR[@]}"
fresh; scen GeneralRandomTest TRIGGER "LOG_OP 1" NEWPATH "UFATAL boom"
       check "fixverify: signature still there"            5 env STUB_MODE=fixverify STUB_TOOL_RC=1 "${PR[@]}"
fresh; echo "0207 0200" >"$T/classes"
       check "baseline: wrong PCI classes"                 1 "${PR[@]}"
fresh; echo 'C 9' >>"$T/nv_cur"; check "baseline: NV drifted" 1 "${PR[@]}"
fresh; echo 9.9.9 >"$T/fw"; check "FW gate"                1 "${PR[@]}"
fresh; echo 9.9.9 >"$T/fw"; check "FW gate with --any-fw"  0 "${PR[@]}" --any-fw
fresh; check "wrong host"                                  1 env STUB_HOST=other "${PR[@]}"
fresh; check "lock held by someone else"                   1 env STUB_OWNER=someone "${PR[@]}"
fresh; touch "$T/utopx_running"; check "utopx already running" 1 "${PR[@]}"
fresh; check "unknown argument"                            2 "${PR[@]}" --bogus
fresh
STUB_TOOL_SLEEP=2 "${PR[@]}" >"$T/out" 2>&1 &
PID=$!
/bin/sleep 1
kill -TERM "$PID"
wait "$PID"
RC=$?
if [ "$RC" = 130 ] && [ "$(wc -l <"$T/resets")" = 2 ]; then printf '  ok    %-44s rc=%s\n' "SIGTERM mid-run: 130, post-run reset ran" "$RC"
else printf '  FAIL  %-44s rc=%s resets=%s\n' "SIGTERM mid-run" "$RC" "$(wc -l <"$T/resets")"; FAILS=$((FAILS + 1)); fi

echo "env_rebuild.sh"
fresh; check "verify only: known-good"                     0 "${ER[@]}"
grep -q '^ENV_REBUILD_RC=0$' "$T/out" || { echo "  FAIL  last line is not ENV_REBUILD_RC=0"; FAILS=$((FAILS + 1)); }
fresh; echo 'C 9' >>"$T/nv_cur"; check "verify only: NV drifted" 1 "${ER[@]}"
fresh; echo "0207 0200" >"$T/classes"; check "verify only: wrong PCI classes" 1 "${ER[@]}"
fresh; printf 'X 1\n' | tee "$T/nv_cur" >"$T/nv_next"
       check "--burn: reset + recipe + power-cycle"        0 "${ER[@]}" --burn --yes
sort "$T/nv_cur" | xargs | grep -qx 'A_P1 1 B_P1 2 C 3' \
    || { echo "  FAIL  NV after the rebuild: $(sort "$T/nv_cur" | xargs)"; FAILS=$((FAILS + 1)); }
fresh; check "--burn: image version mismatch"              1 env STUB_IMG_VER=9.9.9 "${ER[@]}" --burn --yes
[ ! -e "$T/setup_ran" ] && [ ! -e "$T/burned" ] \
    || { echo "  FAIL  a refused --burn still ran setup_box or burned"; FAILS=$((FAILS + 1)); }
fresh; echo 'C 9' >>"$T/nv_cur"
       check "--cycle: pending NV goes live, nothing burned"  0 "${ER[@]}" --cycle --yes
[ ! -e "$T/imaged" ] && [ ! -e "$T/burned" ] && [ -e "$T/setup_ran" ] \
    || { echo "  FAIL  --cycle imaged/burned or skipped setup_box"; FAILS=$((FAILS + 1)); }
fresh; check "--burn and --cycle together"                 2 "${ER[@]}" --burn --cycle --yes
fresh; check "power-cycle that never reboots"              1 env STUB_NO_REBOOT=1 "${ER[@]}" --cycle --yes
fresh; check "--burn: Next Boot read-back mismatch"        1 env STUB_MLX_IGNORE=C "${ER[@]}" --burn --yes
fresh; check "NV_RECIPE group over 4 parameters"           1 bash "$T/tools/env_rebuild.sh" --lab "$T/tools/lab_big_group.conf"
fresh; echo "x utopx.exe --device" >"$T/ps"; check "box busy" 1 "${ER[@]}"
fresh; check "lock held by someone else"                   1 env STUB_OWNER=someone "${ER[@]}"

echo
[ "$FAILS" = 0 ] && echo "selftest: all cases passed" || echo "selftest: $FAILS case(s) FAILED"
[ "$FAILS" = 0 ]

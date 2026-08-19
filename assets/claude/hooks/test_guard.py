#!/usr/bin/env python3
"""Table test for the PreToolUse guard: every case is a command that has plausibly
been typed in this workflow. DENY = must be blocked, PASS = must not be.

The hostname is assembled at runtime so that editing THIS file does not itself trip
the guard when the edit goes through a Bash command.
"""
import json
import subprocess
import sys

GUARD = "/labhome/pexiang/myGit/crosslv/assets/claude/hooks/guard.py"
MR = "l-fw" + "minireg"   # keep the literal out of this file's own source lines

CASES = [
    # --- rule 1: the minireg pool must never be touched ---
    ("DENY", f"ssh root@{MR}-064 'mst status -v'"),
    ("DENY", f"sshpass -p pw ssh -o StrictHostKeyChecking=no root@{MR}-014 uname -a"),
    ("DENY", f"myssh root@{MR}-024 reboot"),
    ("DENY", f"python3 $CLI -l -t host -n {MR}-054 -L 8"),
    ("DENY", f"HOST={MR}-034; ssh root@$HOST 'flint -d /dev/mst/mt4133_pciconf0 q'"),
    ("DENY", f"ipmitool -I lanplus -H {MR}-074-ilo -U ADMIN -P ADMIN chassis power off"),
    ("DENY", f"scp fw.bin root@{MR}-084:/tmp/"),
    ("DENY", f"bash -c 'ssh {MR}-094 true'"),
    ("DENY", f"for h in {MR}-014 {MR}-024; do ssh $h uptime; done"),
    # a tainted variable used in a later segment must still be caught
    ("DENY", f"H={MR}-064\nssh root@$H 'uptime'"),
    ("DENY", f"export BOX={MR}-024 && ipmitool -H ${{BOX}}-ilo chassis power off"),
    # reading logs that merely mention the pool stays allowed
    ("PASS", f"grep -c {MR} logs/minireg_2231.log"),
    ("PASS", f"grep -oE 'session_id [0-9]+' logs/ci.log | grep {MR}"),
    ("PASS", f"curl -s $J/job/golan_fw_minireg/22/consoleText | grep {MR}-064"),
    ("PASS", f"awk '/{MR}-044/{{print}}' status.txt"),
    ("PASS", f"echo 'never touch {MR} boxes'"),
    # regression: a dangerous verb in ANOTHER segment must not taint a segment that
    # only greps for the hostname (this was a real false positive)
    ("PASS", f"mlxconfig -d /dev/null -y set LINK_TYPE_P1=2; grep -rn {MR} SKILL.md"),
    ("PASS", f"flint -d /dev/mst/mt4133_pciconf0 q; grep {MR} notes.md"),
    ("PASS", f"ssh root@l-fwreg-171 uptime && grep -c {MR} logs/ci.log"),

    # --- rule 2: oversized mlxconfig set ---
    ("DENY", "mlxconfig -d /dev/mst/mt4133_pciconf0 -y set " +
             " ".join(f"PARAM_{i}=1" for i in range(20))),
    ("DENY", "mlxconfig -d pciconf-00:00.0 -f dump.conf set"),
    ("DENY", "mlxconfig -d /dev/mst/mt41692_pciconf0 -y set $(cat reference_dump.txt)"),
    # small, deliberate sets are the whole point -- must not be blocked
    ("PASS", "mlxconfig -d /dev/mst/mt41692_pciconf0 -y set LINK_TYPE_P1=2 LINK_TYPE_P2=2"),
    ("PASS", "mlxconfig -d /dev/mst/mt41692_pciconf0 -y set PF_NUM_SAT_PF=1"),
    ("PASS", "mlxconfig -e q LINK_TYPE_P1 LINK_TYPE_P2 VIRTIO_NET_EMULATION_NUM_PF"),
    ("PASS", "mlxconfig -d $D q | grep -E 'PF_BAR2|MEMIC'"),

    # --- unrelated traffic must sail through ---
    ("PASS", "git log -1 --format=%B HEAD | awk '{print length($0), $0}'"),
    ("PASS", "ssh root@l-fwreg-171 'lspci | grep -c ^81:'"),
    ("PASS", "python3 $CLI -l -t host -n l-fwreg-171 -L 8"),
    ("PASS", "flint -d /dev/mst/mt4133_pciconf0 q full"),
    ("PASS", "bash /auto/fwgwork1/pexiang/bugZilla/OCI_EMU/tools/env_rebuild_171.sh"),
]


def run(cmd):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    p = subprocess.run([sys.executable, GUARD], input=payload,
                       capture_output=True, text=True, timeout=15)
    if p.returncode != 0:
        return "ERROR", p.stderr.strip()
    out = p.stdout.strip()
    if not out:
        return "PASS", ""
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        return "ERROR", f"non-JSON output: {out[:200]}"
    dec = d["hookSpecificOutput"]["permissionDecision"]
    return ("DENY" if dec == "deny" else "PASS",
            d["hookSpecificOutput"]["permissionDecisionReason"].split("\n")[0])


fails = 0
for expected, cmd in CASES:
    got, note = run(cmd)
    ok = got == expected
    fails += not ok
    short = cmd.replace("\n", "\\n")
    short = short if len(short) <= 74 else short[:71] + "..."
    print(f"[{'ok ' if ok else 'FAIL'}] exp={expected:4} got={got:5} {short}")
    if not ok and note:
        print(f"         -> {note}")

print(f"\n{len(CASES) - fails}/{len(CASES)} passed")
sys.exit(1 if fails else 0)

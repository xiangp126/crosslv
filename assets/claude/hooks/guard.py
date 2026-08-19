#!/usr/bin/env python3
"""PreToolUse guard: hard-deny a small set of irreversible lab actions.

Runs alongside auto-approve.sh. That hook returns "allow" for everything; when several
PreToolUse hooks disagree, **deny wins**, so this one still stops the call.

Two rules, both written after a real incident:

  1. l-fwminireg-*  -- dedicated CI/DoA machines. NOGA reports them Release/no-owner
     while a live CI session runs on them, and a NOGA lock does not stop the MARS
     scheduler from dispatching there. On 2026-08-12 a repro launched on
     l-fwminireg-064 collided with live regression session 11366827 over the VSEC
     mailbox. Reading a log that merely *mentions* the hostname stays allowed.

  2. Oversized `mlxconfig set` -- replaying a 457-parameter dump in one transaction,
     followed by a cold boot, took out three cards in one day. The mechanism was never
     established; the empirical rule is to apply a few parameters at a time and read
     back Next Boot after each.

Rule 1 evaluates per command segment, and also follows variables assigned a minireg
hostname within the same command (`HOST=l-fwminireg-034; ssh root@$HOST ...`). Judging
the whole command at once instead produced false positives: an unrelated `flint` in one
segment tainted a `grep <hostname>` in another.

Known limit: this sees the command text only. A hostname hidden behind a variable set in
an earlier, separate tool call, or a wrapper script whose body holds the real command, is
not visible here. Conversely, a hostname appearing in a heredoc still counts as command
text -- editing docs that mention the pool is easier through the Write/Edit tools, which
this hook does not gate.

Regression tests: ./test_guard.py (run it after any change here).

Protocol: emit a deny decision on stdout, or stay silent (exit 0) to abstain.
"""
import json
import re
import sys

MAX_MLXCONFIG_PARAMS = 8

# Commands that only read/transform text. A command touching l-fwminireg is allowed
# only if every segment is one of these. python3/bash/sh/xargs/eval are deliberately
# absent -- they can execute anything.
READONLY = {
    "grep", "rg", "ugrep", "egrep", "fgrep", "zgrep",
    "cat", "head", "tail", "less", "more", "tee",
    "awk", "sed", "sort", "uniq", "wc", "cut", "tr", "column", "jq",
    "echo", "printf", "ls", "find", "stat", "file", "diff",
    "curl", "wget", "source", ".", "true", "test", "[",
}

# Anything that could actually reach the box, even via a variable we cannot expand.
DANGER_RE = re.compile(
    r"(?<![\w.-])("
    r"ssh|sshpass|myssh|scp|rsync|ipmitool|"
    r"flint|mlxconfig|mlxfwreset|mlxburn|mlxlink|mlxfwmanager|"
    r"reboot|poweroff|shutdown|"
    r"noga_manage\.py"
    r")(?![\w.-])"
)

SEGMENT_RE = re.compile(r"\|\||&&|;|\n|\||\$\(|`")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
PREFIX_SKIP = {"sudo", "time", "env", "nohup", "command", "exec", "then", "do", "else"}


def first_token(segment: str) -> str:
    for tok in segment.strip().split():
        if ASSIGN_RE.match(tok) or tok in PREFIX_SKIP or tok.startswith("-"):
            continue
        return tok.rsplit("/", 1)[-1]
    return ""


def deny(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    sys.exit(0)


def check_minireg(cmd: str):
    if "l-fwminireg" not in cmd:
        return

    # Variables assigned a minireg hostname earlier in the SAME command; a later segment
    # referencing one of them is reaching the box even though the name is not visible there.
    tainted = set(re.findall(
        r"(?:^|[\s;&|(])([A-Za-z_]\w*)=[\"']?[^\s;&|\"']*l-fwminireg", cmd))

    culprit = None
    for seg in SEGMENT_RE.split(cmd):
        if not seg.strip():
            continue
        refs_tainted = any(re.search(r"\$\{?" + re.escape(v) + r"\b", seg) for v in tainted)
        if "l-fwminireg" not in seg and not refs_tainted:
            continue  # this segment does not touch the pool
        tok = first_token(seg)
        if not tok:
            continue  # a bare assignment, harmless on its own
        danger = DANGER_RE.search(seg)
        if danger:
            culprit = danger.group(1)
            break
        if tok not in READONLY:
            culprit = tok
            break

    if culprit is None:
        return  # pure log/text handling that merely mentions the hostname
    deny(
        "BLOCKED: l-fwminireg-* are dedicated CI/DoA machines and must never be locked, "
        "ssh'd into, burned, mlxconfig'd or fw-reset. This command uses '{}' against one.\n"
        "NOGA is not authoritative for this pool: it reports Release/no-owner while a live CI "
        "session is running, and a NOGA lock does not stop the MARS scheduler from dispatching "
        "there. On 2026-08-12 exactly this collided with regression session 11366827 over the "
        "VSEC mailbox.\n"
        "Instead: let CI run the experiment (push a patchset and read the DoA result), or ask "
        "the minireg pool owner to take a box out of rotation. See skill 'regression-repro'.\n"
        "Reading logs that merely mention the hostname is allowed.".format(culprit)
    )


def check_mlxconfig(cmd: str):
    m = re.search(r"(?<![\w.-])mlxconfig(?![\w.-])", cmd)
    if not m:
        return
    tail = cmd[m.end():]
    sm = re.search(r"(?<![\w-])(set|apply)(?![\w-])", tail)
    if not sm:
        return  # a query (-e q) is fine
    after_set = tail[sm.end():]

    if re.search(r"(?<![\w-])(-f|--file)(?![\w-])", tail) or re.search(r"\$\(\s*cat|`\s*cat", tail):
        deny(
            "BLOCKED: this applies an mlxconfig parameter file/dump in one transaction.\n"
            "Never bulk-transplant a whole mlxconfig dump onto another box -- replaying a "
            "457-parameter dump in one `set`, followed by a cold boot, took out three cards in "
            "one day. The boards were identical and the mechanism was never established.\n"
            "Instead: diff the two configs, set only the few parameters that bear on what you "
            "are chasing, read back Next Boot after each, and verify Current after the cold "
            "boot. See skill 'nic-livefish-recovery'."
        )

    params = re.findall(r"(?<![\w/.=-])[A-Z][A-Z0-9_]{2,}=\S+", after_set)
    if len(params) > MAX_MLXCONFIG_PARAMS:
        deny(
            "BLOCKED: {} parameters in a single `mlxconfig set` (limit {}).\n"
            "Replaying a large parameter set in one transaction, followed by a cold boot, took "
            "out three cards in one day. Apply a few at a time, read back Next Boot after each, "
            "and verify Current after the cold boot. Treat anything that re-lays the PCI/BAR map "
            "(PF_LOG_BAR_SIZE, NUM_PF_MSIX, NUM_VF_MSIX, MEMIC_BAR_SIZE, PF_BAR2_*, "
            "PCI_SWITCH_EMULATION_*, *_EMULATION_ENABLE) with extra care, and stop at the first "
            "anomaly. See skill 'nic-livefish-recovery'.\n"
            "Parameters seen: {}".format(
                len(params), MAX_MLXCONFIG_PARAMS, ", ".join(p.split("=")[0] for p in params[:12])
            )
        )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never break the session on a malformed payload
    if payload.get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    check_minireg(cmd)
    check_mlxconfig(cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main())

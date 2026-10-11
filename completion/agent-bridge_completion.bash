#!/usr/bin/env bash
# Completion function for agent-bridge

# The session ids `send --to` takes: the live sessions `jcl list --json`
# reports, minus agent-bridge's stand-ins, which stand for a Codex session that
# is offered itself. Ids rather than names: a name may hold spaces and change
# with a title, an id does neither. jcl answers in ~0.2 s and, unlike
# `agent-bridge peers`, starts no daemon just to complete a word.
_agent_bridge_session_ids() {
    jcl list --json 2>/dev/null | python3 -c '
import json, sys
try:
    records = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for rec in records:
    if (rec.get("alive") and not rec.get("stand_in_for")
            and rec.get("kind") in (None, "", "interactive")):
        print(rec["session_id"])
' 2>/dev/null
}

_agent_bridge_complete() {
    local cur prev cmd i opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD - 1]}"

    # daemon and hook are agent-bridge's own, run by itself and its stand-ins
    local commands="send peers status scan start stop restart"

    # Locate the subcommand if one has been typed already
    for ((i = 1; i < COMP_CWORD; i++)); do
        case "${COMP_WORDS[i]}" in
            send | peers | status | scan | start | stop | restart)
                cmd="${COMP_WORDS[i]}"
                break
                ;;
        esac
    done

    if [[ $prev == --to ]]; then
        COMPREPLY=($(compgen -W "$(_agent_bridge_session_ids)" -- "$cur"))
        return 0
    fi

    if [[ -z $cmd ]]; then
        if [[ $cur == -* ]]; then
            COMPREPLY=($(compgen -W "-h --help" -- "$cur"))
        else
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
        fi
        return 0
    fi

    case "$cmd" in
        send) opts="-h --help --to" ;;
        peers) opts="-h --help --json" ;;
        status | scan | start | stop | restart) opts="-h --help" ;;
    esac

    if [[ $cur == -* ]]; then
        COMPREPLY=($(compgen -W "$opts" -- "$cur"))
        return 0
    fi

    # send needs --to before the message: offer it until it is there
    if [[ $cmd == send && " ${COMP_WORDS[*]} " != *" --to "* ]]; then
        COMPREPLY=($(compgen -W "--to" -- "$cur"))
    fi
    return 0
}

complete -F _agent_bridge_complete agent-bridge

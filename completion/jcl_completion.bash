#!/usr/bin/env bash
# Completion function for jcl

# Same guard ja uses: bash-completion may not be loaded, and targets contain a
# colon, which readline treats as a word break.
if ! declare -F __ltrim_colon_completions &>/dev/null; then
    __ltrim_colon_completions() {
        if [[ "$1" == *:* && "${COMP_WORDBREAKS-}" == *:* ]]; then
            local colon_word=${1%"${1##*:}"}
            local i=${#COMPREPLY[*]}
            while [[ $((--i)) -ge 0 ]]; do
                COMPREPLY[$i]=${COMPREPLY[$i]#"$colon_word"}
            done
        fi
    }
fi

# The tmux targets refresh can act on, plus the `all` keyword. Only targets are
# offered: they are what `list` shows in its first column and what refresh
# accepts. A second python start-up costs ~4ms against the ~700ms `list` itself
# takes to scan tmux and /proc, so parsing the json properly is effectively free,
# and it is what keeps pane-less background agents out of the list.
_jcl_live_ids() {
    jcl list --json --agent "${2:-all}" 2>/dev/null | python3 -c '
import json, sys
used = set(sys.argv[1].replace(",", " ").split()) if len(sys.argv) > 1 else set()
try:
    records = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
if "all" in used:
    # all is the superset; nothing else on the line would add anything
    sys.exit(0)
print("all")
for rec in records:
    if not (rec.get("alive") and rec.get("target")) or rec.get("stopped"):
        continue
    if rec.get("kind") not in (None, "", "interactive"):
        continue
    if rec["target"] not in used:
        print(rec["target"])
' "$1" 2>/dev/null
}

# Complete one SESSION argument of `refresh`.
#
# COMP_WORDS cannot be used to find what is being typed: it has already split
# 0:6.2 into three words and lost whether a boundary was a space or a colon. The
# raw line up to the cursor still has that, so the word under the cursor is
# whatever follows the last space - colon and all.
#
# Candidates already on the line are dropped, the way jmake does for its
# comma-separated models; here the separator is a space, so the line itself can
# be searched directly.
_jcl_complete_session() {
    local line="${COMP_LINE:0:$COMP_POINT}"
    local word="${line##* }"
    local before="${line% *}"
    local candidates
    candidates=$(_jcl_live_ids "$before" "${1:-all}")

    COMPREPLY=($(compgen -W "$candidates" -- "$word"))
    __ltrim_colon_completions "$word"
}

# Mirrors tmux-resurrect's own resurrect_dir(): honour @resurrect-dir, then fall
# back to ~/.tmux/resurrect when it exists, otherwise the XDG data dir.
_jcl_resurrect_dir() {
    local dir
    dir=$(tmux show-option -gqv "@resurrect-dir" 2>/dev/null)
    if [[ -n $dir ]]; then
        dir=${dir//\$HOME/$HOME}
        dir=${dir//\$HOSTNAME/$(hostname)}
        dir=${dir/#\~/$HOME}
    elif [[ -d "$HOME/.tmux/resurrect" ]]; then
        dir="$HOME/.tmux/resurrect"
    else
        dir="${XDG_DATA_HOME:-$HOME/.local/share}/tmux/resurrect"
    fi
    printf '%s' "$dir"
}

# The `last` symlink first, then the newest few layouts. Kept short on purpose:
# resurrect retains many archives but only the recent ones are worth offering,
# and typing a leading '/' falls through to plain path completion anyway.
_jcl_layout_files() {
    local dir
    dir=$(_jcl_resurrect_dir)
    [[ -d $dir ]] || return 0
    [[ -e "$dir/last" ]] && printf '%s\n' "$dir/last"
    ls -t "$dir"/tmux_resurrect_*.txt 2>/dev/null | head -5
}

# Effort levels, taken from claude's own --help rather than a list baked in
# here, so a level added by a future release shows up without touching this
# file. --effort (the flag) does not list `auto`, but /effort (the slash command,
# which is what jcl actually sends) accepts it, so it is appended.
_jcl_effort_levels() {
    {
        if [[ ${1:-all} != codex ]]; then
        claude --help 2>/dev/null \
            | grep -A1 -- '--effort <level>' \
            | grep -oE '\(([a-z]+,[ ]*)+[a-z]+\)' \
            | tr -d '()' | tr ',' '\n' | tr -d ' '
        echo auto
        fi
        if [[ ${1:-all} != claude ]]; then
            _jcl_codex_catalog efforts
        fi
    } | awk 'NF && !seen[$0]++'
}

# Read Codex's local cache; TAB must not start an agent or a network request.
_jcl_codex_catalog() {
    python3 -c '
import json, os, re, sys
from pathlib import Path
root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
try:
    models = json.loads((root / "models_cache.json").read_text()).get("models", [])
except (OSError, ValueError):
    models = []
if sys.argv[1] == "efforts":
    values = [level["effort"] for m in models for level in m.get("supported_reasoning_levels", [])]
    print("\n".join(dict.fromkeys(values or ["minimal", "low", "medium", "high", "xhigh", "max"])))
else:
    for m in models:
        if m.get("slug"): print(m["slug"])
    try:
        for line in (root / "config.toml").read_text().splitlines():
            if line.lstrip().startswith("["): break
            match = re.match(r"\s*model\s*=\s*\"([^\"]+)\"", line)
            if match: print(match[1])
    except OSError:
        pass
' "$1" 2>/dev/null
}

# Claude model names come from --help and settings; Codex names come from its
# local models cache and config. Explicit --agent narrows both sets.
_jcl_model_names() {
    {
        if [[ ${1:-all} != codex ]]; then
        # claude: --help examples plus the configured model
        claude --help 2>/dev/null \
            | sed -n "/--model <model>/,/^\s*--[a-z]/p" \
            | grep -oE "'[A-Za-z0-9._-]+'" | tr -d "'"
        python3 -c '
import json, os
from pathlib import Path
root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
for f in (root / "settings.json", root / "settings.local.json"):
    try:
        v = json.loads(f.read_text()).get("model")
        if v: print(v)
    except (OSError, ValueError):
        pass
' 2>/dev/null
        fi
        if [[ ${1:-all} != claude ]]; then
            _jcl_codex_catalog models
        fi
    } | awk 'NF && !seen[$0]++'
}

_jcl_complete() {
    local cur prev cmd i opts agent=all
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD - 1]}"

    local commands="list save restore refresh set set-effort set-model patch-resurrect save-auth restore-auth fill-auth"
    for ((i = 1; i < ${#COMP_WORDS[@]}; i++)); do
        case "${COMP_WORDS[i]}" in
            --agent) agent="${COMP_WORDS[i+1]:-all}" ;;
            --agent=*) agent="${COMP_WORDS[i]#--agent=}" ;;
        esac
    done

    # Locate the subcommand if one has been typed already
    for ((i = 1; i < COMP_CWORD; i++)); do
        case "${COMP_WORDS[i]}" in
            list | save | restore | refresh | set | set-effort | set-model | patch-resurrect | save-auth | restore-auth | fill-auth)
                cmd="${COMP_WORDS[i]}"
                break
                ;;
        esac
    done

    # Options that expect a path
    case "$prev" in
        -o | --output | -f | --file)
            COMPREPLY=($(compgen -f -- "$cur"))
            return 0
            ;;
        --model)
            COMPREPLY=($(compgen -W "$(_jcl_model_names "$agent")" -- "$cur"))
            return 0
            ;;
        --effort)
            COMPREPLY=($(compgen -W "$(_jcl_effort_levels "$agent")" -- "$cur"))
            return 0
            ;;
        --agent)
            COMPREPLY=($(compgen -W "claude codex all" -- "$cur"))
            return 0
            ;;
    esac

    if [[ -z $cmd ]]; then
        if [[ $cur == -* ]]; then
            COMPREPLY=($(compgen -W "-h --help" -- "$cur"))
        else
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
        fi
        return 0
    fi

    case "$cmd" in
        list) opts="-h --help --agent -a --all --json --ids-only" ;;
        save) opts="-h --help --agent -o --output" ;;
        restore) opts="-h --help --agent -f --file -n --dry-run" ;;
        refresh) opts="-h --help --agent --timeout -n --dry-run" ;;
        set) opts="-h --help --agent --model --effort --delay --timeout --no-verify -n --dry-run" ;;
        set-effort) opts="-h --help --agent --delay --timeout --no-verify -n --dry-run" ;;
        set-model) opts="-h --help --agent --delay --timeout --no-verify -n --dry-run" ;;
        patch-resurrect) opts="-h --help -n --dry-run -v --verbose" ;;
        save-auth) opts="-h --help -o --output --force -n --dry-run" ;;
        restore-auth) opts="-h --help -f --file --force --no-fill -n --dry-run" ;;
        fill-auth) opts="-h --help -n --dry-run" ;;
    esac

    if [[ $cur == -* ]]; then
        COMPREPLY=($(compgen -W "$opts" -- "$cur"))
        return 0
    fi

    # set has no positional at all and needs one of -m/-e, so offer those two
    # rather than nothing when there is no dash typed yet
    if [[ $cmd == set ]]; then
        COMPREPLY=($(compgen -W "--model --effort" -- "$cur"))
        return 0
    fi

    # refresh takes any number of SESSION arguments
    if [[ $cmd == refresh ]]; then
        _jcl_complete_session "$agent"
        return 0
    fi

    # Use the selected agent's effort catalogue.
    if [[ $cmd == set-effort ]]; then
        COMPREPLY=($(compgen -W "$(_jcl_effort_levels "$agent")" -- "$cur"))
        return 0
    fi

    # set-model's positional is whatever /model itself accepts. Only the alias in
    # daily use is offered, so TAB completes it outright instead of stopping at
    # an ambiguous prefix; any other alias still works typed out in full, since
    # the subcommand validates nothing (they change with each model release) and
    # reports an unknown one back as refused. compgen -W does no pathname
    # expansion, so the [1m] survives even with a file named opus1 in the way.
    if [[ $cmd == set-model ]]; then
        COMPREPLY=($(compgen -W "$(_jcl_model_names "$agent")" -- "$cur"))
        return 0
    fi

    # patch-resurrect takes a resurrect layout file; suggest the saved ones by
    # absolute path unless a path is already being typed out by hand
    if [[ $cmd == patch-resurrect ]]; then
        if [[ $cur == [~/.]* || $cur == \$* ]]; then
            COMPREPLY=($(compgen -f -- "$cur"))
        else
            local IFS=$'\n'
            COMPREPLY=($(compgen -W "$(_jcl_layout_files)" -- "$cur"))
        fi
        return 0
    fi

    return 0
}

complete -o filenames -F _jcl_complete jcl

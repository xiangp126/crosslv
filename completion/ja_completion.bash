# Bash completion for ja (auto-approve for Claude Code / Codex CLI)

# Provide __ltrim_colon_completions if bash-completion is not loaded
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

_ja_complete() {
    local cur prev short_opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    short_opts="-h -w -l -v -D -s -S -L -R -A"
    long_opts="--help --wait --list --verbose --daemon \
               --stop --restart --all --status --log --log-full"

    # The panes ja is for: the ones running an AI.
    #
    # One `tmux list-panes -a` gives every pane's foreground command at once and
    # costs ~0ms, so there is no need to walk session -> window -> pane the way
    # this used to. It matches what `ja --list` reports without paying that
    # command's ~0.9s. ja also accepts a pane not running an AI yet (it boots
    # paused and waits), so when nothing matches, every pane is offered.
    # $1 picks the form: session:window.pane (default) or the pane id (%47).
    # ja takes either, and a word starting with % can only mean the latter, so
    # the two are offered separately instead of doubling every candidate list.
    _ja_ai_panes() {
        local col=2 all ai
        [[ $1 == id ]] && col=3
        all=$(tmux list-panes -a -F \
            '#{pane_current_command} #{session_name}:#{window_index}.#{pane_index} #{pane_id}' 2>/dev/null)
        # codex runs under `node`; claude reports itself
        ai=$(awk -v c="$col" '$1 ~ /^(claude|codex|node)$/ {print $c}' <<< "$all")
        [[ -n $ai ]] && { printf '%s\n' "$ai"; return; }
        awk -v c="$col" '{print $c}' <<< "$all"
    }

    # -w is the only option taking a value, so it is the only thing that can
    # sit between a flag and its argument.
    case "$prev" in
        -w|--wait)
            COMPREPLY=( $(compgen -W "0 1 2 3 5 8 10" -- "$cur") )
            return 0
            ;;
    esac

    if [[ ${cur} == -* ]]; then
        # Mirror jc's split-suggestion style: `--<TAB>` shows only long
        # options, `-<TAB>` shows only short options.
        if [[ ${cur} == --* ]]; then
            COMPREPLY=( $(compgen -W "${long_opts}" -- "${cur}") )
        else
            COMPREPLY=( $(compgen -W "${short_opts}" -- "${cur}") )
        fi
        return 0
    fi

    # Anything else is the PANE, whatever mode flags came before it. ja takes
    # exactly one, so once the line already carries a target there is nothing
    # left to offer. Targets contain a colon, which readline treats as a word
    # break, hence the trim.
    # $cur cannot be used here: readline breaks words on ':' (it is in
    # COMP_WORDBREAKS), so for `ja --log 3:` it holds just ":" and nothing
    # would ever match. The raw line still has the whole word.
    local line="${COMP_LINE:0:$COMP_POINT}"
    local word="${line##* }"
    local before="${line%"$word"}"
    if [[ $before =~ (^|[[:space:]])[%0-9][^[:space:]]*[[:space:]]+$ ]]; then
        return 0
    fi
    # % is not a word-break character, so a pane id arrives whole and needs no trim
    if [[ $word == %* ]]; then
        COMPREPLY=( $(compgen -W "$(_ja_ai_panes id)" -- "$word") )
        return 0
    fi
    COMPREPLY=( $(compgen -W "$(_ja_ai_panes)" -- "$word") )
    __ltrim_colon_completions "$word"
}

complete -F _ja_complete ja

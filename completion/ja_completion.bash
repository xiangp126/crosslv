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
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Complete tmux targets in session[:window[.pane]] format.
    # Generates candidates with raw colons, then uses
    # __ltrim_colon_completions to handle readline's colon word-break.
    _complete_tmux_target() {
        local IFS=$'\n'
        local prefix="$1"
        local candidates

        if [[ "$prefix" == *:*.* ]]; then
            # session:window.pane — complete pane indices
            local session="${prefix%%:*}"
            local after_colon="${prefix#*:}"
            local window="${after_colon%%.*}"
            candidates=$(tmux list-panes -t "${session}:${window}" 2>/dev/null | \
                sed -re "s/^([^:]+):.*$/${session}:${window}.\1/")
        elif [[ "$prefix" == *:* ]]; then
            # session:window — complete window indices
            local session="${prefix%%:*}"
            candidates=$(tmux list-windows -t "$session" 2>/dev/null | \
                sed -re "s/^([^:]+):.*$/${session}:\1./")
            compopt -o nospace
        else
            # session name
            candidates=$(tmux list-sessions 2>/dev/null | \
                sed -re 's/([^:]+:).*$/\1/')
            compopt -o nospace
        fi

        COMPREPLY=( $(compgen -W "$candidates" -- "$prefix") )
        __ltrim_colon_completions "$prefix"
    }

    # Check if we're completing a -t tmux-target argument.
    # Because ':' is in COMP_WORDBREAKS, bash splits targets like "1:2"
    # into ["1", ":", "2"]. We walk back through COMP_WORDS to find -t
    # and reconstruct the full target prefix typed so far.
    local _completing_target=false
    local _full_cur="$cur"

    if [[ "$prev" == "-t" ]]; then
        _completing_target=true
    elif [[ "$cur" != -* ]] && [[ -n "$cur" || "$prev" == ":" ]]; then
        local i w
        for (( i = COMP_CWORD - 1; i >= 1; i-- )); do
            w="${COMP_WORDS[i]}"
            if [[ "$w" == "-t" ]]; then
                _completing_target=true
                _full_cur=""
                local j
                for (( j = i + 1; j <= COMP_CWORD; j++ )); do
                    _full_cur+="${COMP_WORDS[j]}"
                done
                break
            elif [[ "$w" == -* ]]; then
                break
            elif [[ "$w" == ":" ]] || [[ "$w" =~ ^[0-9a-zA-Z_.]+$ ]]; then
                continue
            else
                break
            fi
        done
    fi

    if [[ "$_completing_target" == true ]]; then
        _complete_tmux_target "$_full_cur"
        return 0
    fi

    case "${prev}" in
        -w|--wait)
            COMPREPLY=( $(compgen -W "1 2 3 5 8 10" -- "${cur}") )
            return 0
            ;;
    esac

    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "-h --help -t -w --wait -l --list" -- "${cur}") )
        return 0
    fi
}

complete -F _ja_complete ja

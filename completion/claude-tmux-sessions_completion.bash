#!/usr/bin/env bash
# Completion function for claude-tmux-sessions

# Mirrors tmux-resurrect's own resurrect_dir(): honour @resurrect-dir, then fall
# back to ~/.tmux/resurrect when it exists, otherwise the XDG data dir.
_claude_tmux_sessions_resurrect_dir() {
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
_claude_tmux_sessions_layout_files() {
    local dir
    dir=$(_claude_tmux_sessions_resurrect_dir)
    [[ -d $dir ]] || return 0
    [[ -e "$dir/last" ]] && printf '%s\n' "$dir/last"
    ls -t "$dir"/tmux_resurrect_*.txt 2>/dev/null | head -5
}

_claude_tmux_sessions_complete() {
    local cur prev cmd i opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD - 1]}"

    local commands="list save restore refresh patch-resurrect"

    # Locate the subcommand if one has been typed already
    for ((i = 1; i < COMP_CWORD; i++)); do
        case "${COMP_WORDS[i]}" in
            list | save | restore | refresh | patch-resurrect)
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
        list) opts="-h --help -a --all --json --ids-only" ;;
        save) opts="-h --help -o --output" ;;
        restore) opts="-h --help -f --file -n --dry-run" ;;
        refresh) opts="-h --help --agent --include-self --timeout -n --dry-run" ;;
        patch-resurrect) opts="-h --help -n --dry-run -v --verbose" ;;
    esac

    if [[ $cur == -* ]]; then
        COMPREPLY=($(compgen -W "$opts" -- "$cur"))
        return 0
    fi

    # patch-resurrect takes a resurrect layout file; suggest the saved ones by
    # absolute path unless a path is already being typed out by hand
    if [[ $cmd == patch-resurrect ]]; then
        if [[ $cur == [~/.]* || $cur == \$* ]]; then
            COMPREPLY=($(compgen -f -- "$cur"))
        else
            local IFS=$'\n'
            COMPREPLY=($(compgen -W "$(_claude_tmux_sessions_layout_files)" -- "$cur"))
        fi
        return 0
    fi

    return 0
}

complete -o filenames -F _claude_tmux_sessions_complete claude-tmux-sessions

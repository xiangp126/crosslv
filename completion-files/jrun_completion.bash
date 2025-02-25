#!/bin/bash

_jrun_completion() {
    local cur prev opts longopts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define short and long options
    opts="-h -s -w -p -f -W -o -k -t -i -S -D"
    longopts="--help --session --window --pane --file --wad-debug --output-directly --kernel-debug --packet-trace --ips-debug --scanunit-debug --dns-debug --packet-trace-addr"

    # Function to get active tmux sessions
    _get_tmux_sessions() {
        tmux list-sessions 2>/dev/null | cut -d: -f1
    }

    # Function to get windows from specified session
    _get_tmux_windows() {
        local session="$1"
        tmux list-windows -t "$session" 2>/dev/null | cut -d: -f1
    }

    # Function to get panes from specified session and window
    _get_tmux_panes() {
        local session="$1"
        local window="$2"
        tmux list-panes -t "$session:$window" 2>/dev/null | cut -d: -f1
    }

    # Function to suggest common command files
    _get_common_files() {
        echo "/data/bugzilla/debug.c /data/fos/command.txt $HOME/commands.txt"
    }

    # Handle option arguments
    case $prev in
        # Session options
        -s|--session)
            local sessions=$(_get_tmux_sessions)
            COMPREPLY=( $(compgen -W "${sessions}" -- ${cur}) )
            return 0
            ;;

        # Window options
        -w|--window)
            # Try to find the session from previous arguments
            local session="log"  # Default session
            for (( i=1; i<COMP_CWORD; i++ )); do
                if [[ "${COMP_WORDS[i]}" == "-s" || "${COMP_WORDS[i]}" == "--session" ]]; then
                    if [[ -n "${COMP_WORDS[i+1]}" && "${COMP_WORDS[i+1]:0:1}" != "-" ]]; then
                        session="${COMP_WORDS[i+1]}"
                    fi
                fi
            done
            local windows=$(_get_tmux_windows "$session")
            COMPREPLY=( $(compgen -W "${windows}" -- ${cur}) )
            return 0
            ;;

        # Pane options
        -p|--pane)
            # Try to find the session and window from previous arguments
            local session="log"  # Default session
            local window="1"     # Default window

            for (( i=1; i<COMP_CWORD; i++ )); do
                if [[ "${COMP_WORDS[i]}" == "-s" || "${COMP_WORDS[i]}" == "--session" ]]; then
                    if [[ -n "${COMP_WORDS[i+1]}" && "${COMP_WORDS[i+1]:0:1}" != "-" ]]; then
                        session="${COMP_WORDS[i+1]}"
                    fi
                elif [[ "${COMP_WORDS[i]}" == "-w" || "${COMP_WORDS[i]}" == "--window" ]]; then
                    if [[ -n "${COMP_WORDS[i+1]}" && "${COMP_WORDS[i+1]:0:1}" != "-" ]]; then
                        window="${COMP_WORDS[i+1]}"
                    fi
                fi
            done

            local panes=$(_get_tmux_panes "$session" "$window")
            COMPREPLY=( $(compgen -W "${panes}" -- ${cur}) )
            return 0
            ;;

        # File options
        -f|--file)
            # First suggest common command files, then fall back to regular file completion
            local common_files=$(_get_common_files)
            COMPREPLY=( $(compgen -W "${common_files}" -- ${cur}) )
            if [[ ${#COMPREPLY[@]} -eq 0 ]]; then
                COMPREPLY=( $(compgen -f -- "${cur}") )
            fi
            return 0
            ;;

        # Packet trace address option
        --packet-trace-addr)
            # Suggest some common IP addresses
            local ips="192.168.1.1 127.0.0.1"
            COMPREPLY=( $(compgen -W "${ips}" -- ${cur}) )
            return 0
            ;;
    esac

    # Handle initial options
    if [[ ${cur} == -* ]]; then
        # If it starts with --, only suggest long options
        if [[ ${cur} == --* ]]; then
            COMPREPLY=( $(compgen -W "${longopts}" -- ${cur}) )
        else
            # Suggest only short options
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
        fi
        return 0
    fi

    # Default to tmux session completion if no options have been specified
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        local sessions=$(_get_tmux_sessions)
        COMPREPLY=( $(compgen -W "${sessions}" -- ${cur}) )
        return 0
    fi

    # Default to file completion for first argument if no option specified
    COMPREPLY=( $(compgen -f -- "${cur}") )
    return 0
}

# Register the completion function for jrun
complete -F _jrun_completion jrun

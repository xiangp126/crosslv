#!/bin/bash
#
# Bash completion for jrun command
# Supports completing:
# - tmux sessions, windows, and panes in session[:window[.pane]] format
# - command-line options
# - file paths for -f/--file option
#

_jrun_completion() {
    local cur prev opts longopts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    #---------------------------------------------------------------
    # OPTION DEFINITIONS
    #---------------------------------------------------------------

    # Define short and long options
    opts="-h -s -w -p -f -d -W -O -K -T -I -S -D"
    longopts="--help --session --window --pane --file --debug --wad-debug \
              --output-directly --kernel-debug --packet-trace --ips-debug \
              --scanunit-debug --dns-debug --packet-trace"

    #---------------------------------------------------------------
    # HELPER FUNCTIONS
    #---------------------------------------------------------------

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

    #---------------------------------------------------------------
    # TMUX TARGET COMPLETION HANDLER
    #---------------------------------------------------------------
    function _complete_tmux_target() {
        local IFS=$'\n'
        local cur="${1}"
        local session_name="$(echo "${cur}" | sed 's/\\//g' | cut -d ':' -f 1)"
        local sessions

        # Get list of sessions
        sessions="$(tmux -q list-sessions 2>/dev/null | sed -re 's/([^:]+:).*$/\1/')"

        # If session name is provided, get windows for that session
        if [[ -n "${session_name}" ]]; then
            sessions="${sessions}
            $(tmux -q list-windows -t "${session_name}" 2>/dev/null | sed -re 's/^([^:]+):.*$/'"${session_name}"':\1/')"
        fi

        # Escape colons for proper completion
        cur="$(echo "${cur}" | sed -e 's/:/\\\\:/')"
        sessions="$(echo "${sessions}" | sed -e 's/:/\\\\:/')"

        COMPREPLY=( ${COMPREPLY[@]:-} $(compgen -W "${sessions}" -- "${cur}") )
    }

    #---------------------------------------------------------------
    # OPTION-SPECIFIC COMPLETION HANDLERS
    #---------------------------------------------------------------

    # Handle option-specific arguments
    case $prev in
        # Session option
        -s|--session)
            local sessions=$(_get_tmux_sessions)
            COMPREPLY=( $(compgen -W "${sessions}" -- ${cur}) )
            return 0
            ;;

        # Window option
        -w|--window)
            # Get first session as default if none specified
            local session=$(_get_tmux_sessions | head -n 1)

            # Try to find session from previous arguments
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

        # Pane option
        -p|--pane)
            # Get defaults if none specified
            local session=$(_get_tmux_sessions | head -n 1)
            local window=$(_get_tmux_windows "$session" | head -n 1)

            # Try to find session and window from previous arguments
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

        # File option
        -f|--file)
            # First suggest common command files, then fall back to regular file completion
            local cmd_files
            cmd_files=$(compgen -f -- "${cur}" | grep '^command')
            if [[ -n "$cmd_files" ]]; then
                COMPREPLY=( $(compgen -f -- "${cur}" | grep '^command') )
            else
                # If no command files found, fall back to common file completion
                COMPREPLY=( $(compgen -f -- "${cur}") )
            fi
            return 0
            ;;

        # Packet trace address option
        --packet-trace)
            # Suggest some common IP addresses
            local common_ips="192.168.1.1 127.0.0.1 10.0.0.1 172.16.0.1"
            COMPREPLY=( $(compgen -W "${common_ips}" -- ${cur}) )
            return 0
            ;;
    esac

    #---------------------------------------------------------------
    # OPTION AND DEFAULT COMPLETION LOGIC
    #---------------------------------------------------------------

    # Handle options (arguments starting with - or --)
    if [[ ${cur} == -* ]]; then
        if [[ ${cur} == --* ]]; then
            # Long options
            COMPREPLY=( $(compgen -W "${longopts}" -- ${cur}) )
        else
            # Short options
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
        fi
        return 0
    fi

    # For any non-option argument, try tmux target completion first
    _complete_tmux_target $cur
    if [[ ${#COMPREPLY[@]} -gt 0 ]]; then
        return 0
    fi

    # Fall back to file completion if tmux target completion didn't produce results
    COMPREPLY=( $(compgen -f -- "${cur}") )
    return 0
}

# Register the completion function for jrun
complete -F _jrun_completion jrun

#!/usr/bin/env bash
#
# Bash completion for tmux
# Original source: http://www.debian-administration.org/articles/317
# Based on: http://paste-it.appspot.com/Pj4mLycDE
#

#---------------------------------------------------------------
# HELPER FUNCTIONS
#---------------------------------------------------------------

# Handle path expansion for completion
_tmux_expand() {
    # Handle escape character
    [ "$cur" != "${cur%\\}" ] && cur="$cur"'\\'

    # Handle home directory expansion
    if [[ "$cur" == \~*/* ]]; then
        eval cur=$cur
    else
        if [[ "$cur" == \~* ]]; then
            cur=${cur#\~}
            COMPREPLY=($( compgen -P '~' -u $cur ))
            return ${#COMPREPLY[@]}
        fi
    fi
}

# File and directory completion helper
_tmux_filedir() {
    local IFS=' '
    _tmux_expand || return 0

    if [ "$1" = -d ]; then
        # Directory completion only
        COMPREPLY=(${COMPREPLY[@]} $( compgen -d -- $cur ))
        return 0
    fi

    # File completion
    COMPREPLY=(${COMPREPLY[@]} $( eval compgen -f -- \"$cur\" ))
}

#---------------------------------------------------------------
# TMUX ENTITY COMPLETION FUNCTIONS
#---------------------------------------------------------------

# Complete tmux client names
function _tmux_complete_client() {
    local IFS=$'\n'
    local cur="${1}"
    COMPREPLY=( ${COMPREPLY[@]:-} $(compgen -W "$(tmux -q list-clients 2>/dev/null | cut -f 1 -d ':')" -- "${cur}") )
}

# Complete tmux session names
function _tmux_complete_session() {
    local IFS=$'\n'
    local cur="${1}"
    COMPREPLY=( ${COMPREPLY[@]:-} $(compgen -W "$(tmux -q list-sessions 2>/dev/null | cut -f 1 -d ':')" -- "${cur}") )
}

# Complete tmux window names with optional session prefix
function _tmux_complete_window() {
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
# MAIN COMPLETION FUNCTION
#---------------------------------------------------------------

_tmux() {
    local cur prev
    local i cmd cmd_index option option_index
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Handle file path completion for -f option
    if [ ${prev} == -f ]; then
        _tmux_filedir
        return 0
    fi

    #---------------------------------------------------------------
    # COMMAND AND OPTION DETECTION
    #---------------------------------------------------------------

    # Search for the tmux command in the argument list
    local skip_next=0
    for ((i=1; $i<=$COMP_CWORD; i++)); do
        if [[ ${skip_next} -eq 1 ]]; then
            skip_next=0
        elif [[ ${COMP_WORDS[i]} != -* ]]; then
            cmd="${COMP_WORDS[i]}"
            cmd_index=${i}
            break
        elif [[ ${COMP_WORDS[i]} == -f ]]; then
            skip_next=1
        fi
    done

    # Search for the last option command
    skip_next=0
    for ((i=1; $i<=$COMP_CWORD; i++)); do
        if [[ ${skip_next} -eq 1 ]]; then
            skip_next=0
        elif [[ ${COMP_WORDS[i]} == -* ]]; then
            option="${COMP_WORDS[i]}"
            option_index=${i}
            if [[ ${COMP_WORDS[i]} == -- ]]; then
                break
            fi
        elif [[ ${COMP_WORDS[i]} == -f ]]; then
            skip_next=1
        fi
    done

    #---------------------------------------------------------------
    # COMMAND COMPLETION
    #---------------------------------------------------------------

    if [[ $COMP_CWORD -le $cmd_index ]]; then
        # The user has not specified a command yet - list available commands
        COMPREPLY=( ${COMPREPLY[@]:-} $(compgen -W "$(tmux start-server \; list-commands | cut -d' ' -f1)" -- "${cur}") )
    else
        # Command-specific completion logic
        case ${cmd} in
            #---------------------------------------------------------------
            # WINDOW OPERATIONS
            #---------------------------------------------------------------
            link-window|linkw)
                case "$prev" in
                    -s) _tmux_complete_window "${cur}" ;;
                    -t) _tmux_complete_window "${cur}" ;;
                    *) options="-s -t" ;;
                esac ;;

            unlink-window|unlinkw)
                case "$prev" in
                    -t) _tmux_complete_window "${cur}" ;;
                    *) options="-t" ;;
                esac ;;

            move-window|movew)
                case "$prev" in
                    -s) _tmux_complete_window "${cur}" ;;
                    -t) _tmux_complete_window "${cur}" ;;
                    *) options="-s -t" ;;
                esac ;;

            #---------------------------------------------------------------
            # SESSION OPERATIONS
            #---------------------------------------------------------------
            attach-session|attach)
                case "$prev" in
                    -t) _tmux_complete_session "${cur}" ;;
                    *) options="-t -d" ;;
                esac ;;

            detach-client|detach)
                case "$prev" in
                    -t) _tmux_complete_client "${cur}" ;;
                    *) options="-t" ;;
                esac ;;

            lock-client|lockc)
                case "$prev" in
                    -t) _tmux_complete_client "${cur}" ;;
                    *) options="-t" ;;
                esac ;;

            lock-session|locks)
                case "$prev" in
                    -t) _tmux_complete_session "${cur}" ;;
                    *) options="-t -d" ;;
                esac ;;

            new-session|new)
                case "$prev" in
                    -t) _tmux_complete_session "${cur}" ;;
                    -[n|d|s]) options="-d -n -s -t --" ;;
                    *)
                    if [[ ${COMP_WORDS[option_index]} == -- ]]; then
                        _command_offset ${option_index}
                    else
                        options="-d -n -s -t --"
                    fi
                    ;;
                esac
                ;;

            refresh-client|refresh)
                case "$prev" in
                    -t) _tmux_complete_client "${cur}" ;;
                    *) options="-t" ;;
                esac ;;

            rename-session|rename)
                case "$prev" in
                    -t) _tmux_complete_session "${cur}" ;;
                    *) options="-t" ;;
                esac ;;

            has-session|has|kill-session)
                case "$prev" in
                    -t) _tmux_complete_session "${cur}" ;;
                    *) options="-t" ;;
                esac ;;

            suspend-client|suspendc)
                case "$prev" in
                    -t) _tmux_complete_client "${cur}" ;;
                    *) options="-t" ;;
                esac ;;

            switch-client|switchc)
                case "$prev" in
                    -c) _tmux_complete_client "${cur}" ;;
                    -t) _tmux_complete_session "${cur}" ;;
                    *) options="-l -n -p -c -t" ;;
                esac ;;

            #---------------------------------------------------------------
            # FILE OPERATIONS
            #---------------------------------------------------------------
            source-file|source)
                _tmux_filedir
                ;;

            #---------------------------------------------------------------
            # KEY COMMANDS
            #---------------------------------------------------------------
            send-keys|send)
                case "$option" in
                    -t) _tmux_complete_window "${cur}" ;;
                    *) options="-t" ;;
                esac ;;
        esac

        # Add options to completion if defined
        if [[ -n "${options}" ]]; then
            COMPREPLY=( ${COMPREPLY[@]:-} $(compgen -W "${options}" -- "${cur}") )
        fi
    fi

    return 0
}

# Register the completion function
complete -F _tmux tmux

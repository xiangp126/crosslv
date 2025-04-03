#!/usr/bin/env bash

# Bash completion for jtail
_jt() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    local files="/var/log/auth.log /var/log/syslog /var/log/messages /var/log/secure /var/log/httpd/access_log /var/log/httpd/error_log /var/log/mysql/mysql.log"

    # Basic options
    # Define option lists
    opts="-h -l -f -d"
    long_opts="--help --file --language --debug"

    # Handle option-specific completions
    case "${prev}" in
        -l|--language)
            # Common languages for log files
            local languages="c cpp python bash ruby json xml html yaml ini log plain"
            COMPREPLY=( $(compgen -W "${languages}" -- "${cur}") )
            return 0
            ;;
        -f|--file)
            # File completion for the --file option
            COMPREPLY=( $(compgen -W "${files}" -- "${cur}") )
            return 0
            ;;
        *)
            ;;
    esac

    if [[ ${cur} == -* ]]; then
        # If it starts with --, only suggest long options
        if [[ ${cur} == --* ]]; then
            COMPREPLY=( $(compgen -W "${long_opts}" -- ${cur}) )
        else
            # Suggest only short options
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
        fi
        return 0
    fi

    # Default completion for file names
    COMPREPLY=( $(compgen -W "${files}" -- ${cur}) )
    return 0
}

# Register the completion function
complete -F _jt jt

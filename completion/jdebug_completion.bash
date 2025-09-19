#!/usr/bin/env bash

# Bash completion for jdebug command
_jdebug_complete() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # List of all short options
    opts="-t -w -d -T -l -u -p -P -N -r -k -s -h"

    # List of all long options
    long_opts="--target --worker-type --debug-port --max-attempts --username --password --port \
               --worker-cnt --wad-info --reboot --silent --kill --help --select"

    # Function to get hosts from /etc/hosts
    _get_hosts() {
        awk '/^[^#]/ { print $2 }' /etc/hosts
    }

    # Handle option arguments
    case $prev in
        # Target options
        -t|--target)
            COMPREPLY=( $(compgen -W "$(_get_hosts)" -- ${cur}) )
            return 0
            ;;
        # Worker type options
        -w|--worker-type)
            local workers="manager worker algo informer user-info dev-vuln cert-inspection cert-manager \
                           YouTube-filter-cache-service reverse-connector debug config-notify tls-fgpt-service \
                           ia-cache isolator"
            COMPREPLY=( $(compgen -W "${workers}" -- ${cur}) )
            return 0
            ;;
        # Debug Port options
        -d|--debug-port)
            local ports="444 9229"
            COMPREPLY=( $(compgen -W "${ports}" -- ${cur}) )
            return 0
            ;;
        -P|--port)
            local ports="22 8822"
            COMPREPLY=( $(compgen -W "${ports}" -- ${cur}) )
            return 0
            ;;
        # Worker count options
        -N|--worker-cnt)
            local counts="0 1 2 4 8"
            COMPREPLY=( $(compgen -W "${counts}" -- ${cur}) )
            return 0
            ;;
        --select)
            local counts="0 1 2 3 4"
            COMPREPLY=( $(compgen -W "${counts}" -- ${cur}) )
            return 0
            ;;
        # Max attempts options
        -T|--max-attempts)
            local attempts="1 2 3 4 5"
            COMPREPLY=( $(compgen -W "${attempts}" -- ${cur}) )
            return 0
            ;;
        # Username options
        -l|-u|--username)
            local users="admin root corsair"
            COMPREPLY=( $(compgen -W "${users}" -- ${cur}) )
            return 0
            ;;
        # Password options (no completion)
        -p|--password)
            return 0
            ;;
    esac

    # Handle initial options
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

    # If no options match, return all hosts from /etc/hosts
    COMPREPLY=( $(compgen -W "$(_get_hosts)" -- ${cur}) )
    return 0
}

# Register the completion function for jdebug
complete -F _jdebug_complete jdebug

# Bash completion for jroute command
_jroute_complete() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # List of all short options
    opts="-t -d -h"
    # List of all long options
    long_opts="--gateway --dry-run --help"

    # Handle option arguments
    case $prev in
        # Gateway selection options
        -t|--gateway)
            # List all available gateways from the script's mapping
            local gateways="fgt1 fgt2 fgt3 fpx1 fpx2 fpx3 host_br1 host_br2 host_br3 host_router"
            COMPREPLY=( $(compgen -W "${gateways}" -- ${cur}) )
            return 0
            ;;
        # No completion for other options
        -d|--dry-run|-h|--help)
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
}

# Register the completion function for jroute
complete -F _jroute_complete jroute

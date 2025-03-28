#!/usr/bin/env bash

_jr_completion() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define options
    opts="-h -v -d -k -r -c -n"
    long_opts="--help --vim --debug --kernel --rg-only --check-depends \
               --no-clipboard --regular-match"

    case "${prev}" in
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

    # If no options match, return standard file/directory completions
    # COMPREPLY=( $(compgen -f -- "${cur}") )
    return 0
}

# Register the completion function for the jr command
complete -F _jr_completion jr

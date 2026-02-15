#!/usr/bin/env bash

_code_completion() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define options
    opts="-h -d -f -a -v -p -s -c -r"
    long_opts="--help --debug --force --anyway --version --print --status --clean --reload \
               --install-extension \
               --locate-shell-integration-path \
               --list-extensions"

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
    COMPREPLY=( $(compgen -f -- "${cur}") )
    return 0
}

# Register the completion function for the code/cursor commands
complete -F _code_completion code
complete -F _code_completion cursor

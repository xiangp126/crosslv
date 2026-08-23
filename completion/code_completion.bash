#!/usr/bin/env bash

_code_completion() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define options
    opts="-h -d -e -v -p -s -c -r"
    long_opts="--help --debug --refresh --version --print --status --clean --reload \
               --install-extension \
               --list-extensions \
               --locate-shell-integration-path"

    case "${prev}" in
        --install-extension)
            COMPREPLY=( $(compgen -f -X '!*.vsix' -- "${cur}") $(compgen -d -- "${cur}") )
            return 0
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
complete -o filenames -F _code_completion code
complete -o filenames -F _code_completion cursor

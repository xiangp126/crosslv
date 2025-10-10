#!/usr/bin/env bash

_jdecode_completion() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define options
    opts="-h -e -i -o -w -v -l"
    long_opts="--help --exe --input --output --write --verbose --list-size"

    case "${prev}" in
        -v|--verbose)
            local verboseLevels=("all" "middle" "backtrace")
            COMPREPLY=( $(compgen -W "${verboseLevels[*]}" -- "${cur}") )
            return 0
	    ;;
        -l|--list-size)
            local listSizes=("3" "5" "10")
            COMPREPLY=( $(compgen -W "${listSizes[*]}" -- "${cur}") )
            return 0
        ;;
        -e|--exe)
            local exeFilePath=("./sysinit/init")
            COMPREPLY=( $(compgen -W "${exeFilePath[*]}" -- "${cur}") )
            return 0
        ;;
        -i|--input)
            local crashTxtPath=("./crash.txt" "/data/bugzilla/crash.txt")
            COMPREPLY=( $(compgen -W "${crashTxtPath[*]}" -- "${cur}") )
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
    # COMPREPLY=( $(compgen -f -- "${cur}") )
    return 0
}

# Register the completion function for the jr command
complete -F _jdecode_completion jdecode

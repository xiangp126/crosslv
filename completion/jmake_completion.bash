#!/usr/bin/env bash
# compgen filters the word list based on what the user has already typed ($cur)
# COMPREPLY is an array variable
# COMPREPLY stores the list of possible completion suggestions that will be shown to the user when they press the Tab key.
# COMP_WORDS is an array that contains all the words in the current command line.
# COMP_CWORD is an integer that represents the index of the word that the user is currently typing
# COMP_CWORD is a special shell variable that's automatically set by the bash completion system when a completion function is triggered
# COMP_CWORD can be used without the $ prefix
# The -- in a command is used to signal the end of options, ensuring that subsequent arguments are treated as positional parameters
# rather than options, even if they start with a dash (-).

# Completion function for jmake
_jmake_complete() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # List of all short options
    opts="-h -m -j -w -C -o -D -l"

    # List of all long options
    long_opts="--help --model --jobs --working-dir --clean --clean-db \
               --git-clean --build --bear --debug --max-attempt --no-verbose --list --link"

    # Handle option arguments
    case $prev in
        -m|--model)
            # GOLAN supported models
            local models="arava viper tamar carmel mustang gilboa argaman alpine"
            COMPREPLY=( $(compgen -W "${models}" -- ${cur}) )
            return 0
            ;;
        -w|--working-dir)
            # Directory completion
            COMPREPLY=( $(compgen -d -- ${cur}) )
            return 0
            ;;
        -j|--jobs)
            # Suggest common numbers of parallel jobs
            local jobs="1 2 4 8 16 32"
            COMPREPLY=( $(compgen -W "${jobs}" -- ${cur}) )
            return 0
            ;;
        --max-attempt)
            # Suggest common numbers for max attempts
            local attempts="1 2 3"
            COMPREPLY=( $(compgen -W "${attempts}" -- ${cur}) )
            return 0
            ;;
    esac

    # Handle initial options
    if [[ ${cur} == -* ]]; then
        if [[ ${cur} == --* ]]; then
            # Only suggest long options
            COMPREPLY=( $(compgen -W "${long_opts}" -- ${cur}) )
        else
            # Suggest short options
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
        fi
        return 0
    fi
}

# Register the completion function for jmake
complete -F _jmake_complete jmake

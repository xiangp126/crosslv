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

# GOLAN supported models (same order as jmake)
JMAKE_GOLAN_MODELS="arava tamar viper mustang carmel gilboa argaman alpine"

# Helper function to complete multiple models with comma separation
# Supports: jmake --models mustang,gilboa,<TAB> to suggest remaining models
# No quotes needed!
_jmake_complete_models() {
    local all_models="$JMAKE_GOLAN_MODELS"
    local typed_content="$cur"
    local remaining_models=""
    local last_word=""
    local prefix=""

    # Get the last word being typed (after last comma)
    # and the prefix (already completed models)
    if [[ "$typed_content" == *,* ]]; then
        last_word="${typed_content##*,}"
        prefix="${typed_content%,*},"
    else
        last_word="$typed_content"
        prefix=""
    fi

    # Filter out already-typed models from suggestions
    for m in $all_models; do
        # Check if this model is already in the comma-separated prefix
        if [[ ! ",$prefix" =~ ",$m," ]]; then
            remaining_models+="$m "
        fi
    done

    # Generate completions for the last word
    local completions
    completions=$(compgen -W "$remaining_models" -- "$last_word")

    if [[ -n "$completions" ]]; then
        COMPREPLY=()
        while IFS= read -r completion; do
            COMPREPLY+=("${prefix}${completion}")
        done <<< "$completions"
    fi
}

# Completion function for jmake
_jmake_complete() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # List of all short options
    opts="-h -a -j -w -c -o -D -l -b -m -N"

    # List of all long options
    long_opts="--help --all --jobs --working-dir --clean --clean-db \
               --git-clean --build --bear --debug --attempt --no-verbose --nicx --list --link --models --models-all --models-skip --continue --scratch \
               --fetch --push --rebase --add --stat --show"

    # Handle option arguments
    case $prev in
        -w|--working-dir)
            # Directory completion
            COMPREPLY=( $(compgen -d -- "$cur") )
            return 0
            ;;
        -j|--jobs)
            # Suggest common numbers of parallel jobs
            local jobs="1 2 4 8 16 32"
            COMPREPLY=( $(compgen -W "$jobs" -- "$cur") )
            return 0
            ;;
        --attempt)
            # Suggest common numbers for max attempts
            local attempts="1 2 3"
            COMPREPLY=( $(compgen -W "$attempts" -- "$cur") )
            return 0
            ;;
        -m|--models|--models-skip)
            # Multi-model completion with comma separation (e.g., mustang,gilboa,argaman)
            compopt -o nospace  # Don't add space after completion, allow user to type comma
            _jmake_complete_models
            return 0
            ;;
    esac

    # Handle initial options
    if [[ ${cur} == -* ]]; then
        if [[ ${cur} == --* ]]; then
            # Only suggest long options
            COMPREPLY=( $(compgen -W "$long_opts" -- "$cur") )
        else
            # Suggest short options
            COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
        fi
        return 0
    fi
}

# Register the completion function for jmake
complete -F _jmake_complete jmake
complete -F _jmake_complete jk

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
JMAKE_GOLAN_MODELS="alpine arava arava_codecov arava_ethlt aravacov argaman argaman_codecov \
                     carmel carmel_codecov carmel_ethlt carmelcov gilboa gilboa_codecov gilboacov \
                     mustang mustang_codecov mustangcov tamar tamar_codecov tamarcov \
                     viper viper_codecov vipercov"

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

# Major FW version to device ID mapping (mirrors jmake's FW_MAJOR_TO_DEVID)
declare -A _JMAKE_FW_MAJOR_TO_DEVID=(
    [22]="4125" [24]="41686" [26]="4127" [28]="4129"
    [32]="41692" [40]="4131" [82]="4133"
)
_JMAKE_RELEASE_BASE="/mswg/release/host_fw"

# Tiered version completion for --burn-official
# Tier 1: major (22, 40, 82, ...)
# Tier 2: major.minor (82.49, 82.42, ...)
# Tier 3: major.minor.patch (82.49.0050, 82.49.0052, ...)
_jmake_complete_fw_version() {
    local typed="$cur"
    local dots="${typed//[^.]/}"
    local dot_count=${#dots}

    if [[ $dot_count -eq 0 ]]; then
        local majors="${!_JMAKE_FW_MAJOR_TO_DEVID[*]}"
        COMPREPLY=( $(compgen -W "$majors" -- "$typed") )
        COMPREPLY=( "${COMPREPLY[@]/%/.}" )

    elif [[ $dot_count -eq 1 ]]; then
        local major="${typed%%.*}"
        local devId="${_JMAKE_FW_MAJOR_TO_DEVID[$major]}"
        [[ -z "$devId" ]] && return
        local relDir="${_JMAKE_RELEASE_BASE}/fw-${devId}"
        local minors
        minors=$(ls -d "${relDir}/fw-${devId}-rel-${major}_"*/ 2>/dev/null \
            | grep -v 'build-\|codecov' \
            | sed "s|.*/fw-${devId}-rel-${major}_\([0-9]*\)_.*/|\1|" \
            | sort -un)
        local candidates=""
        for m in $minors; do
            candidates+="${major}.${m} "
        done
        COMPREPLY=( $(compgen -W "$candidates" -- "$typed") )
        COMPREPLY=( "${COMPREPLY[@]/%/.}" )

    elif [[ $dot_count -eq 2 ]]; then
        local major="${typed%%.*}"
        local rest="${typed#*.}"
        local minor="${rest%%.*}"
        local devId="${_JMAKE_FW_MAJOR_TO_DEVID[$major]}"
        [[ -z "$devId" ]] && return
        local relDir="${_JMAKE_RELEASE_BASE}/fw-${devId}"
        local patches
        patches=$(ls -d "${relDir}/fw-${devId}-rel-${major}_${minor}_"*/ 2>/dev/null \
            | grep -v 'build-\|codecov' \
            | sed "s|.*/fw-${devId}-rel-${major}_${minor}_\([0-9]*\)/|\1|" \
            | sort -n)
        local candidates=""
        for p in $patches; do
            candidates+="${major}.${minor}.${p} "
        done
        COMPREPLY=( $(compgen -W "$candidates" -- "$typed") )
    fi
}

# Completion function for jmake
_jmake_complete() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # List of all short options
    opts="-h -a -A -j -w -c -o -D -l -b -m -N -p -T"

    # List of all long options
    long_opts="--help --all --all-extended --jobs --working-dir --clean --clean-db \
               --git-clean --clean-submodule --build --bear --debug \
               --attempt --no-verbose --nicx --list --list-extended --link --models \
               --skip --scratch --track --patch --ethlt --codecov --cov \
               --fetch --push --rebase --add --commit --amend --stat --df --diff --show \
               --burn --burn-official --firmware --device --fwreset --mft-install --ofed-start --ofed-stop \
               --power-cycle --docker-group"

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
        -T|--attempt)
            # Suggest common numbers for max attempts
            local attempts="1 2 3"
            COMPREPLY=( $(compgen -W "$attempts" -- "$cur") )
            return 0
            ;;
        -m|--models|--skip)
            # Multi-model completion with comma separation (e.g., mustang,gilboa,argaman)
            compopt -o nospace  # Don't add space after completion, allow user to type comma
            _jmake_complete_models
            return 0
            ;;
        --burn-official)
            compopt -o nospace
            _jmake_complete_fw_version
            return 0
            ;;
        --device)
            # Suggest MST device paths from /dev/mst/ if available
            if [[ -d /dev/mst ]]; then
                COMPREPLY=( $(compgen -W "$(ls /dev/mst/*pciconf* 2>/dev/null)" -- "$cur") )
            fi
            return 0
            ;;
        --firmware)
            compopt -o filenames
            COMPREPLY=( $(compgen -G "${cur}*.mlx" -- "$cur") )
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
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

_JMAKE_WORKSPACE_BASE="/auto/fwgwork1/$USER"
_JMAKE_WORKSPACE_MARKER="adabe"

# Static list of regression servers, used by --reg-malloc tab completion.
# Extracted from noga cache file. To refresh, run:
#   grep -oE '[a-z]+-fwreg-[0-9]+' \
#     /auto/sw/work/hca_fw/data/noga_alloc/cache_info/cache_setup_info.json | sort -u
_JMAKE_REG_SERVERS="\
l-fwreg-002 l-fwreg-003 l-fwreg-004 l-fwreg-005 l-fwreg-006 l-fwreg-007 \
l-fwreg-008 l-fwreg-009 l-fwreg-010 l-fwreg-011 l-fwreg-012 l-fwreg-013 \
l-fwreg-015 l-fwreg-016 l-fwreg-017 l-fwreg-018 l-fwreg-020 l-fwreg-021 \
l-fwreg-022 l-fwreg-023 l-fwreg-025 l-fwreg-026 l-fwreg-028 l-fwreg-029 \
l-fwreg-031 l-fwreg-032 l-fwreg-035 l-fwreg-036 l-fwreg-037 l-fwreg-038 \
l-fwreg-039 l-fwreg-040 l-fwreg-041 l-fwreg-042 l-fwreg-043 l-fwreg-044 \
l-fwreg-045 l-fwreg-046 l-fwreg-047 l-fwreg-048 l-fwreg-049 l-fwreg-050 \
l-fwreg-051 l-fwreg-052 l-fwreg-053 l-fwreg-054 l-fwreg-055 l-fwreg-056 \
l-fwreg-057 l-fwreg-058 l-fwreg-059 l-fwreg-060 l-fwreg-061 l-fwreg-062 \
l-fwreg-063 l-fwreg-064 l-fwreg-065 l-fwreg-066 l-fwreg-067 l-fwreg-068 \
l-fwreg-069 l-fwreg-070 l-fwreg-071 l-fwreg-072 l-fwreg-073 l-fwreg-074 \
l-fwreg-075 l-fwreg-080 l-fwreg-084 l-fwreg-085 l-fwreg-086 l-fwreg-087 \
l-fwreg-088 l-fwreg-089 l-fwreg-090 l-fwreg-091 l-fwreg-092 l-fwreg-093 \
l-fwreg-094 l-fwreg-095 l-fwreg-096 l-fwreg-097 l-fwreg-100 l-fwreg-101 \
l-fwreg-102 l-fwreg-103 l-fwreg-104 l-fwreg-105 l-fwreg-106 l-fwreg-107 \
l-fwreg-108 l-fwreg-109 l-fwreg-110 l-fwreg-113 l-fwreg-114 l-fwreg-115 \
l-fwreg-116 l-fwreg-117 l-fwreg-118 l-fwreg-119 l-fwreg-121 l-fwreg-122 \
l-fwreg-124 l-fwreg-125 l-fwreg-127 l-fwreg-129 l-fwreg-130 l-fwreg-131 \
l-fwreg-132 l-fwreg-133 l-fwreg-134 l-fwreg-136 l-fwreg-137 l-fwreg-138 \
l-fwreg-139 l-fwreg-140 l-fwreg-141 l-fwreg-142 l-fwreg-143 l-fwreg-144 \
l-fwreg-145 l-fwreg-146 l-fwreg-147 l-fwreg-148 l-fwreg-149 l-fwreg-164 \
l-fwreg-165 l-fwreg-166 l-fwreg-167 l-fwreg-170 l-fwreg-171 l-fwreg-172 \
l-fwreg-173 l-fwreg-174 l-fwreg-175 l-fwreg-176 l-fwreg-177 l-fwreg-178 \
l-fwreg-179 l-fwreg-180 l-fwreg-181 l-fwreg-182 l-fwreg-183 l-fwreg-184 \
l-fwreg-185 l-fwreg-186 l-fwreg-187 l-fwreg-188 l-fwreg-189 l-fwreg-190 \
l-fwreg-191 l-fwreg-192 l-fwreg-193 l-fwreg-194 l-fwreg-195 l-fwreg-196 \
l-fwreg-197 l-fwreg-198 l-fwreg-199 l-fwreg-201 l-fwreg-202 l-fwreg-203 \
l-fwreg-204 l-fwreg-205 l-fwreg-206 l-fwreg-207 l-fwreg-208 l-fwreg-209 \
l-fwreg-210 l-fwreg-211 l-fwreg-212 l-fwreg-213 l-fwreg-214 l-fwreg-215 \
l-fwreg-216 l-fwreg-217 l-fwreg-218 l-fwreg-219 l-fwreg-220 l-fwreg-221 \
l-fwreg-222 l-fwreg-224 l-fwreg-225 l-fwreg-226 \
m-fwreg-010 m-fwreg-011 m-fwreg-012 m-fwreg-013 m-fwreg-014 m-fwreg-016 \
m-fwreg-017 m-fwreg-018 m-fwreg-028 m-fwreg-029 m-fwreg-030 m-fwreg-031"

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
    long_opts="--help --all --all-extended --jobs --working-dir --clean --clean-db --git-clean --clean-submodule \
               --build --bear --debug --attempt --no-verbose --nicx --list --list-extended --link --models \
               --skip --scratch --track --patch --ethlt --codecov --cov --fetch --push --rebase --add --commit \
               --amend --stat --df --diff --show --burn --burn-official --firmware --ini --device --fw-query --fw-reset \
               --mft-install --mft-start --mft-stop --mft-restart --ofed-restart --ofed-start --ofed-stop \
               --power-cycle --power-on --power-off --docker-group \
               --reg-query --reg-malloc --reg-mine --reg-idle --reg-cancel"

    # Handle option arguments
    case $prev in
        -w|--working-dir)
            # Suggest workspaces under $_JMAKE_WORKSPACE_BASE that contain an $_JMAKE_WORKSPACE_MARKER/ subdir
            compopt -o nospace 2>/dev/null
            local candidates="" match ws
            for match in "${_JMAKE_WORKSPACE_BASE}"/*/"${_JMAKE_WORKSPACE_MARKER}"/; do
                [[ -d "$match" ]] || continue
                ws="${match%${_JMAKE_WORKSPACE_MARKER}/}"
                candidates+="$ws "
            done
            COMPREPLY=( $(compgen -W "$candidates" -- "$cur") )
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
            COMPREPLY=( $(compgen -f -X '!*.mlx' -- "$cur") )
            return 0
            ;;
        --ini)
            compopt -o filenames
            COMPREPLY=( $(compgen -f -X '!*.ini' -- "$cur") )
            return 0
            ;;
        --power-cycle|--power-on|--power-off)
            local servers="l-fwdev-107 m-fwdev-167 $_JMAKE_REG_SERVERS"
            COMPREPLY=( $(compgen -W "$servers" -- "$cur") )
            return 0
            ;;
        --reg-malloc)
            COMPREPLY=( $(compgen -W "$_JMAKE_REG_SERVERS" -- "$cur") )
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

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
    opts="-h -m -d -w -j -c -C -g -B -o -t -s -P -p -u -l -k -O"

    # List of all long options
    long_opts="--help --model --debug --working-dir --jobs --clean --configure --generate \
               --build-target --build --clean-removal --max-build-attempt \
               --target --sync-file --sync-port --username --password --kernel \
               --disable-optimization"

    # Function to get hosts from /etc/hosts
    _get_hosts() {
        awk '/^[^#]/ { print $2 }' /etc/hosts
    }

    # Handle option arguments
    case $prev in
        # Build options
        -m|--model)
            # You can customize this list based on your available models
            local models="vmware FGT_VM64_KVM VMWARE"
            COMPREPLY=( $(compgen -W "${models}" -- ${cur}) )
            return 0
            ;;
        -w|--working-dir)
            # Directory completion
            COMPREPLY=( $(compgen -d -- ${cur}) )
            return 0
            ;;
        -j|--jobs)
            # Suggest some common numbers of jobs
            local jobs="1 2 4 8 16"
            COMPREPLY=( $(compgen -W "${jobs}" -- ${cur}) )
            return 0
            ;;
        -B|--build-target)
            # Common build targets
            local targets="image.out"
            COMPREPLY=( $(compgen -W "${targets}" -- ${cur}) )
            return 0
            ;;
        -T|--max-build-attempt)
            # Suggest some common numbers for max attempts
            local attempts="1 2 3"
            COMPREPLY=( $(compgen -W "${attempts}" -- ${cur}) )
            return 0
            ;;
        # Sync options
        -t|--target)
            COMPREPLY=( $(compgen -W "$(_get_hosts)" -- ${cur}) )
            return 0
            ;;
        -s|--sync-file)
            # File completion with .out extension
            COMPREPLY=( $(compgen -f -X '!*.out' -- ${cur}) )
            return 0
            ;;
        -P|--sync-port)
            # Common SSH ports
            local ports="22 8822 8022"
            COMPREPLY=( $(compgen -W "${ports}" -- ${cur}) )
            return 0
            ;;
        -l|-u|--username)
            # Common FortiGate usernames
            local users="admin corsair root"
            COMPREPLY=( $(compgen -W "${users}" -- ${cur}) )
            return 0
            ;;
        -p|--password)
            # For security reasons, don't suggest passwords
            return 0
            ;;
    esac

    # Handle initial options
    if [[ ${cur} == -* ]]; then
        # If it starts with --, only suggest long options
        if [[ ${cur} == --* ]]; then
            COMPREPLY=( $(compgen -W "${long_opts}" -- ${cur}) )
        else
            # Suggest both short and long options
            # COMPREPLY=( $(compgen -W "${opts} ${long_opts}" -- ${cur}) )
            # Suggest only short options
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
        fi
        return 0
    fi
}

# Register the completion function for jmake
complete -F _jmake_complete jmake

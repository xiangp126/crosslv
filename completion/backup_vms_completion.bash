#!/usr/bin/env bash

_backup_vms_completion() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define options
    opts="-h -d -b -a"
    long_opts="--help --debug --backup --all"

    case "${prev}" in
        -b|--backup)
            # Complete directories for the backup path
            COMPREPLY=( $(compgen -d -- "${cur}") )
            return 0
            ;;
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

    # Complete VM names by default
    local vm_names
    vm_names=$(virsh list --all --name 2>/dev/null | grep -v "^$")
    COMPREPLY=( $(compgen -W "${vm_names}" -- "${cur}") )
    return 0
}

# Register the completion function for the backup_vms command
complete -F _backup_vms_completion backup_vms
#!/usr/bin/env bash

_delete_vms_completion() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define options
    opts="-h -d -r -a -b -k"
    long_opts="--help --debug --restore --all --backup --keep-disk"

    # Main backup directory
    MAIN_BACKUP_DIR="/data/Backup/vms"

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

    # Check if we're in restore mode
    for ((i=0; i<${#COMP_WORDS[@]}; i++)); do
        if [[ "${COMP_WORDS[i]}" == "-r" || "${COMP_WORDS[i]}" == "--restore" ]]; then
            # In restore mode, complete with backed up VM names
            local backed_vms
            if [[ -d "$MAIN_BACKUP_DIR" ]]; then
                backed_vms=$(find "$MAIN_BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null)
                COMPREPLY=( $(compgen -W "${backed_vms}" -- "${cur}") )
            fi
            return 0
        fi
    done

    # Default: Complete VM names from virsh list
    local vm_names
    vm_names=$(virsh list --all --name 2>/dev/null | grep -v "^$")
    COMPREPLY=( $(compgen -W "${vm_names}" -- "${cur}") )
    return 0
}

# Register the completion function for the delete_vms command
complete -F _delete_vms_completion delete_vms
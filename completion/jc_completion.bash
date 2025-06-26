# completion.bash for oneKey.sh

_jc_complete() {
    local cur prev opts long_opts
    COMPREPLY=() # Array that will hold the completions
    cur="${COMP_WORDS[COMP_CWORD]}" # Current cursor position
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define command options
    opts="-h -n -d -f"
    long_opts="--help --no-tools --debug --clangd --link-clang-format --nvm --wireshark \
               --auto-remove --upgrade --docker --prerequisite --chinese-pinyin \
               --vnc --vnc-start --vnc-stop --vnc-restart --unlock-vnc --lock-vnc --vnclock \
               --firefox --update --opengrok-start --opengrok-stop --opengrok-restart \
               --opengrok --opengrok-indexer --samba --samba-bypass-password --git-lfs \
               --litellm-start --litellm-stop --litellm-restart --litellm"

    case "${prev}" in
        --vnclock)
            local vnclock_options="unlock lock status"
            COMPREPLY=( $(compgen -W "${vnclock_options}" -- ${cur}) )
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

    COMPREPLY=( $(compgen -f -- "${cur}") )

    return 0
}

# Register the completion function
complete -F _jc_complete jc

# completion.bash for oneKey.sh

_jc_complete() {
    local cur prev opts long_opts
    COMPREPLY=() # Array that will hold the completions
    cur="${COMP_WORDS[COMP_CWORD]}" # Current cursor position
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define command options
    opts="-h -n -d -f"
    long_opts="--help --no-tools --debug --clangd --link-clang-format --nvm --wireshark \
               --auto-remove --upgrade --docker --apps --apps-only --chinese-pinyin \
               --vnc --vnc-start --vnc-stop --vnc-restart --unlock-vnc --lock-vnc --vnclock \
               --firefox --update --samba --samba-reset-password --git-lfs \
               --check-tls --swap --gdm --text --ai --cursor-backup --cursor-restore \
               --rtsp --rtsp-all --rtsp-kill --rtsp-list --rtsp-raw --rtsp-h264 \
               --rtsp-stream --rtsp-ip --rtsp-resolution"

    case "${prev}" in
        --vnclock)
            local vnclock_options="unlock lock status"
            COMPREPLY=( $(compgen -W "${vnclock_options}" -- ${cur}) )
            return 0
            ;;
        --check-tls)
            local hosts="google.com deepseek.com claude.ai"
            COMPREPLY=( $(compgen -W "${hosts}" -- ${cur}) )
            return 0
            ;;
        --rtsp-stream)
            local streams="c700_01_raw c700_02_raw"
            COMPREPLY=( $(compgen -W "${streams}" -- ${cur}) )
            return 0
            ;;
        --rtsp-ip)
            local ips="192.168.10.240 192.168.10.150"
            COMPREPLY=( $(compgen -W "${ips}" -- ${cur}) )
            return 0
            ;;
        --rtsp-resolution)
            # 3360x1890  - Mi Monitor 27" (native)
            # 3456x2234  - Built-in MacBook Pro
            # 3840x2160  - 4K monitors
            # 2560x1440  - Common 27" QHD
            # 2560x1600  - MacBook Pro 14"/16"
            # 1920x1200  - 16:10 laptops
            # 1920x1080  - 15" Lenovo / common FHD
            # 1366x768   - Budget 15" laptops
            local resolutions="3360x1890 3456x2234 3840x2160 2560x1440 2560x1600 1920x1200 1920x1080 1366x768"
            COMPREPLY=( $(compgen -W "${resolutions}" -- ${cur}) )
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

# completion.bash for oneKey.sh

# Single source of truth for camera names. Add a camera by appending here; the
# ACL target list and RTSP stream list update automatically.
JC_CAMERAS="c700_01 c700_02 c700_03 c700_04"

# Each camera exposes two go2rtc streams: <camera>_raw and <camera>_1080p.
JC_STREAM_VARIANTS="raw 1080p"

# Derived: tokens accepted by --acl-block / --acl-unblock / --acl-status / --acl-restart.
JC_ACL_TARGETS="$JC_CAMERAS all"

# Derived: tokens accepted by --rtsp-stream (cartesian product cameras x variants).
JC_RTSP_STREAMS=
for _c in $JC_CAMERAS; do
    for _v in $JC_STREAM_VARIANTS; do
        JC_RTSP_STREAMS+="${_c}_${_v} "
    done
done
JC_RTSP_STREAMS="${JC_RTSP_STREAMS% }"
unset _c _v

# Comma-separated multi-target completion for the --acl-* flags.
# Supports: jc --acl-block c700_01,c700_03,<TAB> -> suggests remaining tokens.
_jc_complete_acl_targets() {
    local typed="$cur" prefix="" last_word="" remaining="" m

    if [[ "$typed" == *,* ]]; then
        last_word="${typed##*,}"
        prefix="${typed%,*},"
    else
        last_word="$typed"
    fi

    for m in $JC_ACL_TARGETS; do
        if [[ ! ",$prefix" =~ ",$m," ]]; then
            remaining+="$m "
        fi
    done

    local completions
    completions=$(compgen -W "$remaining" -- "$last_word")
    if [[ -n "$completions" ]]; then
        COMPREPLY=()
        while IFS= read -r c; do
            COMPREPLY+=("${prefix}${c}")
        done <<< "$completions"
    fi
}

# Comma-separated multi-stream completion for --rtsp-stream.
# Supports: jc --rtsp-stream c700_01_raw,<TAB> -> suggests remaining stream tokens.
_jc_complete_rtsp_streams() {
    local typed="$cur" prefix="" last_word="" remaining="" m

    if [[ "$typed" == *,* ]]; then
        last_word="${typed##*,}"
        prefix="${typed%,*},"
    else
        last_word="$typed"
    fi

    for m in $JC_RTSP_STREAMS; do
        if [[ ! ",$prefix" =~ ",$m," ]]; then
            remaining+="$m "
        fi
    done

    local completions
    completions=$(compgen -W "$remaining" -- "$last_word")
    if [[ -n "$completions" ]]; then
        COMPREPLY=()
        while IFS= read -r c; do
            COMPREPLY+=("${prefix}${c}")
        done <<< "$completions"
    fi
}

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
               --firefox --update --samba --samba-reset-password --git-lfs --check-tls --swap \
               --gdm --text --claude --claude-remove --acl-block --acl-unblock --acl-status --acl-restart \
               --claude-backup --claude-restore --claude-desktop-backup --claude-desktop-restore --claude-link-mcp \
               --codex --codex-remove --codex-backup --codex-restore \
               --cursor-backup --cursor-restore --singbox --singbox-xray --singbox-xray-autossh --singbox-xray-sslh --singbox-wg \
               --xray --xray-port --xray-server --xray-remove \
               --sslh --sslh-ssh-port --sslh-xray-port --sslh-status --sslh-rollback --sslh-remove \
               --bbr --bbr-status \
               --wg --wg-port --wg-server --wg-client --wg-remove \
               --rtsp --rtsp-all --rtsp-kill --rtsp-list --rtsp-raw --rtsp-1080 \
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
            compopt -o nospace 2>/dev/null
            _jc_complete_rtsp_streams
            return 0
            ;;
        --rtsp-ip)
            local ips="192.168.10.240 192.168.10.150"
            COMPREPLY=( $(compgen -W "${ips}" -- ${cur}) )
            return 0
            ;;
        --xray-port|--wg-port)
            local ports="22 443 3389 5900 5902 5903 5904 5905 5906 5907 5908 5909 6000"
            COMPREPLY=( $(compgen -W "${ports}" -- ${cur}) )
            return 0
            ;;
        --sslh-ssh-port)
            # Internal sshd port after sslh takes over :22. Default 8822.
            local ports="8822 8802 8022 2222 22022 22122 22222 22322"
            COMPREPLY=( $(compgen -W "${ports}" -- ${cur}) )
            return 0
            ;;
        --sslh-xray-port)
            # Local xray VLESS+REALITY port (sslh's TLS backend). Default 5902.
            local ports="5902 5903 5904 5905 443"
            COMPREPLY=( $(compgen -W "${ports}" -- ${cur}) )
            return 0
            ;;
        --xray-server|--wg-server)
            local ips=$(hostname -I 2>/dev/null || ipconfig getifaddr en0 2>/dev/null)
            COMPREPLY=( $(compgen -W "${ips}" -- ${cur}) )
            return 0
            ;;
        --wg-client)
            local names="client1 client2 ubuntu01 ubuntu02"
            COMPREPLY=( $(compgen -W "${names}" -- ${cur}) )
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
        --acl-block|--acl-unblock|--acl-status|--acl-restart)
            compopt -o nospace 2>/dev/null
            _jc_complete_acl_targets
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

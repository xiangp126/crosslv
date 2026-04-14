# completion.bash for jw (WireGuard wrapper)
# Adapted from upstream wg.bash-completion

_jw_complete() {
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY+=( $(compgen -W "help show showconf set setconf addconf syncconf genkey genpsk pubkey" -- "${COMP_WORDS[1]}") )
        return
    fi

    case "${COMP_WORDS[1]}" in
        genkey|genpsk|pubkey|help) return ;;
        show|showconf|set|setconf|addconf|syncconf) ;;
        *) return ;;
    esac

    if [[ $COMP_CWORD -eq 2 ]]; then
        local extra
        [[ ${COMP_WORDS[1]} == show ]] && extra=" all interfaces"
        COMPREPLY+=( $(compgen -W "$(sudo wg show interfaces 2>/dev/null)$extra" -- "${COMP_WORDS[2]}") )
        return
    fi

    if [[ $COMP_CWORD -eq 3 && ${COMP_WORDS[1]} == show && ${COMP_WORDS[2]} != interfaces ]]; then
        COMPREPLY+=( $(compgen -W "public-key private-key listen-port peers preshared-keys endpoints allowed-ips fwmark latest-handshakes persistent-keepalive transfer dump" -- "${COMP_WORDS[3]}") )
        return
    fi

    if [[ $COMP_CWORD -eq 3 && ( ${COMP_WORDS[1]} == setconf || ${COMP_WORDS[1]} == addconf || ${COMP_WORDS[1]} == syncconf ) ]]; then
        compopt -o filenames
        local a
        mapfile -t a < <(compgen -f -- "${COMP_WORDS[3]}")
        COMPREPLY+=( "${a[@]}" )
        return
    fi
}

complete -F _jw_complete jw

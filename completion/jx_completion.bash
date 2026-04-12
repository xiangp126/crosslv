#!/usr/bin/env bash
# Completion function for xray-manager (jx)

_jx_complete() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local commands="add change info del url qr start stop restart status log help"

    case $prev in
        jx|xray-manager)
            COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
            return 0
            ;;
        add)
            # Suggest default port
            COMPREPLY=( $(compgen -W "443 8443" -- "$cur") )
            return 0
            ;;
        info|del|change|url|qr)
            # Suggest existing config names (check both system and user paths)
            local confDir=""
            if [[ -d /etc/xray/conf ]]; then
                confDir="/etc/xray/conf"
            elif [[ -d "$HOME/.config/xray/conf" ]]; then
                confDir="$HOME/.config/xray/conf"
            fi
            if [[ -n "$confDir" ]]; then
                local configs=$(ls "$confDir"/*.json 2>/dev/null | xargs -I{} basename {} .json)
                COMPREPLY=( $(compgen -W "$configs" -- "$cur") )
            fi
            return 0
            ;;
    esac

    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "--help" -- "$cur") )
        return 0
    fi

    COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
}

complete -F _jx_complete xray-manager
complete -F _jx_complete jx

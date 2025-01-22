_jssh_complete() {
    local cur prev opts long_opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # List of all short options
    opts="-t -l -u -p -P -d -h -c -C -J -L -R -v -S -T -X -m"

    # List of all long options
    long_opts="--target --username --password --port --debug --help \
              --command --live-capture --jump --jump-password \
              --local-forward --reverse-forward --vdom \
              --sftp --telnet --x11 --mount"

    # Handle option arguments
    case $prev in
        # Target and Jump server options
        -t|--target|-J|--jump)
            # Common targets and jump servers
            local targets="fgt1 fgt2 fpx1 fpx3"
            COMPREPLY=( $(compgen -W "${targets}" -- ${cur}) )
            return 0
            ;;

        # User options
        -l|-u|--username)
            # Common usernames
            local users="admin root corsair"
            COMPREPLY=( $(compgen -W "${users}" -- ${cur}) )
            return 0
            ;;

        # Port options
        -P|--port)
            # Common SSH ports
            local ports="22 8822 8022"
            COMPREPLY=( $(compgen -W "${ports}" -- ${cur}) )
            return 0
            ;;

        # VDOM options
        -v|--vdom)
            # Common VDOMs
            local vdoms="root vdom1 vdom2"
            COMPREPLY=( $(compgen -W "${vdoms}" -- ${cur}) )
            return 0
            ;;

        # Mount options
        -m|--mount)
            # Directory completion
            COMPREPLY=( $(compgen -d -- ${cur}) )
            return 0
            ;;

        # Port forwarding options
        -L|--local-forward|-R|--reverse-forward)
            # Common port forwarding patterns
            local forwards="127.0.0.1:8880:172.18.52.37:22"
            COMPREPLY=( $(compgen -W "${forwards}" -- ${cur}) )
            return 0
            ;;

        # Command options with complex commands
        -c|--command)
            # Define commands as an array to preserve spaces and quotes
            local commands=(
                'tcpdump -i any -s 0 -U -n -w - "not port 22 and not arp"'
                'tcpdump -i any -s 0 -U -n -vv "not port 22 and not arp"'
            )

            # Convert commands array to a format suitable for completion
            local IFS=$'\n'
            COMPREPLY=( $(compgen -W "$(printf '%q\n' "${commands[@]}")" -- ${cur}) )
            # Disable space appending for command completion
            compopt -o nospace
            return 0
            ;;

        # Password options (no completion)
        -p|--password|--jump-password)
            return 0
            ;;
    esac

    # Handle initial options
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
}

# Register the completion function for jssh
complete -F _jssh_complete jssh

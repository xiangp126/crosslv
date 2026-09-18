_jskill_complete() {
    local cur commands skills
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    commands="list path check sync add"

    if (( COMP_CWORD == 1 )); then
        mapfile -t COMPREPLY < <(compgen -W "$commands" -- "$cur")
        return 0
    fi

    case "${COMP_WORDS[1]}" in
        path)
            skills=$(jskill list --json 2>/dev/null | python3 -c \
                'import json,sys; print(" ".join(x["name"] for x in json.load(sys.stdin)))' \
                2>/dev/null)
            mapfile -t COMPREPLY < <(compgen -W "$skills" -- "$cur")
            ;;
        check)
            mapfile -t COMPREPLY < <(compgen -W "--source-only --json" -- "$cur")
            ;;
        sync)
            mapfile -t COMPREPLY < <(compgen -W "--dry-run --backup-conflicts --backup-dir" -- "$cur")
            ;;
        add)
            mapfile -t COMPREPLY < <(compgen -W "--description --title --host-adapters --dry-run" -- "$cur")
            ;;
        list)
            mapfile -t COMPREPLY < <(compgen -W "--json" -- "$cur")
            ;;
    esac
}

complete -F _jskill_complete jskill

# Bash completion for claude (Claude Code).
#
# This file ships flag completion for both:
#   - native claude flags (parsed from `claude --help` output, plus the
#     subcommand list under "Commands:")
#   - the wrapper flags injected by track-files/bashrc:
#       --auto-approve / -y  ⇒ launch ja daemon for auto-approving prompts
#
# Maintenance: when claude adds new flags, regenerate the lists below by
# running:
#     claude --help 2>&1 | grep -E '^  -' \
#         | sed -E 's/^[[:space:]]+//; s/[[:space:]]{2,}.*$//' \
#         | tr ',' '\n' | sed -E 's/^[[:space:]]+//; s/[[:space:]].*$//' \
#         | grep -E '^-' | sort -u
#
# Version baseline: 2.1.121

_claude_complete() {
    local cur prev short_opts long_opts subcommands wrapper_short wrapper_long
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Wrapper-injected flags (see _ai_start_ja_if_needed in bashrc).
    # Single source of truth — add new wrapper flags here only.
    # Split into short / long so we can merge them into the right
    # bucket below ('-' completion vs '--' completion).
    wrapper_short="-y"
    wrapper_long="--auto-approve"

    short_opts="-c -d -h -n -p -r -v -w"

    long_opts="--add-dir --agent --agents --allow-dangerously-skip-permissions \
               --allowedTools --allowed-tools --append-system-prompt --bare \
               --betas --brief --chrome --continue --dangerously-skip-permissions \
               --debug --debug-file --disable-slash-commands --disallowedTools \
               --disallowed-tools --effort --exclude-dynamic-system-prompt-sections \
               --fallback-model --file --fork-session --from-pr --help --ide \
               --include-hook-events --include-partial-messages --input-format \
               --json-schema --max-budget-usd --mcp-config --mcp-debug --model \
               --name --no-chrome --no-session-persistence --output-format \
               --permission-mode --plugin-dir --print \
               --remote-control-session-name-prefix --replay-user-messages \
               --resume --session-id --setting-sources --settings \
               --strict-mcp-config --system-prompt --tmux --tools --verbose \
               --version --worktree"

    subcommands="agents auth auto-mode doctor install mcp plugin plugins \
                 setup-token ultrareview update upgrade"

    # If the previous arg is one of the option-with-value flags, fall back
    # to default file completion for the value.
    case "${prev}" in
        --add-dir|--debug-file|--mcp-config|--plugin-dir|--settings|--file)
            COMPREPLY=( $(compgen -f -- "${cur}") )
            return 0
            ;;
        --model|--fallback-model)
            COMPREPLY=( $(compgen -W "haiku sonnet opus" -- "${cur}") )
            return 0
            ;;
        --output-format)
            COMPREPLY=( $(compgen -W "text json stream-json" -- "${cur}") )
            return 0
            ;;
        --input-format)
            COMPREPLY=( $(compgen -W "text stream-json" -- "${cur}") )
            return 0
            ;;
        --effort)
            COMPREPLY=( $(compgen -W "low medium high xhigh max" -- "${cur}") )
            return 0
            ;;
        --permission-mode)
            COMPREPLY=( $(compgen -W "default plan acceptEdits bypassPermissions" -- "${cur}") )
            return 0
            ;;
    esac

    # Mirror jc/ja style: --<TAB> shows long options only, -<TAB> shows
    # short options only. Wrapper opts merged into the matching bucket.
    if [[ ${cur} == --* ]]; then
        COMPREPLY=( $(compgen -W "${long_opts} ${wrapper_long}" -- "${cur}") )
        return 0
    elif [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "${short_opts} ${wrapper_short}" -- "${cur}") )
        return 0
    fi

    # First non-flag word — could be a subcommand. Check if any prior
    # word was already a non-flag (then we're past subcommand selection).
    local i has_subcommand=0
    for (( i = 1; i < COMP_CWORD; i++ )); do
        case "${COMP_WORDS[i]}" in
            -*) ;;
            *) has_subcommand=1; break ;;
        esac
    done

    if [[ ${has_subcommand} -eq 0 ]]; then
        COMPREPLY=( $(compgen -W "${subcommands}" -- "${cur}") )
        return 0
    fi

    # Default: file completion.
    COMPREPLY=( $(compgen -f -- "${cur}") )
}

complete -F _claude_complete claude

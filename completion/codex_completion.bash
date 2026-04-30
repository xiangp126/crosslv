# Bash completion for codex (OpenAI Codex CLI).
#
# This file ships flag completion for both:
#   - native codex flags (parsed from `codex -h` output, plus the
#     subcommand list under "Commands:")
#   - the wrapper flags injected by track-files/bashrc:
#       --auto-approve / -y  ⇒ launch ja daemon for auto-approving prompts
#
# Note: codex itself has a `codex completion bash` subcommand that
# generates a real bash completion script. We deliberately don't use
# that and ship our own static script for two reasons:
#   1. We need to inject our wrapper flags (--auto-approve / -y) which
#      codex's own script doesn't know about
#   2. Sourcing codex's output requires running codex on every shell
#      startup, which adds latency
#
# Maintenance: when codex adds new flags, regenerate the lists below by
# running:
#     codex -h 2>&1 | grep -E '^  -' \
#         | sed -E 's/^[[:space:]]+//; s/[[:space:]]{2,}.*$//' \
#         | tr ',' '\n' | sed -E 's/^[[:space:]]+//; s/[[:space:]].*$//' \
#         | grep -E '^-' | sort -u

_codex_complete() {
    local cur prev short_opts long_opts subcommands wrapper_short wrapper_long
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Wrapper-injected flags (see _ai_start_ja_if_needed in bashrc).
    # Single source of truth — add new wrapper flags here only.
    wrapper_short="-y"
    wrapper_long="--auto-approve"

    short_opts="-a -c -C -h -i -m -p -s -V"

    long_opts="--add-dir --ask-for-approval --cd --config \
               --dangerously-bypass-approvals-and-sandbox --disable --enable \
               --full-auto --help --image --local-provider --model \
               --no-alt-screen --oss --profile --remote --remote-auth-token-env \
               --sandbox --search --version"

    subcommands="exec review login logout mcp plugin mcp-server app-server \
                 app completion sandbox debug apply resume fork cloud \
                 exec-server features help"

    # Value-completion for option-with-arg flags.
    case "${prev}" in
        -C|--cd|--add-dir|-i|--image)
            COMPREPLY=( $(compgen -f -- "${cur}") )
            return 0
            ;;
        -m|--model)
            COMPREPLY=( $(compgen -W "gpt-5 gpt-5-codex o3 o4-mini" -- "${cur}") )
            return 0
            ;;
        --local-provider)
            COMPREPLY=( $(compgen -W "lmstudio ollama" -- "${cur}") )
            return 0
            ;;
        -s|--sandbox)
            COMPREPLY=( $(compgen -W "read-only workspace-write danger-full-access" -- "${cur}") )
            return 0
            ;;
        -a|--ask-for-approval)
            COMPREPLY=( $(compgen -W "untrusted on-failure on-request never" -- "${cur}") )
            return 0
            ;;
    esac

    # Mirror jc/ja/claude style: --<TAB> shows long options only,
    # -<TAB> shows short options only. Wrapper opts merged into the
    # matching bucket.
    if [[ ${cur} == --* ]]; then
        COMPREPLY=( $(compgen -W "${long_opts} ${wrapper_long}" -- "${cur}") )
        return 0
    elif [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "${short_opts} ${wrapper_short}" -- "${cur}") )
        return 0
    fi

    # First non-flag word — could be a subcommand. Walk back looking for
    # earlier non-flag words to decide whether subcommand selection is
    # still in play.
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

complete -F _codex_complete codex

#!/bin/bash
# set -x
# Wrapper for the VS Code CLI, with Cursor remote compatibility.
# Works on local machines (macOS/Linux) and remote editor servers.
# To install, add `source /path/to/code-function.sh` to your ~/.bashrc.
# For usage, run `code --help`.

if declare -F _code_pre_check &> /dev/null; then
    return
fi

# Colors for output
export MAGENTA='\033[0;35m'
export LIGHTYELLOW='\033[0;93m'
export GREY='\033[0;90m'
export RED='\033[0;31m'
export BLUE='\033[0;34m'
export GREEN='\033[0;32m'
export RESET='\033[0m'

# Helper function: usage
_code_usage() {
    cat << _EOF
Usage: code [options] <args>

Description:
    A wrapper for the VS Code server CLI, compatible with Cursor remote sessions.
    It finds the CLI for the current editor window and sets the correct IPC socket.
    The reason for this function is to avoid the bug which has never been fixed by Microsoft:
    # Unable to connect to VS Code server: Error in request - ENOENT /run/user/1000/vscode-ipc-*.sock
    https://github.com/microsoft/vscode-remote-release/issues/6997#issue-1319650016
    https://github.com/microsoft/vscode-remote-release/issues/6362#issuecomment-1046458477

Options:
    -h, --help                       Show this help message and exit
    --debug                          Enable debug mode (set -x)
    --fresh                          Verify this window's hook, choose a live window if needed, and repair the tmux hook
    --version                        Show version information
    --status                         Print process usage and diagnostics information
    --clean                          Clean obsolete IPC sockets for the selected editor
    --connection                     Show the selected editor, CLI, and IPC socket
    -r, --reload                     Reload and update this function from its source file

Commands:
    --install-extension              Install the specified extension from a .vsix file,
                                     overwriting an already installed version
    --list-extensions                List the installed extensions with versions
    --locate-shell-integration-path  Print the path to a terminal shell integration script

Example: code --version
         code --debug
         code --install-extension gitlens-13.0.2.vsix
         code myfile.txt
         code src/hca/CmdSetHcaCap.cpp:451
         code b/src/hca/CmdSetHcaCap.cpp   (git diff prefix is dropped)
         code somedir/                     (pick a file under it with fzf)

_EOF
    return 0
}

# Helper function: a directory is not something the editor can open in the
# window you are looking at - it spawns a new one. Offer the files under it
# instead, through the same fzf/bat picker jr uses, so the choice happens here
# rather than by reading a listing and running code a second time.
# Prints the chosen path(s), one per line.
# Exit: 0 chose something, 1 nothing chosen (user escaped), 2 could not ask.
_code_pick_in_dir() {
    local dir="$1" listing selected line shown=0
    # rg honours .gitignore, so pointing this at a repo does not drown the picker
    # in build output; find is only the fallback when rg is not installed.
    # `command` keeps an interactive shell's aliases out of this: rg is aliased
    # to --color=ansi in .bashrc and this function is parsed by that same shell,
    # so a bare rg would hand back names wrapped in escape codes. --color=never
    # covers the same ground for a RIPGREP_CONFIG_PATH doing it globally.
    if command -v rg > /dev/null 2>&1; then
        listing=$(command rg --files --color=never "$dir" 2>/dev/null)
    else
        listing=$(command find "$dir" -type f 2>/dev/null)
    fi
    if [[ -z "$listing" ]]; then
        echo -e "${RED}Error:${RESET} $dir is a directory with no files under it." >&2
        return 2
    fi
    # stdout is captured by the caller, so it is never a tty and cannot be the
    # test here; stderr still points at the terminal in an interactive shell.
    if ! command -v fzf > /dev/null 2>&1 || [ ! -t 2 ]; then
        echo -e "${RED}Error:${RESET} $dir is a directory. Files under it:" >&2
        while IFS= read -r line; do
            printf '  %s\n' "$line" >&2
            shown=$((shown + 1))
            if [[ $shown -ge 20 ]]; then
                echo "  ..." >&2
                break
            fi
        done <<< "$listing"
        return 2
    fi
    _code_fzf_pick "$listing" "$dir/"
}

# Helper function: let the user pick from a newline-separated candidate list.
# Prints the chosen path(s), one per line. Exit: 0 chose, 1 escaped.
_code_fzf_pick() {
    local listing="$1" prompt="${2:-}" selected
    selected=$(printf '%s\n' "$listing" | FZF_DEFAULT_OPTS="" fzf \
        --prompt="☞ ${prompt}" \
        --layout=reverse \
        --inline-info \
        --multi \
        --cycle \
        --exit-0 \
        --preview "bat --color=always --style=numbers {} 2>/dev/null || cat {}" \
        --preview-window "top,60%,border-bottom")
    [[ -z "$selected" ]] && return 1
    printf '%s' "$selected"
    return 0
}

# Helper function: a path that resolves nowhere is often just a bare file name
# lifted out of a compiler error or a log line - `hca_cap.c:3701` says nothing
# about which directory it lives in. Search the tree for it rather than refusing.
#
# One exact basename match is opened outright; several go to the picker, since
# guessing between same-named files is exactly the mistake that is hard to
# notice afterwards. Falling back to a substring match catches a half-remembered
# name, and that result always goes to the picker however few it finds.
# Prints the resolved path. Exit: 0 resolved, 1 user escaped, 2 nothing found.
_code_find_by_name() {
    local want="$1" listing hits
    # Separate statement on purpose: `local a=$1 b=${a...}` would expand $a
    # before the assignment to it takes effect, leaving base empty.
    local base="${want##*/}"
    if command -v rg > /dev/null 2>&1; then
        # --no-ignore: honouring ignore files sends rg up through every parent
        # directory looking for them, and /labhome is an autofs mount where each
        # missing name is a mount attempt - `code tmux.conf` from crosslv took
        # 27 s, run after run (2026-10-10). The cost is that ignored files are
        # candidates too, as they are in fzf, whose fd runs with --no-ignore.
        listing=$(command rg --files --no-ignore --color=never 2>/dev/null)
    else
        listing=$(command find . -type f 2>/dev/null)
    fi
    [[ -z "$listing" ]] && return 2

    hits=$(printf '%s\n' "$listing" | grep -F -- "/$base" | grep -E "/${base//./\\.}\$")
    [[ -z "$hits" ]] && hits=$(printf '%s\n' "$listing" | grep -F -- "$base")
    [[ -z "$hits" ]] && return 2

    if [[ $(printf '%s\n' "$hits" | wc -l) -eq 1 && "$hits" == */"$base" ]]; then
        printf '%s' "$hits"
        return 0
    fi
    if ! command -v fzf > /dev/null 2>&1 || [ ! -t 2 ]; then
        return 2
    fi
    _code_fzf_pick "$hits" "$base "
}

# Helper function: paths pasted straight out of `git diff` / `git show` carry
# git's a/ or b/ diff prefix, which is not a real directory. Those paths are
# relative to the repository root rather than to $PWD, so resolve them from
# there. Only reached once the path as given has already failed to resolve, so
# a directory genuinely named a/ or b/ still takes precedence.
# Prints the resolved path (unchanged when nothing applies).
_code_strip_git_prefix() {
    local path="$1" rest root
    if [[ "$path" == [ab]/* ]]; then
        rest="${path#*/}"
        root=$(git rev-parse --show-toplevel 2>/dev/null)
        if [[ -n "$root" && -e "$root/$rest" ]]; then
            # Keep it short when the repo root is where the shell already is
            if [[ "$PWD" == "$root" ]]; then
                printf '%s' "$rest"
            else
                printf '%s' "$root/$rest"
            fi
            return 0
        fi
        # Not in a repo (or not tracked there): a plain relative try still helps
        if [[ -e "$rest" ]]; then
            printf '%s' "$rest"
            return 0
        fi
    fi
    printf '%s' "$path"
    return 1
}

# Helper function: a path copied out of grep/jr output or a chat message often
# carries the very directory the shell is already sitting in - running
# `code OCI_EMU/notes.md` from inside OCI_EMU/. Drop the leading directory run
# that $PWD already ends with, and only that: falling back to the bare basename
# would just as happily open an unrelated file of the same name from elsewhere
# in the tree, which is harder to notice than not opening anything at all.
# Prints the resolved path (unchanged when nothing applies).
_code_strip_cwd_prefix() {
    local path="$1" prefix= rest
    # An absolute path has no repeated-prefix story; a typo there is just a typo
    if [[ "$path" != /* ]]; then
        rest="$path"
        # Shortest prefix first, so as much of the original path as possible
        # survives; the -e test keeps a match that still cannot be opened from
        # ending the search early.
        while [[ "$rest" == */* ]]; do
            prefix="${prefix:+$prefix/}${rest%%/*}"
            rest="${rest#*/}"
            if [[ "$PWD" == */$prefix && -e "$rest" ]]; then
                printf '%s' "$rest"
                return 0
            fi
        done
    fi
    printf '%s' "$path"
    return 1
}

# Helper function: parse options
_code_parse_options() {
    local shortopts="hr"
    local longopts="help,debug,fresh,version,connection,status,clean,reload,install-extension:,list-extensions,locate-shell-integration-path"
    local script_name="code"

    local PARSED
    if ! PARSED=$(getopt --options $shortopts --longoptions "$longopts" --name "$script_name" -- "$@"); then
        echo -e "${MAGENTA}Error: Failed to parse command-line options.${RESET}" >&2
        return 1
    fi

    eval set -- "$PARSED"
    while true; do
        case "$1" in
            -h|--help)
                _code_usage
                return 2
                ;;
            --debug)
                _code_f_debug=true
                set -x
                shift
                ;;
            --fresh)
                _code_f_fresh=true
                shift
                ;;
            --version)
                _code_f_args=("--version")
                shift
                ;;
            --connection)
                _code_f_connection=true
                shift
                ;;
            --status)
                _code_f_args=("--status")
                shift
                ;;
            --clean)
                _code_f_clean=true
                shift
                ;;
            -r|--reload)
                _code_self_reload
                return 2 # Special return code to signal a reload
                ;;
            --install-extension)
                # Without --force the CLI refuses to touch an already installed
                # version, which is never what handing it a local .vsix means.
                _code_f_args+=("--install-extension" "$2" "--force")
                shift 2
                ;;
            --list-extensions)
                _code_f_args=("--list-extensions" "--show-versions")
                shift
                ;;
            --locate-shell-integration-path)
                _code_f_args=("--locate-shell-integration-path" "bash")
                shift
                ;;
            --)
                shift
                break
                ;;
            *)
                echo -e "${MAGENTA}Invalid option: $1${RESET}" >&2
                return 1
        esac
    done

    # Only a regular file can be opened in the window you are looking at. A path
    # that does not exist opens as an empty untitled buffer, so a typo is
    # indistinguishable from a successful open until you notice the file is
    # blank - that one is refused. A directory would open a whole new window, so
    # it turns into a pick among the files under it instead.
    # --goto takes path:line[:col], so a trailing
    # position suffix has to come off before checking - but only while the path
    # does not exist, so a file whose name really ends in :<digits> still wins.
    local arg path pos stripped note picked line rejected= resolved=() missing=() notfile=()
    local tok taken lined=() other=() args=("$@") i=0
    # By index rather than `for arg in "$@"`: a path taken out of a piece of
    # text (the last resort at the end of the loop) goes in right after the
    # argument it came from, and every step below runs on it as on a typed one.
    while [[ $i -lt ${#args[@]} ]]; do
        arg="${args[i]}"
        i=$((i + 1))
        path="$arg"
        pos=
        note=
        # Peel one numeric suffix at a time: bash ERE is greedy, so a single
        # pattern with an optional :col leaves path:line:col at path:line. The
        # suffix is put back afterwards so --goto still lands on the right line.
        while [[ ! -e "$path" && "$path" =~ ^(.+):[0-9]+$ ]]; do
            pos="${path#"${BASH_REMATCH[1]}"}$pos"
            path="${BASH_REMATCH[1]}"
        done
        if [[ ! -e "$path" ]]; then
            stripped=$(_code_strip_git_prefix "$path")
            if [[ "$stripped" != "$path" ]]; then
                note="${LIGHTYELLOW}Dropped git diff prefix ${path:0:2}, opening${RESET} $stripped"
                path="$stripped"
            fi
        fi
        # Complementary rather than alternative: a/ and b/ mark a path pasted
        # from a diff, while this covers prefix-free paths from jr or ls output.
        # The more specific signal gets the first say.
        if [[ ! -e "$path" ]]; then
            stripped=$(_code_strip_cwd_prefix "$path")
            if [[ "$stripped" != "$path" ]]; then
                note="${LIGHTYELLOW}Already inside ${path%"/$stripped"}/, opening${RESET} $stripped"
                path="$stripped"
            fi
        fi
        # The strip notice is held back until the path is known to be openable:
        # announcing "opening X" and then refusing X reads like a contradiction.
        if [[ -f "$path" ]]; then
            [[ -n "$note" ]] && echo -e "$note" >&2
            resolved+=("$path$pos")
        elif [[ -d "$path" ]]; then
            [[ -n "$note" ]] && echo -e "$note" >&2
            picked=$(_code_pick_in_dir "$path")
            case $? in
                # Escaping the picker is a deliberate cancel, not an error: say
                # nothing and open nothing. Only "could not ask" is a failure,
                # and the helper has already printed why.
                0)
                    while IFS= read -r line; do
                        [[ -n "$line" ]] && resolved+=("$line")
                    done <<< "$picked"
                    ;;
                2)
                    rejected=true
                    ;;
            esac
        elif [[ -e "$path" ]]; then
            notfile+=("$path")
        else
            # Nothing resolved it. Before refusing, try the tree: a bare name
            # copied out of a compiler error carries no directory at all.
            picked=$(_code_find_by_name "$path")
            case $? in
                0)
                    [[ -n "$note" ]] && echo -e "$note" >&2
                    while IFS= read -r line; do
                        [[ -z "$line" ]] && continue
                        echo -e "${LIGHTYELLOW}Found${RESET} $line" >&2
                        resolved+=("$line$pos")
                    done <<< "$picked"
                    ;;
                1) ;;  # escaped the picker on purpose: open nothing, say nothing
                *)
                    # Last resort, so nothing that resolves above is touched: text
                    # with a path in it. A double-click in a Chinese reply runs on
                    # through full-width brackets and CJK words to the next space:
                    # DISABLED_HCA（src/hca/CmdTeardownFlow.cpp:69），于是报. It is
                    # text when it holds a space, bracket, quote, comma, full-width
                    # punctuation or the like (CJK letters are [:alnum:], so CJK
                    # file names are not), or ends in . or :.
                    taken=
                    if [[ "$arg" == *[![:alnum:]._/~+@:-]* || "$arg" == *[.:] ]]; then
                        # Pieces: runs of ASCII path characters, less a dot that
                        # ends a sentence, plus up to two :<digits>; LC_ALL=C makes
                        # every non-ASCII byte a separator, `command` keeps the
                        # grep alias out. Candidates have a :<line>, a / or an
                        # extension; those with a line go first, the first that
                        # exists wins, else the first goes on to the fallbacks.
                        lined=()
                        other=()
                        while IFS= read -r tok; do
                            # Never taken: a piece that starts with a dot and has no
                            # / - what is left of a non-ASCII name, .md out of
                            # 文档.md, and with it a bare dotfile - and one with no
                            # letter or digit, such as / or ../, whose directory
                            # listing would be the whole tree under it.
                            [[ "${tok%%:*}" == .* && "$tok" != */* || "${tok%%:*}" != *[A-Za-z0-9]* ]] && continue
                            if [[ "$tok" =~ :[0-9]+$ ]]; then
                                lined+=("$tok")
                            elif [[ "$tok" == */* || "$tok" == *.[A-Za-z]* ]]; then
                                other+=("$tok")
                            fi
                        done <<< "$(printf '%s\n' "$arg" | LC_ALL=C command grep -oE '[A-Za-z0-9._/~+@-]*[A-Za-z0-9_/~+@-](:[0-9]+){0,2}')"
                        for tok in "${lined[@]}" "${other[@]}"; do
                            if [[ -e "${tok%%:*}" ]]; then
                                taken="$tok"
                                break
                            fi
                        done
                        [[ -z "$taken" ]] && taken="${lined[0]:-${other[0]}}"
                    fi
                    if [[ -n "$taken" ]]; then
                        # The piece is never text itself, so it cannot come back
                        # here; said at once, so a later error names a known path.
                        echo -e "${LIGHTYELLOW}Stripped to:${RESET} $taken" >&2
                        args=("${args[@]:0:i}" "$taken" "${args[@]:i}")
                    else
                        missing+=("$path")
                    fi
                    ;;
            esac
        fi
    done
    # Every bad path is reported before giving up, so a command naming several of
    # them does not have to be run again to see the rest.
    if [[ ${#notfile[@]} -gt 0 ]]; then
        for path in "${notfile[@]}"; do
            if [[ -d "$path" ]]; then
                echo -e "${RED}Error:${RESET} $path is a directory." >&2
            else
                echo -e "${RED}Error:${RESET} $path is not a regular file." >&2
            fi
        done
        rejected=true
    fi
    if [[ ${#missing[@]} -gt 0 ]]; then
        for path in "${missing[@]}"; do
            echo -e "${RED}Error:${RESET} $path does not exist." >&2
        done
        # Handing the editor a new name used to be a way to start a file, so
        # point at the explicit replacement instead of only refusing.
        echo -e "${GREY}To create it: touch ${missing[0]} && code ${missing[0]}${RESET}" >&2
        rejected=true
    fi
    if [[ -n "$rejected" ]]; then
        return 1
    fi

    # If _code_f_args is empty here, _code_run_cmd will exit without execution.
    local first_arg=true
    for arg in "${resolved[@]}"; do
        if [[ -n $first_arg ]]; then
            _code_f_args+=("--goto")
            first_arg=
        fi
        _code_f_args+=("$arg")
    done

    return 0
}

# Helper function: check whether an IPC socket still has a window behind it.
# Socket files outlive the window that created them, AND the server process
# keeps the listener fd open (SO_ACCEPTCON) even after the window that owned
# it closes — so `ss -lxn` / lsof LISTEN state matches every socket the
# server ever created, live or orphaned, and can't tell them apart. The one
# thing that actually distinguishes a live window is that its extensionHost
# process (`--type=extensionHost`) holds an open fd to that exact socket. A
# unix-socket fd under /proc/<pid>/fd resolves to `socket:[inode]`, not the
# bound path, so match via the socket's inode from /proc/net/unix rather
# than comparing readlink output to the path directly.
_code_process_editor() {
    local pid="$1" exe cmdline
    exe=$(readlink -f "/proc/$pid/exe" 2>/dev/null)
    case "$exe" in
        "$HOME/.vscode-server/"*) printf 'vscode\n'; return 0 ;;
        "$HOME/.cursor-server/"*) printf 'cursor\n'; return 0 ;;
    esac
    cmdline=$(tr '\0' ' ' 2>/dev/null < "/proc/$pid/cmdline")
    case "$cmdline" in
        *"$HOME/.vscode-server/"*) printf 'vscode\n'; return 0 ;;
        *"$HOME/.cursor-server/"*) printf 'cursor\n'; return 0 ;;
    esac
    return 1
}

# Print the pids of list $2 (whitespace-separated, as pgrep and ps print them)
# that hold an fd on socket inode $1, in list order; status 1 when none does.
# One find reads every fd link: a readlink fork per fd costs ~1.3 ms, an
# extension host holds 80+ fds, and on 2026-10-20 those forks were most of the
# 1.5 s `code <file>` spent choosing a window. `command` keeps a shell function
# named find (an agent shell's bfs) out of it.
_code_socket_holders() {
    local inode="$1" pid line seen=' ' dirs=()
    for pid in $2; do
        dirs+=("/proc/$pid/fd")
    done
    (( ${#dirs[@]} )) || return 1
    while IFS= read -r line; do
        pid="${line#/proc/}"
        pid="${pid%%/*}"
        [[ "$seen" == *" $pid "* ]] && continue
        seen+="$pid "
        printf '%s\n' "$pid"
    done < <(command find "${dirs[@]}" -mindepth 1 -maxdepth 1 -lname "socket:\[$inode\]" -printf '%h\n' 2>/dev/null)
    [[ "$seen" != ' ' ]]
}

_code_ipc_extension_host() {
    local sock="$1" want="${2:-}" pid inode editor
    [[ -n "$sock" && -S "$sock" ]] || return 1
    command -v pgrep > /dev/null 2>&1 || return 1
    inode=$(awk -v s="$sock" '$NF==s{print $(NF-1); exit}' /proc/net/unix 2>/dev/null)
    [[ -n "$inode" ]] || return 1
    # Holders keep pgrep's order, so the first one that passes is the host the
    # editor test would have reached first.
    for pid in $(_code_socket_holders "$inode" "$(pgrep -f -- '--type=extensionHost' 2>/dev/null)"); do
        editor=$(_code_process_editor "$pid") || continue
        [[ -n "$want" && "$editor" != "$want" ]] && continue
        printf '%s %s\n' "$pid" "$editor"
        return 0
    done
    return 1
}

_code_ipc_sock_is_live() {
    _code_ipc_extension_host "$1" "${2:-}" > /dev/null
}

# A terminal's own CLI hook can be served by server-main without an extension
# host fd. Trust that hook only after _code_probe_hook has seen a window answer
# through it; a server-main listener alone can outlive the window it used to serve.
_code_ipc_server_main() {
    local sock="$1" inode pid editor
    [[ -n "$sock" && -S "$sock" ]] || return 1
    inode=$(awk -v s="$sock" '$NF==s{print $(NF-1); exit}' /proc/net/unix 2>/dev/null)
    [[ -n "$inode" ]] || return 1
    for pid in $(_code_socket_holders "$inode" "$(pgrep -f -- '/out/server-main[.]js' 2>/dev/null)"); do
        editor=$(_code_process_editor "$pid") || continue
        printf '%s %s\n' "$pid" "$editor"
        return 0
    done
    return 1
}

# A dead socket is safe to clean only when the selected editor's server still
# owns its listener. Both editors use the same vscode-ipc-* filename pattern.
# Finding the holders first leaves the editor test to them alone, instead of to
# every process of this user.
_code_ipc_sock_owned_by_editor() {
    local sock="$1" want="$2" inode pid editor
    [[ -n "$sock" && -S "$sock" ]] || return 1
    inode=$(awk -v s="$sock" '$NF==s{print $(NF-1); exit}' /proc/net/unix 2>/dev/null)
    [[ -n "$inode" ]] || return 1
    for pid in $(_code_socket_holders "$inode" "$(ps -u "$UID" -o pid= 2>/dev/null)"); do
        editor=$(_code_process_editor "$pid") || continue
        [[ "$editor" == "$want" ]] && return 0
    done
    return 1
}

# Helper function: newest-first scan of a directory's IPC sockets, returning
# the first one that actually has a window listening behind it. A closed
# window's server-side listener fd can outlive the window itself, so the
# newest socket file by mtime is not necessarily attached to anything; taking
# it blindly sends the open request into a void with no error and no window.
_code_pick_live_ipc_sock() {
    local dir="$1" editor="$2" sock
    while IFS= read -r sock; do
        if _code_ipc_sock_is_live "$sock" "$editor"; then
            echo "$sock"
            return 0
        fi
    done < <(ls -t "$dir"/vscode-ipc-*.sock 2>/dev/null)
    return 1
}

# Record the live sockets seen while a tmux client's target still works. A
# later editor reload creates a new path even if its old socket was removed.
# Each socket gets the _code_ipc_sock_is_live test, from one read of
# /proc/net/unix and one fd scan of the extension hosts: testing the sockets
# one by one ran pgrep and an fd scan for each, 0.8 s for 27 sockets on
# 2026-10-20.
_code_live_ipc_snapshot() {
    local editor="$1" dir sock pid link inode path snapshot=''
    local socks=() dirs=()
    local -A inode_of=() holders=() owner=()
    for dir in /tmp "/run/user/$UID"; do
        [[ -d "$dir" ]] || continue
        while IFS= read -r -d '' sock; do
            socks+=("$sock")
        done < <(find "$dir" -maxdepth 1 -type s -uid "$UID" -name 'vscode-ipc-*.sock' -print0 2>/dev/null)
    done
    if (( ${#socks[@]} )) && command -v pgrep > /dev/null 2>&1; then
        # The first inode listed for a path, as the one-socket lookup takes it
        while read -r inode path; do
            inode_of["$path"]="$inode"
        done < <(awk '$NF ~ /vscode-ipc-.*\.sock$/ && !($NF in seen) { seen[$NF]; print $(NF-1), $NF }' /proc/net/unix 2>/dev/null)
        for pid in $(pgrep -f -- '--type=extensionHost' 2>/dev/null); do
            dirs+=("/proc/$pid/fd")
        done
        # inode -> the hosts holding it, in pgrep order
        if (( ${#dirs[@]} )); then
            while read -r dir link; do
                pid="${dir#/proc/}"
                pid="${pid%%/*}"
                inode="${link#socket:[}"
                inode="${inode%]}"
                [[ " ${holders[$inode]-} " == *" $pid "* ]] || holders[$inode]+=" $pid"
            done < <(command find "${dirs[@]}" -mindepth 1 -maxdepth 1 -lname 'socket:*' -printf '%h %l\n' 2>/dev/null)
        fi
        for sock in "${socks[@]}"; do
            [[ -S "$sock" ]] || continue
            inode="${inode_of[$sock]-}"
            [[ -n "$inode" ]] || continue
            for pid in ${holders[$inode]-}; do
                [[ -n "${owner[$pid]+set}" ]] || owner[$pid]=$(_code_process_editor "$pid")
                [[ -n "${owner[$pid]}" ]] || continue
                [[ -n "$editor" && "${owner[$pid]}" != "$editor" ]] && continue
                snapshot+="${snapshot:+|}$sock"
                break
            done
        done
    fi
    printf '%s' "$snapshot"
}

_code_pick_unseen_ipc_sock() {
    local editor="$1" seen="$2" current sock found='' count=0
    local sockets=()
    [[ -n "$seen" ]] || return 1
    current=$(_code_live_ipc_snapshot "$editor")
    [[ -n "$current" ]] || return 1
    IFS='|' read -r -a sockets <<< "$current"
    for sock in "${sockets[@]}"; do
        [[ "|$seen|" == *"|$sock|"* ]] && continue
        found="$sock"
        count=$((count + 1))
    done
    [[ $count -eq 1 ]] || return 1
    printf '%s\n' "$found"
}

# Extension-host children often run from the window's main workspace. Use their
# cwd only as a hint; a multi-root window can contain other folders as well.
_code_extension_host_workspace_hint() {
    local pid="$1" child dir count best='' best_count=0 tied=0 fd log root
    local -A counts=()
    for child in $(pgrep -P "$pid" 2>/dev/null); do
        dir=$(readlink -f "/proc/$child/cwd" 2>/dev/null) || continue
        case "$dir" in
            /|/tmp|"$HOME"|"$HOME/.cursor-server/"*|"$HOME/.vscode-server/"*) continue ;;
        esac
        counts["$dir"]=$(( ${counts["$dir"]:-0} + 1 ))
    done
    for dir in "${!counts[@]}"; do
        count=${counts["$dir"]}
        if (( count > best_count )); then
            best="$dir"
            best_count=$count
            tied=0
        elif (( count == best_count )); then
            tied=1
        fi
    done
    if [[ -n "$best" && $tied -eq 0 ]]; then
        printf '%s\n' "${best##*/}"
        return 0
    fi

    for fd in /proc/"$pid"/fd/*; do
        log=$(readlink "$fd" 2>/dev/null) || continue
        [[ "$log" == */remoteexthost.log ]] || continue
        root=$(awk 'match($0, /folderQueries=\[\{"cwd":"[^"]+"/) {
            value = substr($0, RSTART, RLENGTH)
            sub(/^.*"cwd":"/, "", value)
            sub(/"$/, "", value)
            print value
            exit
        }' "$log" 2>/dev/null)
        if [[ -n "$root" ]]; then
            printf '%s\n' "${root##*/}"
            return 0
        fi
    done
    return 1
}

# A terminal's Git IPC socket is set by the Git extension of the window that
# opened the terminal. Its path comes from the workspace storage path, so it
# usually survives a window reload, but a terminal can also carry a path that
# nothing listens on any more. Only a live socket counts: when exactly one
# candidate's extension host holds it, that host's CLI socket is the window's.
_code_git_handle_ipc_sock() {
    local git_sock="$1" editor="$2" git_inode current sock info pid owner matched='' matches=0
    local sockets=()
    [[ -n "$git_sock" && -S "$git_sock" ]] || return 1
    git_inode=$(awk -v s="$git_sock" '$NF==s{print $(NF-1); exit}' /proc/net/unix 2>/dev/null)
    [[ -n "$git_inode" ]] || return 1
    current=$(_code_live_ipc_snapshot "$editor")
    [[ -n "$current" ]] || return 1
    IFS='|' read -r -a sockets <<< "$current"
    for sock in "${sockets[@]}"; do
        info=$(_code_ipc_extension_host "$sock") || continue
        read -r pid owner <<< "$info"
        # stdout is this function's answer: the holder pid must not reach it
        if _code_socket_holders "$git_inode" "$pid" > /dev/null; then
            matched="$sock"
            matches=$((matches + 1))
        fi
    done
    (( matches == 1 )) || return 1
    printf '%s\n' "$matched"
}

# Use a unique live socket automatically. With several windows, the terminal's
# Git IPC socket identifies its window when that socket is still live.
# Otherwise show workspace hints and ask only from an interactive terminal.
_code_choose_live_ipc_sock() {
    local editor="$1" git_sock="${2:-}" current sock info pid owner workspace_hint choice i
    local bold='' grey='' cyan='' accent='' reset='' name
    local sockets=() host_pids=() owners=()
    current=$(_code_live_ipc_snapshot "$editor")
    [[ -n "$current" ]] || return 1
    IFS='|' read -r -a sockets <<< "$current"
    if (( ${#sockets[@]} == 1 )); then
        printf '%s\n' "${sockets[0]}"
        return 0
    fi
    _code_git_handle_ipc_sock "$git_sock" "$editor" && return 0
    [[ -t 0 && -t 2 && -r /dev/tty ]] || return 1
    for sock in "${sockets[@]}"; do
        info=$(_code_ipc_extension_host "$sock") || info=''
        read -r pid owner <<< "$info"
        host_pids+=("$pid")
        owners+=("$owner")
    done
    # The menu goes to stderr, which is a terminal here; NO_COLOR keeps it plain.
    if [[ -z "${NO_COLOR:-}" ]]; then
        bold=$'\033[1m'
        grey=$'\033[90m'
        cyan=$'\033[36m'
        reset=$'\033[0m'
    fi
    printf '%scode:%s choose the editor window you are using %s(workspace names are hints)%s:\n' \
        "$bold" "$reset" "$grey" "$reset" >&2
    for (( i = 0; i < ${#sockets[@]}; i++ )); do
        sock="${sockets[i]}"
        pid="${host_pids[i]}"
        owner="${owners[i]}"
        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        if [[ "$owner" == cursor ]]; then
            name='Cursor'
            [[ -n "$reset" ]] && accent=$'\033[35m'
        else
            name='VS Code'
            [[ -n "$reset" ]] && accent=$'\033[34m'
        fi
        workspace_hint=$(_code_extension_host_workspace_hint "$pid")
        if [[ -n "$workspace_hint" ]]; then
            printf '  %s%d)%s %s%-7s%s %s%s%s  %s(workspace hint; pid %s)%s\n' \
                "$bold" "$((i + 1))" "$reset" "$accent" "$name" "$reset" \
                "$cyan" "$workspace_hint" "$reset" "$grey" "$pid" "$reset" >&2
        else
            printf '  %s%d)%s %s%-7s%s %sworkspace unknown  (pid %s)%s\n' \
                "$bold" "$((i + 1))" "$reset" "$accent" "$name" "$reset" "$grey" "$pid" "$reset" >&2
        fi
        printf '     %s%s%s\n' "$grey" "$sock" "$reset" >&2
    done
    printf '%sSelect 1-%d%s (Enter cancels): ' "$bold" "${#sockets[@]}" "$reset" >&2
    # Status 2 means the user declined, so callers need not explain how to ask.
    IFS= read -r choice < /dev/tty || return 2
    [[ "$choice" =~ ^[0-9]+$ ]] || return 2
    (( choice >= 1 && choice <= ${#sockets[@]} )) || return 2
    printf '%s\n' "${sockets[choice - 1]}"
}

# After an editor reload, a tmux client can keep the old hook even if tmux was
# reattached. A replacement socket is created shortly after the old one; a
# much later socket may belong to a different window.
_code_ipc_sock_is_recent_successor() {
    local old="$1" newer="$2" old_time newer_time
    [[ -S "$old" && -S "$newer" && "$newer" -nt "$old" ]] || return 1
    old_time=$(stat -c %Y -- "$old" 2>/dev/null) || return 1
    newer_time=$(stat -c %Y -- "$newer" 2>/dev/null) || return 1
    (( newer_time - old_time <= 120 ))
}

# Recover only when exactly one live socket was created soon after the stale
# client hook. The extension host can identify the editor even if the old
# socket has lost every process fd.
_code_pick_successor_ipc_sock() {
    local old="$1" editor="$2" dir sock found='' count=0
    [[ -S "$old" ]] || return 1
    for dir in /tmp "/run/user/$UID"; do
        [[ -d "$dir" ]] || continue
        while IFS= read -r -d '' sock; do
            [[ "$sock" == "$old" ]] && continue
            _code_ipc_sock_is_recent_successor "$old" "$sock" || continue
            if _code_ipc_sock_is_live "$sock" "$editor"; then
                found="$sock"
                count=$((count + 1))
            fi
        done < <(find "$dir" -maxdepth 1 -type s -uid "$UID" -name 'vscode-ipc-*.sock' -print0 2>/dev/null)
    done
    [[ $count -eq 1 ]] || return 1
    printf '%s\n' "$found"
}

_code_ipc_sock_used_by_tmux_client() {
    local sock="$1" pid client_env
    [[ -n "$TMUX" ]] && command -v tmux > /dev/null 2>&1 || return 1
    for pid in $(tmux list-clients -F '#{client_pid}' 2>/dev/null); do
        [[ -r "/proc/$pid/environ" ]] || continue
        while IFS= read -r -d '' client_env; do
            [[ "$client_env" == "VSCODE_IPC_HOOK_CLI=$sock" ]] && return 0
        done < "/proc/$pid/environ"
    done
    return 1
}

# Ask the window behind a hook to answer. An open request cannot tell: the CLI
# server replies to it without waiting for the window, so through a server-main
# hook whose terminal no window shows any more, `code file` exits 0 and opens
# nothing. status and extensionManagement requests do wait for the window, and
# an extensionManagement request with nothing to list or install does no work
# there: 0.33 s. --status, the probe until 2026-10-20, also walks the workspace
# for its diagnostics; that day it took 1-10 s and timed out on a window that
# was fine.
_code_probe_hook() {
    local status
    status=$(command curl -s -o /dev/null -w '%{http_code}' --noproxy '*' --max-time 8 \
        --unix-socket "$1" -H 'content-type: application/json' \
        -d '{"type":"extensionManagement"}' http://localhost/ 2>/dev/null)
    [[ "$status" == 200 ]]
}

_set_vscode_code_path() {
    # A pane's environment is captured at creation, while the tmux client is
    # attached from the window in use now. Choose that window before choosing
    # a CLI, so VS Code stays primary without stealing requests from Cursor.
    local _run_path="/run/user/$UID"
    local newIPCHook='' source='' client_pid='' client_session='' client_hook='' client_git='' client_env='' tmux_hook=''
    local saved_entry='' saved_hook='' saved_editor='' saved_seen='' saved_tail='' snapshot=''
    local host_info='' host_pid='' editor='' label='' host_start='' root='' exe='' commit='' path=''
    local pid_file='' curr_pid='' dir='' preferred='' fallback='' dead_editor='' successor=''
    local client_inode='' trusted_entry='' failed_entry='' failed_match='' use_server_main='' quiet_binding=''
    if [[ -n "$TMUX" ]] && command -v tmux > /dev/null 2>&1; then
        # Resolve the client displaying this pane first. If tmux cannot provide
        # one, use its most recently active client rather than socket mtime.
        if [[ -n "$TMUX_PANE" ]]; then
            client_pid=$(tmux display-message -p -t "$TMUX_PANE" '#{client_pid}' 2>/dev/null)
            client_session=$(tmux display-message -p -t "$TMUX_PANE" '#{session_name}' 2>/dev/null)
        fi
        if [[ ! "$client_pid" =~ ^[0-9]+$ ]]; then
            if [[ -n "$client_session" ]]; then
                client_pid=$(tmux list-clients -F '#{client_activity} #{client_pid} #{session_name}' 2>/dev/null \
                    | awk -v s="$client_session" '$3==s {print $1, $2}' | sort -nr | head -n 1)
            else
                client_pid=$(tmux list-clients -F '#{client_activity} #{client_pid}' 2>/dev/null | sort -nr | head -n 1)
            fi
            client_pid="${client_pid##* }"
        fi
        if [[ -z "$client_session" && "$client_pid" =~ ^[0-9]+$ ]]; then
            client_session=$(tmux list-clients -F '#{client_pid} #{session_name}' 2>/dev/null | awk -v p="$client_pid" '$1==p{sub(/^[^ ]+ /, ""); print; exit}')
        fi
        if [[ "$client_pid" =~ ^[0-9]+$ && -r "/proc/$client_pid/environ" ]]; then
            while IFS= read -r -d '' client_env; do
                case "$client_env" in
                    VSCODE_IPC_HOOK_CLI=*) client_hook="${client_env#VSCODE_IPC_HOOK_CLI=}" ;;
                    VSCODE_GIT_IPC_HANDLE=*) client_git="${client_env#VSCODE_GIT_IPC_HANDLE=}" ;;
                esac
            done < "/proc/$client_pid/environ"
        fi
        if [[ -n "$client_hook" ]]; then
            client_inode=$(awk -v s="$client_hook" '$NF==s{print $(NF-1); exit}' /proc/net/unix 2>/dev/null)
            if [[ "$client_pid" =~ ^[0-9]+$ ]]; then
                saved_entry=$(tmux show-option -gqv "@code_hook_$client_pid" 2>/dev/null)
                trusted_entry=$(tmux show-option -gqv "@code_trusted_$client_pid" 2>/dev/null)
                failed_entry=$(tmux show-option -gqv "@code_failed_$client_pid" 2>/dev/null)
                if [[ -n "$_code_f_fresh" && -z "$_code_f_skip_client_hook" && -n "$failed_entry" ]]; then
                    tmux set-option -gqu "@code_failed_$client_pid" || return 1
                    failed_entry=''
                fi
                if [[ -n "$client_inode" && "$failed_entry" == "$client_hook|$client_inode" ]]; then
                    failed_match=true
                fi
                if [[ "$saved_entry" == "$client_hook|"* ]]; then
                    saved_tail="${saved_entry#*|}"
                    saved_hook="${saved_tail%%|*}"
                    [[ "$saved_tail" == *'|'* ]] && saved_editor="${saved_tail#*|}"
                    saved_seen=$(tmux show-option -gqv "@code_seen_$client_pid" 2>/dev/null)
                fi
            fi
            if [[ -z "$_code_f_skip_client_hook" ]] && host_info=$(_code_ipc_extension_host "$client_hook"); then
                newIPCHook="$client_hook"
                source="tmux client $client_pid"
                quiet_binding=true
                if [[ -n "$failed_match" ]]; then
                    tmux set-option -gqu "@code_failed_$client_pid" || return 1
                fi
            elif [[ -z "$_code_f_skip_client_hook" && -n "$client_inode" \
                && -z "$failed_match" && "$trusted_entry" == "$client_hook|$client_inode" ]] \
                && host_info=$(_code_ipc_server_main "$client_hook"); then
                newIPCHook="$client_hook"
                source="verified hook for tmux client $client_pid"
                use_server_main=true
                quiet_binding=true
            elif [[ -z "$_code_f_skip_client_hook" && -z "$failed_match" \
                && ( -n "$_code_f_fresh" || -n "$_code_f_inspect" || ${#_code_f_args[@]} -gt 0 ) ]] \
                && host_info=$(_code_ipc_server_main "$client_hook"); then
                newIPCHook="$client_hook"
                source="tmux client $client_pid"
                use_server_main=true
                if [[ -n "$_code_f_inspect" && -z "$_code_f_fresh" ]]; then
                    _code_f_unverified=true
                elif [[ -z "$_code_f_fresh" ]]; then
                    _code_f_auto_fresh=true
                fi
            elif [[ -n "$saved_hook" ]] && host_info=$(_code_ipc_extension_host "$saved_hook"); then
                newIPCHook="$saved_hook"
                source="saved hook for tmux client $client_pid"
                quiet_binding=true
            elif [[ -n "$saved_editor" && -n "$saved_seen" ]] \
                && successor=$(_code_pick_unseen_ipc_sock "$saved_editor" "$saved_seen"); then
                newIPCHook="$successor"
                source="unique new $saved_editor socket for tmux client $client_pid"
            elif _code_ipc_sock_owned_by_editor "$client_hook" vscode; then
                label='VS Code'
                dead_editor='vscode'
            elif _code_ipc_sock_owned_by_editor "$client_hook" cursor; then
                label='Cursor'
                dead_editor='cursor'
            else
                label='editor'
            fi
            if [[ -n "$label" ]]; then
                # A remembered live-socket set is stronger than mtime. If it
                # exists but several new windows appeared, do not guess from
                # whichever hook happened to be exported in this shell.
                if [[ -z "$saved_seen" ]]; then
                    # A successful earlier repair updates the shell and tmux
                    # session hooks, while /proc/<client>/environ stays fixed.
                    if [[ "$VSCODE_IPC_HOOK_CLI" != "$client_hook" ]] \
                        && _code_ipc_sock_is_live "$VSCODE_IPC_HOOK_CLI" "$dead_editor" \
                        && _code_ipc_sock_is_recent_successor "$client_hook" "$VSCODE_IPC_HOOK_CLI"; then
                        newIPCHook="$VSCODE_IPC_HOOK_CLI"
                        source="shell hook after stale tmux client $client_pid"
                    else
                        if [[ -n "$client_session" ]]; then
                            tmux_hook=$(tmux show-environment -t "$client_session" VSCODE_IPC_HOOK_CLI 2>/dev/null)
                        else
                            tmux_hook=$(tmux show-environment VSCODE_IPC_HOOK_CLI 2>/dev/null)
                        fi
                        [[ "$tmux_hook" == VSCODE_IPC_HOOK_CLI=* ]] && tmux_hook="${tmux_hook#VSCODE_IPC_HOOK_CLI=}"
                        if [[ "$tmux_hook" != "$client_hook" ]] \
                            && _code_ipc_sock_is_live "$tmux_hook" "$dead_editor" \
                            && _code_ipc_sock_is_recent_successor "$client_hook" "$tmux_hook"; then
                            newIPCHook="$tmux_hook"
                            source="tmux session hook after stale client $client_pid"
                        fi
                    fi
                    if [[ -z "$newIPCHook" ]]; then
                        successor=$(_code_pick_successor_ipc_sock "$client_hook" "$dead_editor")
                        if [[ -n "$successor" ]]; then
                            newIPCHook="$successor"
                            source="newer $label hook after stale tmux client $client_pid"
                        fi
                    fi
                fi
                if [[ -z "$newIPCHook" ]]; then
                    successor=$(_code_choose_live_ipc_sock "${saved_editor:-$dead_editor}" "$client_git")
                    if [[ -n "$successor" ]]; then
                        newIPCHook="$successor"
                        source="selected for tmux client $client_pid"
                    fi
                fi
                if [[ -z "$newIPCHook" ]]; then
                    if [[ -n "$_code_f_skip_client_hook" ]]; then
                        printf 'code: %s hook %s did not respond, and no live replacement was selected. Reload that window or reattach tmux.\n' \
                            "$label" "$client_hook" >&2
                    elif [[ "$label" == editor ]]; then
                        printf 'code: tmux client %s has a stale editor hook %s; run code --fresh to choose a live window.\n' "$client_pid" "$client_hook" >&2
                    else
                        printf 'code: tmux client %s has an unverified %s hook %s; run code --fresh to verify it.\n' "$client_pid" "$label" "$client_hook" >&2
                    fi
                    return 1
                fi
            fi
        fi
    fi

    if [[ -z "$newIPCHook" ]] && host_info=$(_code_ipc_extension_host "$VSCODE_IPC_HOOK_CLI"); then
        newIPCHook="$VSCODE_IPC_HOOK_CLI"
        source="pane environment"
    fi
    # Outside tmux this shell runs in the editor terminal itself. A hook served
    # by server-main is that terminal's own CLI server: each request carries the
    # terminal's id, so it reaches whichever window shows the terminal now.
    if [[ -z "$newIPCHook" && -z "$TMUX" && -z "$_code_f_skip_client_hook" ]] \
        && host_info=$(_code_ipc_server_main "$VSCODE_IPC_HOOK_CLI"); then
        newIPCHook="$VSCODE_IPC_HOOK_CLI"
        source="terminal hook"
        use_server_main=true
    fi
    if [[ -z "$newIPCHook" && -n "$TMUX" ]] && command -v tmux > /dev/null 2>&1; then
        if [[ -n "$client_session" ]]; then
            tmux_hook=$(tmux show-environment -t "$client_session" VSCODE_IPC_HOOK_CLI 2>/dev/null)
        else
            tmux_hook=$(tmux show-environment VSCODE_IPC_HOOK_CLI 2>/dev/null)
        fi
        [[ "$tmux_hook" == VSCODE_IPC_HOOK_CLI=* ]] && tmux_hook="${tmux_hook#VSCODE_IPC_HOOK_CLI=}"
        if host_info=$(_code_ipc_extension_host "$tmux_hook"); then
            newIPCHook="$tmux_hook"
            source="tmux global environment"
        fi
    fi

    # Without a usable hook, a terminal outside tmux can still be placed by its
    # Git IPC socket. Inside tmux the chooser uses the client's Git socket.
    if [[ -z "$newIPCHook" && -z "$TMUX" ]] \
        && newIPCHook=$(_code_git_handle_ipc_sock "${VSCODE_GIT_IPC_HANDLE:-}" ''); then
        source="Git IPC socket of this terminal"
    fi

    if [[ -z "$newIPCHook" && -n "$_code_f_fresh" ]]; then
        newIPCHook=$(_code_choose_live_ipc_sock '' "$client_git") || {
            [[ $? -eq 2 ]] \
                || printf 'code: no window hook could be verified; run code --fresh in an interactive terminal to choose one.\n' >&2
            return 1
        }
        source="selected for current terminal"
    fi

    if [[ -z "$newIPCHook" ]]; then
        # Without a window-specific hook, VS Code wins over Cursor even if a
        # Cursor socket has a newer mtime.
        if [[ "$_code_f_sys_path" == "/tmp" ]]; then fallback="$_run_path"; else fallback="/tmp"; fi
        for preferred in vscode cursor; do
            for dir in "$_code_f_sys_path" "$fallback"; do
                newIPCHook=$(_code_pick_live_ipc_sock "$dir" "$preferred") && break
            done
            [[ -n "$newIPCHook" ]] && break
        done
        [[ -n "$newIPCHook" ]] && source="socket scan"
    fi
    if [[ -z "$newIPCHook" ]]; then
        printf 'code: no live VS Code or Cursor IPC socket found under %s or /tmp.\n' "$_run_path" >&2
        return 1
    fi
    if ! host_info=$(_code_ipc_extension_host "$newIPCHook") \
        && { [[ -z "$use_server_main" ]] || ! host_info=$(_code_ipc_server_main "$newIPCHook"); }; then
        printf 'code: %s lost its extension host during detection. Reload that window and run code --fresh.\n' "$newIPCHook" >&2
        return 1
    fi
    read -r host_pid editor <<< "$host_info"
    _code_f_editor="$editor"
    if [[ "$editor" == cursor ]]; then label='Cursor'; else label='VS Code'; fi
    _code_f_sys_path=$(dirname "$newIPCHook")

    # Use the selected extension host's server commit, not a newer installed
    # CLI that may belong to a server which has not started yet.
    exe=$(readlink -f "/proc/$host_pid/exe" 2>/dev/null)
    if [[ "$editor" == vscode ]]; then
        root="$HOME/.vscode-server/cli/servers"
        if [[ "$exe" == "$root/"* ]]; then
            path="${exe#"$root/"}"
            commit="${path%%/*}"
        fi
        VSCODE_BIN_PATH="$root/$commit/server/bin/remote-cli/code"
        if [[ -z "$commit" || ! -x "$VSCODE_BIN_PATH" ]]; then
            while IFS= read -r -d '' pid_file; do
                curr_pid=$(cat "$pid_file" 2>/dev/null)
                if [[ "$curr_pid" =~ ^[0-9]+$ ]] && kill -0 "$curr_pid" 2>/dev/null; then
                    VSCODE_BIN_PATH="$(dirname "$pid_file")/server/bin/remote-cli/code"
                    [[ -x "$VSCODE_BIN_PATH" ]] && break
                fi
            done < <(find "$root" -maxdepth 2 -type f -name 'pid.txt' -print0 2>/dev/null)
        fi
    else
        root="$HOME/.cursor-server/bin/linux-x64"
        if [[ "$exe" == "$root/"* ]]; then
            path="${exe#"$root/"}"
        else
            path=$(tr '\0' ' ' 2>/dev/null < "/proc/$host_pid/cmdline")
            path="${path#*"$root/"}"
        fi
        commit="${path%%/*}"
        VSCODE_BIN_PATH="$root/$commit/bin/remote-cli/cursor"
    fi
    if [[ ! -x "$VSCODE_BIN_PATH" ]]; then
        printf 'code: no %s CLI found for server pid %s (%s).\n' "$editor" "$host_pid" "$VSCODE_BIN_PATH" >&2
        return 1
    fi

    if [[ -n "$_code_f_fresh" || -n "$_code_f_auto_fresh" ]]; then
        if ! _code_probe_hook "$newIPCHook"; then
            # Without curl the hook was never asked, so it is not to blame.
            if ! command -v curl > /dev/null 2>&1; then
                printf 'code: curl is not installed, so no hook can be verified; install curl.\n' >&2
                return 1
            fi
            if [[ -n "$use_server_main" && -z "$_code_f_skip_client_hook" ]] \
                && [[ "$newIPCHook" == "$client_hook" || "$source" == 'terminal hook' ]]; then
                if [[ "$newIPCHook" == "$client_hook" ]]; then
                    tmux set-option -gqu "@code_trusted_$client_pid" || return 1
                    tmux set-option -gq "@code_failed_$client_pid" "$client_hook|$client_inode" || return 1
                fi
                _code_f_failed_hook="$newIPCHook"
                _code_f_skip_client_hook=true
                _set_vscode_code_path
                return $?
            fi
            if [[ -n "$_code_f_skip_client_hook" ]]; then
                printf 'code: replacement %s hook %s did not respond; reload that window%s.\n' \
                    "$label" "$newIPCHook" "${TMUX:+ or reattach tmux}" >&2
            elif [[ -n "$_code_f_auto_fresh" ]]; then
                printf 'code: tmux client %s has an unverified %s hook %s; run code --fresh to verify it.\n' \
                    "$client_pid" "$label" "$client_hook" >&2
            else
                printf 'code: %s CLI did not respond%s.\n' "$label" "${TMUX:+; the tmux hook was not changed}" >&2
            fi
            return 1
        fi
    fi
    if [[ -n "$_code_f_failed_hook" && "$newIPCHook" != "$_code_f_failed_hook" ]]; then
        printf 'code: %s did not respond; using %s.\n' "$_code_f_failed_hook" "$newIPCHook" >&2
    fi
    if [[ -z "$_code_f_fresh" && -z "$_code_f_auto_fresh" && -z "$_code_f_inspect" \
        && -z "$quiet_binding" \
        && ( "$newIPCHook" != "$VSCODE_IPC_HOOK_CLI" || "$source" == 'socket scan' ) ]]; then
        host_start=$(ps -p "$host_pid" -o lstart= 2>/dev/null)
        printf 'code: using %s via %s (server pid %s, started %s; %s).\n' \
            "$newIPCHook" "$editor" "$host_pid" "$host_start" "$source" >&2
    fi
    # Both remote CLIs use VSCODE_IPC_HOOK_CLI to reach their own server.
    export VSCODE_IPC_HOOK_CLI="$newIPCHook"
    export VSCODE_BIN_PATH
    if [[ ( -n "$_code_f_fresh" || -n "$_code_f_auto_fresh" ) && -n "$TMUX" ]] \
        && command -v tmux > /dev/null 2>&1; then
        if [[ -n "$client_session" ]]; then
            tmux set-environment -t "$client_session" VSCODE_IPC_HOOK_CLI "$newIPCHook" || return 1
        else
            tmux set-environment VSCODE_IPC_HOOK_CLI "$newIPCHook" || return 1
        fi
    fi
    if [[ "$client_pid" =~ ^[0-9]+$ && -n "$client_hook" ]]; then
        if [[ ( -n "$_code_f_fresh" || -n "$_code_f_auto_fresh" ) && -n "$use_server_main" \
            && "$newIPCHook" == "$client_hook" && -n "$client_inode" ]]; then
            tmux set-option -gqu "@code_failed_$client_pid" || return 1
            tmux set-option -gq "@code_trusted_$client_pid" "$client_hook|$client_inode" || return 1
        fi
        snapshot=$(_code_live_ipc_snapshot "$editor")
        tmux set-option -gq "@code_hook_$client_pid" "$client_hook|$newIPCHook|$editor" || return 1
        tmux set-option -gq "@code_seen_$client_pid" "$snapshot" || return 1
    fi
    if [[ -n "$_code_f_fresh" ]]; then
        local green='' accent='' reset='' editor_name="$label"
        if [[ -t 2 && -z "${NO_COLOR:-}" ]]; then
            green=$'\033[32m'
            reset=$'\033[0m'
            if [[ "$editor" == cursor ]]; then accent=$'\033[35m'; else accent=$'\033[34m'; fi
        fi
        if [[ "$client_pid" =~ ^[0-9]+$ ]]; then
            printf 'code: %s✓%s %s%s%s ready for tmux client %s (all its panes)\n' \
                "$green" "$reset" "$accent" "$editor_name" "$reset" "$client_pid" >&2
        else
            printf 'code: %s✓%s %s%s%s ready\n' \
                "$green" "$reset" "$accent" "$editor_name" "$reset" >&2
        fi
    fi
}

# Show the selected connection. Like jcl, color is for a terminal only, and
# NO_COLOR or a pipe gets plain text that can be copied or parsed safely.
_code_show_connection() {
    local bold='' grey='' blue='' cyan='' magenta='' reset='' editor_name editor_color
    if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
        bold=$'\033[1m'
        grey=$'\033[90m'
        blue=$'\033[34m'
        cyan=$'\033[36m'
        magenta=$'\033[35m'
        reset=$'\033[0m'
    fi
    if [[ "$_code_f_editor" == cursor ]]; then
        editor_name='Cursor'
        editor_color="$magenta"
    else
        editor_name='VS Code'
        editor_color="$blue"
    fi

    printf '%scode%s  %s%s%s\n' "$bold" "$reset" "$editor_color" "$editor_name" "$reset"
    printf '%s────────────────────────────────%s\n' "$grey" "$reset"
    printf '  %-7s %s%s%s\n' 'CLI' "$blue" "$VSCODE_BIN_PATH" "$reset"
    printf '  %-7s %s%s%s\n' 'IPC' "$cyan" "$VSCODE_IPC_HOOK_CLI" "$reset"
    if [[ -n "$_code_f_unverified" ]]; then
        printf '  %-7s %s\n' 'State' 'Unverified for file opens; run code --fresh'
    fi
}

# Helper function: run VS Code command
_code_run_cmd() {
    [[ ${#_code_f_args[@]} -eq 0 ]] && return

    local attempt rc
    for attempt in 1 2; do
        "$VSCODE_BIN_PATH" "${_code_f_args[@]}"
        rc=$?
        [[ $rc -eq 0 ]] && return 0
        [[ $attempt -eq 2 ]] && break
        _set_vscode_code_path || return 1
    done
    printf 'code: editor CLI failed with exit status %s.\n' "$rc" >&2
    return "$rc"
}

# Helper function: remove obsolete IPC sockets
_code_clean_obsolete_ipc_socks() {
    local removed=0 kept=0 referenced=0 skipped=0 sock dir
    local _run_path="/run/user/$UID"
    for dir in /tmp "$_run_path"; do
        [[ -d "$dir" ]] || continue
        while IFS= read -r -d '' sock; do
            # The filename is shared by editors. Only touch a socket owned by
            # the selected editor, and keep every live window.
            if ! _code_ipc_sock_owned_by_editor "$sock" "$_code_f_editor"; then
                skipped=$((skipped + 1))
            elif _code_ipc_sock_used_by_tmux_client "$sock"; then
                referenced=$((referenced + 1))
            elif [[ "$sock" == "$VSCODE_IPC_HOOK_CLI" ]] || _code_ipc_sock_is_live "$sock" "$_code_f_editor"; then
                kept=$((kept + 1))
            else
                echo -e "Removing: ${LIGHTYELLOW}$sock${RESET}"
                if rm -f -- "$sock"; then
                    removed=$((removed + 1))
                else
                    printf 'code: could not remove %s.\n' "$sock" >&2
                    return 1
                fi
            fi
        done < <(find "$dir" -maxdepth 1 -type s -uid "$UID" -name "vscode-ipc-*.sock" -print0 2>/dev/null)
    done

    echo "-------------------------------------------------------"
    echo -e "Removed $removed stale $_code_f_editor socket(s), kept $kept live and $referenced tmux-client hook(s), skipped $skipped unverified/other-editor socket(s)"
    echo -e "In use: ${MAGENTA}$VSCODE_IPC_HOOK_CLI${RESET}"
}

# Helper function: pre-check
# Detects a remote VS Code or Cursor server vs a local installation.
_code_pre_check() {
    if [ -d "$HOME/.vscode-server/cli/servers" ] || [ -d "$HOME/.cursor-server/bin" ]; then
        _code_f_is_remote=true
        return 0
    fi

    # The PATH bootstrap sets this marker so it cannot recursively invoke itself
    # when there is no VS Code installation on this host.
    if [[ -n "${CODE_BOOTSTRAP_ACTIVE:-}" ]]; then
        echo -e "${RED}Error: No VS Code or Cursor installation or remote server found.${RESET}" >&2
        return 1
    fi

    # type -P searches PATH for executables, ignoring shell functions/aliases.
    local bin
    bin=$(type -P code 2>/dev/null)

    # macOS: check app bundle paths as fallback
    if [[ -z "$bin" && "$(uname -s)" == "Darwin" ]]; then
        local p
        for p in "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"; do
            [[ -x "$p" ]] && { bin="$p"; break; }
        done
    fi

    if [[ -n "$bin" ]]; then
        CODE_BOOTSTRAP_ACTIVE=1 "$bin" "$@"
        return $?
    fi

    echo -e "${RED}Error: No VS Code or Cursor installation or remote server found.${RESET}" >&2
    return 1
}

_code_self_reload() {
    # Unset all functions defined by this script to allow for reloading
    unset -f code _code_self_reload \
             _code_usage _code_parse_options _set_vscode_code_path \
             _code_show_connection _code_print_core_vars _code_run_cmd _code_clean_obsolete_ipc_socks \
             _code_pre_check _code_ipc_sock_is_live _code_ipc_extension_host _code_ipc_server_main _code_ipc_sock_owned_by_editor _code_ipc_sock_used_by_tmux_client _code_process_editor _code_pick_live_ipc_sock _code_live_ipc_snapshot _code_pick_unseen_ipc_sock _code_extension_host_workspace_hint _code_git_handle_ipc_sock _code_choose_live_ipc_sock _code_ipc_sock_is_recent_successor _code_pick_successor_ipc_sock \
             _code_socket_holders _code_probe_hook \
             _code_strip_cwd_prefix _code_strip_git_prefix _code_pick_in_dir

    # Re-source the script file. BASH_SOURCE[0] refers to the file being sourced.
    if [ -n "${BASH_SOURCE[0]}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
        # shellcheck source=/dev/null
        source "${BASH_SOURCE[0]}"
        echo -e "${MAGENTA}code function has been reloaded.$RESET"
    else
        echo -e "${RED}Error: Could not determine the source file path to reload.$RESET" >&2
    fi
}

# Main code function
code() {
    # Bash exports functions one at a time. An inherited code() needs to load
    # its helpers before it can run in a child shell.
    if ! declare -F _code_parse_options > /dev/null; then
        if [[ ! -r "$HOME/Templates/code-function.sh" ]]; then
            printf 'code: helper functions are unavailable; source code-function.sh.\n' >&2
            return 1
        fi
        # shellcheck source=/dev/null
        source "$HOME/Templates/code-function.sh" || return 1
        if ! declare -F _code_parse_options > /dev/null; then
            printf 'code: could not load helper functions from code-function.sh.\n' >&2
            return 1
        fi
        code "$@"
        return $?
    fi

    local _code_f_is_remote=
    local _code_f_args=()
    local _code_f_fresh=
    local _code_f_auto_fresh=
    local _code_f_skip_client_hook=
    local _code_f_failed_hook=
    local _code_f_clean=
    local _code_f_debug=
    local _code_f_connection=
    local _code_f_inspect=
    local _code_f_unverified=
    local _code_f_editor=
    local _code_f_sys_path
    local _run_path="/run/user/$UID"
    local _newest_run _newest_tmp
    _newest_run=$(ls -t "$_run_path"/vscode-ipc-*.sock 2>/dev/null | head -n 1)
    _newest_tmp=$(ls -t /tmp/vscode-ipc-*.sock 2>/dev/null | head -n 1)
    if [[ -n "$_newest_run" && -n "$_newest_tmp" ]]; then
        # Both have sockets — pick whichever has the newer one
        if [[ "$_newest_run" -nt "$_newest_tmp" ]]; then
            _code_f_sys_path="$_run_path"
        else
            _code_f_sys_path="/tmp"
        fi
    elif [[ -n "$_newest_run" ]]; then
        _code_f_sys_path="$_run_path"
    else
        _code_f_sys_path="/tmp"
    fi
    local parse_result
    _code_parse_options "$@"
    parse_result=$?
    if [[ $parse_result -eq 1 ]]; then
        return 1
    elif [[ $parse_result -eq 2 ]]; then # Help or reload already handled
        return 0
    fi

    if [[ -n "$_code_f_connection" ]]; then
        _code_f_inspect=true
    elif [[ ${#_code_f_args[@]} -eq 1 ]]; then
        case "${_code_f_args[0]}" in
            --status|--version) _code_f_inspect=true ;;
        esac
    fi

    local rc
    _code_pre_check "$@"
    rc=$?
    [[ -z "$_code_f_is_remote" ]] && return $rc

    # Re-evaluate the current window on every call. A cached executable plus a
    # live socket can still point at a different editor after tmux reattachment.
    _set_vscode_code_path || return 1
    _code_f_auto_fresh=
    _code_f_skip_client_hook=
    _code_f_failed_hook=

    if [[ -n "$_code_f_clean" ]]; then
        _code_clean_obsolete_ipc_socks || return 1
        [[ -n "$_code_f_clean" ]] && return 0
    fi

    # Show the selected connection after variables are set.
    if [[ -n "$_code_f_connection" ]]; then
        _code_show_connection
        return 0
    fi

    # Actually run the command
    _code_run_cmd
    rc=$?

    # Disable debug mode
    [ -n "$_code_f_debug" ] && set +x

    return $rc
}

# Export the function so it's available in subshells
export -f code

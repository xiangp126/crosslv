#!/bin/bash
# set -x
# Wrapper for VS Code / Cursor CLI.
# Works on both local machines (macOS/Linux) and remote servers connected via VS Code / Cursor.
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
    A wrapper function for the VS Code / Cursor server CLI.
    It finds the server CLI binary and sets the correct IPC socket.
    Supports both VS Code (.vscode-server) and Cursor (.cursor-server).
    The reason for this function is to avoid the bug which has never been fixed by Microsoft:
    # Unable to connect to VS Code server: Error in request - ENOENT /run/user/1000/vscode-ipc-*.sock
    https://github.com/microsoft/vscode-remote-release/issues/6997#issue-1319650016
    https://github.com/microsoft/vscode-remote-release/issues/6362#issuecomment-1046458477

Options:
    -h, --help                       Show this help message and exit
    -d, --debug                      Enable debug mode (set -x)
    -e, --refresh                    Force re-detection of the server binary and IPC socket, ignoring cache
    -v, --version                    Show version information
    -s, --status                     Print process usage and diagnostics information
    -c, --clean                      Clean obsolete IPC sockets
    -p, --print                      Print core variables
    -r, --reload                     Reload and update this function from its source file

Commands:
    --install-extension              Install the specified extension from a .vsix file,
                                     overwriting an already installed version
    --list-extensions                List the installed extensions with versions
    --locate-shell-integration-path  Print the path to a terminal shell integration script

Example: code --version
         code -d
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
    selected=$(printf '%s\n' "$listing" | FZF_DEFAULT_OPTS="" fzf \
        --prompt="☞ " \
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
    local shortopts="hdevpscr"
    local longopts="help,debug,refresh,version,print,status,clean,reload,install-extension:,list-extensions,locate-shell-integration-path"
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
                return 1
                ;;
            -d|--debug)
                _code_f_debug=true
                set -x
                shift
                ;;
            -e|--refresh)
                _code_f_refresh=true
                shift
                ;;
            -v|--version)
                _code_f_args=("--version")
                shift
                ;;
            -p|--print)
                _code_f_print=true
                shift
                ;;
            -s|--status)
                _code_f_args=("--status")
                shift
                ;;
            -c|--clean)
                _code_clean_obsolete_ipc_socks
                return 1
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
    for arg in "$@"; do
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
            missing+=("$path")
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
_code_ipc_sock_is_live() {
    local sock="$1" pid inode fd
    [[ -n "$sock" && -S "$sock" ]] || return 1
    command -v pgrep > /dev/null 2>&1 || return 0
    inode=$(awk -v s="$sock" '$NF==s{print $(NF-1)}' /proc/net/unix 2>/dev/null | head -n 1)
    [[ -n "$inode" ]] || return 1
    for pid in $(pgrep -f -- '--type=extensionHost' 2>/dev/null); do
        for fd in /proc/"$pid"/fd/*; do
            [[ "$(readlink "$fd" 2>/dev/null)" == "socket:[$inode]" ]] && return 0
        done
    done
    return 1
}

# Helper function: newest-first scan of a directory's IPC sockets, returning
# the first one that actually has a window listening behind it. A closed
# window's server-side listener fd can outlive the window itself, so the
# newest socket file by mtime is not necessarily attached to anything; taking
# it blindly sends the open request into a void with no error and no window.
_code_pick_live_ipc_sock() {
    local dir="$1" sock
    while IFS= read -r sock; do
        if _code_ipc_sock_is_live "$sock"; then
            echo "$sock"
            return 0
        fi
    done < <(ls -t "$dir"/vscode-ipc-*.sock 2>/dev/null)
    return 1
}

_set_vscode_code_path() {
    # Step 1: Find the commit ID of the active server
    # Use process substitution to ensure `commit_id` is set in the current shell scope, not a subshell.
    local pid_file curr_pid commit_id=
    cd "$_code_f_search_path" || return

    # For Cursor: no pid.txt, find the most recent commit directory with cursor binary
    # Cursor path: ~/.cursor-server/bin/linux-x64/<commit>/bin/remote-cli/cursor
    if [[ "$_code_f_is_cursor" == "1" ]]; then
        local cursor_platform_path="$_code_f_search_path/linux-x64"
        local code_bin dir
        if [[ -d "$cursor_platform_path" ]]; then
            while IFS= read -r -d '' dir; do
                code_bin="$cursor_platform_path/$dir/bin/remote-cli/cursor"
                if [[ -x "$code_bin" ]]; then
                    commit_id="$dir"
                    break
                fi
            done < <(find "$cursor_platform_path" -maxdepth 1 -mindepth 1 -type d -printf '%T@\t%f\0' 2>/dev/null | sort -rzn | cut -z -f2-)
        fi
    else
        # For VS Code: use pid.txt to find active server
        while IFS= read -r -d $'\0' pid_file; do
            if [ -f "$pid_file" ]; then
                curr_pid=$(cat "$pid_file" 2>/dev/null)
                if [ -n "$curr_pid" ] && [[ "$curr_pid" =~ ^[0-9]+$ ]]; then
                    if kill -0 "$curr_pid" 2>/dev/null; then
                        commit_id=$(basename "$(dirname "$pid_file")")
                        break
                    fi
                fi
            fi
        done < <(find . -maxdepth 2 -type f -name 'pid.txt' -print0 2>/dev/null)
    fi

    # Step 2: Set the VSCODE_BIN_PATH
    if [[ -z "$commit_id" ]]; then
        echo -e "${MAGENTA}Warning: No active server found under $_code_f_search_path.${RESET}" >&2
        cd - &> /dev/null || return
        return 1
    fi

    # Different path structure for Cursor vs VS Code
    # Cursor: ~/.cursor-server/bin/linux-x64/<commit>/bin/remote-cli/cursor
    # VS Code: ~/.vscode-server/cli/servers/<commit>/server/bin/remote-cli/code
    if [[ "$_code_f_is_cursor" == "1" ]]; then
        VSCODE_BIN_PATH="$_code_f_search_path/linux-x64/$commit_id/bin/remote-cli/cursor"
    else
        VSCODE_BIN_PATH="$_code_f_search_path/$commit_id/server/bin/remote-cli/code"
    fi

    if [[ ! -x "$VSCODE_BIN_PATH" ]]; then
        echo -e "${MAGENTA}Error: Binary not found or not executable at $VSCODE_BIN_PATH${RESET}" >&2
        return 1
    fi

    # Step 3: Set the VSCODE_IPC_HOOK_CLI
    # The integrated terminal exports the hook belonging to its own window, which
    # is the only reliable way to target the window the user is actually looking
    # at. With several windows open, the newest socket belongs to whichever one
    # was active last, so files end up in an unrelated window. Keep the inherited
    # hook while it is alive and only guess when it is not.
    # shellcheck disable=SC2012 disable=SC2155
    local _run_path="/run/user/$UID"
    local newIPCHook=

    if _code_ipc_sock_is_live "$VSCODE_IPC_HOOK_CLI"; then
        newIPCHook="$VSCODE_IPC_HOOK_CLI"
    elif [[ -n "$TMUX" ]] && command -v tmux > /dev/null 2>&1; then
        # A tmux pane keeps the environment captured when the session was first
        # created, so its inherited hook is usually stale. Ask tmux for the value
        # it picked up on the most recent attach before falling back to guessing.
        local _tmuxHook
        _tmuxHook=$(tmux show-environment VSCODE_IPC_HOOK_CLI 2>/dev/null)
        _tmuxHook="${_tmuxHook#VSCODE_IPC_HOOK_CLI=}"
        _code_ipc_sock_is_live "$_tmuxHook" && newIPCHook="$_tmuxHook"
    fi

    if [[ -n "$newIPCHook" ]]; then
        # Keep the socket directory in sync so --clean acts on the right one
        _code_f_sys_path=$(dirname "$newIPCHook")
    else
        newIPCHook=$(_code_pick_live_ipc_sock "$_code_f_sys_path")
    fi
    if [[ -z "$newIPCHook" ]]; then
        local _fallback
        if [[ "$_code_f_sys_path" == "/tmp" ]]; then
            _fallback="$_run_path"
        else
            _fallback="/tmp"
        fi
        newIPCHook=$(_code_pick_live_ipc_sock "$_fallback")
        [[ -n "$newIPCHook" ]] && _code_f_sys_path="$_fallback"
    fi
    if [ -z "$newIPCHook" ]; then
        echo -e "${MAGENTA}Error: No vscode-ipc-*.sock file found under $_run_path or /tmp${RESET}" >&2
        return 1
    fi
    # VSCODE_IPC_HOOK_CLI is an environment variable that is used by the VS Code CLI to communicate with the server.
    export VSCODE_IPC_HOOK_CLI=$newIPCHook
    export VSCODE_BIN_PATH
    # Step 4: Return to the original directory
    cd - &> /dev/null || return
}

# Helper function: print core variables
_code_print_core_vars() {
    echo -e "${MAGENTA}VS Code Server Core Vars${RESET}"
    echo "==============================================="
    echo -e "${GREEN}✔${GREY} Active VS Code Bin Path:${BLUE} $VSCODE_BIN_PATH${RESET}"
    echo -e "${GREEN}✔${GREY} Active VS Code IPC Hook:${BLUE} $VSCODE_IPC_HOOK_CLI${RESET}"
    echo "==============================================="
}

# Helper function: run VS Code command
_code_run_cmd() {
    [[ ${#_code_f_args[@]} -eq 0 ]] && return

    for _ in {1..2}; do
        "$VSCODE_BIN_PATH" "${_code_f_args[@]}" 2>/dev/null
        if [[ $? -eq 0 ]]; then
            break
        else
            _set_vscode_code_path || break
        fi
    done
}

# Helper function: remove obsolete IPC sockets
_code_clean_obsolete_ipc_socks() {
    _set_vscode_code_path || return 1

    local removed=0 kept=0
    while IFS= read -r -d '' sock; do
        # Only sockets nobody listens on are safe to drop. A live socket still
        # belongs to another window, and deleting it breaks `code` over there,
        # so being "not the one we picked" is not a reason to remove it.
        if _code_ipc_sock_is_live "$sock"; then
            kept=$((kept + 1))
        else
            echo -e "Removing: ${LIGHTYELLOW}$sock${RESET}"
            rm -f "$sock" && removed=$((removed + 1))
        fi
    done < <(find "$_code_f_sys_path" -maxdepth 1 -type s -name "vscode-ipc-*.sock" -print0 2>/dev/null)

    echo "-------------------------------------------------------"
    echo -e "Removed $removed stale socket(s), kept $kept live one(s)"
    echo -e "In use: ${MAGENTA}$VSCODE_IPC_HOOK_CLI${RESET}"
}

# Helper function: pre-check
# Detects remote server vs local machine. On local, finds and invokes the
# native editor binary directly (no IPC socket needed).
_code_pre_check() {
    # Remote server: VS Code/Cursor server directories exist
    if [ -d "$HOME/.vscode-server/cli/servers" ] || [ -d "$HOME/.cursor-server/bin" ]; then
        _code_f_is_remote=true
        return 0
    fi

    # Local machine: find the native editor binary
    # type -P searches PATH for executables, ignoring shell functions/aliases
    local bin
    bin=$(type -P cursor 2>/dev/null) || bin=$(type -P code 2>/dev/null)

    # macOS: check app bundle paths as fallback
    if [[ -z "$bin" && "$(uname -s)" == "Darwin" ]]; then
        local p
        for p in "/Applications/Cursor.app/Contents/Resources/app/bin/cursor" \
                 "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"; do
            [[ -x "$p" ]] && { bin="$p"; break; }
        done
    fi

    if [[ -n "$bin" ]]; then
        "$bin" "$@"
        return $?
    fi

    echo -e "${RED}Error: No VS Code or Cursor installation found.${RESET}" >&2
    return 1
}

_code_self_reload() {
    # Unset all functions defined by this script to allow for reloading
    unset -f code _code_self_reload \
             _code_usage _code_parse_options _set_vscode_code_path \
             _code_print_core_vars _code_run_cmd _code_clean_obsolete_ipc_socks \
             _code_pre_check _code_ipc_sock_is_live _code_pick_live_ipc_sock \
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
    local _code_f_is_remote=
    _code_pre_check "$@"
    local rc=$?
    [[ -z "$_code_f_is_remote" ]] && return $rc

    # Remote server path setup:
    # - VS Code: ~/.vscode-server/cli/servers/<commit>/server/bin/remote-cli/code
    # - Cursor:  ~/.cursor-server/bin/linux-x64/<commit>/bin/remote-cli/cursor
    local _code_f_args=()
    local _code_f_refresh=
    local _code_f_debug=
    local _code_f_print=
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
    local _code_f_search_path
    local _code_f_is_cursor=""
    if [ -d "$HOME/.cursor-server/bin" ]; then
        _code_f_search_path="$HOME/.cursor-server/bin"
        _code_f_is_cursor="1"
    else
        _code_f_search_path="$HOME/.vscode-server/cli/servers"
    fi

    local parse_result
    _code_parse_options "$@"
    parse_result=$?
    if [[ $parse_result -eq 1 ]]; then # Skip the following steps silently
        return 1
    elif [[ $parse_result -eq 2 ]]; then # The function was reloaded
        return 0
    fi

    # VSCODE_BIN_PATH being set is not enough to skip detection: the exported
    # VSCODE_IPC_HOOK_CLI a long-lived shell inherited can go stale while the
    # binary path stays valid. A socket whose window closed keeps its listener
    # fd open in the still-running server process, so connect() succeeds and the
    # CLI returns 0 with no output and no file opened. rc=0 makes the retry loop
    # in _code_run_cmd break immediately, so nothing ever re-detects. Re-run
    # detection whenever the inherited hook has no window behind it.
    if [ -z "$VSCODE_BIN_PATH" ] || ! _code_ipc_sock_is_live "$VSCODE_IPC_HOOK_CLI" \
        || [ -n "$_code_f_refresh" ] || [ -n "$_code_f_print" ]; then
        _set_vscode_code_path || return 1
    fi

    # Handle print flag after variables are set
    if [ -n "$_code_f_print" ]; then
        _code_print_core_vars
        return 0
    fi

    # Actually run the command
    _code_run_cmd
    local rc=$?

    # Disable debug mode
    [ -n "$_code_f_debug" ] && set +x

    return $rc
}

# Export the function so it's available in subshells
export -f code

#!/bin/bash
# set -x
# Wrapper for the VS Code / Cursor Server CLI.
# Supports both VS Code (.vscode-server) and Cursor (.cursor-server).
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
    -f, --force                      Force search for the code binary, ignoring \$VSCODE_BIN_PATH
    -v, --version                    Show version information
    -s, --status                     Print process usage and diagnostics information
    -c, --clean                      Clean obsolete IPC sockets
    -p, --print                      Print core variables
    -r, --reload                     Reload and update this function from its source file

Commands:
    --install-extension              Install the specified extension from a .vsix file
    --list-extensions                List the installed extensions with versions
    --locate-shell-integration-path  Print the path to a terminal shell integration script

Example: code --version
         code -d
         code --install-extension gitlens-13.0.2.vsix
         code myfile.txt

_EOF
    return 0
}

# Helper function: parse options
_code_parse_options() {
    local shortopts="hdfvpscr"
    local longopts="help,debug,force,version,print,status,clean,reload,install-extension:,list-extensions,locate-shell-integration-path"
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
            -f|--force)
                _code_f_force=true
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
                _code_f_args=("--install-extension" "$2")
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

    # If _code_f_args is empty here, _code_run_cmd will exit without execution.
    local first_arg=true
    for arg in "$@"; do
        if [[ -n $first_arg ]]; then
            _code_f_args+=("--goto")
            first_arg=
        fi
        _code_f_args+=("$arg")
    done

    return 0
}

_set_vscode_code_path() {
    # Step 1: Find the commit ID of the active server
    # Use process substitution to ensure `commit_id` is set in the current shell scope, not a subshell.
    local pid_file curr_pid commit_id=
    cd "$_code_f_search_path" || return

    # For Cursor: no pid.txt, find the most recent commit directory with code binary
    if [[ "$_code_f_is_cursor" == "1" ]]; then
        # Find the most recently modified directory that has the code binary
        local code_bin
        for dir in $(ls -t "$_code_f_search_path" 2>/dev/null); do
            code_bin="$_code_f_search_path/$dir/bin/remote-cli/code"
            if [[ -x "$code_bin" ]]; then
                commit_id="$dir"
                break
            fi
        done
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
    if [[ "$_code_f_is_cursor" == "1" ]]; then
        VSCODE_BIN_PATH="$_code_f_search_path/$commit_id/bin/remote-cli/code"
    else
        VSCODE_BIN_PATH="$_code_f_search_path/$commit_id/server/bin/remote-cli/code"
    fi

    if [[ ! -x "$VSCODE_BIN_PATH" ]]; then
        echo -e "${MAGENTA}Error: Binary not found or not executable at $VSCODE_BIN_PATH${RESET}" >&2
        return 1
    fi

    # Step 3: Set the VSCODE_IPC_HOOK_CLI
    # Get the most recently created vscode-ipc-*.sock file
    # shellcheck disable=SC2012 disable=SC2155
    local newIPCHook=$(ls -t "$_code_f_sys_path"/vscode-ipc-*.sock 2>/dev/null | head -n 1)
    if [ -z "$newIPCHook" ]; then
        echo -e "${MAGENTA}Error: No vscode-ipc-*.sock file found under $_code_f_sys_path${RESET}" >&2
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
            _set_vscode_code_path
        fi
    done
}

# Helper function: remove obsolete IPC sockets
_code_clean_obsolete_ipc_socks() {
    _set_vscode_code_path || return 1

    local removed=0 remaining=0
    while IFS= read -r -d '' sock; do
        if [[ "$sock" != "$VSCODE_IPC_HOOK_CLI" ]]; then
            echo -e "Removing: ${LIGHTYELLOW}$sock${RESET}"
            rm -f "$sock" && ((removed++))
        else
            ((remaining++))
        fi
    done < <(find "$_code_f_sys_path" -maxdepth 1 -type s -name "vscode-ipc-*.sock" -print0 2>/dev/null)

    echo "-------------------------------------------------------"
    echo -e "Removed: $removed socket(s), Remaining: ${MAGENTA}$VSCODE_IPC_HOOK_CLI${RESET}"
}

# Helper function: pre-check
_code_pre_check() {
    # Check if either VS Code or Cursor server directory exists
    if [ ! -d "$HOME/.vscode-server/cli/servers" ] && [ ! -d "$HOME/.cursor-server/bin" ]; then
        local l_code_bin_path="/usr/local/bin/code"
        if [ -x "$l_code_bin_path" ]; then
            "$l_code_bin_path" "$@"
            return $?
        fi
        return 1
    fi
}

_code_self_reload() {
    # Unset all functions defined by this script to allow for reloading
    unset -f code _code_self_reload \
             _code_usage _code_parse_options _set_vscode_code_path \
             _code_print_core_vars _code_run_cmd _code_clean_obsolete_ipc_socks \
             _code_pre_check

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
    local _code_f_args=()
    local _code_f_force=
    local _code_f_debug=
    local _code_f_print=
    # Support both VS Code and Cursor with different paths:
    # - VS Code: ~/.vscode-server/cli/servers/<commit>/server/bin/remote-cli/code, IPC in /run/user/$UID
    # - Cursor:  ~/.cursor-server/bin/<commit>/bin/remote-cli/code, IPC in /tmp
    local _code_f_sys_path
    local _code_f_search_path
    local _code_f_is_cursor=""
    if [ -d "$HOME/.cursor-server/bin" ]; then
        _code_f_search_path="$HOME/.cursor-server/bin"
        _code_f_sys_path="/tmp"
        _code_f_is_cursor="1"
    else
        _code_f_search_path="$HOME/.vscode-server/cli/servers"
        _code_f_sys_path="/run/user/$UID"
    fi

    _code_pre_check "$@" || return 1

    local parse_result
    _code_parse_options "$@"
    parse_result=$?
    if [[ $parse_result -eq 1 ]]; then # Skip the following steps silently
        return 1
    elif [[ $parse_result -eq 2 ]]; then # The function was reloaded
        return 0
    fi

    if [ -z "$VSCODE_BIN_PATH" ] || [ -n "$_code_f_force" ] || [ -n "$_code_f_print" ]; then
        _set_vscode_code_path || return 1
    fi

    # Handle print flag after variables are set
    if [ -n "$_code_f_print" ]; then
        _code_print_core_vars
        return 0
    fi

    # Actually run the command
    _code_run_cmd

    # Disable debug mode
    [ -n "$_code_f_debug" ] && set +x
}

# Export the function so it's available in subshells
export -f code

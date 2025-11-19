#!/bin/bash
# set -x
# Wrapper for the VS Code Server CLI.
# To install, add `source /path/to/code-function.sh` to your ~/.bashrc.
# For usage, run `code --help`.

if declare -F _code_pre_check &> /dev/null; then
    return
fi

# Helper function: usage
_code_usage() {
    local SCRIPTNAME="code"
    cat << EOF
Usage: code [options] <args>

Description:
    A wrapper function for the VS Code server CLI.
    It finds the VS Code server CLI binary and sets the correct IPC socket.
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

EOF
    return 0
}

# Helper function: parse options
_code_parse_options() {
    local SHORTOPTS="hdfvpsc"
    local LONGOPTS="help,debug,force,version,print,status,clean,reload,install-extension:,list-extensions,locate-shell-integration-path"
    local SCRIPTNAME="code"

    local PARSED
    if ! PARSED=$(getopt --options $SHORTOPTS --longoptions "$LONGOPTS" --name "$SCRIPTNAME" -- "$@"); then
        echo -e "${_CODE_MAGENTA}Error: Failed to parse command-line options.${RESET}" >&2
        return 1
    fi

    eval set -- "$PARSED"
    while true; do
        case "$1" in
            -h|--help)
                _code_usage
                return 0
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
                # _code_f_args=("--version")
                _code_print_core_vars
                shift
                ;;
            -s|--status)
                _code_f_args=("--status")
                shift
                ;;
            -c|--clean)
                _code_clean_obsolete_ipc_socks
                return 0
                ;;
            -r|--reload)
                __code_self_reload
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
                _code_f_args=("--locate-shell-integration-path")
                shift
                ;;
            --)
                shift
                break
                ;;
            *)
                echo -e "${_CODE_MAGENTA}Invalid option: $1${RESET}" >&2
                return 1
        esac
    done
    [ -n "$1" ] && _code_f_args+=("--goto" "$1")
    return 0
}

__code_self_reload() {
    # Unset all functions defined by this script to allow for reloading
    unset -f code _code_usage _code_parse_options __set_vscode_code_path \
              _code_print_core_vars _code_run_cmd _code_clean_obsolete_ipc_socks \
              _code_pre_check __code_self_reload

    # Re-source the script file. BASH_SOURCE[0] refers to the file being sourced.
    if [ -n "${BASH_SOURCE[0]}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
        # shellcheck source=/dev/null
        source "${BASH_SOURCE[0]}"
        echo "code function has been reloaded."
    else
        echo "Error: Could not determine the source file path to reload." >&2
    fi
}

__set_vscode_code_path() {
    # Step 1: Find the commit ID of the active VS Code server
    # Use process substitution to ensure `commit_id` is set in the current shell scope, not a subshell.
    # Added -maxdepth 2 for efficiency, assuming pid.txt is in <commit_id>/pid.txt structure.
    local pid_file curr_pid commit_id=
    cd "$_code_f_search_path" || return
    while IFS= read -r -d $'\0' pid_file; do
        if [ -f "$pid_file" ]; then
            curr_pid=$(cat "$pid_file" 2>/dev/null)
            if [ -n "$curr_pid" ] && [[ "$curr_pid" =~ ^[0-9]+$ ]]; then
                # Check if the process is actually running
                if ps -p "$curr_pid" -o pid= > /dev/null 2>&1; then
                    commit_id=$(basename "$(dirname "$pid_file")")
                    break
                fi
            fi
        fi
    done < <(find . -maxdepth 2 -type f -name 'pid.txt' -print0 2>/dev/null)

    # Step 2: Set the VSCODE_BIN_PATH
    if [[ -z "$commit_id" ]]; then
        echo -e "${MAGENTA}Warning: No active VS Code server found under $_code_f_search_path.${RESET}" >&2
        cd - &> /dev/null || return
        return 1
    fi
    VSCODE_BIN_PATH="$_code_f_search_path/$commit_id/server/bin/remote-cli/code"
    if [[ ! -x "$VSCODE_BIN_PATH" ]]; then
        echo -e "${MAGENTA}Error: VS Code binary not found or not executable at $VSCODE_BIN_PATH${RESET}" >&2
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
    # But you have to remember that only the sub shell can see the new value.
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
            __set_vscode_code_path
        fi
    done
}

# Helper function: remove obsolete IPC sockets
_code_clean_obsolete_ipc_socks() {
    __set_vscode_code_path || return 1

    find "$_code_f_sys_path" -maxdepth 1 -type s -name "vscode-ipc-*.sock" |
          grep -Fxv "$VSCODE_IPC_HOOK_CLI" |
          while IFS= read -r sock; do
        echo -e "Removing: ${LIGHTYELLOW}$sock${RESET}"
        rm -f "$sock"
    done

    echo "-------------------------------------------------------"
    find "$_code_f_sys_path" -maxdepth 1 -type s -name "vscode-ipc-*.sock" |
          while IFS= read -r sock; do
        echo -e "Remaining: ${_CODE_MAGENTA}$sock${RESET}"
    done
}

# Helper function: pre-check
_code_pre_check() {
    if [ ! -d "$_code_f_search_path" ]; then
        local l_code_bin_path="/usr/local/bin/code"
        if [ -x "$l_code_bin_path" ]; then
            "$l_code_bin_path" "$@"
            return $?
        fi
        return 1
    fi
}

# Main code function
code() {
    # Global variables
    _code_f_args=()
    _code_f_force=
    _code_f_debug=
    _code_f_sys_path="/run/user/$UID"
    _code_f_search_path="$HOME/.vscode-server/cli/servers"

    # Colors
    MAGENTA='\033[0;35m'
    LIGHTYELLOW='\033[0;93m'
    GREY='\033[0;90m'
    BLUE='\033[0;34m'
    GREEN='\033[0;32m'
    RESET='\033[0m'

    # Main logic
    local parse_result
    _code_pre_check "$@" || return 1
    _code_parse_options "$@"
    parse_result=$?
    if [[ $parse_result -eq 1 ]]; then # Skip the following steps
        return 1
    elif [[ $parse_result -eq 2 ]]; then # The function was reloaded
        return 0
    fi

    if [ -z "$VSCODE_BIN_PATH" ] || [ -n "$_code_f_force" ]; then
        __set_vscode_code_path || return 1
    fi
    _code_run_cmd

    # Disable debug mode
    [ -n "$_code_f_debug" ] && set +x
}

# Export the function so it's available in subshells
export -f code

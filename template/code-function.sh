#!/bin/bash
# set -x
# VS Code CLI Function - Save as ~/Templates/code-function.sh
# Add "source "$HOME"/Templates/code-function.sh" to your .bashrc
# Usage: code [options] [file/directory]

if declare -F _code_preCheck &> /dev/null; then
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
    -c, --clean                      Clean obsolete IPC sockets
    -s, --status                     Print process usage and diagnostics information
    --print                          Print core variables
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
_code_parseOptions() {
    local SHORTOPTS="hfdvcs"
    local LONGOPTS="help,force,debug,version,clean,install-extension:,locate-shell-integration-path,status,list-extensions,print"
    local SCRIPTNAME="code"

    local PARSED
    if ! PARSED=$(getopt --options $SHORTOPTS --longoptions "$LONGOPTS" --name "$SCRIPTNAME" -- "$@"); then
        echo -e "${MAGENTA}Error: Failed to parse command-line options.${RESET}" >&2
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
                _code_debug=true
                set -x
                shift
                ;;
            -f|--force)
                _code_fForce=true
                shift
                ;;
            --print)
                _code_fArgs=("--version")
                _code_fPrint=true
                shift
                ;;
            -v|--version)
                _code_fArgs=("--version")
                shift
                ;;
            --install-extension)
                _code_fArgs=("--install-extension" "$2")
                shift 2
                ;;
            -c|--clean)
                _code_cleanObsoleteIPCSocks
                return 0
                ;;
            --list-extensions)
                _code_fArgs=("--list-extensions" "--show-versions")
                shift
                ;;
            -s|--status)
                _code_fArgs=("--status")
                shift
                ;;
            --locate-shell-integration-path)
                _code_fArgs=("--locate-shell-integration-path")
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
    [ -n "$1" ] && _code_fArgs+=("--goto" "$1")
    return 0
}

__set_vscode_code_path() {
    local MAGENTA='\033[0;35m'
    local RESET='\033[0m'
    local syspath="/run/user/$UID"
    local searchPath="$HOME/.vscode-server/cli/servers"
    # Step 1: Find the commit ID of the active VS Code server
    # Use process substitution to ensure `commitId` is set in the current shell scope, not a subshell.
    # Added -maxdepth 2 for efficiency, assuming pid.txt is in <commit_id>/pid.txt structure.
    local pidFile currentPid commitId=
    cd "$searchPath" || return
    while IFS= read -r -d $'\0' pidFile; do
        if [ -f "$pidFile" ]; then
            currentPid=$(cat "$pidFile" 2>/dev/null)
            if [ -n "$currentPid" ] && [[ "$currentPid" =~ ^[0-9]+$ ]]; then
                # Check if the process is actually running
                if ps -p "$currentPid" -o pid= > /dev/null 2>&1; then
                    commitId=$(basename "$(dirname "$pidFile")")
                    break
                fi
            fi
        fi
    done < <(find . -maxdepth 2 -type f -name 'pid.txt' -print0 2>/dev/null)
    # Step 2: Set the VSCODE_BIN_PATH
    if [[ -z "$commitId" ]]; then
        echo -e "${MAGENTA}Warning: No active VS Code server found under $searchPath.${RESET}" >&2
        cd - &> /dev/null || return
        return 1
    fi
    VSCODE_BIN_PATH="$searchPath/$commitId/server/bin/remote-cli/code"
    if [[ ! -x "$VSCODE_BIN_PATH" ]]; then
        echo -e "${MAGENTA}Error: VS Code binary not found or not executable at $VSCODE_BIN_PATH${RESET}" >&2
        return 1
    fi
    # Step 3: Set the VSCODE_IPC_HOOK_CLI
    # Get the most recently created vscode-ipc-*.sock file
    # shellcheck disable=SC2012 disable=SC2155
    local newIPCHook=$(ls -t "$syspath"/vscode-ipc-*.sock 2>/dev/null | head -n 1)
    if [ -z "$newIPCHook" ]; then
        echo -e "${MAGENTA}Error: No vscode-ipc-*.sock file found under $syspath${RESET}" >&2
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
_code_printCoreVars() {
    if [ -n "$_code_fPrint" ]; then
        echo -e "${MAGENTA}VS Code Server Core Vars:${RESET}"
        echo "==============================================="
        echo -e "${GREEN}✔${GREY} Active VS Code Binary Path:${BLUE} $VSCODE_BIN_PATH${RESET}"
        echo -e "${GREEN}✔${GREY} Active VS Code IPC Hook:${BLUE} $VSCODE_IPC_HOOK_CLI${RESET}"
        echo "==============================================="
    fi
}

# Helper function: run VS Code command
_code_runCmd() {
    [[ ${#_code_fArgs[@]} -eq 0 ]] && return

    for _ in {1..2}; do
        "$VSCODE_BIN_PATH" "${_code_fArgs[@]}" 2>/dev/null
        if [[ $? -eq 0 ]]; then
            break
        else
            __set_vscode_code_path
        fi
    done
    _code_printCoreVars
}

# Helper function: remove obsolete IPC sockets
_code_cleanObsoleteIPCSocks() {
    local fSysPath="/run/user/$UID"
    local LIGHTYELLOW='\033[93m'
    local MAGENTA='\033[0;35m'
    local RESET='\033[0m'

    __set_vscode_code_path || return 1

    find "$fSysPath" -maxdepth 1 -type s -name "vscode-ipc-*.sock" |
          grep -Fxv "$VSCODE_IPC_HOOK_CLI" |
          while IFS= read -r sock; do
        echo -e "Removing: ${LIGHTYELLOW}$sock${RESET}"
        rm -f "$sock"
    done

    echo "-------------------------------------------------------"
    find "$fSysPath" -maxdepth 1 -type s -name "vscode-ipc-*.sock" |
          while IFS= read -r sock; do
        echo -e "Remaining: ${MAGENTA}$sock${RESET}"
    done
}

# Helper function: pre-check
_code_preCheck() {
    local fSearchPath="$HOME/.vscode-server/cli/servers"
    if [ ! -d "$fSearchPath" ]; then
        local codeBinPath="/usr/local/bin/code"
        if [ -x "$codeBinPath" ]; then
            "$codeBinPath" "$@"
            return $?
        fi
        return 1
    fi
}

# Main code function
code() {
    # Global variables
    _code_fArgs=()
    _code_fForce=
    _code_debug=
    _code_fPrint=
    # Local variables
    local fSysPath="/run/user/$UID"
    local fSearchPath="$HOME/.vscode-server/cli/servers"

    # Colors
    MAGENTA='\033[0;35m'
    GREY='\033[0;90m'
    BLUE='\033[0;34m'
    GREEN='\033[0;32m'
    RESET='\033[0m'

    # Main logic
    _code_preCheck "$@" || return 1
    _code_parseOptions "$@" || return 1

    if [ -z "$VSCODE_BIN_PATH" ] || [ -n "$_code_fForce" ]; then
        __set_vscode_code_path || return 1
    fi
    _code_runCmd

    # Disable debug mode
    [ -n "$_code_debug" ] && set +x
}

# Export the function so it's available in subshells
export -f code

#!/bin/bash
# shellcheck disable=SC2155
# set -x

# Tracking directories
fWKDir=$(cd $(dirname $0); pwd)
fTKFilesDir=$fWKDir/track-files
fTKCompDir=$fWKDir/completion
fTKVimColorsDir=$fWKDir/assets/vim-colors
fTKBatThemeDir=$fWKDir/assets/bat-themes
fTKFontDir=$fWKDir/assets/fonts
fTKFontConfigDir=$fWKDir/assets/fontconfig
fTKtemplateDir=$fWKDir/template
fTKToolsDir=$fWKDir/ftnt-tools
fUpdateClangd=
fDownloads=$HOME/Downloads
# Misc
fVimPlugsManagerPath=$HOME/.vim/autoload/plug.vim
fzfBinPath=$HOME/.vim/bundle/fzf/bin/fzf
# A fzf plugin: fzf-tab-completion
fzfTabCompPath=$HOME/.vim/bundle/fzf-tab-completion/bash/fzf-bash-completion.sh
fBackupDir="$HOME/Public/env.bak"
fOSCategory=debian # ubuntu/debian is the default OS type
fInstallTools=
fForceUpdate=
# Constants
SCRIPT_NAME=$(basename $0)
# Colors
CYAN='\033[36m'
RED='\033[31m'
BOLD='\033[1m'
GREEN='\033[32m'
NORMAL='\033[0m'
MAGENTA='\033[35m'
YELLOW='\033[33m'
LIGHTYELLOW='\033[93m'
NORMAL='\033[0m'
BLUE='\033[34m'
GREY='\033[90m'
RESET='\033[0m'
COLOR=$MAGENTA

usage() {
    cat << _EOF
Usage: ./$SCRIPT_NAME [uth]

This script is used to set up the coding environment in my predifined way.

Options:
    -h, --help      Print this help message
    -t, --tools     Link tools into \$HOME/.usr/bin
    -u, --update    Force an update of prerequisites
    --clangd        Update clangd to the latest released version

Examples:
    ./$SCRIPT_NAME
    ./$SCRIPT_NAME -t
    ./$SCRIPT_NAME -h

_EOF
exit 0
}

parseOptions() {
    SHORTOPTS="tuh"
    LONGOPTS="help,tools,update,clangd"

    # Use getopt to parse command-line options
    if ! PARSED=$(getopt --options $SHORTOPTS --longoptions "$LONGOPTS" --name "$0" -- "$@"); then
        echo -e "${COLOR}Error: Failed to parse command-line options.${RESET}" >&2
        exit 1
    fi

    # Reset positional parameters to the parsed values
    eval set -- "$PARSED"

    while true; do
        case "$1" in
            -t|--tools)
                fInstallTools=true
                shift
                ;;
            -u|--update)
                fForceUpdate=true
                shift
                ;;
            --clangd)
                fUpdateClangd=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            --)
                shift
                break
                ;;
            *)
                echo "Internal error!"
                exit 1
                ;;
        esac
    done
}

checkOSCategory() {
    echo -e "${COLOR}Checking OS platform${RESET}"
    if [[ -f /etc/os-release ]]; then
        local os_name
        os_name=$(awk -F= '/^ID=/{print $2}' /etc/os-release)

        case "$os_name" in
            "ubuntu")
                fOSCategory=debian
                echo "The current OS type is Ubuntu."
                ;;
            "centos")
                fOSCategory=redhat
                echo "The current OS type is CentOS."
                echo "We currently do not support CentOS."
                exit
                ;;
            "raspbian")
                fOSCategory=debian
                echo "The current OS type is raspbian."
                ;;
            *)
                echo "We currently do not support this OS type."
                exit
                ;;
        esac
    elif [[ $(uname) == "Darwin" ]]; then
        fOSCategory=mac
        echo "The current OS type is macOS (Mac)."
    else
        echo "The OS type is not supported or could not be determined."
        echo "We currently do not support this OS type."
        exit 1
    fi
}

updatePrerequisitesForDebian() {
    checkSudoPrivilege
    prerequisitesForUbuntu=(
        tmux # Basic tools
        rsync
        fd-find # fd
        ripgrep # rg
        universal-ctags
        openssl
        libssl-dev
        gdb
        bat
        curl
        jq # JSON parser
        xsel # X11 clipboard
        xclip
        libcurl4
        libcurl4-openssl-dev
        dos2unix
        expect
        sshfs
        sshpass
        shellcheck
        mlocate
        net-tools
        nftables
        bash-completion
        openssh-server
        python3-dev
        ffmpeg
        build-essential # build essentials
        cmake
        libboost-all-dev
        ragel
        sqlite3
        libsqlite3-dev
        libpcap-dev
        libvirt-clients
        texinfo
        libisl-dev
        libgmp-dev
        libncurses-dev
        source-highlight
        libsource-highlight-dev
        libmpfr-dev
        libtool
        autoconf
        gettext
        autopoint
        bear # llvm & clangd
        libear
        gdm3 # gnome desktop
        ubuntu-desktop
        gnome-keyring
        xfce4
        xfce4-goodies
        tigervnc-standalone-server # TigerVNC
        tigervnc-xorg-extension
        tigervnc-viewer
        remmina # remote desktop client
        # samba
        # smbclient
    )

    echo -e "${COLOR}Updating prerequisites for Ubuntu${RESET}"

    sudo apt-get update
    sudo apt-get install -y "${prerequisitesForUbuntu[@]}"
    sudo updatedb
}

updatePrequesitesForMac() {
    checkSudoPrivilege
    prerequisitesForMac=(
        yt-dlp
        fzf
        fd
        bat
        vim
    )

    echo -e "${COLOR}Updating prerequisites for macOS${RESET}"
    brew update
    brew install "${prerequisitesForMac[@]}"
}

setTimeZone() {
    echo -e "${COLOR}Setting timezone to Vancouver${RESET}"
    # check time zone if it is already vancouver
    if [ $(timedatectl | grep "Time zone" | awk '{print $3}') == "America/Vancouver" ]; then
        echo -e "${GREY}Time zone is already vancouver${RESET}"
        return
    fi
    sudo timedatectl set-timezone America/Vancouver
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Success!${RESET}"
    else
        echo -e "${RED}Failed!${RESET}"
        exit 1
    fi
}

updateVimPlugins (){
    echo -e "${COLOR}Installing Vim Plugins Manager${RESET}"

    if [ ! -f ~/.vimrc ]; then
        echo "No .vimrc found, Abort!"
        exit 1
    fi

    if [ ! -f "$fVimPlugsManagerPath" ]; then
        # use the --insecure option to avoid certificate check
        curl --insecure -fLo "$fVimPlugsManagerPath" --create-dirs \
        https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
    else
        echo -e "${GREY}Vim Plug is already installed${RESET}"
    fi

    echo -e "${COLOR}Updating Vim Plugins${RESET}"
    vim +PlugInstall +PlugUpdate +qall
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Success!${RESET}"
    else
        echo -e "${RED}Failed!${RESET}"
        exit 1
    fi
}

followUpTKExceptions() {
    echo -e "${COLOR}Follow up the exceptions${RESET}"
    # Copy back the privileged git config.
    gitconfigCheckFile=$HOME/.gitconfig.fortinet
    if [ -f "$gitconfigCheckFile"  ]; then
        echo "The privileged file $gitconfigCheckFile exists."
        echo "Relink $HOME/.gitconfig to $gitconfigCheckFile"
        ln -sf "$gitconfigCheckFile" "$HOME"/.gitconfig
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Success!${RESET}"
        else
            echo -e "${RED}Failed!${RESET}"
            exit 1
        fi
    fi
}

# linkFile: Creates a symbolic link for a file to a specified destination (dir).
#
# Usage:
#   linkFile /path/to/file /path/to/destination/dir
#   e.g., linkFile ~/myfile.txt /data/backup
#
# Arguments:
#   $1 - Source file
#   $2 - Destination directory path to link to
#   $3 - New link name (optional, default: as is)
#
# Returns:
#   0 if successful, 1 if already linked, 2 if source file does not exist
# ln [OPTION] TARGET LINK_NAME
linkFile() {
    local target="$1"      # The target to link
    local linkPath="$2"    # Destination directory to link to
    local newLinkName="$3" # New link name (optional, default: as is)

    [ ! -d "$linkPath" ] && echo "Destination directory $linkPath does not exist, abort!" && exit 1
    local filename=$(basename "$target")
    local linkName=${newLinkName:-$filename}
    local src="$target"
    local dst="$linkPath/${linkName}"

    echo -e "${COLOR}Creating symlink${RESET}: ${linkName} -> $src"

    [ ! -f "$target" ] && echo "Source file $target does not exist, abort!" && exit 1
    if [ -f "$dst" ] && [ ! -L "$dst" ]; then
        [ ! -d "$fBackupDir" ] && mkdir -p "$fBackupDir"
        echo -e "${BLUE}Warning: $dst is not a link, backing it up to $fBackupDir${RESET}"
        mv "$dst" "$fBackupDir/${linkName}.bak"
    fi

    if [ -L "$dst" ] && [ "$(readlink "$dst")" == "$src" ]; then
        echo -e "${GREY}${linkName} is already well linked.${RESET}"
        return 1
    fi

    ln -sf "$target" "$dst"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Success!${RESET}"
    else
        echo -e "${RED}Failed!${RESET}"
        exit 2
    fi
}

# linkFiles: Creates symbolic links for all files in a source directory to a specified destination directory.
#
# Usage:
#   linkFiles /path/to/source/dir /path/to/destination/dir [linknamePrefix]
#   e.g., linkFiles ~/mydir /data/backup
#
# Arguments:
#   $1 - Source directory
#   $2 - Destination directory path to link to
#   $3 - Prefix for destination filename (optional, Exp: . for hidden files)
#
# Returns:
#   0 if successful, 1 if already linked, 2 if source directory does not exist
# ln [OPTION] TARGET LINK_NAME
linkFiles() {
    local targetDir="$1"        # Source directory
    local linkPath="$2"         # Destination directory
    local linknamePrefix="$3"   # Prefix for destination filename. Exp: . for hidden files

    echo -e "${LIGHTYELLOW}Creating symlink: ${linkPath}/* -> $(basename "$targetDir")/*${RESET}"
    [ ! -d "$targetDir" ] && echo "Source directory $targetDir does not exist, abort!" && exit 1
    [ ! -d "$linkPath" ] && mkdir -p "$linkPath"

    for file in "$targetDir"/*; do
        linkFile "$file" "$linkPath" "${linknamePrefix}$(basename "$file")"
    done

    if [ "$linkPath" == "$HOME" ]; then
        return
    fi

    COLOR=$GREEN
    find "$linkPath" -type l ! \
            -exec test -e {} \; \
            -exec rm -f {} \; \
            -exec echo -e "${COLOR}Deleting broken link: {}${RESET}" \;
    COLOR=$MAGENTA
}

# relinkCommand: Creates a symbolic link for a system command with a new name in new path.
#
# Usage:
#   relinkCommand <sysCmd> <linkName> [linkPath]
#   e.g., relinkCommand batcat bat
#
#   ~/.usr/bin/bat -> /bin/batcat
#
# Arguments:
#   $1 - System command to link
#   $2 - Link name (new name)
#   $3 - Optional destination directory path (new path, default: $HOME/.usr/bin)
#
# Returns:
#   0 if successful, 1 if already linked, 2 if system command does not exist
# ln [OPTION] TARGET LINK_NAME
relinkCommand() {
    local sysCmd=$1
    local linkName=$2
    local linkPath=$HOME/.usr/bin
    [ -n "$3" ] && linkPath=$3
    local dst=$linkPath/$linkName

    [ ! -d "$linkPath" ] && mkdir -p "$linkPath"
    sysCmdPath=$(command -v "$sysCmd")
    if [ -z "$sysCmdPath" ]; then
        echo "${sysCmd} is not installed"
        return 2
    fi

    echo -e "${COLOR}Creating symlink: ${linkName} -> syscmd: ${sysCmdPath}${RESET}"
    if [ -L "$dst" ] && [ "$(readlink "$dst")" == "$sysCmdPath" ]; then
        echo -e "${GREY}${linkName} is already linked to ${sysCmdPath}${RESET}"
        return 1
    fi

    # Create the symlink
    ln -sf "$sysCmdPath" "$dst"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Success!${RESET}"
    else
        echo -e "${RED}Failed!${RESET}"
        exit 2
    fi
}

buildBatTheme() {
    # https://github.com/sharkdp/bat/tree/master/assets/themes
    echo -e "${LIGHTYELLOW}Building bat theme${RESET}"
    local batThemeDir=$HOME/.config/bat/themes
    local needBuild=
    [ ! -d "$batThemeDir" ] && mkdir -p "$batThemeDir"

    for theme in "$fTKBatThemeDir"/*; do
        linkFile "$theme" "$batThemeDir"
        if [ $? -eq 1 ]; then
            continue
        fi
        needBuild=true
    done

    [ -z "$needBuild" ] && return
    bat cache --build
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Success!${RESET}"
    else
        echo -e "${RED}Failed!${RESET}"
        exit 1
    fi
}

buildExtraFonts() {
    echo -e "${LIGHTYELLOW}Building extra fonts${RESET}"
    local needBuild=
    local fontConfigDir="$HOME/.config/fontconfig/conf.d"
    local fontDir=$HOME/.local/share/fonts
    [ ! -d "$fontDir" ] && mkdir -p "$fontDir"
    [ ! -d "$fontConfigDir" ] && mkdir -p "$fontConfigDir"

    for fontConfig in "$fTKFontConfigDir"/*; do
        linkFile "$fontConfig" "$fontConfigDir"
        if [ $? -eq 1 ]; then
            continue
        fi
    done

    for font in "$fTKFontDir"/*; do
        local fontFile=$(basename "$font")
        local fontExists=$(fc-list | grep -i "$fontFile")
        if [ -n "$fontExists" ]; then
            echo -e "${GREY}Font $fontFile already exists in system.${RESET}"
            continue
        fi

        linkFile "$font" "$fontDir"
        if [ $? -eq 1 ]; then
            continue
        fi
        needBuild=true
    done

    [ -z "$needBuild" ] && return
    echo -e "${COLOR}Building font cache...${RESET}"
    sudo fc-cache -fv
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Success!${RESET}"
    else
        echo -e "${RED}Failed!${RESET}"
        exit 1
    fi
}

changeTMOUTToWritable() {
    echo -e "${COLOR}Changing TMOUT to writable${RESET}"
    # TMOUT is readonly in /etc/profile, change it to writable so that we can unset it in .bashrc
    if ! grep -q "TMOUT" /etc/profile; then
        echo -e "${GREY}TMOUT is not found in /etc/profile.${RESET}"
        return
    fi

    if grep -q "^readonly TMOUT" /etc/profile; then
        echo -e "${GREY}TMOUT is readonly in /etc/profile, change it to writable${RESET}"
    else
        echo -e "${GREY}TMOUT is already writable in /etc/profile${RESET}"
        return
    fi

    sudo sed -i 's/^readonly TMOUT/# readonly TMOUT/g' /etc/profile
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Success!${RESET}"
    else
        echo -e "${RED}Failed!${RESET}"
        exit 1
    fi
}

checkSudoPrivilege() {
    echo -e "${COLOR}Checking sudo privilege${RESET}"
    if sudo -v >/dev/null 2>&1; then
        echo "You have sudo privilege. Continue!"
    else
        echo "You do not have sudo privilege. Abort!"
        exit 0
    fi
}

performLinkingFiles() {
    linkFiles "$fTKFilesDir" "$HOME" "."
    linkFiles "$fTKCompDir" "$HOME/.bash_completion.d"
    linkFiles "$fTKVimColorsDir" "$HOME/.vim/colors"
    if [[ "$fOSCategory" != "mac" ]]; then
        if [ -n "$fInstallTools" ]; then
            linkFiles "$fTKToolsDir" "$HOME/.usr/bin"
            linkFiles "$fTKtemplateDir" "$HOME/Templates"
        fi
        linkFile "$fzfTabCompPath" "$HOME/.bash_completion.d" "fzf_tab_completion.bash"
        linkFile "$fzfBinPath" "$HOME/.usr/bin"
    fi
}

updateClangd() {
    echo -e "${COLOR}Updating Clangd${RESET}"
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}Error: jq is required but not installed. Please install jq first.${RESET}"
        return 1
    fi

    local currentVersion=""
    local clangdPath=$(command -v clangd 2>/dev/null)
    if [ -n "$clangdPath" ]; then
        currentVersion=$($clangdPath --version | head -n1 | grep -oP 'version \K[0-9]+\.[0-9]+\.[0-9]+' || echo "")
        echo -e "Current clangd version: ${BLUE}$currentVersion${RESET}"
    else
        echo -e "${LIGHTYELLOW}clangd is not currently installed${RESET}"
        currentVersion="0.0.0"
    fi

    # Get the latest stable release version and download URL
    echo -e "${LIGHTYELLOW}Fetching latest Clangd binary information${RESET}"
    # 20.1.0
    # https://github.com/clangd/clangd/releases/download/20.1.0/clangd-linux-20.1.0.zip
    local output=$(curl -s https://api.github.com/repos/clangd/clangd/releases |
        jq -r '[.[] | select(.prerelease == false)] | .[0] |
               .name, (.assets[] | select(.name | contains("clangd-linux")) | .browser_download_url)')
    mapfile -t lines <<< "$output"
    local latestVersion="${lines[0]}"
    local downloadUrl="${lines[1]}"
    if [ -z "$latestVersion" ] || [ "$latestVersion" == "null" ]; then
        echo -e "${RED}Error: Failed to get latest version information${RESET}"
        return 1
    fi

    echo -e "Latest available clangd version: ${COLOR}$latestVersion${RESET}"
    if [ -n "$currentVersion" ]; then
        if [ "$(printf '%s\n' "$latestVersion" "$currentVersion" | sort -V -r | head -n1)" == "$currentVersion" ]; then
            echo -e "${GREY}No update needed. Current version is up to date.${RESET}"
            return 0
        fi
    fi

    echo -e "${LIGHTYELLOW}Downloading latest version of Clangd${RESET}"
    local fileName=$(basename "$downloadUrl")
    local downloadDst="$fDownloads/$fileName"
    if [ -f "$downloadDst" ]; then
        echo -e "${GREY}File $fileName already exists in $fDownloads, skipping download.${RESET}"
    else
        curl -L -o "$downloadDst" "$downloadUrl"
        if [ $? -ne 0 ]; then
            echo -e "${RED}Error: Failed to download the latest version${RESET}"
            return 1
        fi
    fi

    cd "$fDownloads" || exit 1
    local peekInfo=$(zipinfo -1 "$downloadDst" | head -n 1)
    local extractDir="$fDownloads/$(dirname "$peekInfo")"
    if [ -d "$extractDir" ]; then
        echo -e "${GREY}Directory $extractDir already exists, skipping extraction.${RESET}"
    else
        echo -e "${LIGHTYELLOW}Extracting Clangd${RESET}"
        unzip "$downloadDst"
        if [ ! -d "$extractDir" ]; then
            echo -e "${RED}Error: Failed to extract the downloaded file${RESET}"
            exit 1
        fi
        echo -e "${GREEN}Successfully extracted to $extractDir${RESET}"
    fi

    # find binary named clangd under the extracted directory
    local clangdBinary=$(find "$extractDir" -type f -name "clangd" -executable | head -n 1)
    if [ -z "$clangdBinary" ]; then
        echo -e "${RED}Error: Failed to find the clangd binary in the extracted directory${RESET}"
        return 1
    fi

    linkFile "$clangdBinary" "$HOME/.usr/bin"
}

performRelinkingCmds() {
    relinkCommand "batcat" "bat"
    relinkCommand "fdfind" "fd"
    relinkCommand "bash" "sh" "/bin/"
}

main() {
    parseOptions "$@"
    checkOSCategory
    if [ "$fOSCategory" == "debian" ]; then
        [ -n "$fForceUpdate" ] && updatePrerequisitesForDebian
        performLinkingFiles
        [ -n "$fUpdateClangd" ] && updateClangd
        updateVimPlugins
        performRelinkingCmds
        buildBatTheme
        buildExtraFonts
        followUpTKExceptions
        setTimeZone
        changeTMOUTToWritable
    elif [ "$fOSCategory" == "mac" ]; then
        # [ -n "$fForceUpdate" ] && installPrequesitesForMac
        performLinkingFiles
        updateVimPlugins
        buildBatTheme
        buildExtraFonts
    fi
}

main "$@"

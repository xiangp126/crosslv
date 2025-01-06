#!/bin/bash
# set -x

# Constants
SCRIPT_NAME=$(basename $0)
USER_NOTATION="@@@@"
SEPARATOR="==================================================="
# Variables
workingDir=$(cd $(dirname $0); pwd)
trackedFilesDir=$workingDir/track-files
trackedCompSrc=$workingDir/completion-files
trackedCompDst=$HOME/.bash_completion.d
ftntTempDir=$workingDir/template
ftntToolsDir=$workingDir/ftnt-tools
vimColorsDir=$workingDir/vim-colors
vimPlugsManagerPath=$HOME/.vim/autoload/plug.vim
fzfBinPath=$HOME/.vim/bundle/fzf/bin/fzf
fzfTabCompletionPath=$HOME/.vim/bundle/fzf-tab-completion/bash/fzf-bash-completion.sh
# ubuntu is the default OS type
osCategory=debian
# Flags
fInsTools=false
fForceUpdate=false
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

Options:
    -t, --tools     Link tools into \$HOME/.usr/bin
    -u, --update    Force an update of prerequisites
    -h, --help      Print this help message

Recommdned:
    ./$SCRIPT_NAME -t

Examples:
    ./$SCRIPT_NAME
    ./$SCRIPT_NAME -t
    ./$SCRIPT_NAME -u
    ./$SCRIPT_NAME -h

_EOF
exit 0
}

while getopts "uht" opt; do
    # opt is the option, like 'i' or 'h'
    case $opt in
        t)
            fInsTools=true
            ;;
        u)
            fForceUpdate=true
            ;;
        h)
            usage
            ;;
        ?)
            echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done

# Shift to process non-option arguments. New $1, $2, ..., $@
shift $((OPTIND - 1))
if [ $# -gt 0 ]; then
    echo "Illegal non-option arguments: $@"
    exit 1
fi

updatePrerequisitesForDebian() {
    checkSudoPrivilege
    prerequisitesForUbuntu=(
        ## Basic tools
        tmux
        rsync
        fd-find
        ripgrep
        universal-ctags
        openssl
        libssl-dev
        gdb
        bat
        curl
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
        ## build essentials
        build-essential
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
        ## llvm & clangd
        bear
        libear
        ## TigerVNC
        gdm3
        ubuntu-desktop
        gnome-keyring
        xfce4
        xfce4-goodies
        tigervnc-standalone-server
        tigervnc-xorg-extension
        tigervnc-viewer
        remmina # remote desktop client
        # samba
        # smbclient
        ## hyperscan
        cmake
        libboost-all-dev
        ragel
        sqlite3
        libsqlite3-dev
        libpcap-dev
    )

    echo -e "${COLOR}Updating prerequisites for Ubuntu${RESET}"

    sudo apt-get update
    sudo apt-get install -y "${prerequisitesForUbuntu[@]}"
    sudo updatedb
}

checkOSPlat() {
    echo -e "${COLOR}Checking OS platform${RESET}"
    if [[ -f /etc/os-release ]]; then
        local os_name
        os_name=$(awk -F= '/^ID=/{print $2}' /etc/os-release)

        case "$os_name" in
            "ubuntu")
                osCategory=debian
                echo "The current OS type is Ubuntu."
                ;;
            "centos")
                osCategory=redhat
                echo "The current OS type is CentOS."
                echo "We currently do not support CentOS."
                exit
                ;;
            "raspbian")
                osCategory=debian
                echo "The current OS type is raspbian."
                ;;
            *)
                echo "We currently do not support this OS type."
                exit
                ;;
        esac
    elif [[ $(uname) == "Darwin" ]]; then
        osCategory=mac
        echo "The current OS type is macOS (Mac)."
    else
        echo "The OS type is not supported or could not be determined."
        echo "We currently do not support this OS type."
        exit
    fi
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

handleVimPlugins (){
    echo -e "${COLOR}Install Vim Plugins Manager${RESET}"

    if [ ! -f ~/.vimrc ]; then
        echo "No .vimrc found, Abort!"
        exit 1
    fi

    if [ ! -f "$vimPlugsManagerPath" ]; then
        # use the --insecure option to avoid certificate check
        curl --insecure -fLo "$vimPlugsManagerPath" --create-dirs \
        https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
    else
        echo -e "${GREY}Vim Plug is already installed${RESET}"
    fi

    echo -e "${COLOR}Update Vim Plugins${RESET}"
    vim +PlugInstall +PlugUpdate +qall
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Success!${RESET}"
    else
        echo -e "${RED}Failed!${RESET}"
        exit 1
    fi
}

followUpTrackExceptions() {
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

linkFilesToPath() {
    local targetDir="$1"      # Source directory
    local linkPath="$2"       # Destination directory
    local needHide="$3"       # Copy to hidden file
    local backupDir="$4"      # Optional backup directory
    local linknamePrefix=""   # Prefix for destination filename

    echo -e "${COLOR}Creating symlink: ${linkPath}/* -> $(basename "$targetDir")/*${RESET}"
    [ ! -d "$targetDir" ] && echo "Source directory $targetDir does not exist, abort!" && exit 1
    [ ! -d "$linkPath" ] && mkdir -p "$linkPath"
    [ -n "$backupDir" ] && [ ! -d "$backupDir" ] && mkdir -p "$backupDir"
    [ -n "$needHide" ] && linknamePrefix="."

    # Iterate over files in the source directory
    for file in "$targetDir"/*; do
        local filename=$(basename "$file")
        local src="$targetDir/$filename"
        local dst="$linkPath/${linknamePrefix}$filename"

        # echo -e "Linking ${COLOR}$filename${RESET} => $dst"
        echo -e "${LIGHTYELLOW}$dst -> $filename${RESET}"

        # If target exists in the destination as a regular file (not a symlink), back it up first
        if [ -n "$backupDir" ] && [ -f "$dst" ] && [ ! -L "$dst" ]; then
            echo "$dst is not a link, backing it up to $backupDir"
            mv "$dst" "$backupDir/$filename.bak"
        fi

        # If the symlink already exists and points to the correct location, skip it
        if [ -L "$dst" ] && [ "$(readlink "$dst")" == "$src" ]; then
            echo -e "${GREY}$dst is already linked.${RESET}"
            continue
        fi

        # Create or update the symbolic link
        ln -sf "$src" "$dst"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Success!${RESET}"
        else
            echo -e "${RED}Failed!${RESET}"
            exit 1
        fi
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

linkFileToPath() {
    local target="$1"       # The target to link
    local linkPath="$2"     # Destination directory to link to

    local filename=$(basename "$target")
    local dst="$linkPath/$filename"
    local src="$target"

    echo -e "${COLOR}Creating symlink: $filename -> $src${RESET}"
    [ ! -f "$target" ] && echo "Source file $target does not exist, abort!" && exit 1
    [ ! -d "$linkPath" ] && mkdir -p "$linkPath"

    if [ -L "$dst" ] && [ "$(readlink "$dst")" == "$src" ]; then
        echo -e "${GREY}${filename} is already linked to ${src}${RESET}"
        return
    fi

    ln -sf "$target" "$dst"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Success!${RESET}"
    else
        echo -e "${RED}Failed!${RESET}"
        exit 1
    fi
}

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
        return
    fi

    echo -e "${COLOR}Creating symlink: ${linkName} -> syscmd: ${sysCmdPath}${RESET}"
    if [ -L "$dst" ] && [ "$(readlink "$dst")" == "$sysCmdPath" ]; then
        echo -e "${GREY}${linkName} is already linked to ${sysCmdPath}${RESET}"
        return
    fi

    # Create the symlink
    ln -sf "$sysCmdPath" "$dst"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Success!${RESET}"
    else
        echo -e "${RED}Failed!${RESET}"
        exit 1
    fi
}

changeTMOUTToWritable() {
    echo -e "${COLOR}Change TMOUT to writable${RESET}"
    # TMOUT is readonly in /etc/profile, change it to writable
    # so that we can unset it in .bashrc
    if ! grep -q "TMOUT" /etc/profile; then
        echo "TMOUT is not found in /etc/profile, skip"
        return
    fi

    if grep -q "^readonly TMOUT" /etc/profile; then
        echo "TMOUT is readonly in /etc/profile, change it to writable"
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

mainInstallProcedure() {
    if [ "$osCategory" == "debian" ]; then
        [ "$fForceUpdate" == "true" ] && updatePrerequisitesForDebian
        linkFilesToPath "$trackedFilesDir" "$HOME" 1 "$HOME/Public/.env.bak"
        linkFilesToPath "$trackedCompSrc" "$trackedCompDst"
        linkFilesToPath "$vimColorsDir" "$HOME/.vim/colors"
        followUpTrackExceptions

        if [ "$fInsTools" == "true" ]; then
            linkFilesToPath "$ftntToolsDir" "$HOME/.usr/bin"
            linkFilesToPath "$ftntTempDir" "$HOME/Templates"
        fi

        handleVimPlugins

        linkFileToPath "$fzfTabCompletionPath" "$trackedCompDst"
        linkFileToPath "$fzfBinPath" "$HOME/.usr/bin"
        relinkCommand "batcat" "bat"
        relinkCommand "fdfind" "fd"
        relinkCommand "bash" "sh" "/bin/"

        setTimeZone
        changeTMOUTToWritable
    elif [ "$osCategory" == "mac" ]; then
        # [ "$fForceUpdate" == "true" ] && installPrequesitesForMac
        linkFilesToPath "$trackedFilesDir" "$HOME" true "$HOME/Public/.env.bak"
        linkFilesToPath "$trackedCompSrc" "$trackedCompDst"
        linkFilesToPath "$vimColorsDir" "$HOME/.vim/colors"
        handleVimPlugins
    fi
}

checkOSPlat
mainInstallProcedure

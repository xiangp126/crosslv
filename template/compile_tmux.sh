#!/bin/bash

# Define the target TMUX version tag
TMUX_TARG_TAG="3.3"
USER_NOTATION="@@@@"
TMUX_REPO_URL="https://github.com/tmux/tmux"
DOWNLOAD_DIR="$HOME/Downloads"
NEED_CLEAN=false
INSTALL_FLAG=
INSTALL_DIR="$HOME/.usr/"
SCRIPT_NAME=$(basename "$0")

usage() {
    cat << _EOF_
Usage: $SCRIPT_NAME [-uic]

Options:
    -u  Install the necessary build tools
    -i  Install TMUX
    -c  Clean the build directory before compiling

Examples:
    $SCRIPT_NAME -u
    $SCRIPT_NAME -i

_EOF_
exit 0
}

while getopts "uich" opt; do
    case $opt in
        i)
            INSTALL_FLAG=true
            ;;
        c)
            NEED_CLEAN=true
            ;;
        h)
            usage
            ;;
        ?)
            echo "$USER_NOTATION Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done

# Shift to process non-option arguments. New $1, $2, ..., $@
shift $((OPTIND - 1))
if [[ $# -gt 0 ]]; then
    echo "$USER_NOTATION Illegal non-option arguments: $@"
    exit
fi

# Get the current TMUX version and check if the passed argument is not -f
echo "$USER_NOTATION Checking the current TMUX version"
if [ -x "$(command -v tmux)" ] && [ "$1" != "-f" ]; then
    tmux_path=$(which tmux)
    if [ $? -ne 0 ]; then
        echo "$USER_NOTATION Failed to get the path to the current TMUX"
        exit 1
    fi
    current_version=$(tmux -V | awk '{print $2}')

    # Compare the versions
    if [ "$current_version" = "$TMUX_TARG_TAG" ]; then
        cat << _EOF_
TMUX version $current_version is already installed in $tmux_path
Current TMUX version ($current_version) is the same as $TMUX_TARG_TAG
Use -f to force the installation
_EOF_
        exit
    else
        cat << _EOF_
Current TMUX version ($current_version) is different from $TMUX_TARG_TAG
Start installing TMUX $TMUX_TARG_TAG ...
_EOF_
    fi
fi

echo "$USER_NOTATION Installing necessary build tools"
# Ensure you have necessary build tools installed
sudo apt-get update
sudo apt-get install -y build-essential \
                        libevent-dev \
                        libncurses5-dev \
                        autoconf \
                        automake \
                        bison byacc

# Navigate to the download directory
cd "$DOWNLOAD_DIR" || exit
echo "$USER_NOTATION Cloning the TMUX repository"
if [ ! -d "tmux" ]; then
    git clone "$TMUX_REPO_URL"
    if [ $? -ne 0 ]; then
        echo "$USER_NOTATION Failed to clone the TMUX repository"
        exit 1
    fi
fi

cd tmux || exit

# Check out the specified TMUX tag
if [ "$(git describe --tags)" = "$TMUX_TARG_TAG" ]; then
    echo "$USER_NOTATION Already in the checked out tag $TMUX_TARG_TAG"
else
    echo "$USER_NOTATION Checking out the specified TMUX tag"
    git fetch --tags
    git checkout "tags/$TMUX_TARG_TAG"
    if [ $? -ne 0 ]; then
        echo "$USER_NOTATION Failed to check out tag $TMUX_TARG_TAG"
        exit 1
    fi
fi

if [[ "$NEED_CLEAN" != false ]]; then
    echo "$USER_NOTATION Cleaning the build directory"
    make distclean
fi

# Configure the build
./autogen.sh
./configure --prefix="$INSTALL_DIR"
if [ $? -ne 0 ]; then
    echo "$USER_NOTATION Failed to configure TMUX"
    exit 1
fi

# Compile and install TMUX
make -j$(nproc)
if [ $? -ne 0 ]; then
    echo "$USER_NOTATION Failed to compile TMUX"
    exit 1
fi

if [ -n "$INSTALL_FLAG" ]; then
    echo "$USER_NOTATION Installing TMUX ..."
    make install
    if [ $? -ne 0 ]; then
        echo "$USER_NOTATION Failed to install TMUX"
        exit 1
    fi

    echo "$USER_NOTATION TMUX $TMUX_TARG_TAG has been installed to $INSTALL_DIR"
    cd "$INSTALL_DIR/bin" || exit
    ./tmux -V
fi

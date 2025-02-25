#!/bin/bash
# set -x

# $ lsb_release -a
# No LSB modules are available.
# Distributor ID: Ubuntu
# Description:    Ubuntu 20.04.6 LTS
# Release:        20.04
# Codename:       focal

# Define the target GDB version
# GDB_TARG_VERSION="15.2"
GDB_TARG_VERSION="16.2"
GDB_SOURCE_URL="https://ftp.gnu.org/gnu/gdb/gdb-$GDB_TARG_VERSION.tar.gz"

# Define installation directory
INSTALL_DIR="$HOME/.usr/"
DOWNLOAD_DIR="$HOME/Downloads"
PATCH_NAME="gdb-12.1-archswitch.patch"
PATCH_URL="https://github.com/mduft/tachyon3/raw/master/tools/patches/$PATCH_NAME"
MAGENTA='\033[0;35m'
RESET='\033[0m'
USER_NOTATION="@@@@"

# Add skip build tools flag
SKIP_BUILD_TOOLS=0
CLEAN_INSTALL=
FORCE_INSTALL=

usage() {
    cat << _EOF_

Install GDB $GDB_TARG_VERSION with the patch applied into $INSTALL_DIR

Usage: $(basename $0) [-c] [-h] [--skip] [--clean]
    -c, --clean: Clean and force the installation
    -h: Display this help message
    --skip: Skip installation of build tools

_EOF_
    exit 0
}

OPTS=":chf"  # Changed from :fh
LONG_OPTS="skip,clean,force"  # Added clean
# Process command line arguments
if ! PARSED=$(getopt --options=$OPTS --longoptions=$LONG_OPTS --name "$0" -- "$@"); then
    echo 'Terminating...' >&2
    exit 1
fi

eval set -- "$PARSED"
unset PARSED

while true; do
    case "$1" in
        '-c'|'--clean')
            echo -e "${USER_NOTATION} ${MAGENTA}Forcing clean installation${RESET}"
            CLEAN_INSTALL=true
            shift
            continue
            ;;
        '-f'|'--force')
            echo -e "${USER_NOTATION} ${MAGENTA}Forcing installation${RESET}"
            FORCE_INSTALL=true
            shift
            continue
            ;;
        '-h')
            usage
            ;;
        '--skip')
            SKIP_BUILD_TOOLS=1
            shift
            continue
            ;;
        '--')
            shift
            break
            ;;
        *)
            echo "Internal error!" >&2
            exit 1
            ;;
    esac
done

# Get the current GDB version and check if the passed argument is not -f
echo -e "${USER_NOTATION} ${MAGENTA}Checking the current GDB version${RESET}"
if [ -z "$FORCE_INSTALL" ] && [ -x "$(command -v gdb)" ]; then
    gdb_path=$(which gdb)
    if [ $? -ne 0 ]; then
        echo -e "${MAGENTA}Failed to get the path to the current GDB${RESET}"
        exit 1
    fi
    # current_version=$(gdb --version | grep -oE "[0-9]+\.[0-9]+")
    current_version=$(gdb --version | head -n 1 | awk '{print $NF}')

    # Use bc to compare the versions
    comparison=$(echo "$current_version >= $GDB_TARG_VERSION" | bc -l 2>/dev/null)
    if [ -n "$comparison" ] && [ "$comparison" -eq 1 ]; then
        echo -e "${USER_NOTATION} ${MAGENTA}GDB version $current_version is already installed in $gdb_path${RESET}"
        cat << _EOF_
Current GDB version ($current_version) is greater than or equal to $GDB_TARG_VERSION
Use -f to force the installation.
_EOF_
        exit
    else
        cat << _EOF_
Current GDB version ($current_version) is older than $GDB_TARG_VERSION
Start installing GDB $GDB_TARG_VERSION
_EOF_
    fi
fi

# Only install build tools if not skipped
if [ $SKIP_BUILD_TOOLS -eq 0 ]; then
    echo -e "${USER_NOTATION} ${MAGENTA}Installing necessary build tools${RESET}"
    # Ensure you have necessary build tools installed
    sudo apt-get update
    sudo apt-get install -y build-essential \
                        texinfo \
                        libisl-dev \
                        libgmp-dev \
                        libncurses-dev \
                        python3-dev \
                        source-highlight \
                        libsource-highlight-dev \
                        libmpfr-dev
fi

# Navigate to the download directory
cd "$DOWNLOAD_DIR" || exit

if [ ! -f "gdb-$GDB_TARG_VERSION.tar.gz" ]; then
    echo -e "${USER_NOTATION} ${MAGENTA}Downloading GDB source code${RESET}"
    wget "$GDB_SOURCE_URL"
fi

if [ ! -d "gdb-$GDB_TARG_VERSION" ]; then
    echo -e "${USER_NOTATION} ${MAGENTA}Extracting GDB source code${RESET}"
    tar -xzvf "gdb-$GDB_TARG_VERSION.tar.gz"
fi

cd "$DOWNLOAD_DIR"/gdb-$GDB_TARG_VERSION || exit
if [ ! -f "$PATCH_NAME" ]; then
    echo -e "${USER_NOTATION} ${MAGENTA}Downloading the patch${RESET}"
    wget "$PATCH_URL" -O "$PATCH_NAME"
    if [ $? -ne 0 ]; then
        echo -e "${MAGENTA}${USER_NOTATION} Failed to download the patch${RESET}"
        exit 1
    fi

    echo -e "${USER_NOTATION} ${MAGENTA}Applying the patch${RESET}"
    set -x
    patch -p1 < $PATCH_NAME
    set +x
    if [ $? -ne 0 ]; then
        echo -e "${MAGENTA}${USER_NOTATION} Failed to apply the patch${RESET}"
        exit 1
    fi
fi

# Update force clean check to use CLEAN_INSTALL variable
if [ -n "$CLEAN_INSTALL" ]; then
    echo -e "${USER_NOTATION} ${MAGENTA}Cleaning up the build directory${RESET}"
    make distclean
fi

# Configure the build
# https://sourceware.org/gdb/wiki/BuildingNatively
python3_path=$(which python3)
./configure \
  --prefix="$INSTALL_DIR" \
  --disable-binutils \
  --disable-ld \
  --disable-gold \
  --disable-gas \
  --disable-gprof \
  --with-python="$python3_path" \
  --enable-source-highlight \
  --enable-sim \
  --enable-gdb-stub \
  --enable-tui \
  --with-curses \
  --enable-x86-64 \
  CXXFLAGS='-g3 -O0' \
  CFLAGS='-g3 -O0 -DCURSES_LIBRARY'

# Compile and install GDB
if [ $? -ne 0 ]; then
    echo -e "${MAGENTA}${USER_NOTATION} Failed to configure GDB${RESET}"
    exit 1
fi

# Make full use of all CPU cores
echo -e "${USER_NOTATION} ${MAGENTA}Compiling GDB${RESET}"
make -j"$(nproc)"

if [ $? -ne 0 ]; then
    echo -e "${MAGENTA}${USER_NOTATION} Failed to compile GDB${RESET}"
    exit 1
fi

echo -e "${USER_NOTATION} ${MAGENTA}Installing GDB${RESET}"
make install

# Clean up downloaded files and patch
# cd "$DOWNLOAD_DIR"
# rm -f "gdb-$GDB_TARG_VERSION.tar.gz"
# rm -f "gdb-12.1-archswitch.patch"

# Verify GDB installation
if [ $? -ne 0 ]; then
    echo -e "${MAGENTA}${USER_NOTATION} Failed to install GDB${RESET}"
    exit 1
fi

echo "${USER_NOTATION} ${MAGENTA}GDB $GDB_TARG_VERSION with the patch applied has been installed to $INSTALL_DIR${RESET}"

cd "$INSTALL_DIR"/bin || exit
./gdb --version
./gdb -configuration
ldd gdb
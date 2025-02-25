#!/bin/bash
# set -x

# Define the target Bear version
BEAR_TARG_VERSION="3.1.5"
BEAR_SOURCE_URL="https://github.com/rizsotto/Bear/archive/refs/tags/${BEAR_TARG_VERSION}.tar.gz"

# Define installation directory
INSTALL_DIR="$HOME/.usr/"
DOWNLOAD_DIR="$HOME/Downloads"
MAGENTA='\033[0;35m'
RESET='\033[0m'
USER_NOTATION="@@@@"

# Add skip build tools flag
SKIP_BUILD_TOOLS=0

# Add force install flag
CLEAN_INSTALL=
FORCE_INSTALL=

usage() {
    cat << _EOF_

Install Bear $BEAR_TARG_VERSION into $INSTALL_DIR

Usage: $(basename $0) [-c] [-h] [--skip] [--clean] [--force]
    -c, --clean: Clean and force the installation
    -h: Display this help message
    --skip: Skip installation of build tools
    --force: Force the installation

_EOF_
    exit 0
}

OPTS=":ch"
LONG_OPTS="skip,clean,force"  # Added force option

# Process command line arguments
if ! PARSED=$(getopt --options=$OPTS --longoptions=$LONG_OPTS --name "$0" -- "$@"); then
    echo 'Terminating...' >&2
    exit 1
fi

# Note the quotes around "$TEMP": they are essential!
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
        '--force')
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

# Check current Bear version
echo -e "${USER_NOTATION} ${MAGENTA}Checking the current Bear version${RESET}"
if [ -z "$FORCE_INSTALL" ] && [ -x "$(command -v bear)" ]; then
    bear_path=$(which bear)
    if [ $? -ne 0 ]; then
        echo -e "${USER_NOTATION} ${MAGENTA}Failed to get the path to the current Bear${RESET}"
        exit 1
    fi
    current_version=$(bear --version | head -n 1 | awk '{print $2}')

    # Compare versions with safe handling of bc output
    comparison=$(echo "$current_version >= $BEAR_TARG_VERSION" | bc -l 2>/dev/null)
    if [ -n "$comparison" ] && [ "$comparison" -eq 1 ]; then
        cat << _EOF_
${USER_NOTATION} ${MAGENTA}Bear version $current_version is already installed in $bear_path
Current Bear version ($current_version) is greater than or equal to $BEAR_TARG_VERSION
Use -c to force the installation${RESET}
_EOF_
        exit
    else
        cat << _EOF_
${USER_NOTATION} ${MAGENTA}Current Bear version ($current_version) is older than $BEAR_TARG_VERSION
Start installing Bear $BEAR_TARG_VERSION${RESET}
_EOF_
    fi
fi

# Only install build tools if not skipped
if [ $SKIP_BUILD_TOOLS -eq 0 ]; then
    echo -e "${USER_NOTATION} ${MAGENTA}Installing necessary build tools${RESET}"
    # Install required dependencies
    sudo apt-get update
    sudo apt-get install -y build-essential \
                          cmake \
                          python3-dev \
                          libfmt-dev \
                          libspdlog-dev \
                          nlohmann-json3-dev \
                          libgrpc++-dev \
                          protobuf-compiler-grpc \
                          libssl-dev
fi

# Navigate to download directory
cd "$DOWNLOAD_DIR" || exit

if [ ! -f "bear-${BEAR_TARG_VERSION}.tar.gz" ]; then
    echo -e "${USER_NOTATION} ${MAGENTA}Downloading Bear source code${RESET}"
    wget "$BEAR_SOURCE_URL" -O "bear-${BEAR_TARG_VERSION}.tar.gz"
fi

if [ ! -d "Bear-${BEAR_TARG_VERSION}" ]; then
    echo -e "${USER_NOTATION} ${MAGENTA}Extracting Bear source code${RESET}"
    tar -xzvf "bear-${BEAR_TARG_VERSION}.tar.gz"
fi

cd "Bear-${BEAR_TARG_VERSION}" || exit

# Update force clean check to use CLEAN_INSTALL variable
if [ -n "$CLEAN_INSTALL" ]; then
    echo -e "${USER_NOTATION} ${MAGENTA}Cleaning up the build directory${RESET}"
    rm -rf build
fi

# Create and enter build directory
mkdir -p build && cd build || exit

# Configure the build
echo -e "${USER_NOTATION} ${MAGENTA}Configuring Bear${RESET}"
cmake -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
      -DENABLE_UNIT_TESTS=OFF \
      -DENABLE_FUNC_TESTS=OFF \
      ..

if [ $? -ne 0 ]; then
    echo -e "${MAGENTA}${USER_NOTATION} Failed to configure Bear${RESET}"
    echo -e "${MAGENTA}${USER_NOTATION} Please execute cmake commands manually and take care of the warnings about version mismatch of required libraries${RESET}"
    exit 1
fi

# Compile Bear
echo -e "${USER_NOTATION} ${MAGENTA}Compiling Bear${RESET}"
make all -j"$(nproc)"

if [ $? -ne 0 ]; then
    echo -e "${MAGENTA}${USER_NOTATION} Failed to compile Bear${RESET}"
    exit 1
fi

# Install Bear
echo -e "${USER_NOTATION} ${MAGENTA}Installing Bear${RESET}"
make install

if [ $? -ne 0 ]; then
    echo -e "${MAGENTA}${USER_NOTATION} Failed to install Bear${RESET}"
    exit 1
fi

echo -e "${USER_NOTATION} ${MAGENTA}Bear $BEAR_TARG_VERSION has been installed to $INSTALL_DIR${RESET}"

# Verify Bear installation
cd "$INSTALL_DIR"/bin || exit
./bear --version
ldd bear
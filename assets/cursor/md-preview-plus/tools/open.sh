#!/bin/bash
# Open a file in the Cursor that start.sh started, in its window. A .md file opened this way gets the editor
# the settings choose (the built-in Markdown preview); one passed to start.sh opens in Cursor's own md view.
# Usage: bash open.sh <cursor dir> <work dir> <file>
set -euo pipefail
cursor=$(cd "$1" && pwd)
work=$(cd "$2" && pwd)
exec env -u WAYLAND_DISPLAY -u VSCODE_PORTABLE DISPLAY=:77 XAUTHORITY="$work/xauth" HOME="$work/home" \
    XDG_CONFIG_HOME="$work/home/.config" XDG_CACHE_HOME="$work/home/.cache" XDG_RUNTIME_DIR=/tmp/cx-$(id -u) \
    "$cursor/bin/cursor" --user-data-dir="$work/user-data" --extensions-dir="$work/extensions" --reuse-window "$3"

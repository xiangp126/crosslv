#!/bin/bash
# Start a throw-away Cursor (the Linux build) on a private X display, with its own HOME, user data and
# extensions, and the DevTools protocol on port 9339 for the scripts next to this one. Nothing touches
# your own ~/.cursor or ~/.cursor-server.
# Usage: bash start.sh <cursor dir> <work dir> <folder to open>
#   <cursor dir>  the unpacked Linux package: the folder holding the `cursor` binary (usr/share/cursor in the .deb)
#   <work dir>    where its HOME, user data, extensions, logs and X cookie go; created if missing
# Runs Cursor in the foreground (start it as a background job). Stop it with pkill -f '<cursor dir>/cursor',
# and pkill -9 what is left after a few seconds. Open .md files with open.sh once the window is up.
set -euo pipefail
if curl -s --max-time 2 http://127.0.0.1:9339/json/version >/dev/null; then
    echo "port 9339 is taken: a Cursor started earlier is still running; stop it first" >&2
    exit 1
fi
cursor=$(cd "$1" && pwd)
work=$(mkdir -p "$2" && cd "$2" && pwd)
shift 2
display=:77
# short on purpose: Cursor's IPC socket lives here and a socket path must stay under 108 characters
run=/tmp/cx-$(id -u)
mkdir -p "$run" "$work/home" "$work/extensions" "$work/user-data/User"
chmod 700 "$run" "$work"

if [ ! -s "$work/user-data/User/settings.json" ]; then
    cat > "$work/user-data/User/settings.json" <<'JSON'
{
    "workbench.editorAssociations": { "*.md": "vscode.markdown.preview.editor" },
    "markdown.preview.openMarkdownLinks": "inEditor",
    "workbench.editor.enablePreview": false,
    "update.mode": "none",
    "telemetry.telemetryLevel": "off",
    "workbench.startupEditor": "none",
    "security.workspace.trust.enabled": false,
    "window.restoreWindows": "none",
    "extensions.autoUpdate": false,
    "extensions.autoCheckUpdates": false,
    "workbench.tips.enabled": false
}
JSON
fi

# X server: Xvnc, because Electron's headless ozone platform crashes in GTK. Its VNC side listens only on a
# unix socket of mode 0600, never on TCP (there is no VNC password).
if ! DISPLAY=$display XAUTHORITY="$work/xauth" xdpyinfo >/dev/null 2>&1; then
    rm -f "$work/xauth"
    xauth -f "$work/xauth" add $display . "$(mcookie)"
    Xvnc $display -geometry 1600x1000 -depth 24 -auth "$work/xauth" -SecurityTypes None \
        -rfbunixpath "$run/vnc.sock" -rfbunixmode 0600 -nolisten tcp > "$work/xvnc.log" 2>&1 &
    for _ in $(seq 50); do
        DISPLAY=$display XAUTHORITY="$work/xauth" xdpyinfo >/dev/null 2>&1 && break
        sleep 0.2
    done
fi

rm -f "$run"/vscode-*.sock
exec env -u WAYLAND_DISPLAY -u VSCODE_PORTABLE DISPLAY=$display XAUTHORITY="$work/xauth" HOME="$work/home" \
    XDG_CONFIG_HOME="$work/home/.config" XDG_CACHE_HOME="$work/home/.cache" XDG_RUNTIME_DIR="$run" \
    "$cursor/cursor" --no-sandbox --disable-gpu --remote-debugging-port=9339 --remote-allow-origins='*' \
    --user-data-dir="$work/user-data" --extensions-dir="$work/extensions" "$@" > "$work/cursor.log" 2>&1

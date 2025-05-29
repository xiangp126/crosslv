#!/bin/bash
set -x

echo "Setting up bridge"
cd "$HOME"/Templates || exit
./create_bridge.sh

echo "Setting up vscode max user watches"
./vscode_max_user_watches.sh

# echo "Setting up VNC server"
# How to adjust the resolution of a VNC session?
# Say your local resolution is 1920x1080(width x height)
# and you may need to set the VNC resolution to around 2060x1080 to fit your screen
# How to adjust?
# Keep the height of the resolution the same, and only change the width
# Start by adjusting the width from 1080 to 2060 or more, and choose the one that best fits your screen.
# vncPort=5909
# vnc_resolution=2060x1080
# if lsof -i :$vncPort | grep --quiet LISTEN
# then
#     set +x
#     echo "Port $vncPort is already in use. Stop setting up VNC server"
#     tigervncserver -kill :9
#     set -x
# fi
# echo "Setting up VNC server on port $vncPort"
# cd "$HOME"/.vnc || exit
# tigervncserver :9 -geometry $vnc_resolution

echo "Starting all vms"
start_all_vms

# CPU usage at 100% and Tomcat not responding. Fix it.
# echo "Starting OpenGrok"
# if command -v callIndexer &> /dev/null
# then
#     callIndexer -s
# fi

echo "Reset the DNS Server"
if command -v resetdns &> /dev/null
then
    resetdns
fi

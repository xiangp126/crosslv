#!/bin/bash
set -x

echo "Setting up bridge"
cd "$HOME"/Templates || exit
./create_bridge.sh

echo "Setting up vscode max user watches"
./vscode_max_user_watches.sh

echo "Starting VNC"
if command -v jc &> /dev/null
then
    jc --vnc-start
fi

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

#!/bin/bash

if command -v wireshark &>/dev/null; then
    echo "Wireshark is already installed."
    apt list -a wireshark
    wireshark --version
    exit 0
fi

if ! sudo -v; then
    echo "This script requires sudo privileges to install packages."
    exit 1
fi

# Add the Wireshark PPA repository
echo "Removing the Wireshark stable PPA repository..."
sudo add-apt-repository --remove ppa:wireshark-dev/stable -y
echo "Adding the Wireshark stable PPA repository..."
sudo add-apt-repository -y ppa:wireshark-dev/stable

# Update the package list
echo "Updating package list..."
sudo apt update

# Install Wireshark
echo "Installing Wireshark..."
sudo apt install -y wireshark

# Create the wireshark group if it does not exist
if ! getent group wireshark > /dev/null 2>&1; then
    echo "Creating wireshark group..."
    sudo groupadd wireshark
else
    echo "Group wireshak already exists."
fi

# Check if the current user is already in the wireshark group
if ! groups "$USER" | grep &>/dev/null '\bwireshark\b'; then
    # Add the current user to the wireshark group
    echo "Adding user $USER to the wireshark group..."
    sudo usermod -aG wireshark "$USER"
else
    echo "User $USER is already in the wireshark group."
fi

wiresharkBinPath=$(command -v wireshark)
# -u to test if the setuid bit is set
if [ -x "$wiresharkBinPath" ] && [ -u "$wiresharkBinPath" ]; then
    echo "The setuid bit is already set for wireshark."
else
    echo "Setting setuid bit for tcpdump ..."
    sudo chmod u+s "$wiresharkBinPath"
fi

# Inform the user to log out and log back in
echo "Wireshark installed successfully. Please log out and log back in, or run 'newgrp wireshark' to apply group changes."

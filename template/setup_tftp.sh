#!/bin/bash

# Check if the script has sudo privileges
if ! sudo -v; then
   echo "This script requires sudo privileges to install the TFTP server."
   exit 1
fi

# Install TFTP server
echo "Installing TFTP server..."
sudo apt update
sudo apt install -y tftpd-hpa

# Configure TFTP server
TFTP_CONFIG="/etc/default/tftpd-hpa"

# Add -c option to TFTP_OPTIONS
if ! grep -q -- "secure" "$TFTP_CONFIG"; then
    echo -e "Adding --secure -c option to TFTP_OPTIONS in $TFTP_CONFIG..."
    sudo sed -i 's/^TFTP_OPTIONS="/TFTP_OPTIONS="--secure -c /' "$TFTP_CONFIG"
fi

if [ "$(stat -c %U /srv/tftp)" != "tftp" ]; then
    echo "Changing ownership of /srv/tftp to tftp..."
    sudo chown -R tftp:tftp /srv/tftp
fi

if [ $? -ne 0 ]; then
    echo "Error: Failed to configure TFTP server."
    exit 1
fi

# Restart TFTP server
sudo systemctl restart tftpd-hpa

# Display TFTP_DIRECTORY
echo "TFTP server installation and configuration complete."
echo "TFTP_DIRECTORY: /srv/tftp"
echo "TFTP requires no authentication and is accessible to everyone on the network."

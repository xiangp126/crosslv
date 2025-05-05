#!/bin/bash

# Set the provided VM name as a variable
VM_NAME="$1"
VM_DESCRIPTION="ubuntu20"
VM_RAM="2048"  # in MB
VM_VCPUS="1"
VM_DISK_SIZE="20"  # in GB
VM_ISO_PATH="/usr/local/share/ubuntu-20.04.6-live-server-amd64.iso"
VM_DISK_PATH="/usr/local/vms/ubuntu20-$VM_NAME.qcow2"

# Check if both VM name and ISO file path are provided as arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <vm_name> [vm_iso_path]"
    echo "Example: $0 client0 $VM_ISO_PATH"
    exit 1
fi

# Set the VM ISO file path to the provided argument or use the default
if [ $# -ge 2 ]; then
    VM_ISO_PATH="$2"
fi

# Check if the ISO file exists
if [ ! -f "$VM_ISO_PATH" ]; then
    echo "ISO file not found at: $VM_ISO_PATH"
    exit 1
fi

# Create the Ubuntu VM
sudo virt-install \
    --check path_in_use=off \
    --name="$VM_NAME" \
    --description="$VM_DESCRIPTION" \
    --ram="$VM_RAM" \
    --vcpus="$VM_VCPUS" \
    --disk "size=$VM_DISK_SIZE,format=qcow2,path=$VM_DISK_PATH" \
    --cdrom="$VM_ISO_PATH" \
    --graphics vnc

if [ $? -ne 0 ]; then
    echo "Error while creating the VM"
    exit 1
fi

# Print information about the created VM using cat
cat << _EOF
Ubuntu VM '$VM_NAME' has been created with the following configuration:
Name: $VM_NAME
Description: $VM_DESCRIPTION
RAM: $VM_RAM MB
vCPUs: $VM_VCPUS
Disk Size: $VM_DISK_SIZE GB
ISO Path: $VM_ISO_PATH
Disk Path: $VM_DISK_PATH
_EOF

#!/bin/bash

# Default values
FGT_DESCRIPTION="FortiGate VM"
FGT_RAM="2048"  # in MB
FGT_VCPUS="1"
FGT_DISK_SIZE="10"  # in GB
FGT_NAME=""
FGT_QCOW2_PATH=""
SCRIPT_NAME=$(basename $0)
COLOR="\033[35m"  # MAGENTA color code
RESET="\033[0m"   # Reset color code

# Color definitions
MAGENTA="\033[35m"
LIGHTYELLOW="\033[93m"
RESET="\033[0m"
COLOR=$MAGENTA

usage() {
    cat << _EOF
Usage: $SCRIPT_NAME [OPTIONS] <vm_name> <qcow2_path>

Create a FortiGate VM using virt-install.

Required Arguments:
  <vm_name>         Name for the new FortiGate VM.
  <qcow2_path>      Path to the FortiGate qcow2 disk image.

Options:
  -h, --help        Print this help message.
  -d, --debug       Enable debug output.
  -r, --ram MB      Set RAM size in MB (default: $FGT_RAM).
  -c, --vcpus NUM   Set number of vCPUs (default: $FGT_VCPUS).
  -s, --size GB     Set disk size in GB (default: $FGT_DISK_SIZE).
                    Note: This size is primarily metadata for libvirt;
                    the actual size is determined by the qcow2 image itself when importing.
  -p, --desp DESC   Set VM description (default: "$FGT_DESCRIPTION").

Example: $SCRIPT_NAME fgt1 /vms/fortios.qcow2
         $SCRIPT_NAME --ram 4096 --vcpus 2 fgt5 /data/images/fortios.qcow2

_EOF
    exit 1
}

parseOptions() {
    # Define short and long options
    SHORTOPTS="hdr:c:s:"
    LONGOPTS="help,ram:,vcpus:,size:,desp:,debug"

    # Use getopt to parse command-line options
    # Note: Adding -- after options separates them from positional arguments.
    if ! PARSED=$(getopt --options $SHORTOPTS --longoptions "$LONGOPTS" --name "$0" -- "$@"); then
        echo "Error: Failed to parse command-line options." >&2
        usage
    fi

    # Reset positional parameters to the parsed values
    eval set -- "$PARSED"

    # Parse options
    while true; do
        case "$1" in
            -h|--help)
                usage
                ;;
            -d|--debug)
                set -x
                shift
                ;;
            -r|--ram)
                FGT_RAM="$2"
                shift 2
                ;;
            -c|--vcpus)
                FGT_VCPUS="$2"
                shift 2
                ;;
            -s|--size)
                FGT_DISK_SIZE="$2"
                shift 2
                ;;
            --desp)
                FGT_DESCRIPTION="$2"
                shift 2
                ;;
            --)
                shift
                break # End of options
                ;;
            *)
                echo "Error: Invalid option processing."
                exit 3
                ;;
        esac
    done

    # Handle positional arguments (vm_name and qcow2_path)
    if [ $# -lt 2 ]; then
        echo "Error: Missing required arguments <vm_name> and <qcow2_path>."
        usage
    fi
    FGT_NAME="$1"
    FGT_QCOW2_PATH="$2"

    # Check if qcow2 path exists
    if [ ! -f "$FGT_QCOW2_PATH" ]; then
        echo "Error: Qcow2 file not found at '$FGT_QCOW2_PATH'"
        exit 1
    fi
}

parseOptions "$@"
echo -e "${COLOR}Attempting to create VM '$FGT_NAME' with the following settings:${RESET}"
echo -e "${COLOR}  Description: $FGT_DESCRIPTION${RESET}"
echo -e "${COLOR}  RAM:         $FGT_RAM MB${RESET}"
echo -e "${COLOR}  vCPUs:       $FGT_VCPUS${RESET}"
echo -e "${COLOR}  Disk Size:   $FGT_DISK_SIZE GB (metadata)${RESET}"
echo -e "${COLOR}  Qcow2 Path:  $FGT_QCOW2_PATH${RESET}"
echo -e "${COLOR}---${RESET}"

# Explanation of --import option:
# --import performs the following:
#
# 1. Bypass Installation Phase: Without --import, virt-install would start a VM and wait for you
#    to go through a normal OS installation process (partitioning, package selection, etc.)
# 2. Disk Image Handling: With --import, the command treats your qcow2 file ($FGT_QCOW2_PATH)
#    as a ready-to-boot disk image containing all necessary OS components
# 3. Boot Sequence: It modifies the boot sequence to directly boot from the hard drive
#    instead of looking for installation media
# 4. No Installation Source Required: You don't need to specify --location or --cdrom parameters
#    that would normally point to installation media
#
# Note:
# When using --import, the disk size specified within --disk is ignored.
# The VM will use the pre-defined size from the qcow2 image itself.
# Use the following command to check the size of the qcow2 image:
# $ qemu-img info fortios.qcow2
# image: fortios.qcow2
# file format: qcow2
# virtual size: 2 GiB (2147483648 bytes)
# disk size: 75.3 MiB
# cluster_size: 65536
# Format specific information:
#     compat: 1.1
#     lazy refcounts: false
#     refcount bits: 16
#     corrupt: false

echo -e "${COLOR}Creating VM with virt-install, this may take a moment...${RESET}"
# If current user is in libvirt group, then sudo is not needed
sudo virt-install \
    --check path_in_use=on \
    --name="$FGT_NAME" \
    --description="$FGT_DESCRIPTION" \
    --ram="$FGT_RAM" \
    --vcpus="$FGT_VCPUS" \
    --disk "path=$FGT_QCOW2_PATH,format=qcow2,bus=virtio" \
    --import \
    --network network=default,model=virtio \
    --graphics none \
    --noautoconsole

# Check the exit status of virt-install
VIRT_INSTALL_STATUS=${PIPESTATUS[0]}
if [ "$VIRT_INSTALL_STATUS" -eq 0 ]; then
    echo -e "${COLOR}FortiGate VM '$FGT_NAME' has been installed successfully.${RESET}"
    IP_ADDR=

    # Check if VM is actually created and running
    if virsh dominfo "$FGT_NAME" &>/dev/null; then
        VM_STATUS=$(virsh domstate "$FGT_NAME")
        echo -e "${COLOR}VM Status: $VM_STATUS${RESET}"

        # Get IP address if VM is running
        if [ "$VM_STATUS" = "running" ]; then
            echo -e "${COLOR}Waiting for VM to get an IP address (may take a minute)...${RESET}"
            for _ in {1..24}; do
                IP_ADDR=$(virsh domifaddr "$FGT_NAME" 2>/dev/null | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | head -1)
                if [ -n "$IP_ADDR" ]; then
                    break
                fi
                sleep 2
            done
        fi

        # Provide connection instructions
        echo -e "FortiGate VM '$FGT_NAME' creation attempt finished. Check virt-manager or 'virsh list --all'."
        echo -e "${COLOR}---${RESET}"
        echo -e "To connect to the VM console: ${COLOR}virsh console $FGT_NAME${RESET}"
        echo -e "VM IP Address: ${LIGHTYELLOW}$IP_ADDR${RESET}"
        echo -e "Name: ${COLOR}$FGT_NAME${RESET}"
        echo -e "Description: ${COLOR}$FGT_DESCRIPTION${RESET}"
        echo -e "RAM: ${COLOR}$FGT_RAM${RESET} MB"
        echo -e "vCPUs: ${COLOR}$FGT_VCPUS${RESET}"
        echo -e "Disk Size: ${COLOR}$FGT_DISK_SIZE${RESET} GB"
        echo -e "Qcow2 Path: ${COLOR}$FGT_QCOW2_PATH${RESET}"
        echo -e "${COLOR}---${RESET}"
    fi
else
    echo -e "${COLOR}Error: Failed to install FortiGate VM. Exit code: $VIRT_INSTALL_STATUS${RESET}"
fi

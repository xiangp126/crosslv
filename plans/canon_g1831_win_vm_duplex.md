# Canon PIXMA G1831 -- Windows VM Print Server for Manual Duplex

Windows 11 LTSC VM (KVM) on the Ubuntu host provides Canon-native manual
duplex printing. CUPS on the host forwards AirPrint jobs from iPhones to the
Windows printer via SMB.

Companion doc: [canon_g1831_cups.md](canon_g1831_cups.md) (direct Linux CUPS setup).

## Contents

- [Environment](#environment)
- [Architecture](#architecture)
- [Why NAT (not bridge)](#why-nat-not-bridge)
- [Manual duplex -- what works and what doesn't](#manual-duplex----what-works-and-what-doesnt)
- [Step 0 -- Fix the usbip watchdog path](#step-0----fix-the-usbip-watchdog-path)
- [Step 1 -- Download VirtIO drivers ISO](#step-1----download-virtio-drivers-iso)
- [Step 2 -- Create the Windows 11 LTSC VM](#step-2----create-the-windows-11-ltsc-vm)
- [Step 3 -- USB passthrough to the VM](#step-3----usb-passthrough-to-the-vm)
- [Step 4 -- Install Canon driver in Windows](#step-4----install-canon-driver-in-windows)
- [Step 5 -- Share the printer from Windows (SMB)](#step-5----share-the-printer-from-windows-smb)
- [Step 6 -- Configure CUPS forwarded queue](#step-6----configure-cups-forwarded-queue)
- [Step 7 -- AirPrint](#step-7----airprint)
- [Step 8 -- Test the full chain](#step-8----test-the-full-chain)
- [Step 9 -- Auto-start and monitoring](#step-9----auto-start-and-monitoring)
- [Step 10 -- AutoHotKey duplex automation](#step-10----autohotkey-duplex-automation)
- [Resource impact](#resource-impact)
- [Rollback](#rollback)

## Environment

| Item                | Value                                                                          |
| ------------------- | ------------------------------------------------------------------------------ |
| Host                | Ubuntu 24.04 (`ubuntu01`, `192.168.10.240`), 8 CPU threads, 7.6 GB RAM        |
| Virtualisation      | KVM / libvirt / virt-manager (pre-installed), NAT bridge `virbr0`              |
| Printer             | Canon PIXMA G1831 (China-market, single-function color inkjet, `04a9:18f6`)    |
| Printer connection  | USB cable to OpenWrt router (`192.168.10.1`), exported via USB/IP to host      |
| Existing CUPS queue | `CanonG1831` using `cnijbe2://Canon/?port=usb&serial=6050CA`                   |
| VM OS               | Windows 11 Enterprise LTSC 2024 (zh-cn)                                        |
| VM specs            | 2 vCPU, 4 GB RAM, 40 GB VirtIO disk, NAT networking                           |
| Windows ISO         | `~/Downloads/zh-cn_windows_11_enterprise_ltsc_2024_x64_dvd_cff9cd2d.iso`       |
| VirtIO ISO          | `~/Downloads/virtio-win.iso` (from fedorapeople.org)                           |

## Architecture

```
                      ┌──────────────────────────────────────────┐
                      │         Ubuntu Host (192.168.10.240)     │
                      │                                          │
┌─────────┐ AirPrint  │  ┌──────┐    ┌─────────────────────┐    │
│  iPhone  │──(IPP)───▶│  │ CUPS │───▶│ SMB → Windows VM    │    │
└─────────┘  Wi-Fi    │  └──────┘    │ (192.168.122.100 NAT) │    │
                      │              │                       │    │
┌─────────┐ AirPrint  │              │  ┌────────────────┐  │    │
│   Mac   │──(IPP)───▶│              │  │  Canon driver   │  │    │
└─────────┘  Wi-Fi    │              │  │  (Windows 11)   │  │    │
                      │              │  └───────┬────────┘  │    │
┌─────────┐ AirPrint  │              │          │ USB       │    │
│ Android │──(IPP)───▶│              │          │ passthru  │    │
└─────────┘  Wi-Fi    │              └──────────┼───────────┘    │
                      │                         │                │
                      │                    ┌────▼─────┐          │
                      │                    │  USB/IP  │          │
                      │                    │  client  │          │
                      │                    │(vhci-hcd)│          │
                      │                    └────┬─────┘          │
                      └─────────────────────────┼────────────────┘
                                                │ TCP :3240
                      ┌─────────────────────────┼────────────────┐
                      │   WRT32X Router (OpenWrt)│                │
                      │                    ┌────▼─────┐          │
                      │                    │  USB/IP  │          │
                      │                    │  server  │          │
                      │                    │(usbipd)  │          │
                      │                    └────┬─────┘          │
                      │                         │ USB cable      │
                      └─────────────────────────┼────────────────┘
                                                │
                      ┌─────────────────────────▼────────────────┐
                      │          Canon PIXMA G1831               │
                      │       (USB inkjet, no Wi-Fi)             │
                      └──────────────────────────────────────────┘
```

The VM uses the existing `virbr0` NAT network (`192.168.122.100`), not bridge.
Since CUPS runs on the same host, it reaches the VM directly over NAT. No
bridge or NetworkManager reconfiguration needed.

## Why NAT (not bridge)

The host connects to the LAN over **Wi-Fi** (`wlp3s0`). Wi-Fi does not support
bridging -- the 802.11 standard only allows one MAC address per association, so
a bridged VM's MAC gets blocked by the access point. macvtap ("Host device" in
virt-manager) has the same limitation, plus a further issue: the host cannot
communicate with its own macvtap guest.

NAT is the correct choice because **no external device ever talks to the VM
directly**. CUPS acts as a proxy between the two networks:

```
┌───────────────────────────────────────────────────────────────────┐
│                                                                   │
│  LAN (192.168.10.0/24)  ──── Host ────  NAT (192.168.122.0/24)  │
│                                                                   │
│  iPhone      10.x                       122.x   Windows VM       │
│  Mac         10.x         CUPS          122.1   (host/gateway)   │
│  Router      10.1     bridges the gap                             │
│  Host        10.240                                               │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

The host has two interfaces:

- `wlp3s0` = `192.168.10.240` (Wi-Fi, LAN-facing)
- `virbr0` = `192.168.122.1` (virtual bridge, NAT gateway for VMs)

CUPS runs on the host, so it can natively reach both networks. The data flow
for an iPhone print job:

| Hop | Protocol | Network | What happens |
| --- | -------- | ------- | ------------ |
| iPhone → CUPS | IPP (AirPrint) | LAN (10.x) | iPhone sends PDF to CUPS |
| CUPS → Windows VM | SMB | NAT (122.x) | CUPS forwards job to Windows shared printer |
| Windows → Printer | USB (IVEC) | USB passthrough + USB/IP | Canon driver sends native print data |

Each hop uses the protocol native to that segment. The VM is an implementation
detail hidden behind CUPS -- invisible to the LAN.

**Why NAT is actually better here:**

- **Isolation** -- VM has no attack surface on the LAN.
- **No IP conflict** -- VM doesn't consume a LAN IP or compete with DHCP.
- **Wi-Fi compatible** -- bridging over Wi-Fi is broken by design; NAT works on
  any connection type.
- **Zero config** -- `virbr0` already exists from the libvirt install.
- **Portable** -- if the host moves to a different network, nothing in the VM
  config changes.

## Manual duplex -- what works and what doesn't

The Canon Windows driver shows a **blocking dialog** ("Reload the output pages
into the input tray, then click OK") during manual duplex.

| Print path | Duplex? | Why |
| --- | --- | --- |
| RDP/VNC into Windows VM, print directly | Yes | Dialog appears on screen, you click OK |
| iPhone → AirPrint → CUPS → Windows VM (SMB) | No | Non-interactive network job; dialog blocks spooler or driver falls back to single-sided |
| iPhone → AirPrint → CUPS → Windows VM + AutoHotKey | Maybe | Script auto-clicks dialog after delay; experimental |

**Recommended:** iPhone AirPrint for single-sided. RDP into the VM when you
need duplex.

## Step 0 -- Fix the usbip watchdog path

The watchdog at `/usr/local/bin/usbip-canon-watchdog` hardcodes
`/usr/sbin/usbip`, but the binary moved to `/usr/bin/usbip` after a kernel
tools update. The watchdog was looping every 10 seconds on "No such file or
directory."

```bash
# Find the real usbip binary
find /usr -name usbip -type f 2>/dev/null
# Output: /usr/bin/usbip
#         /usr/lib/linux-hwe-6.17-tools-6.17.0-19/usbip

# Create a symlink to restore the expected path
sudo ln -sf /usr/bin/usbip /usr/sbin/usbip

# Restart and verify
sudo systemctl restart usbip-canon
sudo systemctl status usbip-canon   # Should show active, no errors
```

## Step 1 -- Download VirtIO drivers ISO

VirtIO provides paravirtualized disk, network, and memory balloon drivers for
KVM guests. Windows does not ship with these drivers, so they must be loaded
from the ISO during installation.

```bash
wget -P ~/Downloads/ \
  https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso
```

~753 MB download. After downloading, both ISOs should be in place:

- `~/Downloads/zh-cn_windows_11_enterprise_ltsc_2024_x64_dvd_cff9cd2d.iso`
- `~/Downloads/virtio-win.iso`

## Step 2 -- Create the Windows 11 LTSC VM

### 2a. Prerequisites: swtpm and OVMF

Win11 requires TPM 2.0 and UEFI. These are emulated by `swtpm` and `ovmf`:

```bash
sudo apt install -y swtpm swtpm-tools ovmf
```

### 2b. Create via CLI (virt-install)

Using `virt-install` is faster and more reproducible than the virt-manager GUI.
The VM name is `win11-print`.

```bash
sudo virt-install \
  --name win11-print \
  --os-variant win11 \
  --vcpus 2 \
  --memory 4096 \
  --disk size=40,bus=virtio \
  --cdrom ~/Downloads/zh-cn_windows_11_enterprise_ltsc_2024_x64_dvd_cff9cd2d.iso \
  --disk ~/Downloads/virtio-win.iso,device=cdrom \
  --network network=default,model=virtio \
  --graphics vnc \
  --video virtio \
  --tpm backend.type=emulator,backend.version=2.0,model=tpm-tis \
  --boot uefi \
  --noautoconsole
```

> **Gotcha: libvirt-qemu permissions.** If the ISOs are under your home
> directory, the `libvirt-qemu` user needs execute permission on the path:
>
>     sudo chmod o+x /home/corsair
>
> Without this the VM fails to start with a permission error on the ISO files.

> **Gotcha: Spice and QXL.** On Ubuntu 24.04 with QEMU 8.2+, Spice graphics
> and QXL video are **not supported** (builds without Spice). Use `--graphics
> vnc` and `--video virtio` instead.

> **RAM: use 4096 MB.** Win11 hard-requires 4 GB. With 2 GB the installer
> blocks at "This PC doesn't meet requirements." The bypass registry hack
> (`LabConfig` DWORDs) works but 4 GB avoids the hassle. With VirtIO balloon
> the VM returns unused RAM to the host (~1.5 GB actual when idle).

After creation the VM starts automatically. Check status:

```bash
sudo virsh list --all
sudo virsh vncdisplay win11-print   # e.g. 127.0.0.1:0 (= port 5900)
```

### 2c. Connect to the console

Open `virt-manager` and double-click `win11-print`. Or from a terminal:

```bash
virt-manager --connect qemu:///system --show-domain-console win11-print
```

### 2d. UEFI boot -- first-time gotcha

On first boot (or after a `virsh destroy` + `virsh start`), the VM may land on
the **UEFI firmware setup screen** (TianoCore) instead of booting the Windows
ISO. If this happens:

1. Select **Boot Manager** → Enter
2. Select the **CDROM entry** (e.g., `UEFI QEMU DVD-ROM QM00001`)
3. Press Enter -- the Windows installer starts

### 2e. Windows installation

1. The installer starts in Chinese (zh-cn ISO). Choose language/region.
2. At the disk selection screen ("选择安装 Windows 11 的位置"), the disk list
   is **empty** because Windows has no VirtIO storage driver.
3. Click **"Load Driver"** (加载驱动程序) at the top.
4. Click **"Browse"** (浏览).
5. Navigate to the **second CD/DVD drive** (VirtIO ISO) →
   `viostor` → `w11` → `amd64`.
6. Select the **Red Hat VirtIO SCSI controller** driver → OK → Next.
7. The 40 GB VirtIO disk appears in the list. Select it and proceed.
8. The rest of the install is standard Windows setup (account, region, etc.).

### 2f. Post-install: VirtIO guest tools

After Windows is installed and you're on the desktop:

1. Open **File Explorer** → the VirtIO ISO drive (D: or E:).
2. Run **`virtio-win-gt-x64.msi`**. This installs all remaining VirtIO drivers:
   - **Network** (VirtIO Ethernet -- network comes alive after this)
   - **Balloon** (memory reclamation -- idle VM returns unused RAM to host)
   - **Serial/console** (virtio-serial)
3. Reboot the VM when prompted.

### 2g. Note the VM's IP

After the VirtIO network driver is installed and the VM has connectivity:

```bash
virsh net-dhcp-leases default
```

Example output: `192.168.122.100`. CUPS will use this IP. You can also check
inside Windows: `ipconfig` in CMD.

## Step 3 -- USB passthrough to the VM

### 3a. Stop Linux-side printer usage

```bash
sudo cupsdisable CanonG1831
sudo systemctl stop usbip-canon
```

> **Note:** Stopping the watchdog may cause the USB/IP link to drop. If the
> Canon device disappears from `lsusb`, re-attach it manually before
> proceeding:
>
>     sudo modprobe vhci-hcd
>     sudo usbip attach -r 192.168.10.1 -b 1-1
>     lsusb | grep Canon   # Should show 04a9:18f6

### 3b. Add USB device to VM

Attach the Canon USB device both live (hot-plug) and persistent (survives
reboot):

```bash
cat << 'EOF' > /tmp/canon-usb.xml
<hostdev mode='subsystem' type='usb' managed='yes'>
  <source>
    <vendor id='0x04a9'/>
    <product id='0x18f6'/>
  </source>
</hostdev>
EOF
sudo virsh attach-device win11-print /tmp/canon-usb.xml --persistent
```

Or in virt-manager: VM settings → Add Hardware → USB Host Device → select
"Canon, Inc. G1030 series (04a9:18f6)."

Verify the passthrough is in the VM config:

```bash
sudo virsh dumpxml win11-print | grep -A5 "hostdev.*usb"
```

### 3c. Update the usbip watchdog

The watchdog must keep the USB/IP link alive but no longer claim the device for
CUPS (the VM owns it now). Remove the `lpadmin` call:

```bash
sudo tee /usr/local/bin/usbip-canon-watchdog > /dev/null << 'SCRIPT'
#!/bin/bash
ROUTER=192.168.10.1
BUSID=1-1
VENDOR_PRODUCT=04a9:18f6

/sbin/modprobe vhci-hcd

while true; do
    if lsusb -d "$VENDOR_PRODUCT" > /dev/null 2>&1; then
        sleep 30
        continue
    fi
    /usr/sbin/usbip detach -p 0 2>/dev/null
    if /usr/sbin/usbip attach -r "$ROUTER" -b "$BUSID"; then
        sleep 5
    else
        sleep 10
    fi
done
SCRIPT
sudo chmod +x /usr/local/bin/usbip-canon-watchdog
sudo systemctl start usbip-canon
```

### 3d. Verify in Windows

Open Device Manager in the VM. The Canon printer should appear under
**USB devices** or **Other devices** (before driver installation).

## Step 4 -- Install Canon driver in Windows

1. Download the Canon G1830/G1831 Windows driver from
   [Canon China support](https://www.canon.com.cn/supports/).
2. Install in the VM.
3. The printer should appear in Windows Settings → Printers.

### Test basic printing

Print a test page (Notepad → Print). Verify output.

### Test manual duplex

1. Open a multi-page PDF in the VM.
2. Print → Canon printer → Properties → Duplex (Manual).
3. Expected: odd pages print, dialog appears, click OK after flipping paper,
   even pages print.

## Step 5 -- Share the printer from Windows (SMB)

1. Control Panel → Devices and Printers → right-click Canon printer →
   Printer Properties → Sharing tab.
2. Check "Share this printer," share name: `CanonG1831`.
3. Security tab: allow "Everyone" to print.

Enable sharing: Settings → Network & Internet → Advanced sharing settings →
Turn on file and printer sharing.

> **Why SMB and not IPP?** Windows has no built-in lightweight IPP server. The
> only way to serve printers via IPP on Windows is through IIS (Internet
> Information Services) with the Internet Printing role -- overkill for a
> print-only VM. SMB printer sharing is native to Windows (zero extra software)
> and works reliably with the CUPS SMB backend.

### Verify from Linux

```bash
sudo apt install -y smbclient
smbclient -L //192.168.122.100 -N
# CanonG1831 should appear in the share list
```


## Step 6 -- Configure CUPS forwarded queue

### 6a. Install SMB backend

```bash
sudo apt install -y smbclient
```

> **Note:** There is no separate `cups-backend-smb` package on Ubuntu 24.04.
> Installing `smbclient` provides the CUPS SMB backend at
> `/usr/lib/cups/backend/smb`.

### 6b. Create the forwarded queue

```bash
sudo lpadmin -p CanonWin \
  -v smb://guest@192.168.122.100/CanonG1831 \
  -m raw \
  -D "Canon G1831 (via Windows)" \
  -L "Windows VM" \
  -o printer-is-shared=true \
  -E

sudo lpadmin -d CanonWin
```

`-m raw` passes incoming data directly to Windows without conversion. iPhone
AirPrint sends PDF, which Windows can process through its own driver chain.

If raw mode causes garbled output, switch to a generic PDF PPD:

```bash
sudo lpadmin -p CanonWin \
  -v smb://guest@192.168.122.100/CanonG1831 \
  -P /usr/share/ppd/cupsfilters/Generic-PDF_Printer-PDF.ppd \
  -o printer-is-shared=true \
  -E
```

### 6c. Disable the old direct queue

```bash
sudo cupsdisable CanonG1831
```

## Step 7 -- AirPrint

```bash
sudo cupsctl --share-printers
sudo systemctl restart cups
```

Verify:

```bash
avahi-browse -t _ipp._tcp
```

The `CanonWin` queue should be advertised. iPhones will discover it
automatically.

## Step 8 -- Test the full chain

### Single-sided from iPhone

1. iPhone → Share → Print → select the printer.
2. Print a PDF.
3. Expected: CUPS → SMB → Windows → Canon driver → printer.

### Duplex from Windows VM

1. Open virt-manager or RDP into the VM.
2. Open a PDF, print with manual duplex.
3. Click OK on the dialog after flipping paper.
4. Expected: complete duplex output.

## Step 9 -- Auto-start and monitoring

### Auto-start the VM on boot

```bash
sudo virsh autostart win11-print
```

### Adjust the usbip watchdog

Already done in Step 3c -- the watchdog maintains the USB/IP link from the
router without touching CUPS. KVM owns the USB passthrough to the VM.

### RDP access

Windows 11 LTSC Enterprise has a built-in RDP server. Enable it inside the VM:
Settings → System → Remote Desktop → toggle ON.

From Linux, connect via `remmina` or any RDP client:

```bash
sudo apt install -y remmina
# Connect to 192.168.122.100:3389
```

Or use virt-manager's built-in VNC console (works without any setup in the
guest -- the console is provided by QEMU, not Windows).

## Step 10 -- AutoHotKey duplex automation

> Optional / experimental.

To make iPhone → duplex work unattended:

1. Install [AutoHotKey](https://www.autohotkey.com/) in the VM.
2. Create a script that detects the Canon duplex dialog and auto-clicks OK
   after a configurable delay (e.g., 60 s for paper flipping).
3. Set the script to run at Windows startup.

Depends on the exact Canon driver version and dialog window title.

## Resource impact

| Item      | Usage                                               |
| --------- | --------------------------------------------------- |
| RAM       | ~4 GB allocated, ~1.5 GB actual with VirtIO balloon |
| Disk      | 40 GB qcow2 image                                   |
| CPU       | Near zero when idle; brief spikes during print jobs |
| Boot time | ~30 s from VM start to Windows desktop              |

## Rollback

If the VM approach doesn't work out, restore the direct Linux CUPS setup:

```bash
sudo cupsenable CanonG1831
sudo lpadmin -d CanonG1831
sudo lpadmin -x CanonWin
sudo systemctl start usbip-canon
sudo virsh destroy win11-print
sudo virsh undefine win11-print --remove-all-storage --nvram
```

> **Note:** `--nvram` removes the UEFI NVRAM copy. `--remove-all-storage`
> deletes the 40 GB qcow2 disk image at `/var/lib/libvirt/images/`.

# Canon PIXMA G1831 — CUPS Print Server + AirPrint on Ubuntu

Tested on Ubuntu 24.04 (XFCE). This guide turns an Ubuntu machine into a
LAN print server that re-shares a Canon G1831 printer for iPhones, Android
phones, and other devices via AirPrint (zero-config).

## Contents

- [Environment](#environment)
- [Network topology](#network-topology)
- [Why USB/IP instead of raw socket (port 9100)](#why-usbip-instead-of-raw-socket-port-9100)
- [Step 1 — Router: export the printer via USB/IP](#step-1--router-export-the-printer-via-usbip)
- [Step 2 — Ubuntu: install packages](#step-2--ubuntu-install-packages)
- [Step 3 — Ubuntu: attach the remote USB printer](#step-3--ubuntu-attach-the-remote-usb-printer)
- [Step 4 — Install the Canon cnijfilter2 driver](#step-4--install-the-canon-cnijfilter2-driver)
- [Step 5 — Add the printer to CUPS](#step-5--add-the-printer-to-cups)
- [Step 6 — Configure CUPS for LAN access and AirPrint](#step-6--configure-cups-for-lan-access-and-airprint)
- [Step 7 — Firewall (only if ufw is active)](#step-7--firewall-only-if-ufw-is-active)
- [Step 8 — Verify AirPrint discovery](#step-8--verify-airprint-discovery)
- [Step 9 — Test](#step-9--test)
- [Troubleshooting](#troubleshooting)

## Environment

| Item                | Value                                                                              |
| ------------------- | ---------------------------------------------------------------------------------- |
| Printer             | Canon PIXMA G1831 (China-market, single-function color inkjet, model code `5809C`) |
| Physical connection | USB cable from printer to router (WRT32X / OpenWrt)                                |
| Printer→Ubuntu link | **USB/IP** (router exports USB device, Ubuntu attaches it as virtual local USB)     |
| CUPS printer URI    | `cnijbe2://Canon/?port=usb&serial=6050CA`                                          |
| Linux driver        | `cnijfilter2` v6.60 -- installs PPD as `canong1030.ppd` (G1831 = G1030 series)     |
| AirPrint discovery  | Handled automatically by CUPS via DNS-SD/Avahi (no manual Avahi service file needed) |
| Duplex              | Not supported (no auto-duplexer; `cnijfilter2` cannot handle duplex commands)        |

## Network topology

```
                          ┌──────────────────────────────────────────┐
                          │         Ubuntu Print Server              │
                          │                                          │
  ┌─────────┐   AirPrint  │  ┌──────┐    ┌────────────┐             │
  │  iPhone  │────(IPP)───▶│  │ CUPS │───▶│cnijfilter2 │             │
  └─────────┘    Wi-Fi    │  └──────┘    └─────┬──────┘             │
                          │                    │ Canon IVEC          │
  ┌─────────┐   AirPrint  │               ┌────▼─────┐              │
  │   Mac   │────(IPP)───▶│               │  USB/IP  │              │
  └─────────┘    Wi-Fi    │               │  client  │              │
                          │               │(vhci-hcd)│              │
  ┌─────────┐   AirPrint  │               └────┬─────┘              │
  │ Android │────(IPP)───▶│                    │ TCP :3240           │
  └─────────┘    Wi-Fi    │                    │ (virtual USB)       │
                          └────────────────────┼─────────────────────┘
                                               │ LAN
                          ┌────────────────────┼─────────────────────┐
                          │   WRT32X Router    │    (OpenWrt)        │
                          │               ┌────▼─────┐              │
                          │               │  USB/IP  │              │
                          │               │  server  │              │
                          │               │(usbipd)  │              │
                          │               └────┬─────┘              │
                          │                    │ USB cable           │
                          └────────────────────┼─────────────────────┘
                                               │
                          ┌────────────────────▼─────────────────────┐
                          │          Canon PIXMA G1831               │
                          │       (USB inkjet, no Wi-Fi)             │
                          └──────────────────────────────────────────┘
```

## Why USB/IP instead of raw socket (port 9100)

The Canon `cnijfilter2` driver uses Canon's proprietary **IVEC bidirectional XML
protocol**. It sends print data in chunks and exchanges XML status queries with
the printer between chunks. The router's `p910nd` relay on port 9100 introduces
latency in this handshake, throttling throughput to ~8 KB/s. The printer's
internal buffer underruns mid-page, causing it to stop printing halfway.

USB/IP solves this by presenting the printer as a local USB device on the Ubuntu
machine. The IVEC protocol runs at full USB speed with no relay in the middle.

> [!NOTE]
> `socket://192.168.10.1:9100` works on Windows because the Windows Canon
> driver has different timing tolerance for the IVEC protocol. On Linux with
> `cnijfilter2`, it stalls. Gutenprint cannot be used because the G1831
> requires Canon's proprietary data format.

<!--
Data path comparison:

  Before (broken):
    cnijfilter2 → CUPS socket backend → TCP → p910nd → USB → Printer
                   (IVEC stalls here due to relay latency)

  After (working):
    cnijfilter2 → Canon USB backend → USB/IP tunnel → USB → Printer
                   (IVEC runs at full USB speed, no relay)

The cnijfilter2 driver does NOT simply stream data to the printer. For every
~8 KB chunk it sends, it pauses to exchange an IVEC XML status query/response
with the printer before sending the next chunk. When this handshake goes
through p910nd (a dumb TCP-to-USB relay), each round-trip adds network latency.
At ~8 KB/s the printer physically starts printing but its internal buffer runs
dry mid-page because data arrives too slowly. The printer then stops and ejects
a half-printed page.

Windows works with the same p910nd relay because its Canon driver tolerates
the added latency in the IVEC handshake (likely larger chunks or async status
polling). Gutenprint was tested but the G1831 does not respond to non-Canon
data formats at all (printer ignores the job entirely).

USB/IP (kernel module vhci-hcd on client, usbip-host on server) tunnels raw
USB transactions over TCP. The Canon driver sees a real USB device and the IVEC
protocol runs at native speed. The router still physically hosts the USB cable
but the Ubuntu machine owns the device at the protocol level.
-->

To quantify the difference, compare print times with a multi-page document:

```bash
time lp -d CanonG1831 /path/to/multipage.pdf
```

Expected: USB/IP restores normal print speed; in testing it completes in seconds
rather than crawling at ~8 KB/s through p910nd. The same file through
`socket://router:9100` via p910nd typically stalls mid-page.

## Step 1 — Router: export the printer via USB/IP

On the OpenWrt router (SSH in):

```bash
opkg update
opkg install kmod-usbip kmod-usbip-server kmod-usbip-client \
  usbip usbip-server usbip-client

# Find the printer's bus ID
/usr/sbin/usbip list -l
# Example output:  - busid 1-1 (04a9:18f6)  Canon, Inc.

# Bind the printer (replace 1-1 with actual bus ID)
/usr/sbin/usbip bind -b 1-1

# Start the daemon (listens on port 3240)
usbipd -D
```

To persist across reboots:

```bash
/etc/init.d/usbipd enable
sed -i '/^exit 0/i /usr/sbin/usbip bind -b 1-1' /etc/rc.local
```

> [!NOTE]
> `luci-app-usbip-server` is not available on all OpenWrt builds. If your
> firmware has it (`opkg list | grep luci-app-usbip`), install it for a web
> UI at Services → USBIP Server. Otherwise use the CLI above.

> [!TIP]
> If `p910nd` was previously used, disable it so it releases the USB device:
> `/etc/init.d/p910nd stop && /etc/init.d/p910nd disable`

## Step 2 — Ubuntu: install packages

```bash
sudo apt update
sudo apt install -y \
  cups cups-client cups-filters \
  avahi-daemon avahi-utils \
  linux-tools-common linux-tools-$(uname -r)
```

> [!TIP]
> If `linux-tools-$(uname -r)` is not found, the package name may differ on
> your kernel. Run `apt search linux-tools` to find the matching package.

Ensure Avahi is running (installed does not always mean enabled on Ubuntu 24.04):

```bash
sudo systemctl enable --now avahi-daemon
```

Add your user to the printer admin group:

```bash
sudo usermod -aG lpadmin $USER
newgrp lpadmin
```

## Step 3 — Ubuntu: attach the remote USB printer

```bash
sudo modprobe vhci-hcd
sudo usbip attach -r 192.168.10.1 -b 1-1
```

Verify the printer appears as a local USB device:

```bash
lsusb | grep Canon
# Should show: Canon, Inc. G1030 series
lpinfo -v | grep cnijbe2
# Should show: direct cnijbe2://Canon/?port=usb&serial=...
```

Create a watchdog script that attaches the printer and re-attaches if the
link drops (router reboot, Wi-Fi hiccup, USB reset):

```bash
sudo tee /usr/local/bin/usbip-canon-watchdog > /dev/null << 'SCRIPT'
#!/bin/bash
ROUTER=192.168.10.1
BUSID=1-1
VENDOR_PRODUCT=04a9:18f6
PRINTER_NAME=CanonG1831
PRINTER_URI='cnijbe2://Canon/?port=usb&serial=6050CA'

/sbin/modprobe vhci-hcd

while true; do
    if lsusb -d "$VENDOR_PRODUCT" > /dev/null 2>&1; then
        sleep 30
        continue
    fi
    PORT=$(/usr/sbin/usbip port 2>/dev/null \
      | awk '/'"$VENDOR_PRODUCT"'/ {print prev} {prev=$0}' \
      | sed -n 's/^Port \([0-9]\+\):.*/\1/p')
    [ -n "$PORT" ] && /usr/sbin/usbip detach -p "$PORT" 2>/dev/null
    if /usr/sbin/usbip attach -r "$ROUTER" -b "$BUSID"; then
        sleep 2
        /usr/sbin/lpadmin -p "$PRINTER_NAME" -v "$PRINTER_URI" -E 2>/dev/null
        sleep 30
    else
        sleep 10
    fi
done
SCRIPT
sudo chmod +x /usr/local/bin/usbip-canon-watchdog
```

Create a small helper used by the service to cleanly detach the printer:

```bash
sudo tee /usr/local/bin/usbip-canon-detach > /dev/null << 'SCRIPT'
#!/bin/bash
PORT=$(/usr/sbin/usbip port 2>/dev/null \
  | awk '/04a9:18f6/ {print prev} {prev=$0}' \
  | sed -n 's/^Port \([0-9]\+\):.*/\1/p')
[ -n "$PORT" ] && /usr/sbin/usbip detach -p "$PORT"
SCRIPT
sudo chmod +x /usr/local/bin/usbip-canon-detach
```

Create a systemd service that runs the watchdog:

```bash
sudo tee /etc/systemd/system/usbip-canon.service > /dev/null << 'UNIT'
[Unit]
Description=Attach Canon G1831 via USB/IP from router
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStartPre=/bin/sleep 5
ExecStart=/usr/local/bin/usbip-canon-watchdog
ExecStop=/usr/local/bin/usbip-canon-detach
Restart=always
RestartSec=10
StartLimitIntervalSec=0

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable usbip-canon.service
```

**How the watchdog works:**

1. `lsusb -d 04a9:18f6` checks if a Canon device with that vendor:product ID is
   visible as a USB device. This matches by ID only -- it does not distinguish
   the USB/IP-attached printer from another Canon USB device plugged in locally.
   On a dedicated print server this is fine; on a multi-purpose machine, keep it
   in mind.
2. If yes -- sleeps 30 seconds, checks again. This is the steady-state path.
3. If no (printer disappeared) -- parses `usbip port` to find the VHCI port
   currently assigned to `04a9:18f6`, detaches it to clean up the stale link,
   then runs `usbip attach` to reconnect from the router.
4. If attach succeeds -- waits 2 s for device enumeration, then runs
   `lpadmin -p CanonG1831 -E` to re-enable the CUPS queue (CUPS marks the
   printer "stopped" when the USB device vanishes mid-job).
5. If attach fails (router down, network unreachable) -- sleeps 10 s, retries.

The service unit adds `ExecStartPre=/bin/sleep 5` (handles DHCP not ready at
boot), `Restart=always` + `StartLimitIntervalSec=0` (infinite restart on crash).

**When you need the watchdog vs the old oneshot:**

| Scenario                               | Old oneshot                          | Watchdog                             |
| -------------------------------------- | ------------------------------------ | ------------------------------------ |
| Router reboots while Ubuntu is running | Printer gone until manual restart    | Auto-recovers in ~30 s              |
| Wi-Fi drops briefly                    | Printer gone until manual restart    | Auto-recovers in ~30 s              |
| USB reset on router side               | Printer gone until manual restart    | Auto-recovers in ~30 s              |
| CUPS marks printer stopped on reconnect| Stays stopped, jobs rejected         | `lpadmin -E` re-enables it           |
| Boot before router is fully ready      | May fail once and give up            | Keeps retrying forever               |

If this is a "plug it in and forget it" server for family members printing from
phones, the watchdog is worth it. If you are the only user and always at the
keyboard, the old oneshot was fine -- just run
`sudo systemctl restart usbip-canon` when the link drops.

Overhead is negligible: one bash process sleeping 30 s in a loop, waking for a
single `lsusb` call (~1 ms), going back to sleep. Typical memory usage ~760 KB.

## Step 4 — Install the Canon cnijfilter2 driver

```bash
cd /tmp
wget https://gdlp01.c-wss.com/gds/1/0100011751/01/cnijfilter2-6.60-1-deb.tar.gz
tar xzf cnijfilter2-6.60-1-deb.tar.gz
cd cnijfilter2-6.60-1-deb/packages
sudo dpkg -i cnijfilter2_*_amd64.deb
sudo apt install -f -y
```

Verify the PPD is available:

```bash
lpinfo --make-and-model "Canon" -m | grep -i g1030
```

Expected output (the G1831 is listed under the G1030 series):

```
canong1030.ppd    Canon G1030 series Ver.6.60
```

## Step 5 — Add the printer to CUPS

Use the Canon native USB backend URI (shown by `lpinfo -v | grep cnijbe2`):

```bash
sudo lpadmin -p CanonG1831 \
  -v cnijbe2://Canon/?port=usb&serial=6050CA \
  -m canong1030.ppd \
  -D "Canon PIXMA G1831" \
  -L "Home Office" \
  -E

sudo lpadmin -d CanonG1831
sudo lpadmin -p CanonG1831 -o printer-is-shared=true
```

Verify:

```bash
lpstat -p -d
# Should show: printer CanonG1831 is idle. enabled since ...
# system default destination: CanonG1831
```

## Step 6 — Configure CUPS for LAN access and AirPrint

```bash
sudo cupsctl --share-printers
```

Then add `ServerAlias *` to cupsd.conf (allows access by IP, not just hostname):

```bash
grep -q "ServerAlias" /etc/cups/cupsd.conf || \
  sudo sed -i '/^Port 631/a ServerAlias *' /etc/cups/cupsd.conf
```

Verify cupsd.conf has these key directives (edit with `sudo vim /etc/cups/cupsd.conf`
if any are missing):

```
Port 631
ServerAlias *
Browsing On
BrowseLocalProtocols dnssd
WebInterface Yes

<Location />
  Order allow,deny
  Allow @LOCAL
</Location>
```

`BrowseLocalProtocols dnssd` is the key line -- it tells CUPS to register the
shared printer with Avahi automatically. This is what makes AirPrint work.
No manual Avahi service file (`/etc/avahi/services/*.service`) is needed.
Creating one would result in duplicate printer entries on client devices.

Restart and enable on boot:

```bash
sudo systemctl restart cups
sudo systemctl enable cups
```

Verify CUPS listens on all interfaces:

```bash
ss -tlnp | grep 631
# Should show 0.0.0.0:631 (not 127.0.0.1:631)
```

> [!CAUTION]
> This configuration (`Port 631`, `Allow @LOCAL`, `ServerAlias *`) is safe on a
> private home LAN. Do **not** expose port 631 to the internet -- CUPS has a
> history of remote code execution vulnerabilities. If the machine is reachable
> beyond the LAN (VPN, port-forwarding, public IP), bind CUPS to a specific
> interface instead:
>
>     Listen 192.168.10.240:631

## Step 7 — Firewall (only if ufw is active)

```bash
sudo ufw status
```

If active:

```bash
sudo ufw allow from 192.168.10.0/24 to any port 631 proto tcp
sudo ufw allow from 192.168.10.0/24 to any port 631 proto udp
sudo ufw allow 5353/udp
sudo ufw reload
```

If inactive, skip this step.

## Step 8 — Verify AirPrint discovery

```bash
avahi-browse -t _ipp._tcp
```

Expected output (one entry per interface, not duplicated):

```
+ wlp3s0 IPv4 Canon PIXMA G1831 @ ubuntu01    Internet Printer    local
+ wlp3s0 IPv6 Canon PIXMA G1831 @ ubuntu01    Internet Printer    local
```

If you see TWO different printer names (e.g., "Canon PIXMA G1831" and
"Canon G1831"), you have a stale manual Avahi service file. Remove it:

```bash
sudo rm /etc/avahi/services/CanonG1831.service
sudo systemctl restart avahi-daemon
```

## Step 9 — Test

Send a test page from the Ubuntu machine:

```bash
lp -d CanonG1831 /usr/share/cups/data/testprint
```

The printer will run its post-print maintenance cycle for 1–3 minutes after
printing (head cleaning). This is normal for Canon G-series ink tank printers.

CUPS web interface: `http://<ubuntu-ip>:631`

**iPhone/iPad:** Share → Print. Printer appears automatically.

**Android:** Settings → Connected devices → Printing → Default Print Service.
Or install **Mopria Print Service** from the Play Store and ensure it is toggled ON.
Some Android builds include Mopria by default; others require the separate install.

**Other Linux:** `lpadmin -p RemoteG1831 -v ipp://<ubuntu-ip>:631/printers/CanonG1831 -E`

## Troubleshooting

```bash
# CUPS error log
sudo tail -f /var/log/cups/error_log

# Increase log verbosity temporarily
sudo cupsctl --debug-logging
# Revert: sudo cupsctl --no-debug-logging

# Check services
systemctl status cups
systemctl status avahi-daemon
systemctl status usbip-canon

# Verify USB/IP link is up
lsusb | grep Canon
usbip port

# Re-attach if the USB/IP link dropped
sudo usbip attach -r 192.168.10.1 -b 1-1

# Full CUPS status
lpstat -t

# List all available Canon PPDs
lpinfo --make-and-model "Canon" -m | grep -i g1
```

| Problem                     | Fix                                                                                           |
| --------------------------- | --------------------------------------------------------------------------------------------- |
| Printer not found after boot | Check `systemctl status usbip-canon`; the watchdog retries automatically once the router/network is ready |
| "Filter failed" error       | Wrong PPD. Ensure `canong1030.ppd` is used, not Gutenprint                                    |
| PPD not found after install | G1831 is listed as G1030 series. Search: `lpinfo -m \| grep -i g1030`                        |
| Prints only halfway         | Do NOT use `socket://router:9100`. The IVEC protocol stalls through p910nd. Use USB/IP       |
| Two printers on AirPrint    | Delete `/etc/avahi/services/CanonG1831.service` -- CUPS handles discovery via DNS-SD           |
| "Forbidden" on web UI       | Add `Allow @LOCAL` in `<Location />` blocks in cupsd.conf                                     |
| Only listens on localhost   | Change `Listen localhost:631` to `Port 631` in cupsd.conf                                     |
| Browser can't open :631     | Browser forcing HTTPS. Use incognito window or try `curl http://<ip>:631` to confirm it works |
| Duplex option missing       | G1831 has no duplexer and `cnijfilter2` fails on duplex commands. Manual two-sided: print odd pages, flip, print even |
| USB/IP link drops           | Check router: `/usr/sbin/usbip list -l` should show printer bound. Re-bind if needed         |
| PPD/filters gone after update | `lpinfo -m \| grep canong1030` returns nothing → `sudo apt install --reinstall cnijfilter2-*` then restart CUPS |

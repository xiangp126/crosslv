#!/bin/sh
# netmon snapshot — dump full router/network state for diagnosing client outages.
# Usage: snapshot.sh <reason>   (called by monitor.sh and capture-now)
BASE=/root/netmon
SNAP=$BASE/snapshots
RING=/tmp/netmon/heartbeat.ring
GW=192.168.1.1
T1=223.5.5.5
T2=1.1.1.1
DOMAIN=www.apple.com
REASON=${1:-manual}
BOOTID=$(cut -c1-8 /proc/sys/kernel/random/boot_id 2>/dev/null)
mkdir -p "$SNAP"
TS=$(date "+%m%d-%H%M%S")
f="$SNAP/snap-${BOOTID}-${TS}-${REASON}.txt"
png() { ping -c1 -W2 "$1" >/dev/null 2>&1 && echo ok || echo FAIL; }
{
  echo "##### NETMON SNAPSHOT  reason=$REASON  $(date '+%F %T')  boot=$BOOTID  uptime=$(cut -d' ' -f1 /proc/uptime)s #####"
  echo
  echo "## PROBE MATRIX"
  echo "gateway  $GW : $(png $GW)"
  echo "internet $T1: $(png $T1)"
  echo "internet $T2: $(png $T2)"
  echo -n "DNS via local dnsmasq ($DOMAIN): "; nslookup "$DOMAIN" 127.0.0.1 >/dev/null 2>&1 && echo ok || echo FAIL
  echo
  echo "## RECENT HEARTBEAT (timeline leading up to this) ----------------"
  tail -n 80 "$RING" 2>/dev/null
  echo
  echo "## DNS CHAIN -----------------------------------------------------"
  echo "# via local dnsmasq 127.0.0.1:"; nslookup "$DOMAIN" 127.0.0.1 2>&1 | tail -6
  echo "# via direct upstream $GW:";     nslookup "$DOMAIN" "$GW"    2>&1 | tail -6
  echo
  echo "## ROUTING / WAN -------------------------------------------------"
  ip route
  echo "-- ifstatus wan --"; ifstatus wan 2>/dev/null | grep -iE '"up"|uptime|address|nexthop|proto|dns'
  echo "-- ip neigh --"; ip neigh
  echo
  echo "## DATAPATH / OFFLOAD --------------------------------------------"
  echo "conntrack_count = $(cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null)"
  echo "offloaded_flows = $(grep -c OFFLOAD /proc/net/nf_conntrack 2>/dev/null)"
  echo "-- nft flowtable / offload --"; nft list table inet fw4 2>/dev/null | grep -iE 'flowtable|offload'
  echo "-- nft tables --"; nft list tables 2>/dev/null
  echo "-- eth1(WAN) link --"; printf 'speed=%sMbps duplex=%s carrier=%s carrier_changes=%s\n' "$(cat /sys/class/net/eth1/speed 2>/dev/null)" "$(cat /sys/class/net/eth1/duplex 2>/dev/null)" "$(cat /sys/class/net/eth1/carrier 2>/dev/null)" "$(cat /sys/class/net/eth1/carrier_changes 2>/dev/null)"
  echo "-- eth1(WAN) bytes --"; printf 'rx=%s tx=%s\n' "$(cat /sys/class/net/eth1/statistics/rx_bytes 2>/dev/null)" "$(cat /sys/class/net/eth1/statistics/tx_bytes 2>/dev/null)"
  echo "-- br-lan bytes --";    printf 'rx=%s tx=%s\n' "$(cat /sys/class/net/br-lan/statistics/rx_bytes 2>/dev/null)" "$(cat /sys/class/net/br-lan/statistics/tx_bytes 2>/dev/null)"
  echo "-- WED debug (if present) --"; for x in /sys/kernel/debug/mtk_wed/0/*; do [ -r "$x" ] && echo "# $x" && head -c 400 "$x" 2>/dev/null && echo; done 2>/dev/null
  echo
  echo "## PASSWALL / DNS PROCS ------------------------------------------"
  ps w | grep -iE 'sing-box|chinadns|dns2socks|dnsmasq|passwall|monitor.sh' | grep -v grep
  echo "passwall enabled = $(uci -q get passwall.@global[0].enabled)"
  echo
  echo "## SYSTEM --------------------------------------------------------"
  free -m | grep -iE 'Mem|Swap'
  echo "load = $(cut -d' ' -f1-3 /proc/loadavg)"
  echo
  echo "## KERNEL LOG (dmesg tail — WED/mt76/offload/oom errors) ---------"
  dmesg | tail -n 80
} > "$f" 2>&1
ls -1t "$SNAP"/snap-*.txt 2>/dev/null | tail -n +26 | while read old; do rm -f "$old"; done
logger -t netmon "snapshot captured ($REASON) -> $f"
echo "$f"

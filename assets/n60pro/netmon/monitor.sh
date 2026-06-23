#!/bin/sh
# netmon watchdog — RAM heartbeat ring + auto-snapshot on connectivity transitions.
# Evidence persists in /root/netmon (survives the reboot you use to recover).
# TEMPORARY diagnostic. Remove with:
#   /etc/init.d/netmon disable; /etc/init.d/netmon stop; rm -rf /root/netmon /etc/init.d/netmon
BASE=/root/netmon
RING=/tmp/netmon/heartbeat.ring
ARCHIVE=$BASE/heartbeat.log
RINGMAX=240
INTERVAL=30
FLUSH_EVERY=60
GW=192.168.1.1
T1=223.5.5.5
T2=1.1.1.1
DOMAIN=www.apple.com
WAN=eth1
mkdir -p /tmp/netmon "$BASE/snapshots"
LAST=INIT
LASTSP=""
beat=0
pf() { ping -c1 -W2 "$1" >/dev/null 2>&1 && echo 0 || echo 1; }
logger -t netmon "watchdog started interval=${INTERVAL}s"
while :; do
  g=$(pf "$GW"); a=$(pf "$T1"); b=$(pf "$T2")
  if nslookup "$DOMAIN" 127.0.0.1 >/dev/null 2>&1; then d=0; else d=1; fi
  rx=$(cat /sys/class/net/$WAN/statistics/rx_bytes 2>/dev/null)
  tx=$(cat /sys/class/net/$WAN/statistics/tx_bytes 2>/dev/null)
  sp=$(cat /sys/class/net/$WAN/speed 2>/dev/null)
  cc=$(cat /sys/class/net/$WAN/carrier_changes 2>/dev/null)
  ct=$(cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null)
  if [ "$g" = 1 ] && [ "$a" = 1 ] && [ "$b" = 1 ]; then st=BAD; why=WAN_DOWN
  elif [ "$a" = 1 ] && [ "$b" = 1 ]; then st=BAD; why=INTERNET_UNREACH
  elif [ "$d" = 1 ]; then st=BAD; why=DNS_FAIL
  else st=OK; why=-
  fi
  echo "$(date '+%F %T') $st $why g=$g a=$a b=$b dns=$d sp=${sp}M cc=$cc ct=$ct rx=$rx tx=$tx" >> "$RING"
  tail -n "$RINGMAX" "$RING" > "$RING.t" 2>/dev/null && mv "$RING.t" "$RING"
  # WAN link speed change -> snapshot (catches 2.5G/1G/100M renegotiation = physical/EMI signature)
  if [ -n "$LASTSP" ] && [ "$sp" != "$LASTSP" ]; then
    logger -t netmon "WAN speed change $LASTSP -> $sp Mbps"
    /bin/sh "$BASE/snapshot.sh" "wanspeed_${LASTSP}to${sp}" >/dev/null 2>&1
  fi
  LASTSP=$sp
  [ -f "$BASE/CAPTURE" ] && { rm -f "$BASE/CAPTURE"; /bin/sh "$BASE/snapshot.sh" manual >/dev/null 2>&1; }
  if [ "$st" = BAD ] && [ "$LAST" != BAD ]; then /bin/sh "$BASE/snapshot.sh" "down_${why}" >/dev/null 2>&1; fi
  if [ "$st" = OK ]  && [ "$LAST" = BAD ];  then /bin/sh "$BASE/snapshot.sh" recovered    >/dev/null 2>&1; fi
  LAST=$st
  beat=$((beat+1))
  [ $((beat % FLUSH_EVERY)) = 0 ] && cp "$RING" "$ARCHIVE" 2>/dev/null
  sleep "$INTERVAL"
done

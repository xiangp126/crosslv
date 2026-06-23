#!/bin/sh
# Safely lock WAN (eth1) to 1000baseT/Full. If it cannot reach 1G within ~25s,
# revert to normal 10/100/1000 autoneg so the WAN is NEVER stranded down.
WAN=eth1
ethtool -s $WAN autoneg on advertise 0x020
logger -t wan-lock "set $WAN advertise=1000baseT/Full-only, verifying..."
i=0
while [ $i -lt 6 ]; do
  sleep 4
  [ "$(cat /sys/class/net/$WAN/carrier 2>/dev/null)" = 1 ] && \
  [ "$(cat /sys/class/net/$WAN/speed   2>/dev/null)" = 1000 ] && {
    logger -t wan-lock "OK $WAN up at 1000M"; echo "RESULT=LOCKED_1000M"; exit 0; }
  i=$((i+1))
done
ethtool -s $WAN autoneg on advertise 0x02f
logger -t wan-lock "WARN $WAN could not reach 1000M in 25s; reverted to autoneg (10/100/1000)."
echo "RESULT=REVERTED_LINK_MARGINAL"; exit 1

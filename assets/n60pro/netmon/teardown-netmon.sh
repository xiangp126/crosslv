#!/bin/sh
# ============================================================================
# One-click teardown of ALL diagnostic config from the WAN-outage investigation:
#   (A) WAN 1000M lock   (B) netmon watchdog
# Run ONLY when the WAN link is permanently healthy and none of it is needed.
# Manual equivalent documented in:
#   ~/myGit/crosslv/assets/n60pro/client-outage-runbook.md  (section 五)
# ============================================================================
echo "[teardown] A) removing WAN 1000M lock..."
rm -f /etc/hotplug.d/iface/99-wan-lock-1000
rm -f /root/wan-lock.sh
rm -f /tmp/wan_lock_done

echo "[teardown] B) stopping + removing netmon watchdog..."
/etc/init.d/netmon disable 2>/dev/null
/etc/init.d/netmon stop    2>/dev/null
rm -f  /etc/init.d/netmon
rm -rf /root/netmon /tmp/netmon

echo "[teardown] DONE:"
echo "   - netmon fully removed (service + scripts + snapshots)."
echo "   - WAN lock removed for future boots."
echo "   - The currently-live 1000M-only advertise clears on next reboot."
echo "     To restore full autoneg NOW instead (causes ~10s WAN blink):"
echo "       ethtool -s eth1 autoneg on advertise 0x02f"
echo "[teardown] removing this script."
rm -f /root/teardown-netmon.sh

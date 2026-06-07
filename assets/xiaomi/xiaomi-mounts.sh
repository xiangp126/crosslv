#!/bin/sh
# Mount wrt1200ac's two camera shares read-only on wrt32x. Idempotent;
# recovers from a wrt1200ac reboot (stale mount -> umount -l + remount).
# NOTE: minimal opts on purpose — iocharset=utf8 needs kmod-nls-utf8 (absent here)
# and filenames are pure ASCII, so it is not needed.
# Deployed on wrt32x as /usr/local/bin/xiaomi-mounts.sh (see deploy doc §6).
set -u
PEER=192.168.10.100
CRED=/etc/xiaomi-playback.cred
VERS=3.0                       # if mount fails, try 2.1 then 1.0
. "$CRED"                      # provides SMBUSER + SMBPASS

is_mounted() { grep -q " $1 cifs " /proc/mounts; }

mount_one() {
  share="$1"; mp="$2"
  mkdir -p "$mp"
  if is_mounted "$mp" && ls "$mp" >/dev/null 2>&1; then return 0; fi
  is_mounted "$mp" && umount -l "$mp" 2>/dev/null
  if mount -t cifs "//$PEER/$share" "$mp" -o "ro,user=$SMBUSER,pass=$SMBPASS,vers=$VERS"; then
    logger -t xiaomi-mounts "mounted $share -> $mp"
  else
    logger -t xiaomi-mounts "FAILED $share -> $mp (try VERS=2.1 or 1.0)"
  fi
}

mount_one c700_03 /mnt/c700_03
mount_one c700_04 /mnt/c700_04

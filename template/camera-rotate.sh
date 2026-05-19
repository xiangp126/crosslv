#!/bin/sh
# camera-rotate.sh
#
# Auto-rotation for SMB camera recordings on an OpenWrt/ImmortalWrt NAS.
# Deletes oldest .mp4 chunks once a partition crosses HIGH%, until back below LOW%.
# Uses hysteresis so the cron tick doesn't churn-delete one file at a time.
#
# Install (on the NAS):
#   1.  Save as /usr/local/bin/camera-rotate.sh and chmod +x.
#   2.  Add to /etc/crontabs/root:
#         17 * * * * /usr/local/bin/camera-rotate.sh
#   3.  /etc/init.d/cron enable && /etc/init.d/cron restart
#
# Verify:
#   /usr/local/bin/camera-rotate.sh        # manual run
#   logread | grep camera-rotate | tail    # check what it did
#
# Tunables:
#   HIGH=90 / LOW=85  -> ~5% hysteresis. Tighten for a closer cap (e.g. 85/82).
#
# Notes:
#   - Filename-sort is chronological (chunks are named 00_YYYYMMDDhhmmss_*.mp4).
#   - head -n -2 keeps the newest 2 files so the in-progress and just-finalized
#     chunk are never deleted under the camera.
#   - Add more "<mount> <dir>" lines to PAIRS as cameras 3 & 4 come online.

HIGH=90
LOW=85
TAG=camera-rotate

# <mount>  <camera-recording-dir>
PAIRS="
/mnt/sda1 /mnt/sda1/XiaomiCamera_00_B88880974A38
/mnt/sda2 /mnt/sda2/XiaomiCamera_00_B88880A0FD7C
"

log()      { logger -t "$TAG" "$1"; }
used_pct() { df "$1" | awk 'NR==2 {gsub(/%/,"",$5); print $5}'; }

echo "$PAIRS" | grep -v '^$' | while read mount dir; do
  [ -z "$mount" ] && continue
  [ -d "$dir"  ] || { log "missing dir $dir"; continue; }

  u=$(used_pct "$mount")
  [ -z "$u"          ] && { log "no df for $mount"; continue; }
  [ "$u" -lt "$HIGH" ] && continue

  log "$mount at ${u}% - rotating $dir down to <${LOW}%"

  ls -1 "$dir"/00_*_*.mp4 2>/dev/null | sort | head -n -2 | while read f; do
    cur=$(used_pct "$mount")
    [ "$cur" -lt "$LOW" ] && break
    rm -f "$f"
  done

  log "$mount now at $(used_pct "$mount")% after rotation"
done

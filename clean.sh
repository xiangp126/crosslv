#!/bin/bash
# Git clean filter: real secret values -> placeholders.
# Runs on `git add` (i.e. before every commit/push), so real secrets can never
# enter a commit and therefore never get pushed.
#
# Field-based and UNCONDITIONAL: it scrubs by JSON key name and does NOT depend on
# secrets.conf existing. The previous version substituted value->key only when a
# secrets.conf was present, so on any machine without secrets.conf it silently did
# nothing and leaked real values into commits. This version always scrubs.
#
# Placeholder names match secrets.conf(.example) so smudge.sh can restore them on
# checkout. The filter is idempotent: scrubbing already-placeholdered content is a
# no-op, which keeps `git status` clean (clean(working) always equals the stored blob).
#
# $1 = %f, the repo-relative path of the file being filtered.
content=$(cat)
file="$1"

# scrub <json_key> <placeholder>: replace the string value of "json_key" with the
# placeholder, leaving the key and JSON structure intact. Works for any value
# (uuid, base64 keys, etc.) since the old value is matched as [^"]* and discarded.
scrub() {
    content=$(printf '%s' "$content" \
        | sed -E "s/(\"$1\"[[:space:]]*:[[:space:]]*\")[^\"]*(\")/\1$2\2/g")
}

case "$file" in
    *wireguard*)
        scrub private_key    WG_PRIVATE_KEY
        scrub public_key     WG_PUBLIC_KEY
        scrub pre_shared_key WG_PRESHARED_KEY
        ;;
    *xray*)
        scrub uuid       XRAY_UUID
        scrub public_key XRAY_PUBLIC_KEY
        scrub short_id   XRAY_SHORT_ID
        ;;
esac

printf '%s\n' "$content"

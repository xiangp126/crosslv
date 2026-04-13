#!/bin/bash
# Git smudge filter: placeholders -> real values (on checkout)
SECRETS_FILE="$(git rev-parse --show-toplevel)/assets/sing-box/secrets.conf"
content=$(cat)
if [[ -f "$SECRETS_FILE" ]]; then
    while IFS='=' read -r key value; do
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        content="${content//$key/$value}"
    done < "$SECRETS_FILE"
fi
printf '%s\n' "$content"

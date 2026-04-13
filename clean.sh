#!/bin/bash
# Git clean filter: real values -> placeholders (on commit)
SECRETS_FILE="$(git rev-parse --show-toplevel)/assets/sing-box/secrets.conf"
content=$(cat)
if [[ -f "$SECRETS_FILE" ]]; then
    while IFS='=' read -r key value; do
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        content="${content//$value/$key}"
    done < "$SECRETS_FILE"
fi
printf '%s\n' "$content"

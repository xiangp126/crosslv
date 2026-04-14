#!/bin/bash
# Git smudge filter: placeholders -> real values (on checkout)
# Finds secrets.conf in the same directory as the file being filtered.
REPO_ROOT="$(git rev-parse --show-toplevel)"
SECRETS_FILE="$REPO_ROOT/$(dirname "$1")/secrets.conf"
content=$(cat)
if [[ -f "$SECRETS_FILE" ]]; then
    while IFS= read -r line; do
        [[ -z "$line" || "$line" =~ ^# ]] && continue
        key="${line%%=*}"
        value="${line#*=}"
        content="${content//$key/$value}"
    done < "$SECRETS_FILE"
fi
printf '%s\n' "$content"

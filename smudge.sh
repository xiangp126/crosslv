#!/bin/bash
# Git smudge filter: intentionally a NO-OP (identity pass-through).
#
# Design choice: the real secret values live ONLY in the working-tree config
# files (edited directly, e.g. by hand or an assistant). We deliberately do NOT
# restore them from a secrets.conf on checkout, because a stale secrets.conf
# would silently overwrite freshly-edited real values with old ones.
#
# clean.sh still scrubs values -> placeholders on `git add`, so nothing
# sensitive is ever committed or pushed. The two filters are decoupled:
#   - clean  : working tree -> index   (real value  -> placeholder)  ALWAYS
#   - smudge : index -> working tree   (identity, no restore)
#
# Consequence: a fresh clone / `git checkout -- <file>` / `git reset --hard`
# yields placeholder values that must be re-filled by hand. The working tree is
# the single source of truth for secrets; keep a backup elsewhere (the server's
# own config is the canonical copy).
exec cat

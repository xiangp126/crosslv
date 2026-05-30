# jp-gemini-dev: make `pexiang` sudo passwordless (including `sudo -v`)

## Problem

On `jp-gemini-dev`, `pexiang` was prompted for a password on every `sudo` invocation — including `jc --sslh`'s `sslhSudoWarmup` step (`sudo -v`). `/etc/sudoers.d/pexiang` already contained `pexiang ALL=(ALL) NOPASSWD:ALL` (created 2026-04-05) but it had no effect: the file was inert.

## Root cause (two layers)

1. **LDAP/SSSD shadows the local file.** The host is joined to NVIDIA's AD via SSSD. SSSD publishes a sudoers rule `pexiang ALL=(ALL) ALL` from the role `jp-gemini-dev-superuser` — **no NOPASSWD**. `/etc/nsswitch.conf` had `sudoers: files sss`, which means local files are consulted first, then SSSD. Combined with sudo's **last-matching-rule-wins** semantics: the SSSD rule (no NOPASSWD) was the last match → password required.

2. **`sudo -v` has stricter evaluation than `sudo command`.** Even after fixing layer 1, `sudo -v` still prompted. `sudo -v` ("validate cached credentials") doesn't follow last-match-wins; it asks "would *any* applicable rule require auth?" — and since one of the matching rules (the SSSD one) lacks NOPASSWD, the answer was yes → password required. The journal showed this exactly:
   ```
   sudo[...]:  pexiang : COMMAND=/usr/bin/whoami            ← passwordless (works)
   sudo[...]:  pexiang : a password is required ; COMMAND=validate   ← sudo -v (fails)
   ```

## Fix (two layered changes on jp-gemini-dev, both reversible)

### A. Flip sudoers source order in `/etc/nsswitch.conf`

```
-sudoers:        files sss
+sudoers:        sss files
```

Puts SSSD-supplied rules **first**, local files **last**. With last-match-wins, the local `pexiang ALL=(ALL) NOPASSWD:ALL` then beats the SSSD rule for regular `sudo command`. Fixes layer 1.

Backup on VPS: `/etc/nsswitch.conf.bak.20260530-234713`
Revert: `cp -a /etc/nsswitch.conf.bak.20260530-234713 /etc/nsswitch.conf`

### B. Add a Defaults-layer override in `/etc/sudoers.d/pexiang`

Final file contents (mode 0440, root:root):
```
Defaults:pexiang !authenticate
pexiang ALL=(ALL) NOPASSWD:ALL
```

The `Defaults:pexiang !authenticate` line operates at sudo's Defaults layer, which sits *above* per-rule matching. It means "for user pexiang, never authenticate, regardless of which rule matches." This sidesteps the dual-source `sudo -v` problem because `sudo -v` also consults Defaults. Fixes layer 2.

Backup on VPS: `/etc/sudoers.d/pexiang.bak.20260530-235245`
Revert: `install -o root -g root -m 0440 /etc/sudoers.d/pexiang.bak.20260530-235245 /etc/sudoers.d/pexiang`

## Verification

Run on jp as root, then via `runuser -u pexiang`:

| Test | Expected rc |
|---|---|
| `runuser -u pexiang -- sudo -nk whoami` | 0 (no prompt) |
| `runuser -u pexiang -- sudo -nv` | 0 (no prompt) ← **the jc warmup path** |
| `runuser -u pexiang -- sudo -nl` | 0 (no prompt) |
| `visudo -c -f /etc/sudoers.d/pexiang` | "parsed OK" |
| `sudo -l -U pexiang` shows `Defaults:` line with `!authenticate` | yes |

All confirmed at change time (2026-05-30 23:52 UTC+8).

## How to re-apply if reverted

Run as root on jp:

```bash
# A. nsswitch flip
sed -i -E 's/^([[:space:]]*sudoers:[[:space:]]*)files([[:space:]]+)sss([[:space:]]*)$/\1sss\2files\3/' /etc/nsswitch.conf
grep ^sudoers /etc/nsswitch.conf    # expect: sudoers:        sss files

# B. sudoers.d/pexiang with Defaults override
cat > /tmp/pexiang.sudo <<'EOF'
Defaults:pexiang !authenticate
pexiang ALL=(ALL) NOPASSWD:ALL
EOF
visudo -cf /tmp/pexiang.sudo && install -o root -g root -m 0440 /tmp/pexiang.sudo /etc/sudoers.d/pexiang
rm /tmp/pexiang.sudo

# verify
runuser -u pexiang -- sudo -nv && echo "OK passwordless"
```

## Drift risk

`salt-minion.service` is active on jp. If NVIDIA's Salt master has states defining `/etc/sudoers.d/pexiang` or `/etc/nsswitch.conf`, either change can be reverted on its next state run (~30-60 min). Symptom: sudo prompts come back without you touching anything. If recurring, wrap the two writes above in a oneshot systemd unit + path watcher (or a timer triggered every 30 min) so the fix self-heals.

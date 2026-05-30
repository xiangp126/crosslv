# Deploy `sslh` on the VPS to multiplex SSH + VLESS/REALITY on port 22

A reusable plan to put **`sslh`** in front of port 22 on the VPS so that a
single externally-reachable port carries both ordinary SSH logins **and** the
VLESS+REALITY proxy stream (xray on `127.0.0.1:5902`). This replaces the old
autossh-tunnel architecture, eliminating TCP-over-TCP and double encryption.

Companion client config: **`../assets/xray/sing-box-config.jsonc`** — already
updated to dial `10.6.10.221:22` directly. Once this plan is applied to the
VPS, that file works as-is and `sing-box-config-autossh.jsonc` + autossh on
the laptop can be retired.

---

## 0. Quick path — `jc --sslh` (recommended)

For the common case (Debian/Ubuntu VPS with xray already installed on
`127.0.0.1:5902`), the entire deploy is automated by the `jc` script:

```sh
# On the VPS, inside a tmux session (required — sshd restart drops your shell):
tmux new -s sslh 'jc --sslh'

# Re-attach from a fresh SSH session after cutover:
tmux attach -t sslh

# Check status / view monitor history anytime:
jc --sslh-status
```

What `jc --sslh` does, mapped to the manual sections below:

| Manual section | Automated by |
|---|---|
| §3 Pre-flight checks | Preflight (refuses if Darwin / no apt-get / no tmux when run over SSH / xray unreachable warns) |
| §4 Install sslh        | Phase 1 (apt + binary autodetect: `sslh-ev` > `sslh-select` > `sslh-fork`; sets `cap_net_bind_service`) |
| §5 Move sshd off :22   | Phase 2 (write `/etc/ssh/sshd_config.d/10-sslh.conf` adding `ListenAddress 0.0.0.0:8822`) + Phase 4 (strip `:22` from main config) |
| §6 Configure and start sslh | Phase 3 (write `/etc/sslh.cfg` + DAEMON selector + Layer-3 `Restart=on-failure` drop-in) |
| §7 End-to-end verification  | Phase 3.5 sandbox test on `:22222` (verifies SSH demux before touching `:22`) + Phase 5 loopback verification |
| §8 Hardening (firewall)     | Phase 3.6 (`ufw allow 8822/tcp` / `firewall-cmd --add-port`) |
| Safety net                  | Phase 4 arms a **continuous health monitor** (systemd timer, every 10 min) that auto-rollback if sslh fails 3 consecutive checks |

The CLI also offers:

- `--sslh-ssh-port <port>` — change the internal sshd port (default 8822)
- `--sslh-xray-port <port>` — change the xray TLS backend port (default 5902)
- `--sslh-status` — show current deployment status: port topology, monitor state, recent health checks
- `--sslh-rollback` — manual emergency revert. Stops sslh, restores sshd on :22, keeps the sslh package and configs intact for fast re-deploy via `jc --sslh`.
- `--sslh-remove` — full teardown: stop sslh, restore sshd:22, apt purge package

The manual sections below (§3-§7) remain documented for reference and for
non-Debian distros where `jc --sslh` doesn't apply. The teardown path (§10)
also has a one-command equivalent: `jc --sslh-remove`.

---

## 1. Goal

After the plan:

- Port 22 is the only externally exposed port on the VPS (typical constraint).
- `sslh` listens on `0.0.0.0:22`, inspects the first bytes of every new
  connection, then internally splices it to one of two backends:
  - SSH (banner `SSH-2.0-...`) → `127.0.0.1:8822` (sshd)
  - TLS (`0x16 0x03 0x0?` ClientHello) → `127.0.0.1:5902` (xray VLESS+REALITY)
- sshd ALSO listens on `0.0.0.0:8822` as a **defense-in-depth direct-sshd
  bypass** — reachable if you've opened :8822 at the VPS firewall (the
  automated path opens it in local ufw/firewalld; the provider's outer ACL
  is up to you).
- `ssh user@vps` (still targeting port 22) continues to work, no client-side
  change needed.
- Sing-box on the laptop dials `vps:22` with VLESS+REALITY directly, no SSH
  wrapping. End-to-end TLS, one layer of encryption, ~95% of native VLESS
  throughput.
- A continuous systemd health monitor (armed by `jc --sslh`, lives in
  `/etc/systemd/system/jc-sslh-monitor.{service,timer}`, survives reboot)
  actively checks sslh's :22 every 10 min; 3 consecutive failures (~30 min)
  auto-rollback to plain sshd:22.
- A documented **teardown** path exists (`jc --sslh-remove` or §10 manual
  steps) to revert to plain sshd on 22 + xray-on-localhost.

---

## 2. Assumptions about the target system

- Debian 11/12 or Ubuntu 20.04/22.04/24.04 with `systemd`.
- Root or `sudo` access via SSH.
- `xray-core` already installed and running, with a VLESS+REALITY inbound on
  `127.0.0.1:5902` (or the section below installs/configures one).
- The VPS provider's outer network ACL allows inbound TCP/22 only — this is
  the constraint that motivates the entire design.
- IPv4 single-stack assumed; if IPv6 is in play, every `listen` line below
  needs a parallel `[::]:port` entry, noted inline.
- VPS hostname / IP referenced as `<VPS>`; the public REALITY fingerprint
  target is `www.nvidia.com` (matches client config).

---

## 3. Pre-flight checks (run before changing anything)

### 3.1 Confirm current sshd config and port

```sh
ssh root@<VPS> 'sshd -T 2>/dev/null | grep -E "^(port|listenaddress) " ; ss -tlnp | grep -E ":(22|5902|8822) "'
```

Expected baseline: `port 22`, `listenaddress 0.0.0.0:22` and `[::]:22`, and
something listening on `:5902` (xray). Anything on `:8822` already is a
conflict — pick a different internal port and substitute throughout.

### 3.2 Confirm xray is healthy and reachable from localhost

```sh
ssh root@<VPS> '
  systemctl is-active xray ;
  ss -tlnp | grep 5902 ;
  curl --max-time 3 -sk https://127.0.0.1:5902/ -o /dev/null -w "%{http_code}\n" || true
'
```

`curl` returning `400` or a TLS error is **fine** — it means xray accepted
the TCP connection and tried to TLS-handshake. A connection refused or
timeout means xray isn't actually listening where you think.

### 3.3 Verify the REALITY config matches the client

```sh
ssh root@<VPS> 'jq ".inbounds[] | select(.port==5902) | .streamSettings.realitySettings | {dest, serverNames, shortIds, privateKey: \"<redacted>\"}" /usr/local/etc/xray/config.json'
```

Cross-check against the client (`../assets/xray/sing-box-config.jsonc`):

- `serverNames[0]` must equal client's `tls.server_name` (`www.nvidia.com`).
- `shortIds` array must contain the client's `tls.reality.short_id`
  (`3a050ce1`).
- The client's `tls.reality.public_key` is the *public* half of xray's
  `privateKey`. Compute on the server:
  `xray x25519 -i <privateKey>` → `Public key:` field should match.

Mismatches here will cause REALITY handshake failures **after** the cutover,
which look identical to sslh routing bugs. Fix them now.

### 3.4 Open an emergency back-channel BEFORE touching sshd

Open a second SSH session and **keep it open** for the entire cutover:

```sh
ssh -o ServerAliveInterval=30 root@<VPS>
# leave this terminal alone until the plan finishes successfully
```

If the primary session breaks during sshd restart, this one keeps you in.
Most VPS providers also offer a serial / web console (Hetzner Rescue,
DigitalOcean Recovery Console, Linode Lish, etc.) — locate it now, not at
3am when sshd won't start.

---

## 4. Install sslh

```sh
ssh root@<VPS> '
  apt-get update &&
  apt-get install -y sslh
'
```

Debian's `sslh` package ships **both** `sslh-fork` and `sslh-ev` binaries
under `/usr/sbin/` and a single `sslh.service` unit that reads
`/etc/default/sslh` to pick which one to run. We want `sslh-ev` (libev
event-loop, single process, low latency, fine for personal use; switch to
`sslh-fork` only if you see CPU pinning on a single core under sustained
load).

The package post-install enables the unit and tries to start it — it will
**fail to start** because nothing else has been configured yet. That's fine,
we fix it in §6.

---

## 5. Move sshd off port 22

The order matters. We add the new listen port *first*, restart sshd, verify
the new port works **from the emergency back-channel session**, then remove
the old listen on `:22` in a second step. Never do both in one restart.

### 5.1 Add the new internal listen address

```sh
ssh root@<VPS> '
  install -m 644 /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%Y%m%d-%H%M%S) &&
  printf "\n# sslh multiplex: internal listen, sslh forwards SSH banners here\nListenAddress 127.0.0.1:8822\n" >> /etc/ssh/sshd_config &&
  sshd -t && systemctl reload ssh
'
```

`sshd -t` validates the config; if it errors, **do not reload** — fix the
file and retry. `systemctl reload ssh` rereads config without dropping
existing sessions.

> Gotcha: some Debian/Ubuntu setups use `Include /etc/ssh/sshd_config.d/*.conf`.
> If you see settings inside that directory overriding what you added, drop a
> file `/etc/ssh/sshd_config.d/10-sslh.conf` with the same `ListenAddress`
> line instead of editing the main file.

### 5.2 Verify sshd is listening on both ports

```sh
ssh root@<VPS> 'ss -tlnp | grep -E ":(22|8822) "'
```

Expect two lines — one `:22`, one `127.0.0.1:8822`. Now from your **laptop**
test the new internal port via the still-working :22 session:

```sh
ssh -J root@<VPS> -p 8822 root@127.0.0.1 'echo "8822 reachable"'
```

If this prints `8822 reachable`, sshd-on-8822 works.

### 5.3 Remove the old `:22` listen

```sh
ssh root@<VPS> '
  sed -i.bak.removed22 -E "/^#?\s*Port\s+22\s*\$/d; /^#?\s*ListenAddress\s+0\.0\.0\.0(:22)?\s*\$/d; /^#?\s*ListenAddress\s+::(:22)?\s*\$/d" /etc/ssh/sshd_config &&
  sshd -t && systemctl restart ssh &&
  ss -tlnp | grep -E ":(22|8822) "
'
```

Expected output: **only** `127.0.0.1:8822` remains. `:22` is now free for
sslh.

**Verify your back-channel session is still alive** (it should be — restart
only drops new connections, existing ones persist). If it died, use the
serial console to revert `sshd_config` from the `.bak.*` files.

> Gotcha: on Ubuntu 22.04+ the service is `ssh.service` *and* there's a
> `ssh.socket` unit. If `ss` still shows `:22` after restart, run
> `systemctl disable --now ssh.socket` and restart `ssh.service`.

---

## 6. Configure and start sslh

### 6.1 Write the sslh config

```sh
ssh root@<VPS> 'cat >/etc/sslh.cfg <<'\''CFG'\''
verbose: 0;
foreground: false;
inetd: false;
numeric: true;
transparent: false;
timeout: 5;
user: "sslh";
pidfile: "/var/run/sslh.pid";

listen:
(
    { host: "0.0.0.0"; port: "22"; }
    // For IPv6 add: , { host: "[::]"; port: "22"; }
);

protocols:
(
    { name: "ssh";  host: "127.0.0.1"; port: "8822"; service: "ssh"; probe: "builtin"; },
    { name: "tls";  host: "127.0.0.1"; port: "5902"; probe: "builtin"; }
);
CFG'
```

Notes on the choices:

- `transparent: false` — sslh rewrites the source IP to its own. xray will
  see all clients as `127.0.0.1`. Acceptable for personal use; flip to
  `true` only if you need per-client IP visibility (requires extra
  iptables/`ip rule` setup, scope-creep for this plan).
- Order matters: `ssh` is listed first because its banner-based probe is
  cheap and definitive; `tls` is the fallback. SSH banners are sent by the
  *client* immediately, but the spec lets the server speak first — so sslh
  has a `timeout` (5s) to wait if it sees no bytes; after that it assumes
  TLS-from-server-first scenarios. Our case is always client-speaks-first,
  so 5s is conservative.
- `user: "sslh"` — Debian's package creates this unprivileged account. sslh
  binds :22 as root, then drops privileges. `CAP_NET_BIND_SERVICE` is set
  on the binary so the drop succeeds.

### 6.2 Tell the unit to use `sslh-ev`

```sh
ssh root@<VPS> '
  sed -i.bak -E "s|^DAEMON=.*|DAEMON=/usr/sbin/sslh-ev|" /etc/default/sslh &&
  grep ^DAEMON /etc/default/sslh
'
```

Older versions of the Debian package use `/etc/default/sslh` for legacy
key=value flags; modern ones (Debian 12+) ship a systemd drop-in that reads
the same file. Either way the `DAEMON` selector works.

### 6.3 Start sslh and check

```sh
ssh root@<VPS> '
  systemctl restart sslh &&
  systemctl status --no-pager sslh &&
  ss -tlnp | grep ":22 "
'
```

Expect `Active: active (running)` and `ss` showing `sslh-ev` (or `sslh`)
listening on `:22`.

---

## 7. End-to-end verification

### 7.1 SSH still works on :22

From your laptop (using a **fresh** terminal, not the emergency back-channel):

```sh
ssh -o ControlMaster=no -v root@<VPS> 'echo ssh-via-sslh ok' 2>&1 | tail -5
```

Look for `Authenticated to <VPS>` and the printed `ssh-via-sslh ok`. The
`-o ControlMaster=no` avoids reusing the back-channel's existing connection
so you actually exercise the new path.

### 7.2 REALITY handshake works on :22

```sh
curl --max-time 5 -sk --resolve www.nvidia.com:22:<VPS-IP> https://www.nvidia.com:22/ -o /dev/null -w "TLS code: %{http_code}\nSSL verify: %{ssl_verify_result}\n"
```

This forces curl to dial `<VPS>:22` while presenting SNI `www.nvidia.com` —
exactly what sing-box will do. A response (even an HTTP error code like
`400` or `403`) means the TLS handshake reached xray. A connection refused
/ TLS error / timeout means sslh isn't forwarding TLS, or xray isn't
responding — check `journalctl -u sslh -n 50` and `journalctl -u xray -n 50`.

### 7.3 Switch the laptop over

On the laptop, stop autossh and (re)load sing-box with the updated config:

```sh
# stop autossh — adapt to however you launched it:
launchctl unload ~/Library/LaunchAgents/com.user.autossh.plist 2>/dev/null || pkill -x autossh

# restart sing-box
sudo launchctl kickstart -k system/sh.sagernet.sing-box  # or your launchd label
```

Open a browser, hit `https://www.google.com` — should resolve and load via
the proxy. Check the Clash dashboard at `http://127.0.0.1:9090/ui` and
confirm connections show outbound `proxy` and the remote address is
`10.6.10.221:22`.

### 7.4 Smoke test: measure throughput

```sh
# from laptop, with proxy active
curl -o /dev/null -s -w "speed: %{speed_download} bytes/s\ntime: %{time_total}s\n" \
  https://speed.cloudflare.com/__down?bytes=104857600
```

Expect within 80-95% of the VPS uplink. If you see something dramatically
lower than the autossh setup got, investigate before declaring victory —
the usual suspect is `MTU` being too high (drop laptop sing-box `mtu` from
1400 → 1380 → 1360 and retest).

---

## 8. Hardening (do these once verification passes)

### 8.1 Lock down the VPS firewall to only :22 ingress

Even though the provider's outer ACL already enforces this, defense in
depth:

```sh
ssh root@<VPS> '
  ufw --force reset &&
  ufw default deny incoming &&
  ufw default allow outgoing &&
  ufw allow 22/tcp comment "sslh: SSH+REALITY mux" &&
  ufw --force enable &&
  ufw status verbose
'
```

If you use `nftables` directly instead of `ufw`, the equivalent is one
chain that only accepts `tcp dport 22` and established conns; everything
else drops.

### 8.2 Make sshd refuse password auth (it's the only thing on the public
side that has user-visible auth; REALITY is uuid-gated)

```sh
ssh root@<VPS> '
  sed -i -E "s|^#?PasswordAuthentication .*|PasswordAuthentication no|; s|^#?KbdInteractiveAuthentication .*|KbdInteractiveAuthentication no|" /etc/ssh/sshd_config &&
  sshd -t && systemctl reload ssh
'
```

Make sure you have a working SSH key first.

### 8.3 Enable sslh log rotation / quiet mode

`/etc/sslh.cfg` currently has `verbose: 0`. Leave it — sslh at verbose 0
only logs errors. If you set it higher for debugging, also add a logrotate
entry, otherwise `/var/log/syslog` grows fast under load.

---

## 9. Common failure modes and what to look for

| Symptom | Likely cause | Where to look |
|---|---|---|
| `ssh root@<VPS>` hangs after TCP connect | sslh started but sshd backend down | `systemctl status ssh`; `ss -tlnp \| grep 8822` |
| `ssh` works, REALITY fails ("TLS handshake error") | sslh routes TLS to wrong backend, or xray short_id/public_key mismatch | `journalctl -u sslh -n 100`; re-run §3.3 |
| Sing-box logs "REALITY: processed invalid connection" | client `short_id` not in server `shortIds` array | xray config |
| Everything works but slow | MTU mismatch on TUN; or xray on VPS pinned to one core | drop laptop `mtu`; `top` on VPS during transfer |
| sslh refuses to start, "address already in use" | sshd never released :22 | re-run §5.3, confirm `ss -tlnp \| grep :22` is empty before `systemctl start sslh` |
| sslh starts but immediately exits | bad config syntax | `sslh-ev -F /etc/sslh.cfg -v` in foreground for a real error message |

---

## 10. Teardown — revert to plain sshd:22 + autossh

Use this if sslh proves unreliable or you need to roll back fast. Order is
the inverse of setup. **Keep your emergency back-channel open** during the
teardown too.

### 10.0 Quick path: `jc --sslh-remove`

The full teardown (steps 10.1-10.6 below) is automated:

```sh
ssh root@<VPS>
tmux new -s sslh-remove 'jc --sslh-remove'
# Reconnect and re-attach if your session dropped during the sshd restart:
tmux attach -t sslh-remove
```

What it does, mirror-image of install:

1. Disable and remove the health monitor timer
2. Restore `Port 22` / `ListenAddress 0.0.0.0` / `ListenAddress ::` in
   sshd_config (idempotent — checks each line independently)
3. Stop and disable sslh
4. Restart sshd → reclaims `:22` (emergency-restore retry if it fails)
5. Remove the `/etc/ssh/sshd_config.d/10-sslh.conf` drop-in (kills :8822
   bypass) and reload sshd
6. `apt purge sslh` + clean up `/etc/sslh.cfg`, systemd drop-ins, and the
   `/etc/jc-sslh/` and `/var/lib/jc-sslh/` state directories
7. Timestamped `sshd_config.bak.sslh*` backups are **preserved** for
   forensics — delete manually when confident

The manual steps below remain for non-Debian distros or for understanding
what the automated path is doing under the hood.

### 10.1 Stop sslh

```sh
ssh -p 22 root@<VPS> '
  systemctl disable --now sslh &&
  ss -tlnp | grep ":22 " || echo "port 22 free"
'
```

After this, port 22 has no listener. SSH access is **broken from outside
until step 10.3**. Hence the back-channel.

### 10.2 (Optional) Remove sslh entirely

```sh
ssh root@<VPS> 'apt-get purge -y sslh && rm -f /etc/sslh.cfg'
```

Leave installed if you might want to re-enable later.

### 10.3 Restore sshd on :22

```sh
ssh root@<VPS> '
  # remove our internal-only listen
  sed -i -E "/^ListenAddress 127\.0\.0\.1:8822$/d" /etc/ssh/sshd_config &&
  # add back the public listen
  printf "\n# Restored after sslh teardown\nPort 22\nListenAddress 0.0.0.0\nListenAddress ::\n" >> /etc/ssh/sshd_config &&
  sshd -t && systemctl restart ssh &&
  ss -tlnp | grep ":22 "
'
```

Expect `sshd` on `0.0.0.0:22` and `[::]:22`. SSH from outside should now
work again on the standard port.

### 10.4 Decide what to do with xray on :5902

xray on `127.0.0.1:5902` is harmless when nothing forwards to it — it just
sits idle. Three options:

- **Keep it bound to localhost** (current state). Re-enabling sslh later is
  one `systemctl` away.
- **Expose it on a different public port** (e.g. 8443) and dial it
  directly from sing-box. Only useful if the VPS ACL lets you open another
  port — but if it did, you wouldn't have built sslh in the first place.
- **Re-enable autossh tunnel from the laptop.** Bring autossh back up, point
  it at `root@<VPS> -L 5902:127.0.0.1:5902`, and switch sing-box back to
  `sing-box-config-autossh.jsonc` (which dials `127.0.0.1:5902`).

### 10.5 Restore firewall to original

```sh
ssh root@<VPS> 'ufw --force reset && ufw --force enable && ufw allow 22/tcp && ufw status'
```

Adjust if the original baseline had other allowed ports.

### 10.6 Remove sshd-side artifacts

```sh
ssh root@<VPS> '
  ls -lt /etc/ssh/sshd_config.bak.* 2>/dev/null | head -5 ;
  ls -lt /etc/default/sslh.bak 2>/dev/null
'
```

Once you're confident the rollback is stable, delete the `.bak.*` files.

---

## 11. Post-cutover client cleanup (laptop side)

These steps happen on the laptop, not the VPS, but belong to the same
cutover so listing them here for completeness.

1. Confirm `assets/xray/sing-box-config.jsonc` dials `<VPS>:22` (already
   true as of this plan's companion edit).
2. Disable the autossh launchd job:

   ```sh
   launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.user.autossh.plist 2>/dev/null
   # then either delete the plist or leave it dormant
   ```

3. Optionally remove `route_exclude_address: ["10.6.10.221/32"]` from the
   sing-box TUN inbound. Sing-box auto-bypasses its own outbound traffic,
   so it's not needed; harmless to keep as a belt-and-suspenders measure.
4. Archive `sing-box-config-autossh.jsonc` (don't delete — it's the
   teardown fallback per §10.4 option 3).

---

## 12. Quick reference

| Component | Listen | Backend | Notes |
|---|---|---|---|
| sslh-ev | `0.0.0.0:22` | dispatches to below | only public-facing port |
| sshd | `127.0.0.1:8822` | — | SSH banner → sslh routes here |
| xray VLESS+REALITY | `127.0.0.1:5902` | — | TLS ClientHello (SNI `www.nvidia.com`) → sslh routes here |
| Client sing-box `proxy` outbound | dials `<VPS>:22` | — | sees end-to-end TLS, no SSH wrapping |

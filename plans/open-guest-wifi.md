# Guest Wi-Fi on the main gateway (192.168.10.1) — deployment plan + ops runbook

> **⚠️ DESIGN CHANGED 2026-06-01 — the passwall bypass was removed.** The guest
> network now rides passwall exactly like the `.10` LAN; `.20` is kept purely as
> an **isolated** subnet (own firewall zone, no `guest→lan`). Robust — nothing
> to maintain — at the cost of guests sharing whatever passwall does for the
> LAN. **Steps 6–8's bypass parts and the "Operations & recurrence runbook" are
> now SUPERSEDED**, kept only as history / a revert recipe. See the **Design
> change — 2026-06-01** section just below Context.
>
> Steps 1–5 (wireless/network/dhcp/firewall-zone) remain the current, valid
> deployment. The **Incident log** is retained as history.

## Context

The main router `n60pro-main` at `192.168.10.1` (ImmortalWrt 24.10.5,
mediatek/filogic, MT7986-class) currently runs a single SSID on each of its two
radios — `Gargoyle` (2.4 GHz / `wifinet1` / `radio0`) and `Gargoyle_5G`
(5 GHz / `wifinet3` / `radio1`). Both bridge directly into the `lan` zone
(`192.168.10.0/24`) which means any visitor we give the Wi-Fi password to gets
unrestricted access to the home LAN (Samba NAS, cameras, IoT, IPMI).

We want a **separate guest Wi-Fi**, broadcast on both bands, that:

- gives visitors normal internet access
- is **isolated from the home LAN** (no Samba, no cameras, no admin UIs)
- does **not** route through Passwall (visitors don't need the GFW-bypass tunnel
  and we don't want them sharing the proxy's bandwidth/quota)
- mirrors existing security style: **SAE-mixed (WPA3+WPA2)** with a fresh key
- uses a new subnet **192.168.20.0/24** (verified free — no collision with
  upstream WAN `192.168.1.0/24` or LAN `192.168.10.0/24`)

User decisions captured:

| Question | Choice |
|---|---|
| Passwall handling | **Bypass** — direct to WAN, no proxy/DNS hijack for guest |
| Encryption | **SAE-mixed** (WPA3+WPA2) with a separate, user-supplied password |
| SSID naming | Use **`GGargoyle`** prefix — mirror existing split-band style: `GGargoyle` on 2.4 GHz, `GGargoyle_5G` on 5 GHz |

Hardware verified-supported: both radios advertise `#{ AP, mesh point } <= 16`
in `iw phy info`, currently using 1 AP each — plenty of headroom for a second
BSS per radio.

---

## Design change — 2026-06-01 (part 2): guest = clone of lan, blocked only from .10

Dropping the bypass (part 1, below) left guests with **no usable internet** —
DNS and all foreign/GFW destinations failed; only direct China traffic worked.

**Root cause:** passwall does not proxy at the gateway edge — it
redirects/tproxies traffic to **router-local ports** (`:1041` proxy, `:11400`
DNS). After the redirect the destination is a local port, so the packet must
pass the zone's **input** chain. The `lan` zone is `input=ACCEPT` so it passes;
the guest zone was `input=REJECT` (only `udp/67` + `53` allowed), so the
redirected DNS (→`:11400`) and proxy (→`:1041`) traffic was dropped in
`reject_from_guest`. Direct China traffic worked because passwall `return`s it
un-redirected.

**Fix (current state):** make the guest zone **mirror lan**, with one carve-out:

```sh
uci set firewall.guest_zone.input='ACCEPT'      # was REJECT — this is the fix
uci set firewall.guest_zone.forward='ACCEPT'    # mirror lan
# the single exception — block guest -> .10 LAN:
uci add firewall rule; uci rename firewall.@rule[-1]='block_guest_to_lan'
uci set firewall.block_guest_to_lan.name='Block-guest-to-LAN'
uci set firewall.block_guest_to_lan.src='guest'
uci set firewall.block_guest_to_lan.dest='lan'
uci set firewall.block_guest_to_lan.proto='all'
uci set firewall.block_guest_to_lan.family='any'
uci set firewall.block_guest_to_lan.target='REJECT'
uci commit firewall; /etc/init.d/firewall reload
```

NAT needs nothing extra — the `wan` zone's `masq=1` masquerades guest→wan just
like lan→wan. Result: guest is handled identically to `.10` (same passwall
smart-DNS + selective proxy), and the only thing guests can't do is reach the
`.10` subnet (NAS/cameras).

> ⚠️ **Tradeoff:** `input=ACCEPT` means guests can also reach the router's own
> admin (LuCI :80/:443, SSH :8822) — same as any `.10` client. To deny guest
> admin while keeping internet, add targeted `src=guest` dport REJECTs for those
> ports — **do NOT** revert `input` to REJECT (that re-breaks passwall DNS/proxy).

---

## Design change — 2026-06-01 (part 1): drop the passwall bypass

After the bypass proved fragile (silently wiped on every passwall
restart/node-switch — see Incident log), the decision was reversed: **stop
bypassing passwall for guests; treat `.20` like `.10`.** Passwall here runs with
`tcp_proxy_mode=disable` / `udp_proxy_mode=disable` and DNS-redirect on, so for
clients it's mostly smart-DNS (chinadns-ng), not a full tunnel — the "guests
shouldn't share the proxy" concern that motivated the bypass is minor.

**What changed (partial rollback — only the bypass):**
- Stripped the 5 `iifname "br-guest" return` rules from `inet passwall`.
- Deleted `/usr/local/bin/guest-passwall-bypass.sh`,
  `/etc/hotplug.d/firewall/95-guest-passwall-bypass`, and the `/etc/rc.local`
  line.

**What stayed (current deployment = Steps 1–5):** SSIDs `GGargoyle` /
`GGargoyle_5G`, `br-guest` `192.168.20.1/24`, guest DHCP, and the **isolated**
`guest` firewall zone (no `guest→lan` forwarding). Visitors still cannot reach
the NAS / cameras / admin UIs.

**Result:** `.20` is handled identically to `.10` by passwall, inheriting the
LAN's proven-working behavior, with **no bypass to maintain** — the recurrence
problem is gone. Guests get chinadns-ng DNS and share the proxy only for
whatever the LAN proxies.

**To revert** (put guests back on a direct/bypassed path): re-deploy Steps 6–8
below (recreate the script + hotplug + rc.local line, then run the script).

---

## Recommended approach

Five UCI changes (wireless, network, dhcp, firewall) plus one custom nftables
include file to enforce the passwall bypass. All changes are idempotent and
fully reversible by deleting the named UCI sections / the include file.

The guest SSIDs default to `option isolate '1'` (AP-level client isolation:
visitors can't talk to each other on the air), giving an additional layer on
top of the firewall-zone isolation between guest and LAN.

### Files to modify on the gateway

| File | Change |
|---|---|
| `/etc/config/wireless` | **add** two `wifi-iface` stanzas (`guest_radio0`, `guest_radio1`) |
| `/etc/config/network`  | **add** `device 'br-guest'` (bridge) and `interface 'guest'` (192.168.20.1/24) |
| `/etc/config/dhcp`     | **add** `dhcp 'guest'` stanza |
| `/etc/config/firewall` | **add** zone `guest`, forwarding `guest→wan`, two `rule` stanzas (DHCP, DNS to router) |
| `/usr/local/bin/guest-passwall-bypass.sh` | **new file** — `nft insert rule` at head of each PSW_* chain in `inet passwall` table for `iifname "br-guest"` |
| `/etc/hotplug.d/firewall/95-guest-passwall-bypass` | **new file** — re-runs the bypass after `fw4 reload` |
| `/etc/rc.local` | **add one line** — `(sleep 30; /usr/local/bin/guest-passwall-bypass.sh) &` for boot-time apply |

No edits to passwall's own config — bypass is implemented as a fw4-level
override so a future passwall package upgrade or reconfiguration can't
silently re-include guest traffic.

### Implementation steps (run on gateway via `ssh -l root -p 8822 192.168.10.1`)

**Step 1 — Choose and stash the guest Wi-Fi password.**
Replace `<GUEST_KEY>` everywhere below with a fresh 12+ character string. Do
NOT reuse the existing LAN key `0290wF)@()`.

**Step 2 — `wireless`**: add two AP stanzas. Mirror the SAE-mixed / OCV style
of existing `wifinet1` / `wifinet3`.

```sh
uci batch <<'EOF'
add wireless wifi-iface
rename wireless.@wifi-iface[-1]='guest_radio0'
set wireless.guest_radio0.device='radio0'
set wireless.guest_radio0.mode='ap'
set wireless.guest_radio0.network='guest'
set wireless.guest_radio0.ssid='GGargoyle'
set wireless.guest_radio0.encryption='sae-mixed'
set wireless.guest_radio0.key='<GUEST_KEY>'
set wireless.guest_radio0.ocv='0'
set wireless.guest_radio0.isolate='1'

add wireless wifi-iface
rename wireless.@wifi-iface[-1]='guest_radio1'
set wireless.guest_radio1.device='radio1'
set wireless.guest_radio1.mode='ap'
set wireless.guest_radio1.network='guest'
set wireless.guest_radio1.ssid='GGargoyle_5G'
set wireless.guest_radio1.encryption='sae-mixed'
set wireless.guest_radio1.key='<GUEST_KEY>'
set wireless.guest_radio1.ocv='0'
set wireless.guest_radio1.isolate='1'
EOF
```

**Step 3 — `network`**: empty bridge + L3 interface for the guest network.

```sh
uci batch <<'EOF'
set network.br_guest='device'
set network.br_guest.name='br-guest'
set network.br_guest.type='bridge'

set network.guest='interface'
set network.guest.device='br-guest'
set network.guest.proto='static'
set network.guest.ipaddr='192.168.20.1'
set network.guest.netmask='255.255.255.0'
EOF
```

The two `wifi-iface`s reference `network='guest'`, so netifd will hot-add the
wlan AP interfaces to `br-guest` on bring-up — no `list ports` needed (we
intentionally don't bridge any physical switch port to the guest network).

**Step 4 — `dhcp`**: per-interface DHCP server. 12 h lease (mirrors LAN);
advertise router as DNS so dnsmasq answers them.

```sh
uci batch <<'EOF'
set dhcp.guest='dhcp'
set dhcp.guest.interface='guest'
set dhcp.guest.start='100'
set dhcp.guest.limit='150'
set dhcp.guest.leasetime='12h'
set dhcp.guest.dhcpv4='server'
add_list dhcp.guest.dhcp_option='6,192.168.20.1'
EOF
```

`/etc/config/dhcp` already has `option localservice '1'` globally, so dnsmasq
will accept queries on `br-guest` once the interface comes up — no additional
listen config needed.

**Step 5 — `firewall`**: new zone + forwarding + minimal input rules.

```sh
uci batch <<'EOF'
add firewall zone
rename firewall.@zone[-1]='guest_zone'
set firewall.guest_zone.name='guest'
set firewall.guest_zone.input='REJECT'
set firewall.guest_zone.output='ACCEPT'
set firewall.guest_zone.forward='REJECT'
add_list firewall.guest_zone.network='guest'

add firewall forwarding
rename firewall.@forwarding[-1]='guest_to_wan'
set firewall.guest_to_wan.src='guest'
set firewall.guest_to_wan.dest='wan'

add firewall rule
rename firewall.@rule[-1]='allow_guest_dhcp'
set firewall.allow_guest_dhcp.name='Allow-guest-DHCP'
set firewall.allow_guest_dhcp.src='guest'
set firewall.allow_guest_dhcp.proto='udp'
set firewall.allow_guest_dhcp.dest_port='67'
set firewall.allow_guest_dhcp.target='ACCEPT'

add firewall rule
rename firewall.@rule[-1]='allow_guest_dns'
set firewall.allow_guest_dns.name='Allow-guest-DNS'
set firewall.allow_guest_dns.src='guest'
set firewall.allow_guest_dns.dest_port='53'
set firewall.allow_guest_dns.target='ACCEPT'
EOF
# proto values with spaces ('tcp udp') get tokenised inside uci batch;
# set them with a separate quoted assignment after the batch:
uci set firewall.allow_guest_dns.proto="tcp udp"
```

Zone defaults (`forward=REJECT`, `input=REJECT`) plus no forwarding entry
`guest→lan` means **no guest can reach `192.168.10.0/24`** — Samba, cameras,
LuCI are all unreachable. The two `rule` stanzas punch only the holes needed
for DHCP and DNS *to the router itself*. No `guest→lan` forwarding is
declared, so visitors can't even ping LAN hosts.

> **⚠️ Steps 6–7 SUPERSEDED 2026-06-01** — the bypass was removed (see *Design
> change* above). The following is retained only as history and as the recipe to
> re-enable a guest passwall bypass if ever wanted.

**Step 6 — passwall bypass script.** ⚠ **Important correction discovered during
deployment:** passwall's `PSW_*` chains live in their own nft table
**`inet passwall`**, not in `inet fw4`. A static `/etc/nftables.d/*.nft`
include only feeds the `inet fw4` table, so we instead drop a small shell
script that uses `nft insert rule` to prepend a per-chain
`iifname "br-guest" return` short-circuit. Idempotent — duplicates pruned
before the insert.

Write `/usr/local/bin/guest-passwall-bypass.sh`:

```sh
#!/bin/sh
# Insert "iifname br-guest return" at the head of each PSW_* chain in the
# inet passwall table so passwall is a no-op for guest traffic.
TABLE="inet passwall"
for chain in PSW_DNS PSW_MANGLE PSW_NAT PSW_RULE PSW_MANGLE_V6; do
  nft list chain $TABLE "$chain" >/dev/null 2>&1 || continue
  for h in $(nft -a list chain $TABLE "$chain" 2>/dev/null \
              | awk '/iifname "br-guest".*return/ {print $NF}'); do
    nft delete rule $TABLE "$chain" handle "$h" 2>/dev/null || true
  done
  nft insert rule $TABLE "$chain" iifname "br-guest" counter return
done
logger -t guest-bypass "applied bypass to PSW chains in $TABLE"
```

`chmod +x /usr/local/bin/guest-passwall-bypass.sh`.

> Sanity-check before deploying: confirm chain names with
> `nft list table inet passwall | grep '^\s*chain PSW'`. Passwall may rename
> chains across versions.

**Step 7 — survive future reloads.** The `inet passwall` table is rebuilt by
`/etc/init.d/passwall restart` — at which point our bypass rules are gone.
Cover two pathways:

(a) **Hotplug on firewall reload** at `/etc/hotplug.d/firewall/95-guest-passwall-bypass`
— note this fires on `/etc/init.d/firewall reload`, **not** on a bare `fw4
reload` (see the Operations runbook below):

```sh
#!/bin/sh
# Re-apply guest passwall bypass after every fw4/firewall reload
/usr/local/bin/guest-passwall-bypass.sh
```

`chmod +x /etc/hotplug.d/firewall/95-guest-passwall-bypass`.

(b) **Boot-time apply** — append before `exit 0` in `/etc/rc.local`:

```sh
(sleep 30; /usr/local/bin/guest-passwall-bypass.sh) &
```

The 30-second sleep lets passwall fully initialize before we try to insert.

> **A manual passwall restart** (`/etc/init.d/passwall restart` / LuCI Passwall
> page) **and a bare `fw4 reload`** both do NOT fire the firewall hotplug, so
> after either, re-run `/usr/local/bin/guest-passwall-bypass.sh` manually (or
> wrap passwall's init.d to call it). See the Operations runbook below.

**Step 8 — commit & apply.**

```sh
uci commit wireless
uci commit network
uci commit dhcp
uci commit firewall

/etc/init.d/network reload      # brings up br-guest + 192.168.20.1
/etc/init.d/dnsmasq restart     # picks up new dhcp stanza
fw4 reload                      # applies zone (does NOT wipe inet passwall)
/usr/local/bin/guest-passwall-bypass.sh   # install bypass rules
```

> During `/etc/init.d/network reload` you may see harmless `udhcpc: no lease,
> failing` warnings from the WAN udhcpc client briefly retrying its lease
> renewal — verify WAN is still up with `ip -4 addr show eth1` and
> `ping -c1 192.168.1.1` afterwards; both should succeed.

---

## Verification

Run on the gateway:

```sh
# 1. New SSIDs exist and are up on both radios
iw dev | awk '/Interface|ssid/'
# expect: phy0-ap1 ssid GGargoyle, phy1-ap1 ssid GGargoyle_5G (or phy0-ap0/ap1 ordering)

# 2. br-guest exists, has 192.168.20.1, and the new wifi APs are bridged in
ip -4 addr show br-guest
bridge link show | grep br-guest    # if 'bridge' tool absent: ls /sys/class/net/br-guest/brif/

# 3. DHCP server is listening on br-guest
#    (busybox 'ss' prints nothing for unconnected UDP sockets — use netstat)
netstat -ulnp 2>/dev/null | grep ':67'
logread -e dnsmasq | tail -10

# 4. Firewall zone present
fw4 print | grep -A6 "zone 'guest'"
nft list chain inet fw4 forward_guest

# 5. Passwall bypass is in effect (rule at top of each PSW_* chain)
nft list chain inet passwall PSW_MANGLE | head -5
# expect line 3: iifname "br-guest" counter packets X bytes Y return
```

From a phone or laptop:

```
1. Connect to SSID GGargoyle or GGargoyle_5G with the chosen key.
2. Verify IP from 192.168.20.100-249, gateway 192.168.20.1, DNS 192.168.20.1.
3. ping 8.8.8.8                              -> works  (guest→wan accepted)
4. nslookup google.com                       -> works  (DNS to router accepted)
5. ping 192.168.10.225 (wrt32x)              -> times out  (zone isolation works)
6. curl http://192.168.10.1/                 -> rejected  (input=REJECT to router LAN IP from guest zone)
7. curl http://192.168.20.1/                 -> rejected  (input=REJECT on guest zone too)
8. From wired LAN: ping 192.168.20.x         -> times out  (no lan→guest forwarding)
```

> **Don't confuse cloud-relay app access with LAN access.** Tapo/Mi Home/etc.
> apps reach the cameras via TP-Link's cloud, not via the LAN. Seeing a
> camera feed in the app while connected to guest Wi-Fi is *not* a firewall
> failure — it would also work over cellular. The authoritative test is
> `ping 192.168.10.221` from a guest device (must time out) **or** checking
> conntrack on the gateway for guest→camera flows:
>
> ```sh
> # if isolation is intact, this returns NOTHING:
> cat /proc/net/nf_conntrack | grep "src=192\.168\.20\..* dst=192\.168\.10\."
> ```

Passwall-bypass effectiveness check from a guest client:

```sh
# (gateway side) drain counters
nft list chain inet passwall PSW_MANGLE | grep br-guest
# Then on guest device: open YouTube / google.com / etc.
# Re-check; the br-guest counter should grow (we’re hitting return), while
# the @passwall_gfw redirect counter further down should NOT grow for guest traffic.
```

---

## Complete uninstall / rollback

Removes everything this plan installs, in correct order: prune the running
nftables bypass rules first (so we don't leave orphan rules behind when the
script that maintains them is deleted), then delete UCI sections, then delete
on-disk files, then apply.

```sh
# 1. Strip the bypass rules currently sitting in inet passwall.
#    (Deleting the script alone leaves these inserted until next passwall reload.)
for chain in PSW_DNS PSW_MANGLE PSW_NAT PSW_RULE PSW_MANGLE_V6; do
  for h in $(nft -a list chain inet passwall "$chain" 2>/dev/null \
              | awk '/iifname "br-guest".*return/ {print $NF}'); do
    nft delete rule inet passwall "$chain" handle "$h"
  done
done

# 2. Undo every UCI section the plan added.
uci delete wireless.guest_radio0
uci delete wireless.guest_radio1
uci delete network.guest
uci delete network.br_guest
uci delete dhcp.guest
uci delete firewall.guest_zone
uci delete firewall.guest_to_wan
uci delete firewall.allow_guest_dhcp
uci delete firewall.allow_guest_dns
uci commit wireless
uci commit network
uci commit dhcp
uci commit firewall

# 3. Remove on-disk artefacts (script, hotplug hook, rc.local entry).
rm -f /usr/local/bin/guest-passwall-bypass.sh
rm -f /etc/hotplug.d/firewall/95-guest-passwall-bypass
sed -i '/guest-passwall-bypass/d' /etc/rc.local

# 4. Apply.
/etc/init.d/network reload
/etc/init.d/dnsmasq restart
fw4 reload
```

### Verify everything is gone

```sh
# SSIDs (only Gargoyle and Gargoyle_5G should remain)
iw dev | awk '/Interface|ssid/'

# br-guest interface must be absent
ip -4 addr show br-guest 2>&1 | head -2    # expect: "Device br-guest does not exist"

# UCI sections must be absent
for s in wireless.guest_radio0 wireless.guest_radio1 network.guest network.br_guest \
         dhcp.guest firewall.guest_zone firewall.guest_to_wan \
         firewall.allow_guest_dhcp firewall.allow_guest_dns; do
  uci -q show "$s" || echo "  $s: absent ✓"
done

# Files must be absent
ls /usr/local/bin/guest-passwall-bypass.sh /etc/hotplug.d/firewall/95-guest-passwall-bypass 2>&1

# rc.local must be clean
grep guest-passwall-bypass /etc/rc.local && echo "still present!" || echo "rc.local: clean"

# inet passwall chains must NOT have any iifname "br-guest" rule
for c in PSW_DNS PSW_MANGLE PSW_NAT PSW_RULE PSW_MANGLE_V6; do
  nft list chain inet passwall "$c" 2>/dev/null | grep -q "br-guest" \
    && echo "  $c: STILL HAS bypass rule" || echo "  $c: clean ✓"
done
```

### What is NOT removed (and shouldn't be)

- `/usr/local/bin/` directory — created during this plan; harmless to leave.
  Other plans (e.g. `camera-rotate.sh` on wrt32x) follow the same convention.
- Cron service (`/etc/init.d/cron`) — wasn't touched by this plan.
- Passwall itself, fw4 rules for the existing LAN/WAN zones, and the original
  `Gargoyle` / `Gargoyle_5G` SSIDs — all untouched.

---

## Operations & recurrence runbook

> **⚠️ SUPERSEDED 2026-06-01** — this runbook existed to *maintain* the guest
> passwall bypass, which has since been removed (see *Design change* above).
> With no bypass, there is nothing here to keep healthy. Retained as history of
> the failure mode and the `fw4 reload` ≠ hotplug finding.

### The failure mode (why the bypass disappears)

`inet passwall` is owned by the passwall package and is **rebuilt from scratch
whenever passwall (re)starts, switches nodes, or reloads its own config**. Each
rebuild discards the `iifname "br-guest" return` rules this plan inserts, so the
guest network silently reverts to being routed *through* the proxy — guest DNS
hijacked to `:11400`, guest TCP/UDP steered into sing-box.

Only three things re-apply the bypass, and **none fire on a passwall restart**:

| Re-trigger | Fires on |
|---|---|
| `/etc/hotplug.d/firewall/95-guest-passwall-bypass` | `/etc/init.d/firewall reload` **only** |
| `/etc/rc.local` (`sleep 30; …`) | boot |
| manual run | you |

### ⚠️ Correction to Step 7: `fw4 reload` does NOT fire the hotplug

Observed 2026-06-01: after a bare **`fw4 reload`** the bypass count was still
`0` — the firewall hotplug did **not** run. Only the init wrapper
**`/etc/init.d/firewall reload`** fires `/etc/hotplug.d/firewall/*`; calling the
`fw4` binary directly does not. Practical rule:

> After **any** `fw4 reload`, `/etc/init.d/passwall restart`, or passwall
> node-switch/auto-restart, **re-run `/usr/local/bin/guest-passwall-bypass.sh`
> by hand** (or use `/etc/init.d/firewall reload` instead of `fw4 reload`).

### 30-second health check + fix (from the Mac)

```sh
ssh -p 8822 root@192.168.10.1 \
  'echo "guest bypass: $(nft list table inet passwall | grep -c "iifname \"br-guest\".*return") / 5"'
# If < 5, remediate:
ssh -p 8822 root@192.168.10.1 '/usr/local/bin/guest-passwall-bypass.sh'
```

Symptom that should make you check: guest clients suddenly resolving through the
proxy / odd DNS / proxy bandwidth shared — almost always follows a passwall
restart or node switch.

### Not-yet-done hardening (closes the gap permanently)

The hotplug + rc.local cover fw4-reload and boot, but **not** a bare passwall
restart — the exact path that bit us 2026-06-01. Pick one:

- **passwall post-start hook** — have passwall call the bypass script after it
  rebuilds its table (passwall ships a user-include / post-start mechanism).
  The proper fix.
- **cron watchdog** — every 5 min, `grep -c` the bypass count and re-apply if
  `< 5`. Cruder but bulletproof.

---

## Incident log

### 2026-06-01 — guest bypass wiped + Block_C700 never applied

Found during a routine gateway health-check.

**Issue A — guest bypass missing.** `nft list table inet passwall | grep -c
'iifname "br-guest".*return'` returned `0` (expected `5`); head of `PSW_DNS` was
the `:11400` DNS redirect, i.e. guest DNS was hijacked into passwall. Root
cause: passwall's sing-box had restarted after boot and rebuilt the `inet
passwall` table, discarding the bypass rules; neither the hotplug nor rc.local
re-fired. Fix: ran `/usr/local/bin/guest-passwall-bypass.sh` → back to `5/5`,
verified the `br-guest return` now sits above the `:11400` redirect in
`PSW_DNS`. **This also surfaced the Step 7 correction above** (`fw4 reload`
alone did not re-apply it).

**Issue B (co-occurring, separate control) — `Block_C700`.** The four
camera→WAN block rules (`/etc/config/firewall` rules `Block_C700_01..04`,
MAC-only) existed in UCI but were **absent from the live ruleset** — edited
without a `fw4 reload`, so the cameras could reach the internet. `fw4 reload`
applied them. Within minutes the reject counters climbed to **460–540 packets
each** (~60 B/pkt = bare TCP SYNs) — all four cameras continuously trying to
"phone home" to vendor cloud/telemetry, now blocked. LAN/SMB recording to the
NAS is unaffected (L2/LAN traffic, never on the WAN forward path).

Quick check / re-apply for the camera block:

```sh
ssh -p 8822 root@192.168.10.1 '
  nft list ruleset | grep -i Block_C700          # 4 rules, counters > 0 = working
  # if present in "uci show firewall | grep C700" but missing from nft:
  fw4 reload
  /usr/local/bin/guest-passwall-bypass.sh         # ALWAYS re-run after fw4 reload
'
```

Camera MACs: `01 b8:88:80:97:4a:38` · `02 b8:88:80:a0:fd:7c` · `03 b8:88:80:97:6d:02` · `04 b8:88:80:97:6d:36`.

---

## Files / references used in the existing config

- Existing `wifi-iface` style template: `wifinet1` (2.4G) and `wifinet3` (5G) in `/etc/config/wireless` — already use `sae-mixed`, `ocv='0'`, `mode='ap'`, `network='lan'`. We copy these and switch `network='guest'`, add `isolate='1'`, rotate the key.
- Existing zone template: `lan` and `wan` zones in `/etc/config/firewall`. We model `guest` on `wan` (REJECT input, REJECT forward) and add only the minimum `rule`s needed for client connectivity.
- Existing DHCP template: `dhcp 'lan'` in `/etc/config/dhcp`. We copy the same `start`/`limit`/`leasetime` shape, just adjusted for the new interface.
- Passwall chain names: confirmed from `nft list chain inet fw4 PSW_MANGLE` to be `PSW_DNS / PSW_MANGLE / PSW_NAT / PSW_RULE` in the running ruleset.

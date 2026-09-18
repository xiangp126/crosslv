---
name: aipim-cli-env
description: The ai-pim-utils CLI environment on m-fwdev-167 (confluence-cli, jira-cli, glean-cli, nvbugs-cli, redmine-cli, slack-cli and 22 more running inside the pim Docker container), plus the raw-curl path for writing Confluence pages as an AI agent. Use when a *-cli command is missing or fails, after a reboot or reimage of m-fwdev-167, or when rebuilding the ai-pim image. This skill is about the CLI *environment*; for reading or publishing Confluence content itself use skill managing-confluence.
---

# ai-pim CLI environment (m-fwdev-167) & Confluence writes

## Normal operation — nothing special to do

Bashrc wraps all 28 CLIs as shell functions; **just call them by name** (`confluence-cli foo`).
The wrapper lives in `~/myGit/crosslv/track-files/bashrc`, guarded by `hostname -s ==
m-fwdev-167`. First call auto-starts the persistent `pim` container; subsequent calls
`docker exec` into it (~10 ms overhead).

Why the container exists: native binaries don't run on this host — glibc 2.31, they need ≥2.34.
**On any other NVIDIA host** the native `~/.local/bin/*-cli` binaries work directly and the
bashrc guard skips the docker wrap.

- Image: `ai-pim:latest`, built from `~/myGit/crosslv/assets/aipim` (Dockerfile lives there).
  Rebuild: `docker build -t ai-pim:latest ~/myGit/crosslv/assets/aipim` (~25 s).
- Image lives on the root fs at `/var/lib/docker/` (957 GB volume), **not** on the 5 GB NFS home.
- `aipim-shell` gives an interactive bash inside the container — the simple wrappers are usually
  enough.

## Where the CLIs come from — and how to tell if yours is stale

All 28 ship from **one** internal repo as **prebuilt binaries** (Go, six platform tarballs):

```
gitlab-master.nvidia.com  →  project 206465
  └── Generic Package Registry: ai-pim-utils
        ├── version.json   https://outlook-cli-80d21a.gitlab-master-pages.nvidia.com/version.json
        └── install.sh     (same Pages site — this is the single line in our Dockerfile)
```

The Pages hostname still says `outlook-cli`: the project started as **outlook-cli** and grew into
the 28-CLI suite. Because it is one build, **every CLI reports the same version + commit +
build timestamp** — check any one of them and you know them all.

```bash
# what upstream has
curl -fsSL https://outlook-cli-80d21a.gitlab-master-pages.nvidia.com/version.json | head -5
# what you have
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 pim nvbugs-cli --version
# upgrade = rebuild, then recreate the container
docker tag ai-pim:latest ai-pim:<old-ver>-rollback                        # rollback first
docker build --no-cache --pull -t ai-pim:latest ~/myGit/crosslv/assets/aipim
docker rm -f pim
```

⚠ **`--no-cache` is mandatory. `--pull` alone silently rebuilds the SAME version.** The
Dockerfile's install step is one `RUN curl … install.sh` line; its text never changes, so Docker
reuses the cached layer and "the Dockerfile always fetches latest" does not happen. Measured
2026-09-04: `docker build --pull` reported `#8 … CACHED` / `DONE 0.0s` and produced an image
still on 0.119.0 while upstream was 0.121.3. **Always check the version of the image you just
built, not just the build's exit code:**

```bash
docker run --rm ai-pim:latest nvbugs-cli --version      # must show the new version
```

⚠ **`pim_ensure` is a bashrc function — an AI session does not have it**, so after `docker rm -f
pim` nothing recreates the container and every CLI call fails with "No such container". Spell out
the same `docker run` bashrc uses (`~/.bashrc`, ~line 475):

```bash
docker run -d --name pim -v "$HOME:$HOME" -v /auto:/auto:rslave \
    -u "$(id -u):$(id -g)" --network host -e HOME="$HOME" -w "$HOME" \
    ai-pim:latest sleep infinity
```

⚠ **Rebuilding the image is not enough — the running `pim` container keeps the old binaries.**
`docker rm -f pim` after the build; `pim_ensure` will `docker run` a fresh one. Nothing is lost:
the container holds no state (`$HOME` is bind-mounted, so `~/.ai-pim-utils/` survives).
Tag the old image first for a rollback: `docker tag ai-pim:latest ai-pim:<old-ver>-rollback`.

Drift observed 2026-08-27: installed **0.99.3** (built 2026-05-27) vs upstream **0.119.0**
(released 2026-08-26) — three months / 20 minors behind. Nothing auto-updates this; check
periodically.

### Upgrade history

What each past upgrade changed (0.99.3 → 0.119.0 → 0.121.3) is history, not procedure:
**`references/upgrade-history.md`**.

## ⚠ Calling the CLIs from an agent session — do not rely on interactive wrappers

"Just call them by name" holds for an **interactive** shell only. The 28 CLIs are **shell
functions** defined in bashrc; a managed shell call may not inherit them. A bare
`confluence-cli ...` can therefore fall through to the native binary and die on glibc:

```
~/.local/bin/confluence-cli: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.32' not found
                             /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.34' not found
```

(host glibc **2.31**, container **2.39** — verified 2026-08-26.)

**An agent should spell out the docker exec that the wrapper would have done:**

```bash
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -w "$PWD" pim <cli> <args>
```

`-w "$PWD"` matches the wrapper (`$HOME` and `/auto` are bind-mounted at the same paths, so
relative paths and `~/` both resolve). `AI_PIM_UTILS_TELEMETRY_DISABLED=1` silences the telemetry
banner that otherwise pads every response.

**Only the read path needs the container.** `confluence-update` is a plain shell script using the
system `curl` (7.68.0) — it runs natively on the host, no container involved.

## After a reboot

**No manual step needed.** The `pim` container persists in Docker's storage but transitions to
`Exited` on shutdown. The bashrc wrapper `pim_ensure` does `docker start pim` on the next CLI
call, which boots the existing container in ~1 s. To start it eagerly: `docker start pim`.

All state in `~/.ai-pim-utils/` (tokens, config) and `~/.confluence_env` is on the NFS home and
survives the reboot.

## After reimaging m-fwdev-167 (or moving to a fresh box that still needs the wrap)

The image and container live on local disk under `/var/lib/docker/` and are **lost** on reimage.
NFS-home state (`~/.confluence_env`, `~/.ai-pim-utils/`, `~/myGit/crosslv/`) survives.

1. **Install Docker** — `~/myGit/crosslv/jc --docker` (Peter's bootstrap script; installs from
   the official Docker PPA).
2. **Add yourself to the docker group** — `sudo usermod -aG docker $USER`, then log out / back in
   so the new group is active. Verify: `id | grep docker`.
3. **Build the image** — `docker build -t ai-pim:latest ~/myGit/crosslv/assets/aipim`. The
   Dockerfile fetches `install.sh` from a GitLab Pages URL and runs it inside `ubuntu:24.04`.
4. **First CLI call** auto-creates the `pim` container via the bashrc wrapper. No manual
   `docker run` needed.
5. **Credentials** are already in place under the NFS home; no re-auth needed unless tokens were
   rotated.

## Confluence writes — the AI-only path

**For AI agents publishing/updating Confluence pages, use
`~/myGit/crosslv/assets/aipim/confluence-update` (raw curl).** The user does NOT run this helper
themselves — it exists solely for AI use.

**Do NOT use `confluence-cli page create/update` for writes** — those require an interactive TTY
for typed confirmation, which an AI session cannot provide. Reads (`page get`, etc.) are fine.

> **Verified 2026-09-04** (ai-pim-utils 0.119.0, with a freshly rotated, working token — so this
> is the confirmation gate, not an auth failure). Both subcommands, run from a non-interactive
> agent shell with
> `< /dev/null`, exit **11**:
>
> ```
> CONFIRMATION_REQUIRED
> human confirmation is required for confluence-cli page create, but the current session
> cannot present that prompt to a human. Re-run in an interactive terminal or graphical
> session with a human present: no usable confirmation backend is available: typed
> confirmation requires an interactive terminal (stdin and stderr must be TTYs)
> ```
>
> The gate fires **before** the API call — `page update 999999999999` (a page id that cannot
> exist) still returns 11, not 3/not-found. So nothing is written and nothing is reachable.
>
> ⚠ **Do not try to infer this from `--help`.** The exit-code table says
> *"11 - Confirmation required (**destructive** operation not confirmed)"*, and neither
> `create` nor `update` has any `--yes` / `--force` / `--no-confirm` flag — which reads as
> "creating a page is not destructive, so it will go through". It does not. Creating and
> updating are both gated. This misreading cost a round on 2026-09-04.

**The split is by *who runs the command*, not by read-vs-write.** Peter in an interactive shell
uses `confluence-cli page create/update` — that is what the CLI is for, and the
`managing-confluence` skill documents it correctly for that case. An AI session simply cannot
satisfy the TTY prompt, so for **AI writes only** the path is `confluence-update`.

Credentials in `~/.confluence_env` (mode 600), exporting `ATLASSIAN_EMAIL`,
`ATLASSIAN_API_TOKEN`, `CONFLUENCE_BASE` (= `https://nvidia.atlassian.net/wiki`).
User: `pexiang@nvidia.com`.

> ⚠ **The "two places" hold the SAME token value — so an expired token breaks BOTH paths at
> once, including `confluence-update`.** Measured 2026-09-04: `~/.confluence_env` and
> `tokens.toml` both ended `...37221`, and every endpoint returned **403 "Request rejected
> because caller cannot access Confluence"** — *identical to an unauthenticated request*, which
> is how you tell a dead token from a scope problem.
>
> So when `confluence-update` fails, **check the credential before suspecting the script**:
>
> ```bash
> set -a; . ~/.confluence_env; set +a
> curl -s -o /dev/null -w '%{http_code}\n' -u "$ATLASSIAN_EMAIL:$ATLASSIAN_API_TOKEN" \
>      "$CONFLUENCE_BASE/rest/api/user/current"        # 200 = alive, 403 = rotate
> ```
>
> Token rotated 2026-09-04 after both paths went 403.

> ⚠ **`jira-cli` does NOT share this token automatically** (corrected 2026-08-26). It has its own
> slot (`JIRA_CLI_API_TOKEN` / `jira-cli auth set-token`) and a **different site**
> (`https://nvidia-jira.atlassian.net`). As of 2026-08-26 it reports `Authenticated: false`.
> One Atlassian account token generally works across sites the account can reach, but it must be
> stored separately.

## ★ MCP vs CLI — use the current runtime adapter

NVIDIA MaaS publishes more MCP servers than either agent actively loads. A catalogue entry is
not proof that a server is connected or authenticated. Read the current runtime adapter before
inspecting or changing MCP configuration:

- Claude Code: `references/hosts/claude.md`
- Codex: `references/hosts/codex.md`

The shared rule is: **do not bulk-enable the catalogue.** Every server adds startup and discovery
work and may require its own authorization. Add one only for a concrete use, after it has been
authenticated and verified. Discover the live list from configuration and tools; do not copy a
hard-coded server list into scripts or skills.

> ⚠ **The catalogue says "Read/write" — what you actually get is READ-ONLY.** The ECI consent
> screen offers exactly one checkbox, *"Read bug reports and comments"*; there is no write box to
> tick. The 7 tools that land are all reads:
> `get_bug_details_v2` · `get_bugs_list` · `search_v2` · `summarize_v2` · `get_bug_audit_trail_v2`
> · `bugnemo_find_similar_bugs` · `check_connection_v2`.
> The server *does* implement writes (its own instructions mention `confirm_*=true` +
> `confirmation_id`, `comment_is_public`, "V2 write scope") — they are simply not granted.
> The consent page says *"You can change this later by re-authorizing"*, and write scope is
> ultimately gated by **Information Security** (`#nvaiframework-support`).
> **Decision (Peter, 2026-08-27): do not chase the MCP write scope — writes go through
> `nvbugs-cli`.** Read-only MCP is accepted as-is.

⇒ **Split of duties (nvbugs):**

| | use |
| --- | --- |
| **Read** — query, search, summarise, similar-bugs, audit trail | **MCP** (also has `bugnemo_*` / `summarize_*`, which the CLI has no top-level equivalent for) |
| **Write** — file a bug, comment, attach, OSRB flow | **`nvbugs-cli` only.** Needs its own token from `nv-auth.nvidia.com` (**not** Atlassian); still unauthenticated as of 2026-08-27 |

Both are needed — this is complementary, not a migration.

### Until then, for Confluence

⇒ **Prose / research reads:** Glean MCP (`glean_search`, `glean_get_file`, `system="confluence"`)
— cheapest, but returns Glean's *index*: no page id, no version, no ancestors.
⇒ **Reads needing page id / version, or preceding a write:** `confluence-cli` (in the container).
⇒ **Writes:** `confluence-update` (raw curl, native) — it does GET page → `version+1` → PUT, so it
needs the id and version that Glean cannot supply.

## Rotating the Atlassian API token — TWO places, both required

New tokens come from <https://id.atlassian.com/manage-profile/security/api-tokens>.

```bash
# 1. write path (confluence-update, raw curl) — edit in place, keep mode 600
#    replace the export ATLASSIAN_API_TOKEN=... line in ~/.confluence_env
#    verify:
set -a; . ~/.confluence_env; set +a
curl -s -o /dev/null -w '%{http_code}\n' -u "$ATLASSIAN_EMAIL:$ATLASSIAN_API_TOKEN" \
     "$CONFLUENCE_BASE/rest/api/user/current"          # want 200

# 2. read path (confluence-cli, cached in ~/.ai-pim-utils/tokens.toml)
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -w "$PWD" pim \
     confluence-cli auth set-token '<new-token>'
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -w "$PWD" pim \
     confluence-cli space get FW                        # real read, not `auth status`
```

**Bare `space list` will hang** — since 0.99.3 it walks every space in the instance (it ate a
120 s timeout on 2026-09-04). Either `space get FW` or `space list --limit 5` proves the same
thing in seconds; both are fine.

**Updating only `~/.confluence_env` is not enough** — `confluence-cli` never reads that file; it
uses the base64 cache in `tokens.toml` and will keep failing with
`403 ... caller cannot access Confluence` until `auth set-token` is run.
Conversely `auth status` only proves a token is *stored*, not that it *works* — always finish with
a real read.

### Updating

```bash
confluence-update <page-id> <md-file>
confluence-update <md-file>     # page id read from a <!-- confluence-page-id: N --> comment
```

Convention: write that HTML comment into the markdown file **immediately after creating a page**,
so future updates are idempotent.

### Creating (the helper only updates)

Pattern after the curl POST used on 2026-05-28:

1. `sed '1{/^# /d;}' <md> | pandoc -f gfm -t html5 > body.html` — strip the leading H1
   (Confluence shows the title separately) and convert to storage XHTML.
2. Build the JSON with `python3 json.dumps` — **NEVER hand-quote, HTML breaks shell escaping.**
   Payload: `{type:"page", title, space:{key:"FW"}, ancestors:[{id:"<parent>"}],
   body:{storage:{value:<html>, representation:"storage"}}}`.
3. `POST $CONFLUENCE_BASE/rest/api/content` with `Content-Type: application/json`.
4. Capture the returned page id; add `<!-- confluence-page-id: <id> -->` to the markdown source.

### Limits

Confluence-specific macros (Page Properties, Info panels, Status badges) **won't appear** from a
plain markdown push — those need UI edits or pre-converted XHTML using `<ac:structured-macro>`
tags.

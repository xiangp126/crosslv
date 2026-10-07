---
name: aipim-cli-env
description: The ai-pim-utils CLI environment on m-fwdev-167 (confluence-cli, jira-cli, glean-cli, nvbugs-cli, redmine-cli, slack-cli and 22 more running inside the pim Docker container), plus the raw-curl path for writing Confluence pages as an AI agent. Use when a *-cli command is missing or fails, after a reboot or reimage of m-fwdev-167, or when rebuilding the ai-pim image. This skill is about the CLI *environment*; for reading or publishing Confluence content itself use skill managing-confluence.
---

# ai-pim CLI environment (m-fwdev-167) & Confluence writes

## How the CLIs run

- m-fwdev-167 has glibc 2.31 and the native binaries need ≥2.34, so bashrc wraps all 28 CLIs as
  shell functions that run them in the persistent `pim` Docker container (glibc 2.39). In an
  interactive shell **just call them by name** (`confluence-cli foo`): the first call auto-starts
  the container (`pim_ensure`); later calls `docker exec` into it (~10 ms overhead).
- The wrapper lives in `~/myGit/crosslv/track-files/bashrc`, guarded by
  `hostname -s == m-fwdev-167`. **On any other NVIDIA host** the native `~/.local/bin/*-cli`
  binaries work directly and the guard skips the docker wrap.
- `aipim-shell` gives an interactive bash inside the container; the simple wrappers are usually
  enough.
- Image: `ai-pim:latest`, built from `~/myGit/crosslv/assets/aipim` (the Dockerfile lives there).
  Rebuild: `docker build -t ai-pim:latest ~/myGit/crosslv/assets/aipim` (~25 s); to pick up a new
  CLI release, follow "Versions and upgrades" below. The image lives on the root fs at
  `/var/lib/docker/` (957 GB volume), **not** on the 5 GB NFS home.

## Calling the CLIs from an agent session

The wrappers and `pim_ensure` are bashrc functions, and a managed shell call may not inherit them.
A bare `confluence-cli ...` then falls through to the native binary and dies on glibc:

```
~/.local/bin/confluence-cli: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.32' not found
                             /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.34' not found
```

Spell out the docker exec that the wrapper would have done:

```bash
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -w "$PWD" pim <cli> <args>
```

- `-w "$PWD"` matches the wrapper: `$HOME` and `/auto` are bind-mounted at the same paths, so
  relative paths and `~/` both resolve.
- `AI_PIM_UTILS_TELEMETRY_DISABLED=1` silences the telemetry banner that otherwise pads every
  response.
- Without `pim_ensure` nothing recreates a removed container (e.g. after `docker rm -f pim`), and
  every CLI call fails with "No such container". Spell out the same `docker run` that
  `pim_ensure` in `~/.bashrc` uses:

  ```bash
  docker run -d --name pim -v "$HOME:$HOME" -v /auto:/auto:rslave \
      -u "$(id -u):$(id -g)" --network host -e HOME="$HOME" -w "$HOME" \
      ai-pim:latest sleep infinity
  ```

- Only the read path needs the container. `confluence-update` is a plain shell script using the
  system `curl` (7.68.0); it runs natively on the host.

## Managed skill sync — keep it off

Every CLI call except `--help`, `--version`, `config`, `skills` and `completion` syncs the skills
the CLI owns into the agents' skill directories. Those entries are links into
`~/myGit/crosslv/assets/skills`, so the sync overwrites the shared skill files: any file whose
content still matches the checksum in `~/.ai-pim-utils/skills-state.json` is replaced with the
CLI's shipped copy. The container build and native builds share the NFS home, so two versions can
overwrite each other.

- It is disabled: `[defaults] skill_sync_disabled = true` in `~/.ai-pim-utils/config.toml`.
  Check before any CLI call; set it again if it is missing:
  ```bash
  grep -A1 '^\[defaults\]' ~/.ai-pim-utils/config.toml      # want: skill_sync_disabled = true
  docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 pim redmine-cli config defaults set skill_sync_disabled true
  ```
  `AI_PIM_UTILS_SKILL_SYNC_DISABLED=1` in the environment does the same for one call.
- Never run `<cli> skills reset` or `<cli> skills uninstall`: both write or delete through the
  links.
- After any unexpected change to a CLI-owned skill (`tracking-redmine`, `tracking-nvbugs`,
  `managing-*`, `creating-nvidia-github-repo`), check `git -C ~/myGit/crosslv diff` before
  trusting it.

## After a reboot

No manual step needed. The `pim` container persists in Docker's storage but is `Exited` after
shutdown; `pim_ensure` does `docker start pim` on the next CLI call, which boots the existing
container in ~1 s. To start it eagerly (or from an agent session, which has no `pim_ensure`):
`docker start pim`.

All state in `~/.ai-pim-utils/` (tokens, config) and `~/.confluence_env` is on the NFS home and
survives the reboot.

## After reimaging m-fwdev-167 (or moving to a fresh box that still needs the wrap)

The image and container live on local disk under `/var/lib/docker/` and are **lost** on reimage.
NFS-home state (`~/.confluence_env`, `~/.ai-pim-utils/`, `~/myGit/crosslv/`) survives.

1. **Install Docker**: `~/myGit/crosslv/jc --docker` (Peter's bootstrap script; installs from the
   official Docker PPA).
2. **Join the docker group**: `sudo usermod -aG docker $USER`, then log out and back in so the new
   group is active. Verify: `id | grep docker`.
3. **Build the image**: `docker build -t ai-pim:latest ~/myGit/crosslv/assets/aipim`. The
   Dockerfile fetches `install.sh` from a GitLab Pages URL and runs it inside `ubuntu:24.04`.
4. **First CLI call** auto-creates the `pim` container via the bashrc wrapper; no manual
   `docker run` needed (an agent session uses the `docker run` above).
5. **Credentials** are already in place under the NFS home; re-auth only if tokens were rotated.

## Versions and upgrades

All 28 CLIs ship from **one** internal repo as **prebuilt binaries** (Go, six platform tarballs):

```
gitlab-master.nvidia.com  →  project 206465
  └── Generic Package Registry: ai-pim-utils
        ├── version.json   https://outlook-cli-80d21a.gitlab-master-pages.nvidia.com/version.json
        └── install.sh     (same Pages site — this is the single line in our Dockerfile)
```

The Pages hostname says `outlook-cli` because the project started as **outlook-cli** and grew into
the 28-CLI suite. It is one build, so **every CLI reports the same version + commit + build
timestamp** — check any one of them and you know them all. Nothing auto-updates the image; check
installed against upstream periodically.

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

- **`--no-cache` is mandatory; `docker build --pull` alone silently rebuilds the SAME version.**
  The Dockerfile's install step is one `RUN curl … install.sh` line whose text never changes, so
  Docker reuses the cached layer — the Dockerfile does not "always fetch latest" (the build
  reports `#8 … CACHED` / `DONE 0.0s`).
- **Check the version of the image you just built**, not just the build's exit code:
  `docker run --rm ai-pim:latest nvbugs-cli --version` must show the new version.
- **Rebuilding is not enough — the running `pim` container keeps the old binaries.** Run
  `docker rm -f pim` after the build; `pim_ensure` (from an agent: the `docker run` above) starts
  a fresh one. Nothing is lost: the container holds no state (`$HOME` is bind-mounted, so
  `~/.ai-pim-utils/` survives).

Sanity sequence after an upgrade (each step distinguishes a different failure):

```bash
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 pim <cli> --version        # new build in place?
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 pim confluence-cli auth status   # token survived?
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -e AE=… -e AT=… pim \
    sh -c 'curl -s -o /dev/null -w "%{http_code}\n" -u "$AE:$AT" \
           https://nvidia.atlassian.net/wiki/rest/api/user/current'          # network+auth? want 200
docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 pim confluence-cli space list --limit 5  # real read
```

In that curl, `$AE`/`$AT` **must** be inside single quotes so they expand *in the container*.
Double-quoting expands them on the host (empty) and gives a misleading `401`.

What each past upgrade changed (0.99.3 → 0.119.0 → 0.121.3): **`references/upgrade-history.md`**.

## Confluence writes — the AI-only path

AI agents publish and update Confluence pages with
**`~/myGit/crosslv/assets/aipim/confluence-update`** (raw curl; `confluence-update` below). The
user does not run this helper; it exists solely for AI use.

**Do not use `confluence-cli page create/update` for writes from an AI session.** The split is by
*who runs the command*, not by read vs write: Peter in an interactive shell uses those subcommands
(that is what the CLI is for, and skill `managing-confluence` documents them for that case); an AI
session cannot provide the interactive TTY their typed confirmation needs. Reads (`page get`,
etc.) are fine.

The gate, measured on ai-pim-utils 0.119.0 and unchanged on 0.121.3 — `confluence-update` stays
the AI write route; do not re-litigate this per release:

- Both subcommands, run from a non-interactive agent shell with `< /dev/null`, exit **11**:

  ```
  CONFIRMATION_REQUIRED
  human confirmation is required for confluence-cli page create, but the current session
  cannot present that prompt to a human. Re-run in an interactive terminal or graphical
  session with a human present: no usable confirmation backend is available: typed
  confirmation requires an interactive terminal (stdin and stderr must be TTYs)
  ```

- It is the confirmation gate, not an auth failure (it happens with a working token), and it fires
  **before** the API call: `page update 999999999999` (a page id that cannot exist) still returns
  11, not 3/not-found. Nothing is written.
- Do not infer otherwise from `--help`. The exit-code table says *"11 - Confirmation required
  (**destructive** operation not confirmed)"*, and neither `create` nor `update` has any `--yes` /
  `--force` / `--no-confirm` flag — which reads as "creating a page is not destructive, so it will
  go through". It does not: creating and updating are both gated.

### Updating

```bash
confluence-update <page-id> <md-file>
confluence-update <md-file>     # page id read from a <!-- confluence-page-id: N --> comment
```

Write that HTML comment into the markdown file **immediately after creating a page**, so future
updates are idempotent.

### Creating (the helper only updates)

1. `sed '1{/^# /d;}' <md> | pandoc -f gfm -t html5 > body.html` — strip the leading H1
   (Confluence shows the title separately) and convert to storage XHTML.
2. Build the JSON with `python3 json.dumps` — **never hand-quote; HTML breaks shell escaping.**
   Payload: `{type:"page", title, space:{key:"FW"}, ancestors:[{id:"<parent>"}],
   body:{storage:{value:<html>, representation:"storage"}}}`.
3. `POST $CONFLUENCE_BASE/rest/api/content` with `Content-Type: application/json`.
4. Capture the returned page id; add `<!-- confluence-page-id: <id> -->` to the markdown source.

### Limits

Confluence-specific macros (Page Properties, Info panels, Status badges) **won't appear** from a
plain markdown push — those need UI edits or pre-converted XHTML using `<ac:structured-macro>`
tags.

## Atlassian credentials

`~/.confluence_env` (mode 600) exports `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN`,
`CONFLUENCE_BASE` (= `https://nvidia.atlassian.net/wiki`). User: `pexiang@nvidia.com`.

The write path (`~/.confluence_env`) and the read path (`confluence-cli`, cached in
`~/.ai-pim-utils/tokens.toml`) hold the **same token value**, so an expired token breaks both
paths at once, including `confluence-update`. A dead token gets **403 "Request rejected because
caller cannot access Confluence"** from every endpoint — identical to an unauthenticated request,
which is how you tell a dead token from a scope problem. When `confluence-update` fails, check the
credential before suspecting the script:

```bash
set -a; . ~/.confluence_env; set +a
curl -s -o /dev/null -w '%{http_code}\n' -u "$ATLASSIAN_EMAIL:$ATLASSIAN_API_TOKEN" \
     "$CONFLUENCE_BASE/rest/api/user/current"        # 200 = alive, 403 = rotate
```

**`jira-cli` does NOT share this token automatically.** It has its own slot
(`JIRA_CLI_ACCESS_TOKEN` / `jira-cli auth set-token`) and a **different site**
(`https://nvidia-jira.atlassian.net`); check it with `jira-cli auth status`. One
Atlassian account token generally works across sites the account can reach, but it must be stored
separately.

### Rotating the Atlassian API token — TWO places, both required

New tokens come from <https://id.atlassian.com/manage-profile/security/api-tokens>.

1. **Write path** (`confluence-update`): replace the `export ATLASSIAN_API_TOKEN=...` line in
   `~/.confluence_env` in place, keeping mode 600. Verify with the curl above — want `200`.
2. **Read path** (`confluence-cli`, cached in `~/.ai-pim-utils/tokens.toml`):

   ```bash
   docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -w "$PWD" pim \
        confluence-cli auth set-token '<new-token>'
   docker exec -e AI_PIM_UTILS_TELEMETRY_DISABLED=1 -w "$PWD" pim \
        confluence-cli space get FW                        # real read, not `auth status`
   ```

- **Updating only `~/.confluence_env` is not enough**: `confluence-cli` never reads that file. It
  uses the base64 cache in `tokens.toml` and keeps failing with
  `403 ... caller cannot access Confluence` until `auth set-token` is run.
- `auth status` may only prove a token is *stored* (confluence-cli 0.121.3 does validate it:
  `validation: accepted`) — always finish with a real read. **Bare `space list` hangs**: it walks every space in the instance and can exceed a 120 s
  timeout. `space get FW` or `space list --limit 5` proves the same thing in seconds.

## MCP vs CLI — use the current runtime adapter

NVIDIA MaaS publishes more MCP servers than either agent actively loads. A catalogue entry is not
proof that a server is connected or authenticated. Read the current runtime adapter before
inspecting or changing MCP configuration:

- Claude Code: `references/hosts/claude.md`
- Codex: `references/hosts/codex.md`

Shared rules:

- **Do not bulk-enable the catalogue.** Every server adds startup and discovery work and may
  require its own authorization. Add one only for a concrete use, after it has been authenticated
  and verified.
- Discover the live list from configuration and tools; do not copy a hard-coded server list into
  scripts or skills.

Confluence read/write routing (Glean MCP, `confluence-cli`, `confluence-update`): skill
`managing-confluence`.

### NVBugs: MCP for reads, `nvbugs-cli` for writes

The catalogue says "Read/write", but what you actually get is **read-only**. The ECI consent screen
offers exactly one checkbox, *"Read bug reports and comments"*, with no write box to tick, and the
7 tools that land are all reads: `get_bug_details_v2` · `get_bugs_list` · `search_v2` ·
`summarize_v2` · `get_bug_audit_trail_v2` · `bugnemo_find_similar_bugs` · `check_connection_v2`.
The server *does* implement writes (its own instructions mention `confirm_*=true` +
`confirmation_id`, `comment_is_public`, "V2 write scope"); they are simply not granted. The consent
page says *"You can change this later by re-authorizing"*, and write scope is ultimately gated by
**Information Security** (`#nvaiframework-support`).

**Do not chase the MCP write scope — writes go through `nvbugs-cli`.** The
read-only MCP is accepted as-is.

| | use |
| --- | --- |
| **Read** — query, search, summarise, similar-bugs, audit trail | **MCP** (also has `bugnemo_*` / `summarize_*`, which the CLI has no top-level equivalent for) |
| **Write** — file a bug, comment, attach, OSRB flow | **`nvbugs-cli` only.** Needs its own token from `nv-auth.nvidia.com` (**not** Atlassian); check with `nvbugs-cli auth status` before relying on it |

Both are needed — this is complementary, not a migration.

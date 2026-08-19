---
name: aipim-cli-env
description: The ai-pim-utils CLI environment on m-fwdev-167 (confluence-cli, jira-cli, glean-cli, nvbugs-cli, redmine-cli, slack-cli and 22 more running inside the pim Docker container), plus the raw-curl path for writing Confluence pages as an AI agent. Use when a *-cli command is missing or fails, after a reboot or reimage of m-fwdev-167, when rebuilding the ai-pim image, or when creating/updating a Confluence page.
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

Credentials in `~/.confluence_env` (mode 600), exporting `ATLASSIAN_EMAIL`,
`ATLASSIAN_API_TOKEN`, `CONFLUENCE_BASE` (= `https://nvidia.atlassian.net/wiki`).
User: `pexiang@nvidia.com`. The same Atlassian token works for `jira-cli` (Cloud Jira shares
Atlassian auth).

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

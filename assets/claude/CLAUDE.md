# Project Notes

- `jk` is an alias for `jmake` (located at `$HOME/.usr/bin/jmake`). Use `jmake` directly in Bash since shell aliases aren't available.
- When running builds in other directories, prefix with `cd /path/to/dir &&`.
- `code` is a bash function defined in `$HOME/Templates/code-function.sh`. It's a VS Code / Cursor remote CLI wrapper. Before using `code`, source the function first: `source $HOME/Templates/code-function.sh && code <args>`.

## Host: m-fwdev-167 (Ubuntu 20.04, glibc 2.31)

- ai-pim-utils CLIs (`confluence-cli`, `jira-cli`, `glean-cli`, `nvbugs-cli`, `redmine-cli`, `outlook-cli`, `calendar-cli`, `slack-cli`, `helios-cli`, `transcript-cli`, `pplx-cli`, `sharepoint-cli`, ...) run via the Docker container `pim` (image `ai-pim:latest`). Native binaries don't run on this host — glibc too old (need ≥2.34).
- Bashrc wraps all 28 CLIs as shell functions; just call them by name (`confluence-cli foo`). The wrapper lives in `~/myGit/crosslv/track-files/bashrc` guarded by `hostname -s == m-fwdev-167`.
- First call auto-starts the persistent `pim` container; subsequent calls `docker exec` into it (~10 ms overhead).
- Build the image: `docker build -t ai-pim:latest ~/myGit/crosslv/assets/aipim`. Dockerfile lives there too.
- Image lives on root fs at `/var/lib/docker/` (957 GB volume), not on the 5 GB NFS home.
- Helpers in bashrc: `aipim-shell` (interactive bash inside the container) — though the simple wrappers are usually enough.
- On any other NVIDIA host: native `~/.local/bin/*-cli` binaries work directly; the bashrc guard skips the docker wrap.

## Confluence writes (AI-only path)

- **For AI agents publishing/updating Confluence pages, use `~/myGit/crosslv/nv-tools/confluence-update`** (raw curl). The user does NOT run this helper themselves — it is solely for AI use.
- **Do NOT use `confluence-cli page create/update`** for writes — those require an interactive TTY for typed confirmation, which AI sessions cannot provide. Reads (`page get`, etc.) are fine.
- Credentials in `~/.confluence_env` (mode 600), exporting `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN`, `CONFLUENCE_BASE` (= `https://nvidia.atlassian.net/wiki`). User: `pexiang@nvidia.com`.
- Same Atlassian token works for `jira-cli` (Cloud Jira shares Atlassian auth).
- `confluence-update <page-id> <md-file>` updates an existing page. `confluence-update <md-file>` extracts the page id from a `<!-- confluence-page-id: N -->` HTML comment embedded in the markdown's front matter — convention: write that comment to a markdown file immediately after creating a Confluence page so future updates are idempotent.
- For **creating a new** page (the helper only updates), pattern after the curl POST used on 2026-05-28:
  1. `sed '1{/^# /d;}' <md> | pandoc -f gfm -t html5 > body.html` — strip the leading H1 (Confluence shows title separately) and convert to storage XHTML.
  2. Build JSON via `python3 json.dumps` (NEVER hand-quote — HTML breaks shell escaping). Payload: `{type:"page", title, space:{key:"FW"}, ancestors:[{id:"<parent>"}], body:{storage:{value:<html>, representation:"storage"}}}`.
  3. `POST $CONFLUENCE_BASE/rest/api/content` with `Content-Type: application/json`.
  4. Capture returned page id; add `<!-- confluence-page-id: <id> -->` to the markdown source.
- Confluence-specific macros (Page Properties, Info panels, Status badges) won't appear from plain markdown push — those need UI edits or pre-converted XHTML using `<ac:structured-macro>` tags.

## gitlab-master.nvidia.com

- SSH on **port 12051**, not the default 22. Clone with `git clone ssh://git@gitlab-master.nvidia.com:12051/<group>/<repo>.git`. The server prints this on banner if you connect on port 22.
- HTTPS clones need a PAT (`https://oauth2:<token>@gitlab-master.nvidia.com/<group>/<repo>.git`).

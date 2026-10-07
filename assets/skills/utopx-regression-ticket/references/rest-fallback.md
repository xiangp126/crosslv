## When the redmine MCP is down — the REST fallback

Use the REST API when the `nvidia-redmine` MCP (`yai__create_task`) is unavailable. It needs
neither the MCP nor `redmine-cli`: a native `redmine-cli` on m-fwdev-167 fails with
`GLIBC_2.32 / 2.34 not found`, and the CLI now runs in the pim container (skill `aipim-cli-env`).
The key is in `~/.redmine_env` (mode 600 — never echo it):

```bash
set -a; . ~/.redmine_env; set +a
K="${REDMINE_API_KEY:-$REDMINE_TOKEN}"; U="${REDMINE_URL:-https://redmine-api.nvidia.com}"
curl -sk -H "X-Redmine-API-Key: $K" "$U/issues/<id>.json?include=journals,attachments,relations"
```

API calls go to `redmine-api.nvidia.com`: the 2026-10-05 domain migration retired the
`*.mellanox.com` API hosts, and `redmine.mellanox.com` only redirects browsers.

Create with `POST {U}/issues.json`. The MCP's friendly names become numeric ids:

| skill field | REST key | value (as used on #5273244) |
|---|---|---|
| `project` | `project_id` | `5581` |
| `tracker` `Task` | `tracker_id` | **`9`** (`Bug SW` = 28) |
| `priority` `P1: Critical` | `priority_id` | **`6`** (P2 = 5, P3 = 4) |
| `scrum_type` `Story` | `scrum_type` | **`2`** |
| `assigned_to` `Peter Xiang` | `assigned_to_id` | **`25616`** |
| `target_version` | `fixed_version_id` | `9505` |
| sprint | `sprint_id` | `30624` = `MTBC_YL 26-08` |
| `Chips` Bronco (BF4) | `custom_fields:[{"id":843,"value":["167"]}]` | note: **list of strings** |

When something 422s, look the ids up rather than trusting this table:
`{U}/trackers.json` · `{U}/enumerations/issue_priorities.json` ·
`{U}/projects/5581/versions.json?limit=100` · `{U}/custom_fields.json` (needs admin; otherwise read
the ids off an existing ticket's JSON).

Which sprint: ask, don't infer it from the date — SKILL.md → "Sprint lookup".

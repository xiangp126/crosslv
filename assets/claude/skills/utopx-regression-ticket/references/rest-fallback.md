## When the redmine MCP is down — the REST fallback

`yai__create_task` was unavailable on 2026-09-15 (`mcp__nvidia-redmine__yai__*` disconnected) and
`redmine-cli` is broken on m-fwdev-167 (`GLIBC_2.32 / 2.34 not found`). The working path is the
REST API with the key in `~/.redmine_env` (mode 600 — never echo it):

```bash
set -a; . ~/.redmine_env; set +a
K="${REDMINE_API_KEY:-$REDMINE_TOKEN}"; U="${REDMINE_URL:-https://redmine.mellanox.com}"
curl -sk -H "X-Redmine-API-Key: $K" "$U/issues/<id>.json?include=journals,attachments,relations"
```

Create with `POST {U}/issues.json`. The MCP's friendly names become numeric ids:

| skill field | REST key | value used on #5273244 |
|---|---|---|
| `project` | `project_id` | `5581` |
| `tracker` `Task` | `tracker_id` | **`9`** (`Bug SW` = 28) |
| `priority` `P1: Critical` | `priority_id` | **`6`** (P2 = 5, P3 = 4) |
| `scrum_type` `Story` | `scrum_type` | **`2`** |
| `assigned_to` `Peter Xiang` | `assigned_to_id` | **`25616`** |
| `target_version` | `fixed_version_id` | `9505` |
| sprint | `sprint_id` | `30624` = `MTBC_YL 26-08` |
| `Chips` Bronco (BF4) | `custom_fields:[{"id":843,"value":["167"]}]` | note: **list of strings** |

Look ids up rather than trusting this table when something 422s:
`{U}/trackers.json` · `{U}/enumerations/issue_priorities.json` ·
`{U}/projects/5581/versions.json?limit=100` · `{U}/custom_fields.json` (needs admin; otherwise read
the ids off an existing ticket's JSON).

### Ask which sprint, don't infer it from the date

Filing on 2026-09-15 I picked `MTBC_YL 26-09` and Peter corrected it to **`26-08`**. The sprint
follows the team's planning board, not the calendar month. If he has not said, ask — it is one
question and the fix afterwards costs a ticket update plus a note.

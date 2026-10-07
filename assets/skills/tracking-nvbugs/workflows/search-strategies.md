# Search Strategies Workflow

## Search Order

1. **Bug ID known** → `nvbugs-cli bug get <id> --json` (skip search entirely)
2. **Module known** → `search bugs --module X` + additional filters
3. **Person known** → resolve the full name via helios, then `search bugs --requester/--engineer "Full Name" --module X`
4. **Only keywords** → `search by-synopsis "specific phrase" --limit 10`
5. **All else fails** → `search ai "natural language description"` (experimental)

## Rules

**Names:** `--engineer` and `--requester` require **full names, not usernames**.

- Works: `--requester "Julie Yaunches"` / Fails: `--requester jyaunches`
- Works: `--engineer "John Smith"` / Fails: `--engineer jsmith`

Always resolve usernames to full names first with helios-cli; if helios-cli is unavailable, try
the common format "Firstname Lastname".

```bash
# Resolve username → full name
helios-cli user get jyaunches --json
```

**Raw `--criteria`** uses NVBugs **database field names**, not convenience names. `Engineer=...`
or `Requester=...` can trigger API errors; some criteria key names are case-sensitive. Prefer
`--engineer` / `--requester` with full names unless you specifically need raw criteria.

- Good: `BugEngineerFullName=John Smith`
- Good: `BugRequesterFullName=Julie Yaunches`
- Good: `ActionReqByFullName=Alice Smith`
- Bad: `Engineer=jdoe`
- Bad: `Requester=Julie Yaunches`

**Narrow person searches:** broad person searches often time out or return empty — always add at
least one more filter (`--module`, `--status`, `--priority`).

## Strategy 1: By Person

```bash
# BAD — too broad, likely to timeout or return empty
nvbugs-cli search bugs --requester "Julie Yaunches" --json

# GOOD — narrow by module (module + requester is the most reliable pattern for finding someone's bugs)
nvbugs-cli search bugs --requester "Julie Yaunches" --module "Open-Source-Review-Board" --json

# GOOD — narrow by status
nvbugs-cli search bugs --engineer "Julie Yaunches" --status open --json

# GOOD — narrow by priority
nvbugs-cli search bugs --engineer "John Smith" --priority P1 --json
```

If `--requester` returns empty, try `--engineer` (and vice versa) — the person may be listed under
a different role on the bug:

```bash
nvbugs-cli search bugs --requester "Julie Yaunches" --module "My-Module" --json
nvbugs-cli search bugs --engineer "Julie Yaunches" --module "My-Module" --json
```

## Strategy 2: By Synopsis/Topic

`search by-synopsis` can be unreliable for short or common terms (timeouts, empty results due to
API scope):

```bash
# Specific phrases work better than single words
nvbugs-cli search by-synopsis "OSRB: Request to contribute" --json

# Add module-id to narrow scope and avoid timeouts
nvbugs-cli search by-synopsis "memory leak" --module-id 15766 --json

# Limit results to avoid large payloads
nvbugs-cli search by-synopsis "display flicker" --limit 10 --json
```

When `by-synopsis` fails, fall back to `search bugs` with `--criteria`, or to AI-powered search
(experimental; handles natural language):

```bash
nvbugs-cli search bugs --criteria "Synopsis=memory leak" --module "Graphics Driver" --json
nvbugs-cli search ai "OSRB bugs filed by Julie for open sourcing" --json
```

## Strategy 3: By Module

When you know the module (team/component), make it the primary filter:

```bash
# All open bugs in a module
nvbugs-cli search bugs --module "Open-Source-Review-Board" --status open --json

# Combine with other filters
nvbugs-cli search bugs --module "Graphics Driver" --priority P1 --severity S1 --json
```

Common module: **Open-Source-Review-Board** — OSRB / open-source approval bugs. To find a module
name, read it from an existing bug in that area:

```bash
nvbugs-cli bug get <known-bug-id> --json | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['ModuleInfo'])"
```

## Strategy 4: Combined Criteria

Use `--criteria` for fields not covered by convenience flags (field names: see Rules):

```bash
# Custom field filters
nvbugs-cli search bugs --criteria "BugAction=Dev - Open - To fix" --module "My-Module" --json

# Multiple criteria (AND logic)
nvbugs-cli search bugs --criteria "BugTypeID=6" --module "Open-Source-Review-Board" --json

# Raw person criteria must use database field names
nvbugs-cli search bugs --criteria "BugEngineerFullName=John Smith" --criteria BugAction=Open --json
```

## Strategy 5: Sorting and Pagination

```bash
# Newest bugs first
nvbugs-cli search bugs --engineer "John Smith" --status open --sort BugId:desc --json

# Paginate through results
nvbugs-cli search bugs --module "My-Module" --page 1 --limit 20 --json
nvbugs-cli search bugs --module "My-Module" --page 2 --limit 20 --json
```

## Troubleshooting

**Search returns empty but you know bugs exist:**
- Check name format (full name, not username)
- Add `--module` to narrow scope
- Try the other person field (`--engineer` vs `--requester`)
- Try `--status open` to filter out closed bugs

**Search times out:**
- Add more filters to narrow results (`--module`, `--priority`, `--status`)
- Use `--limit 10` to reduce payload
- Use `search by-synopsis` with `--module-id` instead of broad text search

**API internal error with `--criteria`:** don't use `--criteria Engineer=...` or
`--criteria Requester=...` — see Rules.

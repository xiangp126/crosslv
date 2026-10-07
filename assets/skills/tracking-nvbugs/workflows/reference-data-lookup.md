# Reference Data Lookup Workflow

Before creating or updating a bug, look up valid IDs for bug type, action, disposition, priority,
severity, platform, and hardware with `nvbugs-cli lookup`. Most lookups require `--div-id`
(division ID) and `--type-id` (bug type ID). When creating bugs, pass the looked-up IDs to
`--action-id` and `--disposition-id`.

## 1. Get Bug Types for a Division

```bash
nvbugs-cli lookup bug-types --div-id 100 --json
```

Returns bug type IDs and names; the `BugTypeID` is needed for the other lookups.

## 2. Look Up Valid Actions and Dispositions

```bash
# Actions for a division + bug type
nvbugs-cli lookup bug-actions --div-id 100 --type-id 6 --json

# Dispositions for a division + bug type
nvbugs-cli lookup dispositions --div-id 100 --type-id 6 --json

# Valid action-disposition pairs (which combinations the API accepts)
nvbugs-cli lookup action-disposition-pairs --div-id 100 --type-id 6 --json
```

## 3. Look Up Priorities and Severities

```bash
nvbugs-cli lookup priorities --div-id 100 --type-id 6 --json
nvbugs-cli lookup severities --div-id 100 --type-id 6 --json
```

## 4. Look Up Platforms and Hardware

```bash
# Platforms (no division filter; optional --hardware-type, --active-only)
nvbugs-cli lookup platforms --json

# Hardware by type (exact type names like "GPU/Board", not "GPU")
nvbugs-cli lookup hardware --hardware-type "GPU/Board" --json
```

## 5. Look Up Applications

Requires at least one filter: `--name` or `--type-id`.

```bash
# By name pattern
nvbugs-cli lookup applications --name "CUDA" --json

# By application type ID
nvbugs-cli lookup applications --type-id 5 --json
```

## 6. Other Lookups

```bash
# Status list (--div-id required)
nvbugs-cli lookup status-list --div-id 100 --json
nvbugs-cli lookup status-list --status-type Open --div-id 100 --json

# Application types
nvbugs-cli lookup application-types --json

# Audit types (--div-id and --type-id required)
nvbugs-cli lookup audit-types --div-id 100 --type-id 6 --json

# Software versions: by name pattern, by module + division, or by version IDs
nvbugs-cli lookup versions --name "v1.0" --json
nvbugs-cli lookup versions --module "GPU Driver" --app-div-id 100 --json
nvbugs-cli lookup versions --ids 1,2,3 --json
```

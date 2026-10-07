# Module Management Workflow

Discover NVBugs modules, view members, categories, and NSpect/Redmine mappings. Module names must
be exact — use `module list` first to discover available names (`module categories` returns
HTTP 500 for a name that doesn't exist).

## 1. Search for Modules

```bash
# Search modules by name pattern
nvbugs-cli module list "GPU Driver" --json

# Get a specific module (requires --app-division, a numeric division ID 1-5)
nvbugs-cli module get "GPU Driver" --app-division 1 --json
```

## 2. View Module Categories

```bash
# List categories for a module (returns category names as strings)
nvbugs-cli module categories "GPU Driver" --json
```

## 3. View Module Members

```bash
# List members of a specific module (--app-division is the numeric division ID)
nvbugs-cli module members list "GPU Driver" --app-division 1 --json

# List members across multiple modules (--app-division required)
nvbugs-cli module members all "Module A" "Module B" --app-division 1 --json
```

## 4. NSpect IDs

```bash
# List NSpect IDs for a module (--div-id, required, is the numeric division ID, not the name)
nvbugs-cli module nspect list "GPU Driver" --div-id 1 --json
```

## 5. Redmine Integration

```bash
# List Redmine module mappings
nvbugs-cli module redmine list --json

# List Redmine module name mappings
nvbugs-cli module redmine mapping --json
```

# Dependency Analysis Workflow

Analyze bug dependency trees to find blockers and critical paths. Start with `--max-depth 1` and
increase if needed.

## 1. Map Gated-By (What Blocks This Bug?)

```bash
# Shallow (direct dependencies only)
nvbugs-cli bug relationships gated-by <bug-id> --json

# Deep (up to 5 levels)
nvbugs-cli bug relationships gated-by <bug-id> --max-depth 5 --json

# Flat list (no hierarchy; easier for programmatic processing)
nvbugs-cli bug relationships gated-by <bug-id> --max-depth 5 --flat --json

# Exclude closed/fixed (focus on active blockers)
nvbugs-cli bug relationships gated-by <bug-id> --max-depth 3 --hide-closed --hide-fixed --json
```

## 2. Map Gating (What Does This Bug Block?)

```bash
# What depends on this bug?
nvbugs-cli bug relationships gating <bug-id> --json

# Deep tree
nvbugs-cli bug relationships gating <bug-id> --max-depth 5 --json
```

## 3. Check Blocker Details

For each blocker found:

```bash
nvbugs-cli bug get <blocker-id> --json
nvbugs-cli bug history <blocker-id> --json
```

## 4. Add Dependencies (Requires Write Mode)

```bash
# Bug 12345 is now gated by 67890
nvbugs-cli bug relationships add-gated 12345 67890 --json

# Bug 12345 now gates 67890
nvbugs-cli bug relationships add-gating 12345 67890 --json
```

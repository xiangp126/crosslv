# Bug Investigation Workflow

Gather all available context for a bug. Use `--json | jq` to filter large results.

## 1. Get Bug Details

```bash
# Full bug record
nvbugs-cli bug get <bug-id> --json

# Alternative endpoint (includes more fields); with --include-plaintext: full description with metadata
nvbugs-cli bug get-alt <bug-id> --include-plaintext --json

# Description only
nvbugs-cli bug description <bug-id> --json
```

If the description contains inline screenshots or diagrams (embedded in `DescriptionMarkup`;
these are separate from normal NVBugs attachments), inspect/export them:

```bash
nvbugs-cli bug images list <bug-id> --json
nvbugs-cli bug images extract <bug-id> --output-dir /tmp/bug-<bug-id>-images
```

## 2. Check Audit Trail

```bash
nvbugs-cli bug history <bug-id> --json
```

Look for: priority escalations, engineer reassignments, status transitions. For multiple bugs at
once use `bug history-batch`.

## 3. Review Comments

```bash
nvbugs-cli comment list <bug-id> --json
```

## 4. Check Dependencies

```bash
# What blocks this bug?
nvbugs-cli bug relationships gated-by <bug-id> --max-depth 2 --json

# What does this bug block?
nvbugs-cli bug relationships gating <bug-id> --max-depth 2 --json
```

Check gated-by before closing: blocked bugs may need attention.

## 5. Check Perforce Changelists

```bash
nvbugs-cli perforce info <bug-id> --json
```

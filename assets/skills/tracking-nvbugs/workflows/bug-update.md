# Bug Update Workflow

Create, update, and manage bugs. Use `--json` to capture the result (e.g., the new bug ID after
create/clone), and always verify with `bug get` after updates.

## 1. Create a Bug

`--synopsis`, `--div-id` and `--bug-type` (or `--bug-type-id`) are required, and the API rejects
`Key: 0` for action/disposition, so pass a valid `--action-id`/`--disposition-id` pair. Look all
of them up first ([Reference Data Lookup](reference-data-lookup.md)). Pass `--module` only
together with `--module-id`: `--module` alone fails silently and leaves the module unset.

```bash
nvbugs-cli bug create \
  --synopsis "Memory leak in driver" \
  --div-id <div-id> --bug-type "<bug-type>" \
  --action "<action>" --action-id <action-id> \
  --disposition "<disposition>" --disposition-id <disposition-id> \
  --module "<module-name>" --module-id <module-id> \
  --priority "<priority>" --severity "<severity>" \
  --dry-run --json
```

- Priority and severity take the division's values (e.g. `4-Fix Before Ship`,
  `3-Functionality`); list them with `lookup priorities` / `lookup severities`.
- `--dry-run` resolves and validates the payload without saving; drop it to file the bug, then
  check `ModuleInfo` with `nvbugs-cli bug get <new-bug-id> --json`.

## 2. Update a Bug

```bash
# Update specific fields (only changed fields are sent)
nvbugs-cli bug update <bug-id> --priority P2 --json
nvbugs-cli bug update <bug-id> --synopsis "Updated title" --json

# Update description (inline, from a file, or piped via stdin)
nvbugs-cli bug update-description <bug-id> --description "New description" --json
nvbugs-cli bug update-description <bug-id> --file description.txt --json
echo "text" | nvbugs-cli bug update-description <id>
```

## 3. Clone a Bug

```bash
nvbugs-cli bug clone <bug-id> --json
nvbugs-cli bug clone <bug-id> --send-email --include-attachments --json
```

## 4. Add Comments

```bash
nvbugs-cli comment add <bug-id> --text "Fix verified in build 1234" --json
nvbugs-cli comment add <bug-id> --text "Internal note" --private --json
nvbugs-cli comment update <bug-id> <comment-guid> --text "Updated text" --json
```

## 5. Manage Attachments

```bash
# Upload
nvbugs-cli attachment upload <bug-id> screenshot.png --json

# Download (without --output: original filename, current directory)
nvbugs-cli attachment download <bug-id> <attachment-guid> --output output.txt

# Delete
nvbugs-cli attachment delete <attachment-guid> --json
```

Inline screenshots embedded in `DescriptionMarkup` are separate from uploaded attachments; inspect
or export them with `nvbugs-cli bug images list/extract <bug-id>`.

## 6. Set Relationships

```bash
nvbugs-cli bug relationships add-gated <bug-id> <blocker-id> --json
nvbugs-cli bug relationships add-gating <bug-id> <dependent-id> --json
```

# Page Lifecycle Workflow

Use this workflow when the user needs to review, update, archive, restore, or otherwise manage existing Confluence content.

## Typical flow

1. Inspect the current page state
2. Review labels, comments, and version history
3. Update or annotate the page
4. Archive or restore when needed

## Inspect the current state

```bash
confluence-cli page get 12345 --json
confluence-cli page ancestors 12345 --json
confluence-cli page permissions 12345 --json
```

## Review labels, comments, and history

```bash
confluence-cli label list 12345 --json
confluence-cli comment list 12345 --json
confluence-cli history list 12345 --limit 10 --json
```

## Update the page

```bash
confluence-cli page update 12345 '# Updated Content'
confluence-cli comment create 12345 'Reviewed and updated.'
confluence-cli comment update 67890 'Edited review comment.'
```

## Archive content

```bash
confluence-cli page archive 12345 --json
```

## Restore an older version

```bash
confluence-cli history get 12345 3
confluence-cli page restore-version 12345 --version 3 --json
```

## Find stale or review-tagged content

```bash
confluence-cli page find --label requires-periodic-review --json
confluence-cli page find --cql 'type=page AND lastmodified<=now("-180d")' --limit 50 --json
```

## Notes

- Use `history list` before restoring so the target version is explicit
- Use labels to mark review state instead of relying only on comments
- Archive only after confirming replacements or successors when the user mentions deprecation

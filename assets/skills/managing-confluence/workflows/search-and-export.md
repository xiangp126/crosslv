# Search and Export Workflow

Use this workflow when the user needs to locate Confluence content, inspect results, and export pages.

## Typical flow

1. Start with text search
2. Narrow with `--space`, `--label`, or `--cql`
3. Review results in JSON when filtering is needed
4. Export one or more pages

## Search by text

```bash
confluence-cli page find 'authentication guide'
confluence-cli page find 'deployment' --space ENG --limit 10 --json
```

## Search by label

```bash
confluence-cli page find --label api-docs
confluence-cli page find --label api-docs --label reviewed --space ENG --json
```

## Search with CQL

```bash
confluence-cli page find --cql 'type=page AND lastmodified>=now("-7d")' --json
confluence-cli page find --cql 'label="api-docs" AND space=ENG' --json
```

## Filter results

```bash
RESULTS=$(confluence-cli page find 'API documentation' --space ENG --json)

echo "$RESULTS" | jq '.data | length'
echo "$RESULTS" | jq -r '.data[].title'
echo "$RESULTS" | jq '.data[] | {id, title, spaceKey, updatedAt}'
```

## Export a page

```bash
confluence-cli page get 12345 > page.md
confluence-cli page export 12345 --output page.html
```

## Export multiple matching pages

```bash
RESULTS=$(confluence-cli page find 'runbook' --space ENG --limit 20 --json)

echo "$RESULTS" | jq -r '.data[] | "\(.id)|\(.title)"' | while IFS='|' read -r id title; do
  safe=$(echo "$title" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd '[:alnum:]-')
  confluence-cli page get "$id" > "$safe.md"
done
```

## Notes

- Start broad, then narrow with `--space`, `--label`, or `--cql`
- Use `--json` when another tool needs to inspect or rank results
- Use `page export` when the requested output is HTML or another file-oriented export

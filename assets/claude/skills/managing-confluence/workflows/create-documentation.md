# Create Documentation Workflow

Use this workflow when the user wants to publish or update documentation in Confluence.

## Typical flow

1. Confirm the target space or parent page
2. Create a new page or update an existing one
3. Add labels or attachments if needed
4. Verify hierarchy and ancestry

## Confirm context

```bash
confluence-cli config show
confluence-cli space list --json
confluence-cli space pages ENG --limit 20 --json
```

## Create a page

```bash
confluence-cli page create 'Feature X Documentation' '# Overview'
confluence-cli page create 'API Reference' '# API Reference' --parent 12345
```

## Update a page

```bash
confluence-cli page update 12345 '# Updated Content'
confluence-cli page upsert --parent 12345 --title 'Feature X Documentation' '# Overview'
```

## Add metadata

```bash
confluence-cli label add 12345 documentation reviewed
confluence-cli attachment upload 12345 ./diagram.png
confluence-cli comment create 12345 'Initial draft published.'
```

## Verify hierarchy

```bash
confluence-cli page ancestors 12345 --json
confluence-cli page children 12345 --depth 1 --json
```

## Notes

- Prefer `page upsert` when the user wants idempotent publishing
- Prefer a configured default space for title-based lookups
- Use `page ancestors` before moving content into an existing hierarchy

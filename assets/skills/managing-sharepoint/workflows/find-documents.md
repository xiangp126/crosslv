# Document Discovery Workflow

Find a document by name or topic, then read it (for review or summarization) or check who owns it
and who has access. Command details: `../SKILL.md`.

## 1. Search

Use specific terms; very common words may fail.

```bash
sharepoint-cli search --query "quarterly report"           # searches file names and content
sharepoint-cli search --query "onboarding" --limit 10      # more results per page
sharepoint-cli search --query "design doc" --output json   # JSON for scripting
```

## 2. Get the file URL from the results

Results show file title, author, date, and URL. Human output lists the URLs directly; to extract
title and URL from JSON:

```bash
sharepoint-cli search --query "budget"

sharepoint-cli search --query "budget" --output json \
  | jq -r '.data.results[] | "\(.document.title // .title)\t\(.url)"'
```

## 3. Check metadata before reading

Confirms you have the right file; shows title, type, owner, dates, and permissions.

```bash
sharepoint-cli file metadata --url <url-from-search>
```

## 4. Retrieve content

```bash
sharepoint-cli file get --file-url <url-from-search>
sharepoint-cli file get --file-url <url> --max-length 2000   # limit length for large documents
```

## More results

```bash
sharepoint-cli search --query "project" --output json > results.json
jq '.data.hasMoreResults' results.json                       # more results exist?
CURSOR=$(jq -r '.data.cursor' results.json)
sharepoint-cli search --query "project" --cursor "$CURSOR"
```

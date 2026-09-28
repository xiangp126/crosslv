# Document Discovery Workflow

Search for files across SharePoint, retrieve content, and inspect metadata.

## When to Use

- Looking for a specific document by name or topic
- Need to read document content for review or summarization
- Checking who owns a file and who has access

## Workflow Overview

1. Search for files by keyword
2. Review search results
3. Retrieve content or inspect metadata

## Step-by-Step

### Step 1: Search for Files

```bash
# Search by keyword (searches file names and content)
sharepoint-cli search --query "quarterly report"

# More results per page
sharepoint-cli search --query "onboarding" --limit 10

# JSON for scripting
sharepoint-cli search --query "design doc" --output json
```

### Step 2: Get File URL from Results

Search results show file titles, authors, dates, and URLs. Extract the URL for the file you want:

```bash
# Human output shows URLs directly in the result list
sharepoint-cli search --query "budget"

# Or extract URLs programmatically
sharepoint-cli search --query "budget" --output json \
  | jq -r '.data.results[] | "\(.document.title // .title)\t\(.url)"'
```

### Step 3: Retrieve Content

```bash
# Get the full text content of a document
sharepoint-cli file get --file-url <url-from-search>

# Limit content length for large documents
sharepoint-cli file get --file-url <url> --max-length 2000
```

### Step 4: Inspect Metadata and Permissions

```bash
# See title, type, owner, dates, and permission breakdown
sharepoint-cli file metadata --url <url-from-search>
```

Metadata output includes:
- **Title, Type, Owner** — basic file info
- **Created/Updated dates** — when the file was created and last modified
- **Owners** — users with full control
- **Contributors** — users with edit access
- **Viewers** — users with read-only access

## Paginating Through Results

If there are more results than one page:

```bash
# First page
sharepoint-cli search --query "project" --output json > results.json

# Check if more results exist
jq '.data.hasMoreResults' results.json

# Get next page using cursor
CURSOR=$(jq -r '.data.cursor' results.json)
sharepoint-cli search --query "project" --cursor "$CURSOR"
```

## Tips

- **Search indexes content** for Office docs and PDFs — not just filenames
- **Use `--limit`** to control how many results per page (default 3)
- **Check metadata before reading** to confirm you have the right file
- **Broad queries may fail** — use specific terms rather than very common words

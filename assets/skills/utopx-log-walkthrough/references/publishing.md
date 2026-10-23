# Publishing and recording a page

## 1. Publish

- Publish the fragment the build wrote with `--out` (a page without `<html>`/`<head>`; the
  Artifact tool wraps it), not the standalone copy. Load skill `artifact-design` first if the
  session has not, as the Artifact tool requires; the page already follows its contract (title,
  tokens, light and dark, Google Fonts only, no external scripts).
- First publish: icon `chart`, a one-sentence description naming the feature and the run.
- Keep the fragment in the session's scratchpad under one name per page; republishing the same
  path updates the same URL.
- A page published in an earlier conversation: find its URL (Tracking.md, or the Artifact
  list), read it with the Artifact tool, then publish with that `url`.
- Pages are private; Peter decides whether to share one.

## 2. Record

In the task directory, in the same step as the publish (skill `markdown-docs`):

- `reports/<name>.html`: the standalone copy (`--standalone`), with its md5 in the Ledger entry.
- `Tracking.md`: one row per page with the Artifact link, the standalone file, the log, the
  run-info file, the build command, and the version.
- `Ledger.md`: an entry with the build command, the step count and left-out steps, the check
  result, the golden diff against the previous version, the md5, and the Artifact version.
- The log and its `<stem>.runinfo.json` stay in the task's `logs/`; the page cites the log.

## 3. Versions

A rebuilt page replaces the published one only when Peter wants it. Report what the golden
diff shows (the changed regions) and ask before republishing a page Peter is presenting from.

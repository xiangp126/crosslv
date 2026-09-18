# Codex adapter

Read the sprint resource with:

```text
read_mcp_resource({server: "nvidia-redmine", uri: "redmine://projects/103/sprints"})
```

If that URI is not known to the session, call `list_mcp_resources` for `nvidia-redmine` first
and use the returned URI exactly. If the server is unavailable, follow the REST fallback
referenced by the shared skill.

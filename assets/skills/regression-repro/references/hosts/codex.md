# Codex adapter

Use `ssh` directly. If Codex permissions require approval, request approval for the exact
host-scoped command or a suitably narrow `ssh` prefix. Do not rename or wrap `ssh` to bypass the
permission model.

Start a test as a long-running exec session, retain its session id, and poll that same session.
Do not launch another run just because output is quiet. Use a named tmux pane or another external
supervisor when a job must survive a Codex restart. Follow skill `noga-lock` for long watches.

# Codex adapter

- **SSH:** use `ssh` directly. If Codex permissions require approval, request it for the exact
  host-scoped command or a suitably narrow `ssh` prefix. Never rename or wrap `ssh` to bypass the
  permission model.
- **Test runs:** start the test as a long-running exec session, retain its session id, and poll
  that same session. Do not launch another run just because output is quiet.
- **Jobs that must survive a Codex restart:** use a named tmux pane or another external
  supervisor.
- **Long watches:** follow skill `noga-lock`.

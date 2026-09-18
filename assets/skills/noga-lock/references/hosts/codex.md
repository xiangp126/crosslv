# Codex adapter

Start `noga_wait.sh` as a long-running exec session, retain its session id, and poll that same
session instead of starting another watcher. Chain provisioning with `--then`.

If the watch must survive a Codex restart, put it in a named tmux pane or another external
supervisor. After a restart or resume, verify both the process and heartbeat-log mtime before
trusting it.

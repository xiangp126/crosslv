# Codex adapter

Start `noga_watchdog.sh <box> --until-locked` as a long-running exec session, retain its session id,
and poll that same session instead of starting another watcher. Nothing wakes you when it ends:
report the grab at the first poll that shows `LOCK_ACQUIRED`.

If the watch must survive a Codex restart, put it in a named tmux pane or another external
supervisor. After a restart or resume, verify both the process and heartbeat-log mtime before
trusting it.

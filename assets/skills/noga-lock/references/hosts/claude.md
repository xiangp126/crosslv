# Claude Code adapter

For a wait that must outlive an ordinary Bash tool timeout, use Claude Code's persistent
monitoring facility when available. Keep one watcher, make it persistent, and chain provisioning
through `noga_wait.sh --then` so acquisition and setup remain one operation.

Session commands such as `/model` may end a managed background task. After a model switch or
resume, verify both the process and heartbeat-log mtime before trusting the watcher.

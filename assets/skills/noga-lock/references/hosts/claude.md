# Claude Code adapter

Run `noga_watchdog.sh <box> --until-locked` as a Bash background task (`run_in_background`). The
task's exit is what wakes you, and that is the moment to report the grab. Lines the task prints
while it runs wake nobody, so a task that never exits (`noga_watchdog.sh` holding a box) reports
nothing. A `Monitor` streams each output line as an event but expires after at most 30 minutes, too
short for a multi-hour wait. Keep one watcher per box.

Session commands such as `/model` may end a managed background task. After a model switch or
resume, verify both the process and heartbeat-log mtime before trusting the watcher.

# Claude Code adapter

For SSH, use the command allowed by the current Claude Code harness. Some harnesses hard-deny
plain `ssh`; this environment provides `~/.usr/bin/myssh` as a direct link to `/bin/ssh`, with the
same arguments and behavior. Use it only when the normal command is denied; never point it at a
shell wrapper.

For a test run, use Claude Code's background-task mechanism and wait for its completion
notification. For a multi-hour NOGA watch, follow the Claude adapter in skill `noga-lock` and use
persistent monitoring when available. After a model switch or resume, verify process liveness
before assuming the job survived.

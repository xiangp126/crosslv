# Claude Code adapter

- **SSH:** use the command the current Claude Code harness allows. Some harnesses hard-deny plain
  `ssh`; this environment provides `~/.usr/bin/myssh`, a direct link to `/bin/ssh` with the same
  arguments and behavior. Use it only when the normal command is denied; never point it at a shell
  wrapper.
- **Test runs:** use Claude Code's background-task mechanism and wait for its completion
  notification.
- **Multi-hour NOGA watch:** follow the Claude adapter in skill `noga-lock`; use persistent
  monitoring when available.
- **After a model switch or resume:** verify process liveness before assuming the job survived.

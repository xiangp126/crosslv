### Introduction
- I wrote some tools to help me work more efficiently. These tools are mainly used for building, debugging, decoding, searching, connecting, and setting up working environments in the easiest way possible.
- The tools are versatile, though they are primarily written for use in the Fortinet environment. However, they can be easily modified to support other devices.

### Key Tools

| Category   | Language | Tool | Description |
|:----------:|:---------:|:-----------------|-------------|
| Construct  | Bash Script | [jc](#jc)                   | Setting up working environment and links all the following tools                                     |
| Compile    | Bash Script | [jmake](#jmake)             | Building tool for large C projects                                                                   |
| Connect    | Bash Script | [jssh](#jssh)               | Connecting tool for connecting devices via SSH, SSHFS, SFTP, or setting up Wireshark live packet capture |
| Search     | Bash Script | [jr](#jr)                   | Powerful search tool for searching code in large projects                                            |
| Search     | Bash Function | [code](#code)               | Work with `jr` to search and open code in VSCode with  powerful features                          |
| Decode     | Python Script | [jdecode](#jdecode)         | Decode crash reports from Fortinet devices                                                         |
| Debug      | Bash Script | [jdebug](#jdebug)           | Debugging tool for devices running gdbserver                                                         |
| Debug      | Bash Script | [jrun](#jrun)               | Command Runner by sending commands to a tmux pane running an SSH session                             |
| Debug      | Bash Script | [jroute](#jroute)           | Simple script to switch the default route between available gateways                                 |
| Debug      | Bash Script | [jt](#jt)                   | Log file viewer with syntax highlighting                                                             |
| Agents     | Python Script | [jcl](#jcl)               | List, save, restore, refresh, and configure Claude Code and Codex sessions in tmux |
| Agents     | Python Script | [agent-bridge](#agent-bridge) | Let Claude Code and Codex sessions message each other by name or session id |
| Agents     | Python Script | [jskill](#jskill)         | Maintain one skill source shared by Claude Code and Codex |
| Debug      | Python Script | [gdb_tools](#gdb_tools)     | Python tools for visualizing data structures in memory while debugging with GDB                      |
| VM         | Bash Script | [backup_vms](#backup_vms)   | Backup vms and config files                                                                         |
| VM         | Bash Script | [delete_vms](#delete_vms)   | Delete VMs or restore VMs from backups |

### Other Tools

| Tool               | Description                                                                                         |
|:------------------:|:--------------------------------------------------------------------------------------------------|
| [completion](#completion) | Bash completion scripts for all the above tools                                             |

<a id="jcl"></a>
#### [jcl](./nv-tools/jcl)

Manage local Claude Code and Codex interactive sessions without losing their conversation IDs:

```bash
jcl list                                  # both agents; --json for scripting
jcl save                                  # snapshot both agents
jcl show                                  # what the snapshot holds, which of it runs here
jcl restore --agent codex --dry-run        # preview Codex recovery from the snapshot
jcl restore --agent codex
jcl refresh codex --dry-run                # preview restart in the same tmux panes
jcl refresh codex                          # every Codex pane; `all` is both agents
jcl refresh 3:11.1                         # one exact pane, either agent
jcl exit-session all                       # quit both agents, panes stay at the shell
jcl delete -n 01a139e7-7b96                 # what deleting a session for good would do
jcl delete 3:6.1 01a139e7-7b96             # quit if live, then remove its history; asks first
jcl set --agent codex --model gpt-6-astra --effort high
jcl set --effort xhigh --agent codex        # retain each pane's current model
jcl bridge status                          # agent-bridge, given the rest of the line
jcl set --model opus --model gpt-6-astra    # route one model to each agent
jcl set 0:6.2 3:4.1 --model opus --effort max   # only the named panes, either agent
```

`restore` and `set` take `--agent` and default to both agents. `refresh` and
`exit-session` name agents instead: `claude` or `codex` selects every pane of one
agent, `all` every pane of both. `list`, `save`, and `show` always cover both.
`delete` takes no keyword at all: each session is named by its id (8+ leading
characters) or its pane. A live one in a pane is quit first; a Codex session is
then removed with `codex delete`, through Codex Desktop's app-server when that
runs, and a Claude session's transcript and the other files Claude Code keeps
under its id are removed. It is also taken out of the snapshot. It refuses the
calling session, a suspended one, and a live one outside tmux other than a Codex
Desktop thread, and asks before deleting (`-y` outside a terminal).
The default snapshot remains `~/.claude/tmux-snapshot.json`; use `-o` on save and
`-f` on restore for another file. Existing Claude-only snapshots remain readable.

Codex discovery supports open rollout files and thread-writer locks, with optional
read-only state DB metadata (including a custom `sqlite_home`). Headless execs and
subagents are excluded. This targets local TUIs; remote/shared app-server browsing
is not a local interactive session. Codex snapshots retain known model/effort and
custom home settings. `patch-resurrect` adds the proper resume command for either
agent to tmux-resurrect layouts, and every tmux-resurrect save also runs `jcl save`
and `jcl save-auth` (`@resurrect-hook-post-save-all` in [tmux.conf](./track-files/tmux.conf)),
so the snapshot and the MCP token backup are as new as the last save.

`set*` sends slash commands to the TUI and clears the current input line. Codex
effort-only changes require its model/effort footer to be visible; otherwise use
`set --agent codex --model NAME --effort LEVEL`. Unknown/refused commands and
unconfirmed changes return nonzero. `--no-verify` reports only that keys were sent.
The calling agent and suspended sessions are excluded from typing and refresh.

`save-auth`, `restore-auth`, and `fill-auth` continue managing Claude MCP OAuth.
Codex MCP server entries live in `~/.codex/config.toml`. The entries contain
URLs and a header-helper command, never credentials.
`assets/codex/bin/claude-mcp-headers` reads Claude's OAuth tokens or static HTTP
headers at connection time and checks the exact server name and URL. NVIDIA MaaS
servers get an additional URL-pattern check. `claude-mcp-headers --list` prints
active HTTP server names without exposing tokens. OAuth refresh starts in the
background when a token has 15 minutes or less remaining; an expired token can
leave one server unavailable until Claude refreshes it and Codex starts a new
session. These configured servers need no separate Codex authorization or copied
refresh token.

Tests: `python3 -B -m unittest discover -s tests -p 'test_*.py' -v`.

<a id="agent-bridge"></a>
#### [agent-bridge](./nv-tools/agent-bridge)

Lets every Claude Code and Codex session on this host message every other one by
session name. Claude-to-Claude is Claude Code's own cross-session messaging and
is left as it is; this adds Claude-to-Codex, Codex-to-Claude and Codex-to-Codex.
The names are the ones `jcl list` shows - a Codex session is reached by its title, spaces
written as hyphens as in Claude's own session names, so it copies whole - and a
session id from its SESSION ID column works too (the first 8+ characters will do).
The design, the stand-in design it replaced, and how to go back to that one are in
[plans/agent-bridge-claude-codex-messaging.md](./plans/agent-bridge-claude-codex-messaging.md).

```bash
agent-bridge                               # status: the daemon and the Codex sessions it relays for; starts nothing
agent-bridge peers                         # who can be messaged, by name and session id
agent-bridge send --to Explain-ISSI-in-QUERY_ISSI 'text'     # from a Codex or Claude shell
agent-bridge send --to 01a11eb2-382c 'text'                  # the same, by session id
agent-bridge start                         # the daemon again after a stop; send and peers start it too
agent-bridge stop                          # the daemon
agent-bridge restart                       # both, then status
```

`jcl bridge …` runs it with the rest of the line (`jcl bridge -h` is its own help),
all but `send`, which agent sessions run from their own shell.
`peers` takes jcl's look - the colours, the rule, the summary line - and is an
address book: a name, the agent and the session id, with the rare session a
message cannot reach named in the summary; where a session runs and on what is
`jcl list`'s to show. `status` says whether the daemon runs, its log, and the
Codex sessions it relays for, by name and pane. And
`completion/agent-bridge_completion.bash` completes its commands, their options
and the session ids `--to` takes. `send` is the one command a terminal cannot
run: a message goes out as the session whose shell sends it.

- **From a Claude session**: Codex sessions are not in `/list-agents`. Reach one
  with `agent-bridge send --to '<name or id>' '<text>'` from the Bash tool. A Codex
  session's message arrives as `Message from @<codex title>` with a `uds:` address
  to reply to: answer it with `SendMessage` to that address - a reply by name is
  not found. Given another Claude session, `agent-bridge send` prints the `uds:`
  address to hand `SendMessage` instead.
- **From a Codex session**: `agent-bridge send --to '<name or id>' '<text>'`, run
  from its shell (it identifies the sender by `CODEX_THREAD_ID`). A message arriving
  in Codex reads `Message from @<name> - another agent. Reply with: agent-bridge send
  --to ...` above the sender's text; `assets/codex/AGENTS.md` tells Codex to treat it
  as a colleague's request, never as the user's approval.

How it works: into a Codex session, `codex queue`. Into a Claude session, the
daemon writes one line into the session's inbox socket - the socket Claude Code
documents for scripts to post into - in the form `SendMessage` itself writes it.
That form is not documented; it was copied from `SendMessage` byte for byte. The
reply address in it is a socket the daemon keeps for the Codex session sending,
`/var/tmp/agent-bridge-<uid>/r/<session id>.sock`: a `SendMessage` answer to it
comes back to the daemon and is queued into that session, and the address stays
the same across daemon restarts. The message is signed with the Codex session's
name (its title with spaces as hyphens, or `codex-<last 6 of its id>` when it has
none; `-<last 4>` is added when another session already has that name; the title
typed with its spaces still finds it). The bridge adds nothing to the
text itself: a Claude session gets the sender's words in Claude's own envelope, and
a Codex session gets them under that one line. After writing, `send` looks for the
message's id in the recipient's transcript, where Claude Code records each peer
message it delivers, and answers `delivered`, `queued` (the session is busy, or
waiting for its user), `held` (its permission mode keeps messages from other sessions
for its user's approval) or `not confirmed`, with the recipient's Claude Code version -
which is how a Claude Code upgrade that changed the form would show, on its first
message. Claude Desktop runs a Claude Code of its own that updates itself.

The daemon starts on demand, from start, send or peers (`agent-bridge
start` does nothing else), and keeps a reply socket for each live Codex session
that has had a first message, looking every 30 s; it leaves after 15 minutes with
no Codex session and no request. Everything it keeps is in `/var/tmp/agent-bridge-<uid>/`:
its socket and lock, the reply sockets under `r/`, and `daemon.log`. Not `/tmp`,
whose files m-fwdev-167 deletes after two days untouched - a long-running daemon's
socket among them. Nothing cleans `/var/tmp`, so the daemon keeps its log small:
turned over at 256 KB with one `.1` generation kept, two files and 512 KB at most.
Limits:
- the form of the line written into a Claude inbox is Claude Code's own and not
  documented; a change shows as `not confirmed` for an idle recipient;
- Claude Code sends its held/refused receipts only to an address named after the
  sending process's pid in its own socket directory, never to a reply socket here:
  a message held by an explicit `crossSessionInbound: hold` reads `not confirmed`;
- a Codex session that has had no message yet cannot be queued into; `codex queue`
  itself is not in Codex's documentation;
- a Codex session whose last turn was interrupted (Esc), in a terminal or in Codex
  Desktop, holds every queued message until its next typed one and runs them
  right after it. The sender is told: `agent-bridge send` adds a `Held:` line,
  and a Claude sender gets one notice per interruption;
- `codex queue` must reach the shared app-server (`--no-daemon` is refused for it),
  and runs one in-process when none is up - it starts no daemon of its own;
- the bridge tells Claude it prompts for permissions, which it does, so a message
  to a Claude session in bypass-permissions mode is held for approval, as it would
  be between two Claude sessions;
- terminal Codex sessions run with `--no-daemon`, so Codex's own task tools
  between Codex sessions stay off; Codex-to-Codex goes through `agent-bridge`.

<a id="jskill"></a>
#### [jskill](./nv-tools/jskill)

Claude Code and Codex share one canonical tree at `assets/skills`. Each receives the same one link
per shared skill, Claude under `~/.claude/skills` and Codex under `~/.agents/skills`, so both load
exactly the same skills while what a client keeps there itself (Claude Code's synced account skills,
independently installed Codex skills) stays out of the repository.

```bash
jskill list
jskill path noga-lock
jskill add my-skill --description "What it does and when an agent should use it"
jskill add my-host-skill --description "..." --host-adapters
jskill sync --dry-run
jskill sync
jskill check
```

Both agents are instructed by their global files to invoke `skill-maintainer` for any add or
modify request. Shared workflow belongs in `SKILL.md`; genuine runtime-only tool syntax belongs
in `references/hosts/claude.md` or `references/hosts/codex.md`. `jskill sync` refuses to overwrite
unknown directories or links unless `--backup-conflicts` is explicitly requested.

<a id="jc"></a>
#### [jc](./jc)
- Do not use `sh` to run the script on a freshly installed ubuntu.
- Use `bash` cuz `sh` is not linked to `bash` on a freshly installed ubuntu.
```bash
$ git clone https://github.com/crosslv/crosslv.git
$ cd crosslv
$ bash jc
```
```bash
$ jc -h
Usage: jc [OPTIONS]

This script is used to set up the coding environment in my predefined way.

Options:
    -h, --help                      Print this help message
    -n, --no-tools                  Don't install tools
    -d, --debug                     Enable debug mode
    --insecure                      Allow insecure TLS
    --link-clang-format             Link clang-format to current path
    --link-nodejs                   Link nodejs from VsCode Server to current path
    --vnc-start                     Start VNC server
    --vnc-stop                      Stop VNC server
    --vnc,--vnc-restart             Restart VNC server
    --unlock-vnc                    Unlock VNC
    --lock-vnc                      Lock VNC
    --opengrok-start                Start OpenGrok Docker container
    --opengrok-stop                 Stop OpenGrok Docker container
    --opengrok,--opengrok-restart   Restart OpenGrok Docker container
    --opengrok-indexer              Start OpenGrok indexer
    --samba                         Install and configure Samba Server
    --samba-bypass-password         Don't set password for Samba Server again
    --auto-remove                   Remove unused packages
    --update                        Update all packages
    --upgrade                       Upgrade all packages

The following options force updates or re-installation (installed by default):
    --prerequisite                  Force install prerequisites
    --chinese-pinyin                Force Update Rime Pinyin
    --docker                        Force update Docker from Docker PPA
    --wireshark                     Force update wireshark from Wireshark PPA
    --firefox                       Force install firefox from Mozilla PPA
    --clangd                        Force update clangd from Github

Examples:
    jc -h
    jc --link-clang-format $HOME/crosslv

```

<a id="jmake"></a>
#### [jmake](./ftnt-tools/jmake)
`jmake` is a tool to build large C projects with many additional features.
```bash
$ jmake -h
Usage: jmake [OPTIONS]

Build Flags:
    -c, --clean                 Clean the repo (default: false)
    -C, --configure             Run Configure intelligently (default: false)
    -o, --build                 Run build commands (set automatically if any of the [bmjwT] options is set)
    -b, --bear                  Use Bear to generate compile_commands.json (default: false)
    --bear-remove               Remove compile_commands.json (default: false)
    -O, --optimization          Enable optimization (default: false)

Build Options:
    -m, --model                 Set the build model  (default: KVM)
    -j, --jobs                  Set the number of jobs (default: 20)
    -w, --working-dir           Set working directory  (default: /home/xiangp/myGit/crosslv)
    -k, --kernel                Rebuild the kernel (default: false)
    --max-build-attempt         Set the maximum number of build attempts (default: 1)
    -B, --build-target          Set the build target (default: image.out)

Sync Options:
    -t, --target                Set the sync target machine
    -s, --sync-file             Set the sync source file (default: image.out)
    -P, --sync_port             Set the sync ssh port (default: 22)
    -l/-u, --username           Set the sync username (default: admin)
    -p, --password              Set the sync password (default: password)

Other Options:
    -h, --help                  Print this help message

Example:
    jmake -m FGT_VM64_KVM -c -T1 -j4 -b
    jmake -m VMWARE
    jmake -t fgt1 -s FGT_VM64_KVM-v7-build1662.out -l "admin" -p "password" -P 22
    jmake -h

```

<a id="jssh"></a>
#### [jssh](./ftnt-tools/jssh)
`jssh` enables automatic login to devices via SSH, SSHFS, SFTP, or Telnet, with special support for live packet capture using Wireshark/tcpdump.
```bash
$ jssh
Usage: jssh [OPTIONS] Target

Basic Options:
    -h, --help               Print this help message
    -t, --target             The device to connect to
    -l/-u, --username        Username for login (default: admin)
    -p, --password           Password for login (default: password)
    -P, --port               SSH Port to connect to (default: 22)
    -d, --debug              Enable debug mode (-vvv)
    -c, --command            Execute commands remotely without opening an interactive login session
    -C, --wireshark          Live capture packets from the remote device
    --tls-keylog-file        Set the path to the TLS key log file (default: $HOME/.ssl-keys.log)
    --get-system-status      Get the system status of the target device

Forward Options:
    -L, --local-forward      Format: [local_listen_addr:]local_listen_port:target_listen_addr:target_listen_port
    -R, --reverse-forward    Format: [remote_listen_addr:]remote_listen_port:target_listen_addr:target_listen_port
    -J, --jump               The jump server to connect to. Format: user@jumpserver[:port]
    --jump-password          Password for jump server (default: password)

Advanced Options:
    -X, --x11        Enable X11 forwarding
    -v, --vdom       Specify the VDOM (Used for FGT/FPX devices)
    -m, --mount      Mount a remote directory to a local directory using sshfs. Format: [remote_dir:]mountpoint
    -S, --sftp       Connect to the target device via SFTP
    -T, --telnet     Auth to the target device via Telnet
```

<a id="code"></a>
#### [code](./template/code-function.sh)
- `code` has been refactored into a function to modify public variables in place.
- `code` is a wrapper for the `code` command provided by VSCode. It allows you to open files in VSCode with additional features.
```bash
$ code -h
Usage: code [options] <args>

Description:
    A wrapper for the VS Code server CLI, compatible with Cursor remote sessions.
    It finds the CLI for the current editor window and sets the correct IPC socket.
    The reason for this function is to avoid the bug which has never been fixed by Microsoft:
    # Unable to connect to VS Code server: Error in request - ENOENT /run/user/1000/vscode-ipc-*.sock
    https://github.com/microsoft/vscode-remote-release/issues/6997#issue-1319650016
    https://github.com/microsoft/vscode-remote-release/issues/6362#issuecomment-1046458477

    Sample Error message:

    Unable to connect to VS Code server: Error in request.
    Error: connect ENOENT /run/user/1677703415/vscode-ipc-df98ad2d-40c7-4415-af75-e304c3269b89.sock
        at PipeConnectWrap.afterConnect [as oncomplete] (node:net:1611:16) {
      errno: -2,
      code: 'ENOENT',
      syscall: 'connect',
      address: '/run/user/1677703415/vscode-ipc-df98ad2d-40c7-4415-af75-e304c3269b89.sock'
    }

Options:
    -h, --help                       Show this help message and exit
    --debug                          Enable debug mode (set -x)
    --fresh                          Verify this window's hook, choose a live window if needed, and repair the tmux hook
    --version                        Show version information
    --status                         Print process usage and diagnostics information
    --clean                          Clean obsolete IPC sockets for the selected editor
    --connection                     Show the selected editor, CLI, and IPC socket
    -r, --reload                     Reload and update this function from its source file

Commands:
    --install-extension              Install a .vsix extension, overwriting an installed version
    --list-extensions                List the installed extensions with versions
    --locate-shell-integration-path  Print the path to a terminal shell integration script

Example: code --version
         code --debug
         code --install-extension gitlens-13.0.2.vsix

```
Existing shells use `code -r` to reload the function; sourcing the file again is ignored.

<a id="jdecode"></a>
#### [jdecode](./ftnt-tools/jdecode)
```bash
$ jdecode -h
usage: jdecode [-h] [-e EXEFILEPATH] [-i CRASHTXTPATH] [-o DECODEDOUTPUTPATH] [-l LISTSIZE] [-w] [-v {all,middle,backtrace}]

Decode crash reports from FTNT devices v0.2

Examples:
  jdecode --exe ./sysinit/init --crash /data/bugzilla/crash.txt
  jdecode --write
  jdecode -v backtrace
  jdecode --write -v all

options:
  -h, --help            show this help message and exit
  -e EXEFILEPATH, --exe EXEFILEPATH
                        Path to the executable file
  -i CRASHTXTPATH, --input CRASHTXTPATH
                        Path to the crash txt file
  -o DECODEDOUTPUTPATH, --output DECODEDOUTPUTPATH
                        Path to the decoded output file
  -l LISTSIZE, --list-size LISTSIZE
                        Number of source lines gdb will list by default is 3
  -w, --write           Write output to file
  -v {all,middle,backtrace}, --verbose {all,middle,backtrace}
                        Verbose level: all=show all source lines, middle=show middle line only (default), backtrace=show backtrace only (no code)
```

<a id="jdebug"></a>
#### [jdebug](./ftnt-tools/jdebug)
`jdebug` is a tool for debugging Fortinet devices that have `gdbserver` running. It can be easily modified to support other devices.
```bash
$ jdebug
Usage: jdebug [OPTIONS] Target

Options:
    -h, --help           Print this help message
    -w, --worker-type    Worker type(default: worker)
    -d, --debug-port     GDB Server listen port(default: 444)
    -l/-u, --username    Username(default: admin)
    -p, --password       Password(default: password)
    -P, --port           SSH connection port(default: 22)
    -N, --worker-cnt     Set wad worker count(default: -1)
                         0: unlimited, 1: 1 worker to make life easier, N: N workers
    -r, --reboot         Reboot the device
    -s, --silent         Silent mode. Suppress the output of the wad process info
    --select             Select the worker index(default: 0) to attach to if multiple workers are found
    --display-only       Only display the WAD process info without entering the debug session
    -k, --kill           Kill the existing gdbserver process attached to the worker PID
    -T, --max-attempts   Maximum attempt(default: 2)

Example:
    jdebug fgt1
    jdebug fgt1 -k
    jdebug fgt1 -p "123" -N1
    jdebug fgt1 -w algo -d 9229 -l "admin" -p "123"
    jdebug -h
```

<a id="jrun"></a>
#### [jrun](./ftnt-tools/jrun)
```bash
$ jrun -h
Usage: jrun -t session[:window[.pane]] [OPTIONS]

This script sends commands to a specific tmux session, window, and pane.
The target is specified with -t (or with -s/-w/-p), then it sends either a
single command, the lines of a command file, or broadcasts a command to every pane.

Options:
    -h, --help               Print this help message
    -t, --target             Set target as session[:window[.pane]]
    -s, --session            Set session ID (default: )
    -w, --window             Set window ID (default: 1)
    -p, --pane               Set pane ID (default: 1)
    -c, --cmd CMD            Send a single CMD to the target session/window/pane
    -f, --file               Specify command file (default: commands.txt)
    -d, --debug              Enable debug mode with verbose output
    -B, --broadcast CMD      Send CMD to all panes across all tmux sessions

Examples:
    jrun -t log:2.2 --file=/home/xiangp/commands.txt
    jrun -t log -c 'export DISPLAY=:0'        # Uses default window 1 and pane 1
    jrun -t log:2 -c 'export DISPLAY=:0'      # Uses default pane 1
    jrun -t log:2.3 -c 'export DISPLAY=:0'    # Specifies all parts
    jrun --broadcast 'source ~/.bashrc'       # Send to all tmux panes (no -t needed)

Note: always quote multi-word commands, e.g. -c 'export DISPLAY=:0'.

Tips:
    1. Type 'C-x, q' to view the pane number within the tmux window.
    2. Type 'C-x, s' to view the session name in tmux.
    3. Use // to comment out a line in the command file.
    4. Use ! to omit the rest of the commands in the command file.

```

<a id="jr"></a>
#### [jr](./ftnt-tools/jr)
`jr` is a powerful search tool for searching code in large projects. It is a wrapper that takes advantage of the open-source tools `rg`, `fzf`, and the `code` command provided by VSCode.
```bash
$ jr --help
Usage: jr [OPTIONS] [SEARCH_TERM]

This script requires the following dependencies:
- rg (ripgrep)
- fzf (fuzzy finder)
- bat (cat replacement)
- xsel (clipboard manager)
- code/vim

Run this script with the --check-depends option to check if these dependencies are installed.

Options:
    -h, --help               Print this help message
    -r, --rg-only            Only use rg to search, not use fzf
    -k, --kernel             Include the linux kernel source code in the search
    -v, --vim                Open the file with vim (default is code)
    -c, --check-depends      Check if dependencies are installed
    -n, --no-clipboard       Do not use clipboard content as the search term
    --regular-match          Use regular expressions for matching (default is fixed strings)
    -d, --debug              Print debug information

Example: jr wad_tcp_bind
         jr --kernel

```

<a id="jroute"></a>
#### [jroute](./ftnt-tools/jroute)
`jroute` is a simple script to switch the default route between available gateways in a lab environment for a Linux device.
```bash
$ jroute --help
Usage: jroute [OPTIONS] <gateway>

Options:
    -h, --help           Show this help message
    -d, --dry-run        Show what would be done without making changes
    -t, --gateway NAME   Specify the gateway to use (Only available gateways are allowed)
```

<a id="jt"></a>
#### [jt](./ftnt-tools/jt)
```bash
$ jt -h
Usage: jt [OPTIONS] [LOG_FILE]

This script displays and tails log file with syntax highlighting.
By default, it uses $HOME/.gdblog as the log file.

This script requires the following dependencies:
- bat (for syntax highlighting)

Options:
    -h, --help               Print this help message
    -f, --file FILE          Specify the log file to read from
    -l, --language LANG      Set syntax language (default: c)
    -d, --debug              Enable debug mode with verbose output

Example: jt
         jt --language cpp
         jt --log /var/log/messages
```

<a id="gdb_tools"></a>
#### [gdb_tools](template/gdb_tools.py)
A set of Python tools for visualizing data structures in memory while debugging with GDB.

```c
+pl tree
Tree Root: 0x7f320d8b3430, Input: ((struct fg_avl_tree *) 0x7f3204808460)
=== Total nodes found: 19 ===
Tree Visualization (right nodes 'above', left nodes 'below')
0x7f320d8b3430
    ├── 0x7f320d8b24b8
    │   ├── 0x7f320d8b1a68
    │   │   ├── 0x7f320d8b3a60
    │   │   │   ├── 0x7f320d8b26c8
    │   │   │   └── 0x7f320d8b4090
    │   │   └── 0x7f320d8b1960
    │   │       ├── 0x7f320d8b3d78
    │   │       └── 0x7f320d8b3c70
    │   └── 0x7f320d8b42a0
    │       └── 0x7f320d8b3010
    └── 0x7f320d8b3640
        ├── 0x7f320d8b3328
        │   ├── 0x7f320d8b2bf0
        │   └── 0x7f320d8b4cf0
        │       └── 0x7f320d8b3f88
        └── 0x7f320d8b4be8
            ├── 0x7f320d8b49d8
            └── 0x7f320d8b3b68
=== Summary: 19 nodes found ===

(gdb) pl msg
+pl msg
Head: 0x7f3204793d08, Input: ((struct wad_http_proc_msg *) 0x7f3204793cf0)
=== Total nodes found: 7 ===
Raw List Nodes (addresses):
     0x7f3204615e78 => 0x7f3204617e88 => 0x7f3204612bd8 => 0x7f3204615848 => 0x7f3204615338
     0x7f3204617f18 => 0x7f3204617a98
=== Summary: 7 nodes found ===

+pl msg --hhd
Head: 0x7f3204793d08, Input: ((struct wad_http_proc_msg *) 0x7f3204793cf0)
Trying to lookup type: struct wad_http_hdr
=== Total nodes found: 7 ===
=== Node 1/7 ===
List Elem: 0x7f3204615e78, member in container: link
Container: 0x7f3204615e38, ((struct wad_http_hdr *) 0x7f3204615e38)
Field: data, Type: struct wad_sstr
(((struct wad_http_hdr *) 0x7f3204615e38)->data)
{
  buff = 0x7f320dffe710,
  start = 0,
  len = 46
}
++p/s ((struct wad_sstr *)0x7f3204615e38)->buff->data[0]@46
$10 = "last-modified: Thu, 18 Jul 2019 15:04:43 GMT\r\n"

Current pointers:
  next: 0x7f3204617e88 (head: 0x7f3204793d08)
  prev: 0x7f3204793d08
=== Summary: 7 nodes found, 7 nodes printed (in reverse order) ======
```

<a id="completion"></a>
#### [completion](./completion)
All the bash completion scripts for the above tools are under this directory. You can source them in your `.bashrc` or `.bash_profile` to enable auto-completion for the tools.

### License
The [MIT](./LICENSE.txt) License (MIT)

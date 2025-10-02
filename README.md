### Introduction
- I wrote some tools to help me work more efficiently. These tools are mainly used for building, debugging, searching, connecting, and setting up working environments in the easiest way possible.
- The tools are versatile, though they are primarily written for use in the Fortinet environment. However, they can be easily modified to support other devices.

### Key Tools

| Category   | Tool | Description |
|:----------:|:---------:|:-----------------|
| Construct  | [jc](#jc)                   | Setting up working environment and links all the following tools                                     |
| Search     | [jr](#jr)                   | Powerful search tool for searching code in large projects                                            |
| Search     | [code](#code)               | Wrapper for the `code` command provided by VSCode, designed to bypass a long-standing and overlooked bug |
| Compile    | [jmake](#jmake)             | Building tool for large C projects                                                                   |
| Connect    | [jssh](#jssh)               | Connecting tool for connecting devices via SSH, SSHFS, SFTP, or setting up Wireshark live packet capture |
| Debug      | [gdb_tools](#gdb_tools)     | Python tools for visualizing data structures in memory while debugging with GDB                      |
| Debug      | [jdebug](#jdebug)           | Debugging tool for devices running gdbserver                                                         |
| Debug      | [jrun](#jrun)               | Command Runner by sending commands to a tmux pane running an SSH session                             |
| Debug      | [jroute](#jroute)           | Simple script to switch the default route between available gateways                                 |
| Debug      | [jt](#jt)                   | Log file viewer with syntax highlighting                                                             |
| VM         | [backup_vms](#backup_vms)   | Backup vms and config files                                                                         |
| VM         | [delete_vms](#delete_vms)   | Delete VMs or restore VMs from backups                                                              |

### Other Tools

| Tool               | Description                                                                                         |
|:------------------:|:--------------------------------------------------------------------------------------------------|
| [completion](#completion) | Bash completion scripts for all the above tools                                             |

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
    A wrapper script for the VS Code server CLI.
    It finds the VS Code server CLI binary and set the correct IPC socket.
    The reason for this script is to avoid the bug which has never been fixed by Microsoft:
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
    -d, --debug                      Enable debug mode (set -x)
    -f, --force                      Force search for the code binary, ignoring $VSCODE_BIN_PATH,
    -v, --version                    Show version information
    -r, --remove                     Remove obsolete IPC sockets
    -s, --status                     Print process usage and diagnostics information
    --print                          Print core variables
    --install-extension              Forcely install the specified extension from a .vsix file
    --list-extensions                List the installed extensions with versions
    --locate-shell-integration-path  Print the path to a terminal shell integration script

Example: code --version
         code -d
         code --install-extension gitlens-13.0.2.vsix

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
Usage: jrun session[:window[.pane]] [OPTIONS]

This script sends commands to a tmux pane running a FortiGate CLI session.
It allows you to specify a tmux session, window, and pane ID, as well as an optional command file.
You can also send predefined debug commands automatically with simple flags.
The script parses command files and handles various FortiGate debugging scenarios efficiently.

Options:
    -h, --help               Print this help message
    -s, --session            Set session ID (default: )
    -w, --window             Set window ID (default: 1)
    -p, --pane               Set pane ID (default: 1)
    -f, --file               Specify command file (default: )
    -d, --debug              Enable debug mode with verbose output
    -W, --wad-debug          Send WAD debug commands automatically
    -O, --output-directly    Configure console to output directly (no pagination)
    -K, --kernel-debug       Send kernel debug commands automatically
    -T, --packet-trace       Send packet trace commands automatically
    -I, --ips-debug          Send IPS debug commands automatically
    -S, --scanunit-debug     Send scanunit debug commands automatically
    -D, --dns-debug          Send DNS debug commands automatically

Examples:
    jrun --session=log --window=2 --pane=2 --file=/home/xiangp/commands.txt
    jrun log --wad-debug      # Uses default window 1 and pane 1
    jrun log:2 --wad-debug    # Uses default pane 1
    jrun log:2.3 --wad-debug  # Specifies all parts
    jrun log -t --packet-trace-addr=192.168.1.100

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

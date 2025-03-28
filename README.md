### Introduction
- I wrote some tools to help me work more efficiently. These tools are mainly used for building, debugging, searching and connecting to devices.
- The tools are versatile, though they are primarily written for use in the Fortinet environment. However, they can be easily modified to support other devices.

### Key Tools

- [jmake](#jmake)
- [jssh](#jssh)
- [jdebug](#jdebug)
- [jr](#jr)
- [jroute](#jroute)
- [gdb_tools](#gdb_tools)
- [bash_completion](#completion)

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

<a id="jmake"></a>
#### [jmake](./ftnt-tools/jmake)
`jmake` is a tool to build large C projects with many additional features.
```bash
$ jmake
Usage: jmake [-m|--model model] [-w|--working-dir working_dir] [-j|--jobs num_of_jobs]
             [--bear-remove] [--max-build-attempt max_attempt] [-t|--target sync_target]
             [-s|--sync-file sync_file] [-P|--sync-port sync_port] [-l/-u|--username username]
             [-p|--password password] [-B|--build-target build_target]
             [-bcCohkO|--bear --clean --configure --build --help --kernel --disable-optimization]

Build Flags:
    -c, --clean                 Clean the repo (default: false)
    -C, --configure             Run Configure intelligently (default: false)
    -o, --build                 Run build commands (set automatically if any of the [bmjwT] options is set)
    -b, --bear                  Use Bear to generate compile_commands.json (default: false)
    --bear-remove               Remove compile_commands.json (default: false)
    -O, --disable-optimization  Disable optimization (default: false)

Build Options:
    -m, --model                 Set the build model  (default: KVM)
    -j, --jobs                  Set the number of jobs (default: 20)
    -w, --working-dir           Set working directory  (default: /data/fpx)
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
    -C, --wireshark       Live capture packets from the remote device
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

<a id="completion"></a>
#### [completion](./completion-files)
All the bash completion scripts for the above tools are under this directory. You can source them in your `.bashrc` or `.bash_profile` to enable auto-completion for the tools.

### License
The [MIT](./LICENSE.txt) License (MIT)

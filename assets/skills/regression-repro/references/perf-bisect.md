# A performance-degradation ticket: bisect the releases, then confirm the commit

A performance-degradation ticket — a throughput drop, a timeout, a device that hangs under load,
working in one release and broken in a later one — keeps the ticket's three documents
(`ticket-documents.md`) and replaces Phases 6–9 of `procedure.md` with this: find the last good
and the first bad release on the box, then build and test the commits between them.

## 1. Where the results go

| What | Where |
|---|---|
| reported version, last known working, the range to bisect | `Tracking.md` §2 Goal |
| box, DUT, MST device, interfaces, DOCA-OFED, MFT, host OS, Docker image, FW worktree, private image archive | `Tracking.md` §3 Environment, one row each |
| the repro command, verbatim, and the PASS / FAIL criteria (e.g. PASS: no error signature in the container log and `flint q` still answers; FAIL: an error signature, or `flint q` returns `MFE_CMDIF_TIMEOUT_ERR`) | `Tracking.md` §4 Reproduction steps, decided before the first run and never changed across runs |
| the restore point: `flint q full` before the first burn | a `Ledger.md` entry |
| every run: FW version or commit, PASS / FAIL, error signatures, power cycle needed, anomalies, log | a Run log row, written before the next run starts |
| every build: commit, title, result, archived image path | a `Ledger.md` entry |
| the release table (version, runs, result) and the commit table (commit, title, result) | `Defects.md` §6 |
| last good and first bad release, the root-cause commit with author, gerrit change and reviewers, confidence and its basis | `Defects.md` §3 |
| the mail that reassigns the ticket to the commit's author | `drafts/<what>_<to whom>_draft.txt` until it is sent (skill `markdown-docs`, "Files") |

## 2. Local or remote

- **Local** — run on the test server itself, no ssh wrappers. Only when no run needs a power
  cycle: the server cannot power cycle itself and keep the session.
- **Remote** — drive the test server from the dev box when runs need a power cycle. The power
  cycle is of the test server, never of `m-fwdev-167` (CLAUDE.md hard rule 5). A device stuck
  during a local session means switching to remote.

One ssh control socket for the whole session; a power cycle breaks it, so open it again once the
server is back:

```bash
ssh -o BatchMode=yes -fNM -S /tmp/<hostname>.sock pexiang@<hostname>                  # open once
ssh -o BatchMode=yes -S /tmp/<hostname>.sock pexiang@<hostname> '<command>'           # every command
ssh -o BatchMode=yes -S /tmp/<hostname>.sock -O exit pexiang@<hostname>               # close
```

The commands below are the local form; remotely each runs through the socket, with `jmake` as
`$HOME/.usr/bin/jmake`. `sudo` is needed for `flint`, `mst` and every firmware operation.

## 3. Before the first burn

Record the current firmware as the restore point:

```bash
sudo flint -d <device> q full
```

## 4. Release-level bisection

Burn an official release, or a private image (`-w` names the golan_fw worktree):

```bash
jmake --burn-official <version> --device <device> --fw-reset
jmake --burn --firmware <image_path> --device <device> --fw-reset -w <golan_fw_path>
```

Each run, in this order:

1. Remote only: power cycle the server (`sudo ipmitool power cycle` through the socket), wait for
   it, check `uptime` to confirm it really rebooted, open the socket again. Runs that need a fresh
   boot get one before every test.
2. Check the device: `sudo mst restart && sudo flint -d <device> q | head -3`.
3. Burn the image.
4. Check that the running FW version is the expected one: `sudo flint -d <device> q | head -3`.
5. Run the repro command exactly as recorded. Detached, for unattended runs:

```bash
sudo docker run --rm -d --privileged --net=host <all repro flags> <docker_image> /entrypoint.sh
```

6. After the test window, read the errors and check the device:

```bash
sudo docker logs <container_id> 2>&1 | grep -iE "CRITICAL|ERROR|Failed|TIMEOUT"
sudo flint -d <device> q | head -3
sudo docker stop <container_id>
```

7. Write the Run log row before starting the next run.

A run that leaves the device stuck — `flint q` fails, for example with `MFE_CMDIF_TIMEOUT_ERR` —
needs a power cycle before the next run: remote, step 1; local, switch to remote.

## 5. Commit-level confirmation

Build in the ticket's worktree off `golan_fw2` (`procedure.md` Phase 4), never in a clone's own
checkout and never in `/tmp`. The images go to an archive directory on NFS, so the test server
reads them. One commit at a time:

```bash
git -C <golan_fw worktree> reset --hard <commit_id>
jmake -w <golan_fw worktree> -m <target> --patch
mv <build_output>.mlx <archive_dir>/fw-<device>-<commit_id>.mlx      # mv, not cp: the next build overwrites it
```

Test each image with the run procedure of section 4.

The root-cause commit is the first bad one: commit N PASS and commit N+1 FAIL make N+1 the root
cause. Test the suspect and the commit just before it first; when the suspect fails and the one
before passes, confirm with one more commit below and one above the boundary.

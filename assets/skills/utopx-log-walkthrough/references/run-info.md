# Run facts

The page header names the run: result, box and functions, FW, utopx and udriver, seed and
iterations, the log. `scripts/wt/runinfo.py` collects them from three sources.

## 1. Sources and precedence

| Source | Where | Gives |
|---|---|---|
| the log | the log itself | utopx command line (`--seed`, `--iter`, `--ops_per_it`, `--xml_conf_file`, `--conf_file`, `-e` options, `--device`), device name from `mt<id>`, FW version (`fw version is: ...`), udriver version as printed (`udriver version 3.9` means 3.09), the functions (VHCA, GVMI, PCI address), the verdict |
| the per_run record | `<stem>.out` beside the log (written by `per_run.sh` of skill `regression-repro`) | box, start time with its zone, utopx tree hash, FW version |
| the run-info JSON | `<stem>.runinfo.json` beside the log, or `build --run-info FILE` | what neither of the others has: the FW build and its changes, the utopx tree with its changes, the udriver build, the start time in CST |

A fact found in several sources is taken from the log first, then the record, then the JSON.
The JSON only fills keys the other two leave empty, plus the description keys only it has.
The build prints `run facts from ...` with the files it read.

## 2. JSON keys

All keys are optional; a missing one shows as "not recorded" on the page.

| Key | Shown as | Example |
|---|---|---|
| `box` | Box | `l-fwreg-012` (when there is no `.out`) |
| `fw` | FW | `40.51.0299 + <a href="{g}1519292">1519292</a> PS10 (local build 442a6a61066), PSF on in the INI` |
| `utopx` | utopx | `psf-track 4a3a81d5dc, the content of <a href="{u}1533759">1533759</a> PS4, no local change` |
| `udriver` | utopx line, udriver step note 1 | `{"text": "3.09 (717c5fb; the log prints 3.9)", "version": "3.09", "artifact": "717c5fb"}` |
| `run` | Run | `2026-10-23 17:29 CST (box clock 12:29 IDT)` |
| `trees` | every source line the story cites | see section 2a |

- `fw` and `utopx` are HTML. `{g}` expands to the golan_fw gerrit change URL prefix and `{u}`
  to the utopx one, so `<a href="{g}1519292">1519292</a>` links the change.
- Take every value from a record of the run (the Ledger entry, the Run log row, the build log),
  never from memory. A local build is named by its local SHA; a gerrit change by number and
  patchset.
- `assets/runinfo.example.json` is a template with placeholder values.

## 2a. Trees: where the cited source lines are found

```json
"trees": {
  "golan_fw": {"path": "/auto/fwgwork1/<user>/golan_fw-psf", "commit": "<full sha of the FW build>",
               "changes": [{"change": 1537640, "ps": 1, "commit": "<the patchset's sha, optional>"}]},
  "utopx": {"path": "/auto/fwgwork1/<user>/utopx-psf", "commit": "<full sha>",
            "patch": "/auto/fwgwork1/<user>/bugZilla/<task>/patches/<run stamp>.diff"}
}
```

- `path` is a local git tree that holds `commit`; `commit` is the commit the FW image was built
  from, or the utopx tree the binary was built from (the Run log row has both).
- `patch`: the `git diff` the run's tree had on top of `commit` (uncommitted changes); the lines
  are found in the file with the patch applied.
- `changes`: gerrit patchsets the build contains. They give the link when the server has no
  commit with the run's copy of the file.
- Links (`scripts/wt/coderefs.py`): the run's own file when a commit the server has holds it
  (gitiles, or gerrit's file view of a listed patchset); otherwise the same code in a server copy
  (dotted underline, the tooltip says which commit and line); otherwise no link, the line number
  only. A local build that is not on the server gets exact links only after its commits are
  pushed where the server shows them; that is Peter's call.
- A missing tree: the page names the file without line numbers. A line the tree does not have:
  the build stops. Neither is ever replaced by a guessed number.

## 3. What does not go into run facts

History and status that age (a ticket's priority, how many seeds of an earlier batch failed,
which box has which problem) are not run facts. A story may state feature history that stays
true (a change fixed a rejection), with its gerrit or Redmine link.

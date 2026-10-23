# The PSF story

Story `psf` (`scripts/stories/psf/`) walks one run of the PSF ICM global mode feature: the PSF
(page supplier function) brings itself up and hands FW one or more ranges of host memory as a
pool; the PFs come up as consumers and get their ICM from that pool inside the device; at
teardown the PFs go first and the PSF last. It applies to any debug log with a PSF function
(`match()`).

## 1. Steps

Built in log order by the builders in `steps.py`; four flows follow the FW slides
*PSF ICM global mode executive refresh*.

| Flow | Step id | Shows | Left out when |
|---|---|---|---|
| 1 | `psf-enable` | the PSF's ENABLE_HCA, `function_id 0` | no ENABLE_HCA from the PSF |
| 1 | `psf-issi` | QUERY_ISSI and SET_ISSI: the command interface version, before any page command | no QUERY_ISSI or SET_ISSI from the PSF |
| 1 | `psf-query-pages` | boot QUERY_PAGES: `icm_mng_global`, boot page count | no QUERY_PAGES from the PSF |
| 1 | `psf-udriver` | udriver maps the first range as one IOVA window (split off `psf-range-1`) | the range's allocation lines are missing |
| 1 | `psf-range-1` | the first PROVIDE_PAGES_RANGE: start address and page count | no range |
| 1 | `psf-ranges` | the further ranges and their replies | the run sends one range |
| 1 | `psf-caps` | QUERY_HCA_CAP max, SET_HCA_CAP, QUERY_HCA_CAP cur; `page_request_disable`, `icm_mng_function_id_mode` | the capability commands are missing |
| 1 | `psf-init` | the PSF's INIT_HCA, READY | no INIT_HCA from the PSF |
| 2 | `pf-enable` | every PF that sends ENABLE_HCA; PFs running as NODNIC are named | no PF sends ENABLE_HCA |
| 2 | `pf0-boot-pages`, `pf0-init` | PF0's boot and init QUERY_PAGES (chosen by `op_mod`), MANAGE_PAGES, INIT_HCA | PF0 lacks them |
| 3 | `pf0-regular` | PF0 READY, regular QUERY_PAGES | PF0 lacks it |
| 3 | `page-request-eq` | the page-request EQ a PF creates | no such CREATE_EQ |
| 3 | `no-page-request` | the per-iteration page-request checks and the event types read | no check lines |
| 4 | `pf0-teardown`, `pf0-reclaim`, `pf0-disable` | PF0's TEARDOWN_HCA, its empty reclaim, the PFs' DISABLE_HCA | PF0 lacks them |
| 4 | `psf-teardown` | the PSF's TEARDOWN_HCA after the last PF DISABLE_HCA | no TEARDOWN_HCA from the PSF |
| 4 | `psf-disable` | the PSF's DISABLE_HCA and FW's answer (1533759 PS4 runs) | no DISABLE_HCA from the PSF |
| 4 | `psf-return`, `psf-no-disable` | the PSF's return of its pages and the skipped DISABLE_HCA (runs with the local workaround) | no return command |
| last | `run-fails` (engine) | what utopx dropped before the FATAL, the FATAL, MAIN_FATAL, test status | the run passed |

The steps follow PF0; the other PF's lines are in the folds between steps, and flow 2 has a
side-by-side table of both PFs when two PFs enable themselves.

## 2. Variants of the end of a run

`statements.variant(f)` decides the flow 4 introduction and some statements:

- `wa`: the PSF returns its pages (a RECLAIM MANAGE_PAGES from the PSF); utopx carried a local
  change that skips the PSF's DISABLE_HCA.
- `ps4`: no return; the PSF's DISABLE_HCA follows its TEARDOWN_HCA (utopx 1533759 PS4). FW
  accepts it only with golan_fw 1537640.
- `stopped`: neither; the run stops after the PSF's TEARDOWN_HCA (a failed run).

## 3. Read before publishing a PSF page

- The `left out` lines of the build: one range, a PF running as NODNIC or a run that stopped
  early explain a missing step; anything else is a parser or builder problem to fix.
- Step `psf-ranges`: every further range accepted. Its first note says a second range is
  rejected with `0xFF2C2D` without golan_fw 1519292; check that the FW of the run has it when
  the ranges are accepted.
- Step `psf-teardown` and the flow 4 text: they must match the variant (section 2).
- The statements table: a verdict "Seen" must follow from the log; a statement whose step is
  missing shows "Not in this run" with the reason.
- The failure step of a failed run: the dropped commands and the FATAL must be the first
  failure in the log, not a consequence of an earlier one.
- The source lines: every one the page cites is resolved from the run's `trees`
  (`stories/psf/refs.py`: the pool reclaim, the global-mode branch of `psf_teardown_hca()` and the
  pre-init DISABLE_HCA path in golan_fw; the reclaim request, the range checks and the random
  draws in utopx's `CmdManagePages.cpp` and `common_constraints.conf`). The build prints
  `source lines: ...` when a tree is missing; publish only with both trees given. When a cited
  function changed so that its anchor no longer matches, the build stops: update the anchor in
  `refs.py` to the new code and re-read the sentence that cites it.

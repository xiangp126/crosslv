---
name: utopx-log-walkthrough
description: >-
  Turn one utopx debug log into an animated, self-checking HTML walkthrough page and publish
  it as a private Artifact: a sticky stage that replays every command for each function, the
  real log lines with numbered notes under the line they explain, a run map, and a table that
  checks the feature's design statements against the log. Numbers are computed from the log,
  FW behavior is labeled as code, failed runs end in a failure step. A generic engine plus
  the PSF ICM global-mode story, which is the template for other features. Use when Peter
  says create a walkthrough demo or walkthrough page for a log or a run, asks to regenerate,
  update, check, screenshot or publish the PSF Log Walkthrough or another log walkthrough,
  asks for a presenter talk track for one, or wants a walkthrough story for a new feature.
---

# utopx log walkthrough pages

One utopx debug log becomes one page: a stage that replays the commands of each function, the
real log lines of every step with numbered notes under the line they explain, a run map, and
a table that checks the feature's design statements against the log. The page is a fragment
published with the Artifact tool; a standalone copy stays in the task's `reports/`.

Code: `scripts/walkthrough.py` (commands `build`, `check`, `golden`), the engine in
`scripts/wt/` (log parser, step cards, stage frame and script `stage.js`, run map, failure step,
run facts, source-line resolver, checks), one story per feature in `scripts/stories/<name>/`
(steps, statements, the device side of the stage, the source lines it cites). The PSF ICM
global-mode story (`stories/psf`) is the only story so far and the template for new ones. Unit
tests on synthetic logs: `cd ~/myGit/crosslv/assets/skills/utopx-log-walkthrough && python3 -B -m
unittest discover -s tests`.

```bash
W=~/myGit/crosslv/assets/skills/utopx-log-walkthrough/scripts
python3 $W/walkthrough.py build LOG --out FRAG.html --standalone PAGE.html [--run-info RUN.json] [--story psf]
python3 $W/walkthrough.py check PAGE.html --log LOG
python3 $W/walkthrough.py golden OLD.html NEW.html
$W/shots.sh PAGE.html OUTDIR WIDTH stage|card STEP_ID...
```

## 1. "Create a walkthrough demo for <log>"

1. **The log must be debug level**: the utopx command line carries
   `--xml_conf_file debug_conf.xml`, so the log has the command dumps (`LOG_KEY_CMDIF`). The
   build refuses any other log with exit code 2 and says so; ask Peter for a debug run instead
   of building from a partial log. The log lives in the task's `logs/` (copy it there first);
   the page cites it.
2. **Run facts**: the build reads the log (command line, FW version, udriver version, functions,
   verdict), then `<stem>.out` beside it (the `per_run.sh` record: box, start time, utopx tree),
   then `<stem>.runinfo.json` beside it (or `--run-info`) for what neither has: the FW build and
   its changes, the utopx tree and local patches, the udriver build, the start time in CST, and
   `trees`: the local tree and commit of golan_fw and utopx the run used (plus the uncommitted
   patch, if any), from which the source lines the story cites are resolved. Take these values
   from the run's Ledger entry or Run log row; leave a key out rather than guess, and the header
   says "not recorded". Format and rules: `references/run-info.md`.
3. **Build** into the scratchpad (fragment) and the task's `reports/` (standalone copy). The
   build prints the step count, every step it left out with the reason (`left out <builder>:
   <why>`), the files the run facts came from, and `source lines: ...` when a tree is missing (the
   page then names the file without line numbers; `--strict` refuses that). A cited line that the
   run's tree does not have stops the build (`source line not found: <name>`). Read the left-out lines: each must be
   explained by the run (one range, PF1 running as NODNIC, a run that stopped early), not by a
   parser miss.
4. **Check**: `walkthrough.py check PAGE --log LOG` must report 0 errors. It verifies the links,
   the page data, the script syntax (node), note order, that every shown line says what the log
   says, that every fold names the commands it hides, and that every `file:line` in the page text
   was resolved from a tree or comes from the log. Read each warning.
5. **Read the page as its reader** before publishing: every note against its marked lines, the
   statements table (each verdict must follow from the log), the flow introductions, the
   failure step if the run failed. What to look at per story: `references/story-psf.md`. A
   wrong sentence is fixed in the story code and the page rebuilt; never edit the HTML output.
6. **Screenshots**, looked at one by one: the stage at the first step of each flow, the udriver
   and run steps, the last step; one or two step cards; one shot at 390 px width.
   `references/verification.md` has the commands and what to look for.
7. **Publish** the fragment (`--out`, not the standalone file) with the Artifact tool, icon
   `chart`. Republishing the same fragment path keeps the URL; a page from an earlier
   conversation is updated by passing its `url` after reading it. `references/publishing.md`.
8. **Record** in the task directory, in the same step: the standalone copy and its md5 in
   `reports/`, the page's row in `Tracking.md` (Artifact link, standalone file, log, run-info
   file, build command), and a `Ledger.md` entry (skill `markdown-docs`).

## 2. Rules

- **A question about the page is not a change request.** Answer it from the log and the code;
  change the page only when Peter asks for a change, and say what will change before doing it.
- **Every number comes from the log.** Story text never carries a literal count, size, address,
  time or version: the builder computes it from the log or the run facts. A sentence whose
  claim the log does not show (FW internals, history) says where it comes from ("FW code, not
  in the log", a gerrit change, a ticket) and cites the source line.
- **Source lines are never typed.** The story names a line by its code (`CodeRef` in its
  `refs.py`) and writes `[[ref:<name>]]`; the build finds it in the run's tree and links it. The
  link opens the run's exact file when its commit is on the server, the same code in a server
  copy otherwise (dotted underline), and nothing when no server copy has it.
- **A step the log cannot show is left out, never faked.** Builders raise `Skip(reason)`; the
  statements table then shows "Not in this run" with that reason.
- **Talk track only on request**: a presenter script in Chinese, in the reply, never on the
  page. Structure: `references/talk-track.md`.
- **Optional peer review**: send another session the standalone path, its md5 and the golden
  diff against the previous version; it reviews against the log and replies with findings.
  Apply fixes in the story code, rebuild, and send the new md5.

## 3. Changing a published page, the engine or a story

1. Run the unit tests; then rebuild the published page from its own log into the scratchpad.
2. `walkthrough.py golden <published standalone> <rebuilt standalone>`: every difference in
   the visible text and the page data must be one you meant to make. An engine or story change
   that is not meant to change a page must report "same text and data" for every published page.
3. Then build, check, screenshot and publish as in section 1.

## 4. A walkthrough for another feature

Write a new story in `scripts/stories/<name>/` and add the name to `NAMES` in
`scripts/stories/__init__.py`. A story writes only its own parts: the step builders, the
statements, the device side of the stage (`scene_parts` and a `story.js` with the hooks the
engine's stage script calls), its `story.css`, and the source lines it cites. The engine's files
are not copied. `references/new-story.md` lists every hook and what it must return; `stories/psf`
is the worked example. Add a synthetic log shape for it to `tests/synth.py` and tests to
`tests/`.

## References

- `references/run-info.md`: the three sources of run facts, the JSON keys, precedence.
- `references/story-psf.md`: what the PSF story shows, the log shapes it handles, its variants,
  what to read before publishing a PSF page.
- `references/verification.md`: check, golden, screenshots, the review loop.
- `references/publishing.md`: Artifact publishing, updating, recording.
- `references/new-story.md`: the story interface for a new feature.
- `references/talk-track.md`: how to write the presenter talk track.
- `assets/runinfo.example.json`: a run-info file with placeholder values.

# Verifying a page

## 0. Unit tests

```bash
cd ~/myGit/crosslv/assets/skills/utopx-log-walkthrough && python3 -B -m unittest discover -s tests -v
```

Synthetic logs (`tests/synth.py`) in every shape the PSF story handles: passed with the PSF's
DISABLE_HCA accepted, with the local workaround, one range, PF1 as NODNIC, stopped with a FATAL,
DISABLE_HCA refused, across midnight, a non-debug log. They check the parser (dumps, ANSI,
interleaved GEN/EXE/VER threads, the checker's copies, sub-op opcodes), the steps built and left
out, the computed captions and stage, the failure step, the source-line resolver and its links,
and that `check` catches a changed line, a wrong fold and a typed source line. Run them before
and after any change to the engine or a story.

## 1. check

```bash
python3 $W/walkthrough.py check PAGE.html --log LOG
```

Errors make the page unfit to publish: a dangling `#` link, page data that does not parse or
does not match the step cards, a step without choreography or caption, a script that does not
parse (`node --check`), a shown log line whose text is not in the log, a fold whose line count
or command count differs from the log, a `file:line` in the page text that was not resolved from
the run's tree (or does not come from the log, such as the FATAL's source line). Warnings: a note under no marked line, notes out of
line order, CJK characters in the page text. Fix each in the story code and rebuild.

## 2. golden

```bash
python3 $W/walkthrough.py golden OLD.html NEW.html
```

Compares the visible text region by region (title, hero, stage, summary, each flow head, each
step, each gap, footer) and the page data. It prints a unified diff per changed region and
exits 1 when anything differs. Use it whenever the engine or a story changes: rebuild every
published page from its log and compare with its published standalone copy; every reported
difference must be one you meant to make.

## 3. Screenshots

```bash
$W/shots.sh PAGE.html OUTDIR 1440 stage psf-enable psf-udriver no-page-request psf-teardown
$W/shots.sh PAGE.html OUTDIR 1440 card pf-enable
$W/shots.sh PAGE.html OUTDIR 390 stage psf-range-1
```

Headless Firefox with reduced motion, so the stage shows each step's end state. `stage` opens
the page at a step (`#go-<step id>` on a copy whose header is hidden) and shoots the stage;
`card` shows only that step's card. Files: `OUTDIR/<mode>_<step id>_<width>.png`. Look at every
image with the Read tool:

- the stage: each function's HCA stage chip, the request and reply labels (no overflow), the
  pool bar and its legend, the global-mode lamp, the pass or fail banner at the last step;
- a card: notes sit right under their marked lines, the function tags on command lines, folds
  labelled with the commands they hide;
- 390 px: nothing scrolls sideways except the tables and log blocks inside their own scroll
  areas.

## 4. Peer review

Optional, for a page that will be presented. Send another session the standalone path, its
md5, the log, and the golden diff against the last published version; ask for findings against
the log only. Reply to each finding with the fix (story code, rebuilt page, new md5) or the
reason it stays.

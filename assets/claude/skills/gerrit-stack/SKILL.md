---
name: gerrit-stack
description: Push a stack of dependent commits to gerrit (git-nbu.nvidia.com) as one atomic submission using topics RELATED_CHANGES and IGNORE. Use when pushing more than one commit at once, when the CI stage "Related Changes Check" fails, when a change has related/child changes, when propagating a multi-commit series to an ES or review branch, or when deciding how to collect +2 votes on a chain.
---

# Pushing a stack of dependent changes (gerrit topics)

Pushing a chain — `git push origin <tip>:refs/for/<branch>` — creates one change per commit and
gerrit records the parent/child dependency. That alone guarantees **order** (a child can never
merge before its parent) but **not atomicity**: by default each change gets its own CI round and
its own submission, so a 4-deep stack costs 4 CI rounds spread over days.

## Set the topics — this is mandatory, not an optimisation

```bash
for c in <lower changes>; do
  ssh -p 12023 git-nbu.nvidia.com gerrit set-topic $c --topic IGNORE
done
ssh -p 12023 git-nbu.nvidia.com gerrit set-topic <top change> --topic RELATED_CHANGES
```

Setting a topic creates no patchset and outdates no vote.

The CI runs `fw_automations/ci/utopx/scripts/check_for_related_changes.py` in a stage called
**`Related Changes Check`**, and it fails the build unless one of these holds:

- the top change's topic contains `RELATED_CHANGES` **and** every related change's topic
  contains `IGNORE`; or
- there are no related changes at all (the stack was rebased apart).

Its own error text: *"Your change has related changes, but the topic in your top change doesn't
contain RELATED_CHANGES … if not please rebase and break the related changes chain"*.
Reference: `https://confluence.nvidia.com/display/FW/Setting+The+Gerrit+Topic`

Once the topics are in place, `submission_id` becomes `<topChangeNum>-RELATED_CHANGES` and every
change in the stack carries that same id with an identical `submitted` timestamp — verified on
`fw_ver/utopx` with `1467618 + 1455654/55/56` and with `1463162 + 1463160/61`.

## The measurement that settles the argument

Same four-deep stack, same commits, same reviewers, pushed to two branches on 2026-08-13:

| | topics set | outcome |
|---|---|---|
| review branch | no | 3 separate CI rounds, 3 submissions, spread over two days |
| ES branch | yes | **one CI round, all four merged the same day** |

The only difference was the topics.

## Habits that go with it

- **Collect every `+2` at once.** Voting does not merge anything; submission does, and
  submission respects the chain. There is no risk in approving a whole stack in one pass.
- **Stop hand-editing the stack once votes are in.** When a parent merges, gerrit rebases the
  children automatically and copies votes whose copy condition allows it (`TRIVIAL_REBASE` keeps
  them, `REWORK` drops them). A manual rebase to resolve a conflict is a `REWORK` and costs you
  every vote on the stack.
- To find out whether a project ever submits stacks atomically, look at `submission_id` on
  already-merged changes (the REST search returns it; the ssh `gerrit query` output does not).
  `<num>-<topic>` means an atomic stack submit; `submission_id == the change's own number`
  means it went in alone.

## Related

- Message format and cherry-picks → skill `gerrit-change`.
- After pushing: CR+2 must be in place **before** any CI re-run → skill `utopx-ci-rerun`.

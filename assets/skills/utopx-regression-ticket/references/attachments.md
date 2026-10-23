## Attachments — upload as much as you can, this is not optional

Attach as many supporting files as possible, so the next reader does not have to re-extract
everything from the MARS tarball. Template: **[#5273909](https://redmine.nvidia.com/issues/5273909)**
— the ten per-case artifacts of the failing node plus the instrumented repro log and the probe
script, all in the journal of the first comment, each with a description; then
`ROOTCAUSE_analysis.md` in a separate comment.

### The MARS per-case artifact set

The failing `key_id` node itself usually holds only `status.txt`, `log.txt` and one `.cap`. The
artifacts sit in **sibling nodes** of the same case index:

```
0.15.1.1.1.8.1.6.<caseIdx>.2.1/   fw_reset.cap    + log.txt
0.15.1.1.1.8.1.6.<caseIdx>.5.1/   query_mlxconfig.cap + log.txt
0.15.1.1.1.8.1.6.<caseIdx>.6.1/   run_case.cap    + log.txt   <- the failing node
0.15.1.1.1.8.1.6.<caseIdx>.8.1/   dump_file.cap
0.15.1.1.1.8.1.6.<caseIdx>.9.1/   mstdump_1.cap
0.15.1.1.1.8.1.6.<caseIdx>.10.1/  mstdump_2.cap
0.15.1.1.1.8.1.6.<caseIdx>.11.1/  mstdump_3.cap
0.15.1.1.1.8.1.6.<caseIdx>.12.1/  dmesg.cap
0.15.1.1.1.8.1.6.<caseIdx>.13.1/  custom_post_checker.cap
0.15.1.1.1.8.1.6.<caseIdx>.14.1/  oplist.cap
```

**The `.cap` file is MARS metadata (XML), not the artifact.** The real content is the `log.txt`
next to it. Upload that `log.txt`, renamed to the convention:

```
<artifact>_<failing key_id>.log        e.g. query_mlxconfig_0.15.1.1.1.8.1.6.61.6.1.log
```

`scripts/mars_artifacts.sh <setup_id> <session_id> <key_id> <outdir>` does all of it: one `tar`
listing, one `tar` extract of the sibling nodes (no full unpack), the renames, and
`<outdir>/manifest.tsv` with the standard descriptions (`custom post checker`, `dmesg`,
`dump_file`, `fw_reset step`, `mstdump N`, `oplist`, `NV config dump`,
`Failing case log (<case_name>, session <id>)`). It warns about any of the ten that is missing.
The archive is `/.autodirect/sw_regression/host_fw/HCA_CORE_FWV/MARS/conf/results/<setup_id>/<session_id>/<session_id>.tgz`;
it stays for months, but the MARS API forgets the session in about two weeks: record the archive
path as soon as you have it (skill `ci-forensics`).

### Also attach your own work

- `redmine/ROOTCAUSE_analysis.md`, the English analysis, in its own comment (above)
- every arm of an A/B experiment, named so the arm is obvious
  (`AB_arm_A_as_is.log` / `AB_arm_B_*.log` / `AB_arm_C_candidate_fix.log`)
- the candidate patch **and** any patch used only to build an experiment arm — label the latter
  clearly as *NOT a proposed fix*, or someone will merge it
- gzip anything over ~5 MB; plain `.log` otherwise so it renders inline

Give every upload a `description` — the filename alone does not say what the reader is looking at.

### The upload flow (REST)

`scripts/post_ticket.py note --ticket <id> --note <file> --manifest <tsv>` uploads every manifest
row and posts them with the note in one journal, then reads the ticket back. Append your own files
to the manifest as `<file><TAB><description>[<TAB><upload name>]`. The raw flow underneath — two
steps, the token is single-use:

```python
POST {U}/uploads.json?filename=<name>   Content-Type: application/octet-stream, body = raw bytes
  -> {"upload":{"token": "..."}}
PUT  {U}/issues/<id>.json               {"issue":{"uploads":[{token,filename,content_type,description}], "notes":"..."}}
```

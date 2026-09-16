## Attachments — upload as much as you can, this is not optional

**Peter's rule (2026-09-15): attach as many supporting documents as possible.** A ticket with
only a description forces the next reader to re-extract everything from the MARS tarball.
Reference to copy: **[#5232246](https://redmine.mellanox.com/issues/5232246)** — 13 attachments,
all the per-case artifacts of the failing node.

### The MARS per-case artifact set

The artifacts do **not** live under the failing `key_id` itself — that node usually only has
`status.txt`, `log.txt` and one `.cap`. They sit in **sibling nodes** of the same case index:

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

⚠ **The `.cap` file is MARS metadata (XML), not the artifact.** The real content is the
`log.txt` next to it. Upload the `log.txt`, renamed to the reference convention:

```
<artifact>_<failing key_id>.log        e.g. query_mlxconfig_0.15.1.1.1.8.1.6.61.6.1.log
```

Extract with one `tar` call, no full unpack:

```bash
tar tzf <session>.tgz | grep -E "^0\.15\.1\.1\.1\.8\.1\.6\.<caseIdx>\." > /tmp/members
tar xzf <session>.tgz -C /tmp/stage $(grep -E '\.(cap|txt)$' /tmp/members)
```

### Also attach your own work

- the local root-cause markdown
- every arm of an A/B experiment, named so the arm is obvious
  (`AB_arm_A_as_is.log` / `AB_arm_B_*.log` / `AB_arm_C_candidate_fix.log`)
- the candidate patch **and** any patch used only to build an experiment arm — label the latter
  clearly as *NOT a proposed fix*, or someone will merge it
- gzip anything over ~5 MB; plain `.log` otherwise so it renders inline

Give every upload a `description` — the filename alone does not say what the reader is looking at.

### The upload flow (REST)

Two steps; the token is single-use:

```python
POST {U}/uploads.json?filename=<name>   Content-Type: application/octet-stream, body = raw bytes
  -> {"upload":{"token": "..."}}
PUT  {U}/issues/<id>.json               {"issue":{"uploads":[{token,filename,content_type,description}], "notes":"..."}}
```

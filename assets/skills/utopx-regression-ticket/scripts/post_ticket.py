#!/usr/bin/env python3
"""Post a reviewed ticket draft to redmine.nvidia.com through the REST API.

  desc    --ticket N --description FILE [--subject TEXT]
          Replace the description (and the subject). If FILE has no "via YAI Redmine MCP" footer,
          the footer already on the ticket (textile or HTML) is carried over in its HTML form.
  note    --ticket N --note FILE [--manifest TSV]
          Add one comment. Every file listed in TSV is uploaded and attached in the SAME journal.
          TSV lines: <file><TAB><description>[<TAB><upload name>]. Relative paths are taken from
          the TSV's directory; the upload name defaults to the file's basename.
  verify  --ticket N [--subject TEXT] [--description FILE] [--journal ID --note FILE]
          Read only: compare what is stored with the local files.

  --dry-run   show what would be sent; no write requests (GETs still run).

Every write is read back: the stored text must equal what was sent (CRLF-normalised) and the new
journal must carry exactly the uploaded files. Text is sent with CRLF line ends, as the web editor
stores it. The key comes from ~/.redmine_env (REDMINE_API_KEY or REDMINE_TOKEN) and is never
printed; REDMINE_URL overrides https://redmine-api.nvidia.com.
"""
import argparse
import difflib
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

FOOTER_RE = re.compile(r"via YAI Redmine MCP (\[[^\]]*\])")
HTML_FOOTER = '<p><span style="font-size:smaller">via YAI Redmine MCP {}</span></p>'
CTYPES = {".md": "text/markdown", ".gz": "application/gzip", ".tgz": "application/gzip",
          ".html": "text/html", ".png": "image/png", ".jpg": "image/jpeg", ".pdf": "application/pdf"}
TEXT_EXT = {".log", ".txt", ".patch", ".diff", ".py", ".sh", ".tsv", ".csv", ".ini", ".conf", ".xml", ".json"}


def load_env():
    env = {}
    path = os.path.expanduser("~/.redmine_env")
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.replace("export ", "").strip()] = v.strip().strip("'\"")
    for k in ("REDMINE_API_KEY", "REDMINE_TOKEN", "REDMINE_URL"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


ENV = load_env()
KEY = ENV.get("REDMINE_API_KEY") or ENV.get("REDMINE_TOKEN")
URL = (ENV.get("REDMINE_URL") or "https://redmine-api.nvidia.com").rstrip("/")
CTX = ssl._create_unverified_context()      # same as the curl -k used elsewhere in this skill


def die(msg):
    sys.exit("ERROR: " + msg)


def call(method, path, body=None, ctype="application/json"):
    if not KEY:
        die("no REDMINE_API_KEY / REDMINE_TOKEN in ~/.redmine_env")
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    req = urllib.request.Request(URL + path, data=data, method=method,
                                 headers={"X-Redmine-API-Key": KEY, "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=300) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        die("{} {} -> HTTP {}: {}".format(method, path.split("?")[0], e.code,
                                          e.read().decode(errors="replace")[:500]))


def issue(ticket):
    return call("GET", "/issues/{}.json?include=journals,attachments".format(ticket))[1]["issue"]


def norm(text):
    return (text or "").replace("\r\n", "\n").strip()


def crlf(text):
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def same(label, stored, sent):
    if norm(stored) == norm(sent):
        print("OK    {} stored as sent".format(label))
        return True
    print("DIFF  {}:".format(label))
    for line in list(difflib.unified_diff(norm(sent).splitlines(), norm(stored).splitlines(),
                                          "sent", "stored", lineterm=""))[:40]:
        print("      " + line)
    return False


def with_footer(text, current):
    if FOOTER_RE.search(text):
        return text
    m = FOOTER_RE.search(current or "")
    if not m:
        return text
    return text.rstrip("\n") + "\n\n" + HTML_FOOTER.format(m.group(1)) + "\n"


def ctype_of(name):
    ext = os.path.splitext(name)[1].lower()
    return CTYPES.get(ext) or ("text/plain" if ext in TEXT_EXT else "application/octet-stream")


def read_manifest(path):
    base = os.path.dirname(os.path.abspath(path))
    rows = []
    for n, line in enumerate(open(path), 1):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 2 or not cols[1].strip():
            die("{}:{}: need <file><TAB><description>".format(path, n))
        f = cols[0] if os.path.isabs(cols[0]) else os.path.join(base, cols[0])
        if not os.path.isfile(f):
            die("{}:{}: no such file {}".format(path, n, f))
        name = cols[2] if len(cols) > 2 and cols[2].strip() else os.path.basename(f)
        rows.append((f, name, cols[1].strip()))
    return rows


def cmd_desc(a):
    text = open(a.description).read()
    cur = issue(a.ticket)
    text = with_footer(text, cur.get("description"))
    body = {"issue": {"description": crlf(text)}}
    if a.subject is not None:
        if len(a.subject) > 255:
            die("subject is {} chars; Redmine allows 255".format(len(a.subject)))
        body["issue"]["subject"] = a.subject
    print("ticket #{}: description {} chars{}".format(
        a.ticket, len(text), ", subject {} chars".format(len(a.subject)) if a.subject is not None else ""))
    if a.dry_run:
        print("dry run: nothing sent")
        return 0
    st, _ = call("PUT", "/issues/{}.json".format(a.ticket), body)
    print("PUT -> {}".format(st))
    got = issue(a.ticket)
    ok = same("description", got.get("description"), text)
    if a.subject is not None:
        ok = same("subject", got.get("subject"), a.subject) and ok
    return 0 if ok else 1


def cmd_note(a):
    note = open(a.note).read()
    rows = read_manifest(a.manifest) if a.manifest else []
    print("ticket #{}: note {} chars, {} upload(s)".format(a.ticket, len(note), len(rows)))
    for f, name, desc in rows:
        size = os.path.getsize(f)
        warn = "   <- over 5 MB, gzip it" if size > 5 * 1024 * 1024 else ""
        print("  {:>10}  {:<55} {}{}".format(size, name, desc, warn))
    if a.dry_run:
        print("dry run: nothing sent")
        return 0
    before = issue(a.ticket)
    old_att = {x["id"] for x in before.get("attachments", [])}
    ups = []
    for f, name, desc in rows:
        st, js = call("POST", "/uploads.json?filename=" + urllib.parse.quote(name),
                      open(f, "rb").read(), "application/octet-stream")
        if st != 201:
            die("upload {} -> HTTP {}".format(name, st))
        ups.append({"token": js["upload"]["token"], "filename": name,
                    "content_type": ctype_of(name), "description": desc})
    body = {"issue": {"notes": crlf(note)}}
    if ups:
        body["issue"]["uploads"] = ups
    st, _ = call("PUT", "/issues/{}.json".format(a.ticket), body)
    print("PUT -> {}".format(st))
    after = issue(a.ticket)
    new_j = after.get("journals", [])[len(before.get("journals", [])):]
    new_a = [x for x in after.get("attachments", []) if x["id"] not in old_att]
    ok = len(new_j) == 1
    print("{}  new journals: {}".format("OK   " if ok else "DIFF ", [j["id"] for j in new_j]))
    if new_j:
        ok = same("note (journal {})".format(new_j[-1]["id"]), new_j[-1].get("notes"), note) and ok
    got = sorted(x["filename"] for x in new_a)
    want = sorted(u["filename"] for u in ups)
    att_ok = got == want
    print("{}  attachments added: {}/{}{}".format("OK   " if att_ok else "DIFF ", len(got), len(want),
                                                  "" if att_ok else " got {}".format(got)))
    return 0 if (ok and att_ok) else 1


def cmd_verify(a):
    got = issue(a.ticket)
    ok = True
    if a.subject is not None:
        ok = same("subject", got.get("subject"), a.subject) and ok
    if a.description:
        ok = same("description", got.get("description"),
                  with_footer(open(a.description).read(), got.get("description"))) and ok
    if a.journal:
        if not a.note:
            die("--journal needs --note")
        j = [x for x in got.get("journals", []) if x["id"] == a.journal]
        if not j:
            die("journal {} not on #{}".format(a.journal, a.ticket))
        ok = same("note (journal {})".format(a.journal), j[0].get("notes"), open(a.note).read()) and ok
        names = [d["new_value"] for d in j[0].get("details", []) if d.get("property") == "attachment"]
        print("      journal {} attachments: {}".format(a.journal, len(names)))
    print("attachments on #{}: {}".format(a.ticket, len(got.get("attachments", []))))
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    for name in ("desc", "note", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--ticket", type=int, required=True)
        s.add_argument("--dry-run", action="store_true")
        if name in ("desc", "verify"):
            s.add_argument("--subject")
            s.add_argument("--description", required=(name == "desc"))
        if name in ("note", "verify"):
            s.add_argument("--note", required=(name == "note"))
        if name == "note":
            s.add_argument("--manifest")
        if name == "verify":
            s.add_argument("--journal", type=int)
    a = p.parse_args()
    if not a.cmd:
        p.print_help()
        return 2
    return {"desc": cmd_desc, "note": cmd_note, "verify": cmd_verify}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

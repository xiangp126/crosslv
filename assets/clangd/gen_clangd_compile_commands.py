#!/usr/bin/env python3

"""
Generate a per-file compile_commands.json for clangd from a CMake Unity build.

Primary use case: utopx, which builds with CMAKE_UNITY_BUILD=ON. CMake then
writes a compile_commands.json that describes the generated unity_*.cxx
aggregation units -- each one #include-ing several real .cpp files -- instead of
the real source files. clangd can only resolve a definition that lives in a file
it has a translation unit for, so go-to-definition on a symbol defined in, e.g.,
VHCA.cpp (merged into a unity unit) only finds the header declaration.

This tool reads that Unity-based compile_commands.json and rewrites it so every
real .cpp gets its own entry, reusing the exact compiler flags of the unity unit
it belongs to. That reuse is correct by construction: CMake compiles a whole
unity_*.cxx with a single command, so every .cpp merged into it was built with
those identical flags (-I / -D / -std / PCH ...). Entries that already point at a
real source are kept as-is; the generated PCH wrapper entries are dropped.

The build is never touched -- Unity build stays on, the binary is unaffected.
This only post-processes the compile database for code navigation.

This script lives in crosslv/assets/clangd and is normally invoked
automatically by `jmake --db` (see linkWorkspaceFiles in nv-tools/jmake),
which passes the repo root via --root. It can also be run by hand from the
repo root.

Usage:
    # From the repo root, after a build: auto-detect the newest cmakeBuild
    # compile_commands.json, expand it, and repoint
    # <root>/compile_commands.json at the expanded database:
    gen_clangd_compile_commands.py

    # Explicit repo root (what jmake does):
    gen_clangd_compile_commands.py --root /auto/fwgwork1/<user>/utopx

    # Explicit paths / no symlink update:
    gen_clangd_compile_commands.py --input <compile_commands.json> \
                                   --output <expanded.json> --no-link
"""

import argparse
import json
import os
import re
import shlex
import sys
from typing import List, Optional

# Matches: #include "..."  (the form CMake emits in unity_*.cxx)
INCLUDE_RE = re.compile(r'^\s*#\s*include\s+"([^"]+)"')

# Name CMake gives the generated database (also our discovery target).
DB_NAME = "compile_commands.json"
# Name we write the expanded database under, next to the source database.
EXPANDED_NAME = "compile_commands.clangd.json"


def log(msg: str) -> None:
    print(f"[gen-clangd-db] {msg}")


def find_default_db(root: str) -> Optional[str]:
    """Newest cmakeBuild/**/compile_commands.json, ignoring our own output."""
    base = os.path.join(root, "cmakeBuild")
    found = []
    for dirpath, _dirnames, filenames in os.walk(base):
        if DB_NAME in filenames:
            found.append(os.path.join(dirpath, DB_NAME))
    if not found:
        return None
    found.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return found[0]


def is_unity(path: str) -> bool:
    return "/Unity/" in path and path.endswith(".cxx")


def is_pch_wrapper(path: str) -> bool:
    return path.endswith("cmake_pch.hxx.cxx")


def unity_sources(unity_path: str) -> List[str]:
    """Real .cpp files #include-d by a generated unity_*.cxx."""
    srcs = []
    try:
        with open(unity_path) as f:
            for line in f:
                m = INCLUDE_RE.match(line)
                if not m:
                    continue
                inc = m.group(1)
                if os.path.isabs(inc):
                    srcs.append(os.path.normpath(inc))
                else:
                    srcs.append(os.path.normpath(
                        os.path.join(os.path.dirname(unity_path), inc)))
    except OSError as exc:
        log(f"WARNING: cannot read unity file {unity_path}: {exc}")
    return srcs


def entry_command_tokens(entry: dict) -> List[str]:
    """Tokenized compile command, from either the 'command' or 'arguments' key."""
    if "command" in entry and entry["command"]:
        return shlex.split(entry["command"])
    if "arguments" in entry and entry["arguments"]:
        return list(entry["arguments"])
    return []


def rewrite_for_source(tokens: List[str], new_source: str) -> List[str]:
    """Copy a unity unit's command for one real source.

    Drops the object-output (-o <obj>) and replaces the compiled file after -c
    with the real source. clangd only consumes the flags + the source path; the
    object path is irrelevant.
    """
    out: List[str] = []
    replaced = False
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok == "-o" and i + 1 < n:
            i += 2
            continue
        if tok == "-c" and i + 1 < n:
            out.append("-c")
            out.append(new_source)
            replaced = True
            i += 2
            continue
        out.append(tok)
        i += 1
    if not replaced:
        out += ["-c", new_source]
    return out


def expand(db: List[dict]) -> List[dict]:
    out: List[dict] = []
    seen = set()
    n_unity = n_expanded = n_normal = n_pch = 0

    def add(directory: str, file_path: str, tokens: List[str]) -> None:
        if file_path in seen:
            return
        seen.add(file_path)
        # Emit the "arguments" array form (not the "command" string form) so
        # pretty-printing puts every flag -- each -I, -D, ... -- on its own
        # line. clangd accepts both per the JSON Compilation Database spec.
        out.append({
            "directory": directory,
            "file": file_path,
            "arguments": tokens,
        })

    for entry in db:
        file_path = entry.get("file", "")
        directory = entry.get("directory", "")
        if is_pch_wrapper(file_path):
            n_pch += 1
            continue
        if is_unity(file_path):
            n_unity += 1
            tokens = entry_command_tokens(entry)
            for src in unity_sources(file_path):
                add(directory, src, rewrite_for_source(tokens, src))
                n_expanded += 1
        else:
            n_normal += 1
            add(directory, file_path, entry_command_tokens(entry))

    log(f"unity units expanded: {n_unity} -> {n_expanded} source entries")
    log(f"non-unity entries kept: {n_normal}")
    log(f"pch wrapper entries dropped: {n_pch}")
    log(f"total entries written: {len(out)}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Expand a Unity-build compile_commands.json into per-file "
                    "entries for clangd.")
    parser.add_argument("--root", default=os.getcwd(),
                        help="repo root (default: current directory). jmake "
                             "passes the build tree here.")
    parser.add_argument("--input",
                        help="source compile_commands.json (default: newest "
                             "under <root>/cmakeBuild)")
    parser.add_argument("--output",
                        help="expanded database path (default: "
                             f"<input_dir>/{EXPANDED_NAME})")
    parser.add_argument("--no-link", action="store_true",
                        help="do not repoint <root>/compile_commands.json")
    parser.add_argument("--compact", action="store_true",
                        help="write compact single-line JSON (default: "
                             "pretty-printed, one entry per block)")
    args = parser.parse_args()

    root = os.path.abspath(args.root)

    src = args.input or find_default_db(root)
    if not src or not os.path.isfile(src):
        log("ERROR: no compile_commands.json found under "
            f"{os.path.join(root, 'cmakeBuild')} — build the project first.")
        return 1
    log(f"input : {src}")

    try:
        with open(src) as f:
            db = json.load(f)
    except (OSError, ValueError) as exc:
        log(f"ERROR: cannot read/parse {src}: {exc}")
        return 1

    expanded = expand(db)
    if not expanded:
        log("ERROR: no entries produced — aborting.")
        return 1

    out_path = args.output or os.path.join(os.path.dirname(src), EXPANDED_NAME)
    try:
        with open(out_path, "w") as f:
            if args.compact:
                json.dump(expanded, f)
            else:
                json.dump(expanded, f, indent=2)
            f.write("\n")
    except OSError as exc:
        log(f"ERROR: cannot write {out_path}: {exc}")
        return 1
    log(f"output: {out_path}")

    if not args.no_link:
        link = os.path.join(root, DB_NAME)
        try:
            if os.path.islink(link) or os.path.exists(link):
                os.remove(link)
            os.symlink(out_path, link)
            log(f"linked: {link} -> {out_path}")
        except OSError as exc:
            log(f"WARNING: cannot update symlink {link}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

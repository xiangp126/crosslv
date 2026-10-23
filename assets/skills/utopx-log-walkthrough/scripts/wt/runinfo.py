"""Run facts for the page header, from three sources: the log itself, the per_run record next to it (<stem>.out),
and a JSON file with what neither carries (<stem>.runinfo.json next to the log, or --run-info). For a fact found in
several, the log wins over the record and the record over the JSON; descriptions only the JSON has (the FW build and
its changes, the utopx tree) come from the JSON. See references/run-info.md."""
import json
import os
import re

ANSI = re.compile(r'\x1b\[[0-9;]*m')
DEVICES = {'4125': 'ConnectX-6 Dx', '4127': 'ConnectX-6 Lx', '4129': 'ConnectX-7', '4131': 'ConnectX-8',
           '41686': 'BlueField-2', '41692': 'BlueField-3'}


def from_log(L):
    cmd = next((t for t in L.lines[1:400] if t and 'utopx' in t and '--seed' in t), '')
    opt = lambda name: (re.search(r'--%s[= ](\S+)' % name, cmd) or [None, None])[1]  # noqa: E731
    dev = opt('device') or ''
    m = re.search(r'mt(\d+)', dev)
    fw = L.first(r'fw version is: [\d.]+')
    ud = L.first(r'udriver version [\d.]+')
    return dict(cmd=cmd, seed=opt('seed'), iters=opt('iter'), ops=opt('ops_per_it'), xml=opt('xml_conf_file'),
                conf=opt('conf_file'), eopts=re.findall(r'-e (\S+)', cmd), device=dev,
                device_name=DEVICES.get(m.group(1)) if m else None,
                fw_version=re.search(r'fw version is: ([\d.]+)', L.lines[fw]).group(1) if fw else None,
                udriver_log=re.search(r'udriver version ([\d.]+)', L.lines[ud]).group(1) if ud else None)


def from_out(path):
    """The per_run.sh record: box, start time with its zone, utopx tree, FW version."""
    with open(path, encoding='utf-8', errors='replace') as f:
        text = ANSI.sub('', f.read())
    got = {}
    m = re.search(r'=== per_run \S+ on (\S+)\s+seed (\d+)\s+(\d{4}-\d\d-\d\d \d\d:\d\d(?::\d\d)? \w+)', text)
    if m:
        got.update(box=m.group(1), started=m.group(3))
    m = re.search(r'identity : tree (\w+)', text)
    if m:
        got['tree'] = m.group(1)
    m = re.search(r'OK\s+FW ([\d.]+)', text)
    if m:
        got['fw_out'] = m.group(1)
    return got


def load(L, path=None):
    """All run facts as one dict; 'sources' says which files were read."""
    ri = from_log(L)
    stem = os.path.splitext(L.path)[0]
    sources = [L.path]
    if os.path.exists(stem + '.out'):
        for k, v in from_out(stem + '.out').items():
            ri.setdefault(k, v)
        sources.append(stem + '.out')
    path = path or (stem + '.runinfo.json' if os.path.exists(stem + '.runinfo.json') else None)
    if path:
        with open(path, encoding='utf-8') as f:
            for k, v in json.load(f).items():
                if ri.get(k) in (None, '', []):
                    ri[k] = v
        sources.append(path)
    ri['sources'] = sources
    return ri

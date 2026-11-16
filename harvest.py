#!/usr/bin/env python3
"""Harvest finite-state Forms from the RCE repository using the RCE reference implementation.

For every .rce file with step declarations (payload events instantiated at fixed values), explore the reachable states breadth
first with `rce run FILE EVENTS`, which prints the state after every event (a failed step prints
"kept: <error>" and leaves the state unchanged; emitted outputs are ignored). States are identified by the text the reference
implementation prints, so the transition table comes from the reference and not from a transcription.
A Form is kept exactly when it has 2 to 16 reachable states and 1 to 8 events. A Form with more reachable
states (an unbounded counter, say) is truncated by a fixed rule and labelled: the first 8 states in
breadth-first order are kept and any step that leaves them becomes a self-loop. Duplicate tables are dropped.
Usage: harvest.py <rce repo> <rce binary> <out dir>
"""
import collections, hashlib, json, os, re, subprocess, sys
repo, rce, out = sys.argv[1:4]
MAXS, MAXE, TRUNC = 16, 8, 8

INT = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"}

def events_of(src):
    """Event instances. A payload-free event is itself. A payload event is instantiated by a fixed rule:
    every bool field at true and false, every integer field at 1 and 2. Other field types reject the Form."""
    ev, lines = [], src.split("\n")
    for i, l in enumerate(lines):
        m = re.match(r"^event (\w+)\s*(?:\((.*)\))?\s*$", l)
        if not m:
            if re.match(r"^event ", l): return None
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if nxt.startswith((" ", "\t")) and nxt.strip(): return None      # block-form payload
        if not m.group(2): ev.append(m.group(1)); continue
        inst = [""]
        for field in m.group(2).split(","):
            if ":" not in field: return None
            name, typ = [x.strip() for x in field.split(":", 1)]
            vals = ["true", "false"] if typ == "bool" else ["1", "2"] if typ in INT else None
            if vals is None: return None
            inst = [(p + ", " if p else "") + f"{name}: {v}" for p in inst for v in vals]
        ev += [f"{m.group(1)}({p})" for p in inst]
    return ev

def run(path, seq):
    """States after each event, as printed by the reference; index 0 is the initial state."""
    r = subprocess.run([rce, "run", path, ", ".join(seq)], capture_output=True, text=True, timeout=20)
    states = []          # exit status is 1 whenever a step is kept, so the printed lines decide
    for line in r.stdout.rstrip().split("\n"):
        if line.startswith((" ", "\t")): continue      # emitted outputs, not state
        m = re.match(r"^(\d+) (\(initial\)|\w+(?:\([^)]*\))?) (.*)$", line)
        if not m: return None
        body = m.group(3)
        states.append(states[-1] if body.startswith("kept:") else body)
    return states if len(states) == len(seq) + 1 else None

why = collections.Counter(); kept, seen = [], set()
files = subprocess.run(["grep", "-rl", "--include=*.rce", "-E", "^step ", repo], capture_output=True, text=True).stdout.split()
for path in sorted(files):
    if "/target/" in path: continue
    src = open(path, errors="replace").read()
    ev = events_of(src)
    if ev is None: why["event payload of unsupported type"] += 1; continue
    if not ev or len(ev) > MAXE or len(set(ev)) != len(ev): why["event count"] += 1; continue
    s0 = run(path, [])
    if s0 is None: why["does not run"] += 1; continue
    def explore(cap, saturate):
        """Breadth-first table. With saturate, a step that leaves the first `cap` states is replaced by a self-loop."""
        ids, paths, table, queue = {s0[0]: 0}, [[]], {}, [0]
        while queue:
            s = queue.pop(0)
            for k, e in enumerate(ev):
                st = run(path, paths[s] + [e])
                if st is None: return "step does not run"
                if st[-1] not in ids:
                    if len(paths) >= cap:
                        if saturate: table[(s, k)] = s; continue
                        return "more than 16 states"
                    ids[st[-1]] = len(paths); paths.append(paths[s] + [e]); queue.append(ids[st[-1]])
                table[(s, k)] = ids[st[-1]]
        return ids, paths, table
    res, kind = explore(MAXS, False), "exact"
    if res == "more than 16 states":
        res, kind = explore(TRUNC, True), f"truncated to the first {TRUNC} reachable states, steps leaving them kept"
    if isinstance(res, str): why[res] += 1; continue
    ids, paths, table = res
    n = len(paths)
    if n < 2: why["one state"] += 1; continue
    rows = [[table[(s, k)] for k in range(len(ev))] for s in range(n)]
    key = json.dumps(rows)
    if key in seen: why["duplicate table"] += 1; continue
    seen.add(key)
    rel = os.path.relpath(path, repo)
    names = [None] * n
    for text, i in ids.items(): names[i] = text
    kept.append({"source": rel, "sha256": hashlib.sha256(src.encode()).hexdigest(), "events": ev, "kind": kind, "states": n, "table": rows, "paths": paths, "state_text": names})
    print(rel, "states", n, "events", len(ev), kind.split()[0], flush=True)
json.dump(kept, open(os.path.join(out, "harvest.json"), "w"), indent=1)
print(len(kept), "distinct finite Forms;", "rejected:", dict(why))

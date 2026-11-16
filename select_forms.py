#!/usr/bin/env python3
"""Fix the Aim 2 program set from the harvest by a rule that does not look at any result:
exact tables first, in path order, then truncated tables in path order, until 40 are chosen.
Usage: select_forms.py <harvest.json> <selected.json>"""
import json, os, re, sys
H = json.load(open(sys.argv[1]))
order = sorted(H, key=lambda f: (f["kind"] != "exact", f["source"]))[:40]
names = set()
for f in order:
    base = re.sub(r"\W+", "_", os.path.basename(f["source"])[:-4]); name, k = base, 2
    while name in names: name = f"{base}_{k}"; k += 1
    names.add(name); f["name"] = name
json.dump(order, open(sys.argv[2], "w"), indent=1)
print(len(order), "selected:", sum(f["kind"] == "exact" for f in order), "exact,", sum(f["kind"] != "exact" for f in order), "truncated, of", len(H), "harvested")

#!/usr/bin/env python3
"""Write each Aim 1 Ising instance as a QUBO text file for the ferromorphic runner.
E(s) = -sum J s_i s_j - sum h s_i with s = 2x - 1 gives x^T Q x + offset."""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.abspath(__file__))
import os
import glob, json, os, sys
R = os.path.join(ROOT, "results"); out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "inst")
for p in sorted(glob.glob(f"{R}/aim1_[ABCDR]_*.json")):
    d = json.load(open(p)); n = d["n"]; tag = os.path.basename(p)[5:-5]
    lin = [-2.0 * h for h in d["h"]]; quad = {}; off = sum(d["h"])
    for i, j, w in d["edges"]:
        i, j = sorted((int(i), int(j))); quad[(i, j)] = quad.get((i, j), 0.0) - 4 * w
        lin[i] += 2 * w; lin[j] += 2 * w; off -= w
    terms = [(i, i, lin[i]) for i in range(n) if lin[i]] + [(i, j, v) for (i, j), v in quad.items() if v]
    terms.sort()
    with open(f"{out}/{tag}.txt", "w") as f:
        f.write(f"{n} {d['e_min']!r} {off!r} {len(terms)}\n" + "".join(f"{i} {j} {v!r}\n" for i, j, v in terms))

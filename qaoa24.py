#!/usr/bin/env python3
"""Ideal cold QAOA on the program-repair instances at 24 variables, with transferred angles (results/qaoa24.json).

At 12 to 20 variables program repair is the one family where ideal depth-3 QAOA needs fewer shots times gates than the
edge arms need operations. This extends the comparison one size up, to the largest state vector that fits in memory here.
Angles are not optimised at 24 variables: each donor's optimised angles (the 7 repair instances at 12 to 20 variables) are
applied with the cost angle rescaled, and the donor with the lowest energy expectation is kept. That choice uses only the
expectation, which hardware can measure; the optimum is used for scoring alone."""
import glob, json, math, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); R = f"{ROOT}/results"
from aim1_post import diag_energy, qaoa_state
def scale(d):
    w = [hi * hi for hi in d["h"]]
    for i, j, v in d["edges"]: w[int(i)] += v * v; w[int(j)] += v * v
    return float(np.sqrt(np.mean(w)))
donors = [json.load(open(p)) for p in sorted(glob.glob(f"{R}/aim1_R_*.json"))]
post = {(r["family"], r["n"], r["seed"]): r for r in json.load(open(f"{R}/scale_post.json"))}
out = []
for path in sorted(glob.glob(f"{R}/scale/scale_R_24_*.json")):
    d = json.load(open(path)); n = d["n"]; e = diag_energy(n, d["h"], d["edges"]); emin = float(e.min()); emax = float(e.max())
    assert abs(emin - d["reference_energy"]) < 1e-6, "exhaustive minimum differs from the branch-and-bound optimum"
    gs = e <= emin + 1e-9 * (1 + abs(emin)); rec = {"family": "R", "n": n, "seed": d["seed"], "n_ground": int(gs.sum()), "pt_tts99_proposals": d["pt_tts99_proposals"], "depths": []}
    for p in (1, 2, 3):
        best = None
        for dn in donors:
            q = dn["qaoa"][p - 1]; f = scale(dn) / scale(d); pr = np.abs(qaoa_state(e, n, [g * f for g in q["gamma"]], q["beta"])) ** 2
            r = {"donor": f"R_{dn['n']}_{dn['seed']}", "expectation": float(pr @ e), "ratio": float((emax - pr @ e) / (emax - emin)), "p_gs": float(pr[gs].sum())}
            if best is None or r["expectation"] < best["expectation"]: best = r
        rzz = post[("R", n, d["seed"])]["transpile"][p - 1]["all_to_all_rzz"]
        shots = math.log(0.01) / math.log(1 - best["p_gs"]) if 0 < best["p_gs"] < 0.99 else (1.0 if best["p_gs"] >= 0.99 else None)
        best.update({"p": p, "all_to_all_rzz": rzz, "shots_to_99pct": shots, "shots_times_gates": shots * rzz if shots else None}); rec["depths"].append(best)
        print(d["seed"], p, best, flush=True)
    out.append(rec)
json.dump(out, open(f"{R}/qaoa24.json", "w"), indent=1)

#!/usr/bin/env python3
"""Certified gap in problem units for the penalty-encoded families.

The gap used elsewhere is (E_found - bound) / |E_min| in Ising form, where the mean energy over all states is zero, so
|E_min| is the spread between a random state and the optimum. For one-hot encoded problems (A: 4 directions per link,
C: 3 colours per node, R: one next state per suspect entry) a random state breaks the encoding and pays the penalty, so
that spread is dominated by the penalty and the percentage understates the gap. Here the same gap is divided by the spread
among FEASIBLE states: mean energy over one-hot assignments minus the optimum. The mean is exact (it is a sum of
single and pair expectations over independent uniform groups). Families B and D have no encoding; their figure is unchanged.
Writes results/feasible_gap.json."""
import glob, json, os
ROOT = os.path.dirname(os.path.abspath(__file__)); R = f"{ROOT}/results"

def group_size(fam, n, seed):
    if fam == "A": return 4
    if fam == "C": return 3
    if fam == "R": return json.load(open(f"{ROOT}/repair/R_{n}_{seed}.json"))["states"]
    return None

def feasible_mean(n, h, edges, q):
    # s_i = +1 for the chosen member of each group of q, else -1; choices uniform and independent across groups
    m1 = 2.0 / q - 1.0                      # E[s_i]
    same = 1.0 - 4.0 / q                    # E[s_i s_j], i != j in one group: both -1 unless one of them is chosen
    e = -sum(hi * m1 for hi in h)
    for i, j, w in edges:
        e -= w * (same if int(i) // q == int(j) // q else m1 * m1)
    return e

rows = []
for path in sorted(glob.glob(f"{R}/aim1_[ABCDR]_*.json")) + sorted(glob.glob(f"{R}/scale/scale_*.json")):
    d = json.load(open(path)); fam, n, seed = d["family"], d["n"], d["seed"]; q = group_size(fam, n, seed)
    e_ref = d.get("e_min", d.get("reference_energy")); gap = e_ref - d["sdp_bound"]
    row = {"family": fam, "n": n, "seed": seed, "set": "scale" if "scale" in os.path.basename(path) else "small", "reference_energy": e_ref, "sdp_bound": d["sdp_bound"],
           "gap_pct_of_all_state_spread": 100 * gap / abs(e_ref)}
    if q:
        fm = feasible_mean(n, d["h"], d["edges"], q); row["feasible_mean_energy"] = fm; row["gap_pct_of_feasible_spread"] = 100 * gap / (fm - e_ref)
    else:
        row["gap_pct_of_feasible_spread"] = row["gap_pct_of_all_state_spread"]
    if "pt_best_energy" in d:   # scale-up set: the certified gap of the answer parallel tempering actually returned
        spread = (row["feasible_mean_energy"] - e_ref) if q else abs(e_ref)
        row["tempering_answer_gap_pct_of_feasible_spread"] = 100 * (d["pt_best_energy"] - d["sdp_bound"]) / spread
    rows.append(row)
json.dump(rows, open(f"{R}/feasible_gap.json", "w"), indent=1)
import statistics as st
for s in ("small", "scale"):
    for fam in "ABCDR":
        v = [r["gap_pct_of_feasible_spread"] for r in rows if r["family"] == fam and r["set"] == s]
        if v: print(s, fam, len(v), "feasible-spread gap %%: min %.3f median %.3f max %.3f | within 1%%: %d" % (min(v), st.median(v), max(v), sum(x <= 1 for x in v)))
v = [r for r in rows if r["set"] == "scale"]
for fam in "ABCDR":
    for n in sorted({r["n"] for r in v if r["family"] == fam}):
        g = [r["tempering_answer_gap_pct_of_feasible_spread"] for r in v if r["family"] == fam and r["n"] == n]
        print("tempering answer", fam, n, "certified gap %%: %s | within 1%%: %d of %d" % (" ".join("%.3f" % x for x in g), sum(x <= 1 for x in g), len(g)))

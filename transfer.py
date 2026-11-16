#!/usr/bin/env python3
"""Does angle transfer hold? The proposal optimises QAOA angles in simulation up to 20 qubits and transfers them within a
family above that. Test at sizes we can still simulate: apply the angles optimised on each of 5 donor instances at 12
variables to every same-family instance at 15 to 20 variables, and compare with the angles optimised on the target itself.
Cold QAOA, depths 1 to 3. Energies are comparable across sizes within a family by construction of the generators, so
Two rules are compared: angles transferred unchanged, and gamma rescaled by the ratio of donor to target coupling scale
(root mean square over qubits of the field and coupling weights at that qubit), as is standard for weighted problems
(Shaydulin et al., arXiv:2305.15201). Writes results/transfer.json."""
import glob, json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from aim1_post import diag_energy, qaoa_state
R = f"{ROOT}/results"; A = {}
for p in glob.glob(f"{R}/aim1_[ABCDR]_*.json"):
    d = json.load(open(p)); A[(d["family"], d["n"], d["seed"])] = d
def scale(d):
    n = d["n"]; w = [hi * hi for hi in d["h"]]
    for i, j, v in d["edges"]: w[int(i)] += v * v; w[int(j)] += v * v
    return float(np.sqrt(np.mean(w)))
rows = []
for fam in "ABCDR":
    donors = sorted(k for k in A if k[0] == fam and k[1] == 12)[:5]
    for k in sorted(k for k in A if k[0] == fam and k[1] > 12):
        d = A[k]; n = d["n"]; e = diag_energy(n, d["h"], d["edges"]); emin, emax = e.min(), e.max(); gs = e <= emin + 1e-9 * (1 + abs(emin))
        for p in (1, 2, 3):
            own = d["qaoa"][p - 1]; res = []
            for dk in donors:
                q = A[dk]["qaoa"][p - 1]; r = {"donor_seed": dk[2]}
                for rule, f in (("unchanged", 1.0), ("rescaled", scale(A[dk]) / scale(d))):
                    pr = np.abs(qaoa_state(e, n, [g * f for g in q["gamma"]], q["beta"])) ** 2
                    r[rule] = {"ratio": float((emax - pr @ e) / (emax - emin)), "p_gs": float(pr[gs].sum())}
                res.append(r)
            row = {"family": fam, "n": n, "seed": k[2], "p": p, "own_ratio": own["ratio"], "own_p_gs": own["p_gs"], "transferred": res}
            for rule in ("unchanged", "rescaled"):
                row[f"median_ratio_{rule}"] = float(np.median([r[rule]["ratio"] for r in res])); row[f"median_p_gs_{rule}"] = float(np.median([r[rule]["p_gs"] for r in res]))
                row[f"best_p_gs_{rule}"] = float(max(r[rule]["p_gs"] for r in res))
            rows.append(row)
        print(fam, n, k[2], [(round(r["own_ratio"], 3), round(r["median_ratio_unchanged"], 3), round(r["median_ratio_rescaled"], 3), round(r["own_p_gs"], 4), round(r["median_p_gs_unchanged"], 4), round(r["median_p_gs_rescaled"], 4)) for r in rows[-3:]], flush=True)
json.dump(rows, open(f"{R}/transfer.json", "w"), indent=1)

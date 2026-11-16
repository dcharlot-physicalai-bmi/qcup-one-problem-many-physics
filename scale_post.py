#!/usr/bin/env python3
"""Scale-up instances (24 to 60 variables): gate counts of the QAOA circuits that hardware would run, and the admission rule.

For each instance in results/scale, the depth 1 to 3 QAOA circuit is built (angles do not change gate counts) and transpiled
to an n-qubit heavy-hex patch in CZ (as for the 120 small instances) and to all-to-all RZZ. A circuit is admitted when its
two-qubit gate count is within the budget at which modelled trace fidelity is 30% (660 CZ, 2,000 RZZ; fitted in Aim 2).
Writes results/scale_post.json."""
import glob, json, os, sys
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from aim1_post import qaoa_circuit
from qiskit import transpile
from qiskit.transpiler import CouplingMap

def patch(n):
    full = CouplingMap.from_heavy_hex(5 if n <= 57 else 7); adj = {}
    for a, b in full.get_edges(): adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
    order, seen, queue = [], {0}, [0]
    while queue and len(order) < n:
        v = queue.pop(0); order.append(v)
        for w in sorted(adj[v]):
            if w not in seen: seen.add(w); queue.append(w)
    idx = {v: k for k, v in enumerate(order)}
    return CouplingMap(sorted({(idx[a], idx[b]) for a in order for b in adj[a] if b in idx}))

BUDGET = {"heavy_hex_cz": 660, "all_to_all_rzz": 2000}
out = []
for path in sorted(glob.glob(f"{ROOT}/results/scale/scale_*.json")):
    d = json.load(open(path)); n = d["n"]; hh = patch(n); rec = {"family": d["family"], "n": n, "seed": d["seed"], "couplings": len(d["edges"]), "transpile": []}
    for p in (1, 2, 3):
        qc = qaoa_circuit(n, d["h"], d["edges"], [0.3] * p, [0.2] * p)
        t_hh = transpile(qc, coupling_map=hh, basis_gates=["cz", "rz", "sx", "x"], optimization_level=3, seed_transpiler=7)
        t_aa = transpile(qc, basis_gates=["rzz", "rz", "rx", "ry"], optimization_level=3, seed_transpiler=7)
        r = {"p": p, "heavy_hex_cz": int(t_hh.count_ops().get("cz", 0)), "all_to_all_rzz": int(t_aa.count_ops().get("rzz", 0))}
        r["admitted"] = {k: r[k] <= v for k, v in BUDGET.items()}; rec["transpile"].append(r)
    out.append(rec); print(rec["family"], n, rec["seed"], [(t["heavy_hex_cz"], t["all_to_all_rzz"]) for t in rec["transpile"]], flush=True)
json.dump(out, open(f"{ROOT}/results/scale_post.json", "w"), indent=1)

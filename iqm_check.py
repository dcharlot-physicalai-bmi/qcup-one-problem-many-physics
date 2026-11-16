#!/usr/bin/env python3
"""Check of the IQM request against IQM's own published device model.

The admission rule counts CZ gates after transpiling to a heavy-hex patch, which is IBM's layout. IQM's QCUP devices are
square-lattice (crystal) processors. This script transpiles every Aim 1 circuit requested on IQM to IQMFakeAphrodite,
the 54-qubit crystal-lattice fake backend that ships with IQM's open-source client (no account needed; a fake backend is
a published device model, not a live device), in IQM's native gate set, and compares CZ counts with the heavy-hex figure.

Two steps, because IQM's client pins an older Qiskit than the rest of this package:
  iqm_check.py export   (package environment)  writes OpenQASM 2 circuits to results/iqm/qasm
  iqm_check.py count    (an environment with `pip install "iqm-client[qiskit]"`)  writes results/iqm/check.json"""
import glob, json, os, sys
ROOT = os.path.dirname(os.path.abspath(__file__)); R = f"{ROOT}/results"; OUT = f"{R}/iqm"; BUDGET = 660
def export():
    from qiskit import qasm2
    sys.path.insert(0, ROOT); from aim1_post import qaoa_circuit
    os.makedirs(f"{OUT}/qasm", exist_ok=True); rows = []
    src = [(json.load(open(p)), json.load(open(p.replace("post_", "aim1_")))) for p in sorted(glob.glob(f"{R}/post_*.json"))]
    sc = {(d["family"], d["n"], d["seed"]): d for d in json.load(open(f"{R}/scale_post.json"))}
    for p in sorted(glob.glob(f"{R}/scale/scale_*.json")):
        d = json.load(open(p)); k = (d["family"], d["n"], d["seed"])
        if k in sc: src.append((sc[k], d))
    for post, inst in src:
        f, n, s = post["family"], post["n"], post["seed"]
        for t in post["transpile"]:
            p = t["p"]
            if n > 54 or t["heavy_hex_cz"] > BUDGET or (f == "B" and n > 20 and p > 1): continue
            name = f"{f}_{n}_{s}_p{p}"; qc = qaoa_circuit(n, inst["h"], [tuple(e) for e in inst["edges"]], [0.4] * p, [0.3] * p); qasm2.dump(qc, f"{OUT}/qasm/{name}.qasm"); rows.append({"circuit": name, "family": f, "n": n, "seed": s, "p": p, "heavy_hex_cz": t["heavy_hex_cz"]})
    json.dump(rows, open(f"{OUT}/exported.json", "w"), indent=1); print(len(rows), "circuits exported")
def count():
    from qiskit import qasm2, transpile
    from iqm.qiskit_iqm import IQMFakeAphrodite
    be = IQMFakeAphrodite(); rows = json.load(open(f"{OUT}/exported.json")); done = {r["circuit"]: r for r in (json.load(open(f"{OUT}/check.json"))["rows"] if os.path.exists(f"{OUT}/check.json") else [])}
    for k, r in enumerate(rows):
        if r["circuit"] in done: rows[k] = done[r["circuit"]]; continue
        qc = qasm2.load(f"{OUT}/qasm/{r['circuit']}.qasm", custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS); t = transpile(qc, backend=be, optimization_level=3, seed_transpiler=7); r["iqm_cz"] = int(t.count_ops().get("cz", 0)); r["admitted_on_iqm_model"] = bool(r["iqm_cz"] <= BUDGET)
        if k % 20 == 0: print(k, r["circuit"], r["heavy_hex_cz"], r["iqm_cz"], flush=True); json.dump({"rows": [x for x in rows if "iqm_cz" in x]}, open(f"{OUT}/check.json", "w"))
    ratio = sorted(r["iqm_cz"] / r["heavy_hex_cz"] for r in rows); tot = {"backend": "IQMFakeAphrodite (54 qubits, crystal lattice)", "circuits": len(rows), "admitted_on_iqm_model": sum(r["admitted_on_iqm_model"] for r in rows), "median_ratio_iqm_to_heavy_hex": ratio[len(ratio) // 2], "ratio_range": [ratio[0], ratio[-1]],
           "not_admitted": [r["circuit"] for r in rows if not r["admitted_on_iqm_model"]], "by_family": {f: {"circuits": sum(1 for r in rows if r["family"] == f), "admitted": sum(1 for r in rows if r["family"] == f and r["admitted_on_iqm_model"])} for f in sorted({r["family"] for r in rows})}}
    json.dump({"totals": tot, "rows": rows}, open(f"{OUT}/check.json", "w"), indent=1); print(tot)
if __name__ == "__main__": {"export": export, "count": count}[sys.argv[1]]()

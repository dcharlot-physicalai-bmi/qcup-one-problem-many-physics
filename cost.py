#!/usr/bin/env python3
"""Vendor cost of the hardware request, from the transpiled circuits (results/cost.json).

Trapped-ion circuits are rebuilt and transpiled to the all-to-all basis (rzz, rz, rx, ry) and their operations counted.
Quantinuum: HQC = 5 + C (N1q + 10 N2q + 5 Nm) / 5000 per circuit, the published H-series formula, with C shots, N2q the
two-qubit gates and Nm the state preparations, measurements and resets. Rz is counted as a one-qubit gate, which overstates
the cost where the device applies it virtually.
IonQ: one- and two-qubit gate-shots (the quantity QCUP records as two-qubit gate equivalents is fixed by OLCF's agreement
and is not public), and for scale the list price at the published Forte pay-as-you-go rates with error mitigation off (raw samples are needed).
IBM: QPU time from shots x (repetition delay 250 us + circuit duration), circuit duration taken as 100 ns per layer of
transpiled depth. This is an estimate to be replaced by the usage IBM reports.
These are estimates from public formulas. IonQ's own estimate for every IonQ circuit, in credits at a per-compute-second rate, is in
vendor/results/ionq/estimates.json and supersedes the IonQ figures here; the request the application states is vendor/results/final_request.json."""
import glob, json, math, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); R = f"{ROOT}/results"
from qiskit import transpile
from aim1_post import qaoa_circuit
from aim2 import build
from aim2b import is_permutation, build_inplace
ION = ["rzz", "rz", "rx", "ry"]

def ops(qc, extra=()):
    t = transpile(qc, basis_gates=ION + list(extra), optimization_level=3, seed_transpiler=7); c = t.count_ops()
    return {"n1q": int(sum(c.get(g, 0) for g in ("rz", "rx", "ry"))), "n2q": int(c.get("rzz", 0)), "resets": int(c.get("reset", 0)), "measure": int(c.get("measure", 0)), "qubits": qc.num_qubits}

def hqc(o, shots, spam): return 5 + shots * (o["n1q"] + 10 * o["n2q"] + 5 * spam) / 5000

# ---- Aim 1 on trapped ions: seed 0 of each family and size; IonQ up to 32 variables, Quantinuum from 40
inst = {}
for p in glob.glob(f"{R}/aim1_[ABCDR]_*.json") + glob.glob(f"{R}/scale/scale_*.json"):
    d = json.load(open(p))
    if d["seed"] == 0: inst[(d["family"], d["n"])] = d
rows = []
for (fam, n), d in sorted(inst.items()):
    vendor, shots = ("IonQ", 500) if n <= 32 else ("Quantinuum", 200)
    for p in (1, 2, 3):
        if fam == "B" and n > 20 and p > 1: continue
        o = ops(qaoa_circuit(n, d["h"], d["edges"], [0.3] * p, [0.2] * p))
        if o["n2q"] > 2000: continue
        for kind in ("cold", "warm"):   # the warm-start circuit replaces n Hadamards by n Ry and the Rx mixer by Ry Rz Ry
            oo = dict(o); oo["n1q"] = o["n1q"] + (2 * n * p if kind == "warm" else 0)
            tier = ("core" if p == 1 else "extension") if vendor == "IonQ" else ("core" if (fam == "A" and n == 60 and p == 1) or fam == "R" else "extension")
            rows.append({"aim": 1, "vendor": vendor, "tier": tier, "circuit": f"{fam}_{n}_0_p{p}_{kind}", "shots": shots, **oo, "spam": 2 * n})
# ---- Aim 2 on trapped ions: reset and in-place styles, first event stream, T = 1, 5 (IonQ) and 1, 3, 5 (Quantinuum)
forms = json.load(open(f"{ROOT}/forms/selected.json"))
for i, F in enumerate(forms):
    table, S, E = F["table"], F["states"], len(F["events"])
    sb = max(1, math.ceil(math.log2(S))); eb = math.ceil(math.log2(E)) if E > 1 else 0
    delta = lambda s, e, table=table, S=S, E=E: table[s][e] if s < S and e < E else s
    rng = np.random.default_rng([20261111, i]); stream = [int(x) for x in rng.integers(0, E, 5)] if E > 1 else [0] * 5
    perm = is_permutation(delta, sb, eb) and eb == 0
    for T in (1, 3, 5):
        for style in ["R"] + (["P"] if perm else []):
            qc = build_inplace(delta, sb, 0, T) if style == "P" else build(style, delta, sb, eb, 0, stream[:T])[0]
            o = ops(qc, ("reset", "measure"))
            if o["n2q"] > 2000: continue
            for vendor, shots, steps in (("IonQ", 500, (1, 5)), ("Quantinuum", 200, (1, 3, 5))):
                if T in steps: rows.append({"aim": 2, "vendor": vendor, "tier": "core" if o["n2q"] <= 300 else "extension", "circuit": f"{F['name']}_{style}_T{T}", "shots": shots, **o, "spam": o["qubits"] + o["resets"] + o["measure"]})
    print(F["name"], flush=True)
FORTE_1Q, FORTE_2Q, FORTE_MIN = 0.0001645, 0.001121, 25.7899   # minimum with error mitigation off: raw samples are required for certification and fidelity
summary = []
for vendor in ("IonQ", "Quantinuum"):
  for tier in ("core", "extension"):
    for aim in (1, 2):
        q = [r for r in rows if r["vendor"] == vendor and r["aim"] == aim and r["tier"] == tier]
        rec = {"vendor": vendor, "tier": tier, "aim": aim, "circuits": len(q), "shots": sum(r["shots"] for r in q), "two_qubit_gates_max": max(r["n2q"] for r in q),
               "one_qubit_gate_shots": sum(r["shots"] * r["n1q"] for r in q), "two_qubit_gate_shots": sum(r["shots"] * r["n2q"] for r in q)}
        if vendor == "Quantinuum":
            h = [hqc(r, r["shots"], r["spam"]) for r in q]; rec["hqc_total"] = round(sum(h)); rec["hqc_max_circuit"] = round(max(h)); rec["hqc_median_circuit"] = round(float(np.median(h)))
        else:
            rec["list_price_usd_forte_pay_as_you_go"] = round(sum(max(FORTE_MIN, r["shots"] * (FORTE_1Q * r["n1q"] + FORTE_2Q * r["n2q"])) for r in q))
        summary.append(rec); print(rec)
# ---- IBM time from shots and transpiled depth
ibm = []
for aim, shots, src in ((1, 4000, None), (2, 1000, None)):
    pass
post = [json.load(open(p)) for p in glob.glob(f"{R}/post_*.json")]
a1 = json.load(open(f"{R}/aim1_request.json"))[0]; a2 = json.load(open(f"{R}/aim2_request.json"))[0]
a2rows = [r for p in glob.glob(f"{R}/aim2/*.json") for r in json.load(open(p))]
d2 = [r["sc_like"]["depth"] for r in a2rows if r["sc_like"]["two_qubit_gates"] <= 660]
dur2 = float(np.mean(d2)) * 100e-9
est = {"vendor": "IBM", "aim1_shots": a1["total_shots"], "aim2_shots": a2["total_shots"], "assumed_repetition_delay_s": 250e-6, "assumed_seconds_per_depth_layer": 100e-9,
       "aim2_mean_depth_admitted": round(float(np.mean(d2))), "aim1_assumed_depth": 3000}
est["minutes"] = round((a1["total_shots"] * (250e-6 + 3000 * 100e-9) + a2["total_shots"] * (250e-6 + dur2)) / 60, 1)
print(est)
json.dump({"trapped_ion": summary, "ibm_time_estimate": est, "circuits": rows}, open(f"{R}/cost.json", "w"), indent=1)

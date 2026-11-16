"""Independent check of the exported IonQ circuits for the 44 one-step Aim 2 programs: simulate the QIS JSON that was
sent (rx, ry, rz, zz in radians, qubit q = bit q) and the IonQ-compiled native circuit (gpi, gpi2, zz in turns), and
compare each with the reference trace. Also simulates the builder's native lowering (to_native.py output)."""
import json, math, os, sys
import numpy as np
B = sys.argv[1]
C = json.load(open(f"{B}/circuits/index.json"))["circuits"]

def apply1(psi, nq, q, u):
    psi = psi.reshape([2] * nq); ax = nq - 1 - q
    psi = np.moveaxis(np.tensordot(u, psi, axes=([1], [ax])), 0, ax); return psi.reshape(-1)

def rx(t): return np.array([[math.cos(t/2), -1j*math.sin(t/2)], [-1j*math.sin(t/2), math.cos(t/2)]])
def ry(t): return np.array([[math.cos(t/2), -math.sin(t/2)], [math.sin(t/2), math.cos(t/2)]])
def rz(t): return np.diag([np.exp(-1j*t/2), np.exp(1j*t/2)])
def gpi(ph): a = 2*math.pi*ph; return np.array([[0, np.exp(-1j*a)], [np.exp(1j*a), 0]])
def gpi2(ph): a = 2*math.pi*ph; return np.array([[1, -1j*np.exp(-1j*a)], [-1j*np.exp(1j*a), 1]]) / math.sqrt(2)

def run(nq, circ, native):
    psi = np.zeros(1 << nq, complex); psi[0] = 1; idx = np.arange(1 << nq)
    for g in circ:
        n = g["gate"]
        if n in ("rx", "ry", "rz"): psi = apply1(psi, nq, g["target"], {"rx": rx, "ry": ry, "rz": rz}[n](g["rotation"]))
        elif n == "gpi": psi = apply1(psi, nq, g["target"], gpi(g["phase"]))
        elif n == "gpi2": psi = apply1(psi, nq, g["target"], gpi2(g["phase"]))
        elif n == "zz":
            a, b = g["targets"]; za = 1 - 2*((idx >> a) & 1); zb = 1 - 2*((idx >> b) & 1)
            th = (2*math.pi*g["angle"]) if native else g["rotation"]      # native angle in turns: exp(-i pi angle ZZ)
            psi = psi * np.exp(-1j * th / 2 * za * zb)
        else: raise ValueError(n)
    return np.abs(psi) ** 2

def p_ref(prob, mp, want):
    nb = len(want); tot = 0.0
    for s, p in enumerate(prob):
        if p < 1e-12: continue
        bits = "".join(str((s >> mp[str(k)]) & 1) for k in reversed(range(nb)))
        if bits == want: tot += p
    return tot

rows = []
for cid, c in sorted(C.items()):
    if c.get("aim") != 2 or c.get("T") != 1 or c.get("mid_circuit_measure_or_reset"): continue
    d = json.load(open(f"{B}/circuits/ionq/{cid}.json")); mp = d["clbit_to_qubit"]; want = c["reference_bits_qiskit_order"]
    pq = run(d["input"]["qubits"], d["input"]["circuit"], False)
    nat = json.load(open(f"{B}/circuits/ionq-native/{cid}.json")); pn = run(nat["input"]["qubits"], nat["input"]["circuit"], True)
    comp = json.load(open(f"{B}/ionq/raw/compiled/compiled-{cid}-s500.json"))["answer"]
    pc = run(max(comp["qubits"], 1), comp["circuit"], True) if comp["circuit"] else None
    # compiled circuit qubit numbering may differ; report the most likely output bitstring
    rec = {"id": cid, "rzz_sent": sum(1 for g in d["input"]["circuit"] if g["gate"] == "zz"), "p_reference_sent_qis": round(p_ref(pq, mp, want), 9),
           "p_reference_native_lowering": round(p_ref(pn, mp, want), 9), "max_prob_sent": round(float(pq.max()), 9),
           "compiled_qubits": comp["qubits"], "compiled_gates": len(comp["circuit"]), "compiled_2q": sum(1 for g in comp["circuit"] if g["gate"] in ("zz", "ms")),
           "compiled_max_prob": round(float(pc.max()), 6) if pc is not None else 1.0, "compiled_mode": int(pc.argmax()) if pc is not None else 0, "reference_bits": want}
    rows.append(rec)
json.dump(rows, open(f"{B}/verify/sim_sent_aim2.json", "w"), indent=1)
bad = [r for r in rows if r["p_reference_sent_qis"] < 0.999999 or r["p_reference_native_lowering"] < 0.999999]
print("circuits", len(rows), "sent QIS reproduces reference with p>=1-1e-6:", sum(1 for r in rows if r["p_reference_sent_qis"] >= 0.999999),
      "native lowering:", sum(1 for r in rows if r["p_reference_native_lowering"] >= 0.999999), "bad", [r["id"] for r in bad])
print("compiled circuits deterministic (max prob > 0.9999):", sum(1 for r in rows if r["compiled_max_prob"] > 0.9999), "of", len(rows))
for r in rows:
    if r["compiled_2q"] or r["compiled_max_prob"] < 0.9999: print(r)

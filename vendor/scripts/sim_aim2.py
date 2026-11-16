#!/usr/bin/env python3
"""Trace fidelity of the Aim 2 request circuits simulated under the published-figure device models, to check the way
the admission rule is carried over (F_rule^(b_device/b_generic)) and to refit the package's per-gate law under each.

The noise is written into the circuit as Qiskit Aer error instructions at the places models.py charges them:
  quantinuum-h2-1-2023  depolarising after each rzz at its folded angle (lambda = 4r/3, r on the published line), after
                        each rx/ry (2 x 2.7e-5), the memory dephasing (Z with chance (1 - (1 - 3r)^k)/2, r = 1.95e-4)
                        right after a qubit's last two-qubit gate by WAI Quantum's rule, readout p01 9e-4 / p10 2.2e-3,
                        and a bit flip of 1.55e-3 after each reset (no published figure; an assumption);
  ionq-forte-1          depolarising 4(1 - 0.9936)/3 after each zz, 2(1 - 0.9999) per native gpi/gpi2, readout 3.4e-3
                        (no relaxation or idling: a lower bound on its budget).
Statevector trajectories, SHOTS shots, seed 11, as aim2.py.  Usage: sim_aim2.py BASE PKG MODEL i/k"""
import json, math, os, sys
import numpy as np
BASE, PKG, MODEL, PART = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
SHOTS = int(os.environ.get("SHOTS", "2000"))
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, pauli_error, ReadoutError
PI = math.pi
C = json.load(open(f"{BASE}/circuits/index.json"))["circuits"]
ids = sorted(i for i, c in C.items() if c.get("aim") == 2 and c["qubits"] <= 12 and c["n2q"] <= 2000)
k, m = map(int, PART.split("/")); ids = ids[k::m]


def fold(t):
    t = abs(math.remainder(t, 2 * PI)); return min(t, PI - t)


def native_1q(t):
    t = abs(math.remainder(t, 2 * PI))
    if t < 1e-9: return 0
    if abs(t - PI / 2) < 1e-9 or abs(t - PI) < 1e-9: return 1
    return 2


def build(gl, nq, ncl):
    qc = QuantumCircuit(nq, ncl)
    at = [0] * nq; partner = [-1] * nq; memory_at = [0] * nq; moved = [False] * nq; moved_at = [False] * nq; layers = 0
    after = [None] * nq; pending = {}          # instruction slot -> list of (qubit, pz)
    ops = []
    r_mem = 1.95e-4 if MODEL == "quantinuum-h2-1-2023" else 0.0; one = 1.5 * r_mem
    def charge(q, kk):
        if r_mem <= 0 or kk <= 0 or after[q] is None: return
        pz = (1 - (1 - 2 * one) ** kk) / 2; pending.setdefault(after[q], []).append((q, pz))
    for name, qs, ps, cs in gl:
        if name == "rzz":
            t = fold(ps[0])
            if t < 1e-12: ops.append(("rzz", qs, ps, None)); continue
            a, b = qs
            if not (partner[a] == b and partner[b] == a):
                l = max(at[a], at[b]) + 1; at[a] = at[b] = l; partner[a], partner[b] = b, a; layers = max(layers, l)
                for q in qs:
                    if moved_at[q]: charge(q, l - memory_at[q])
                    memory_at[q] = l
            if MODEL == "quantinuum-h2-1-2023": r = 0.46e-3 + (1.91e-3 - 0.46e-3) * t / (PI / 2)
            else: r = 1 - 0.9936
            ops.append(("rzz", qs, ps, ("dep2", 4 * r / 3)))
            for q in qs: moved_at[q] = moved[q]; after[q] = len(ops) - 1
        elif name in ("rx", "ry"):
            q = qs[0]; moved[q] = True
            lam = 2 * 2.7e-5 if MODEL == "quantinuum-h2-1-2023" else 2 * (1 - 0.9999) * native_1q(ps[0])
            ops.append((name, qs, ps, ("dep1", lam) if lam > 0 else None))
        elif name == "rz": ops.append(("rz", qs, ps, None))
        elif name == "measure":
            ops.append(("measure", qs, cs, None)); moved[qs[0]] = moved_at[qs[0]] = False
        elif name == "reset":
            ops.append(("reset", qs, [], ("flip", 1.55e-3) if MODEL == "quantinuum-h2-1-2023" else None)); moved[qs[0]] = moved_at[qs[0]] = False
    for q in range(nq):
        if moved_at[q]: charge(q, layers - memory_at[q])
    for i, (name, qs, ps, err) in enumerate(ops):
        if name == "rzz": qc.rzz(ps[0], *qs)
        elif name in ("rx", "ry", "rz"): getattr(qc, name)(ps[0], qs[0])
        elif name == "measure": qc.measure(qs[0], ps[0])
        elif name == "reset": qc.reset(qs[0])
        if err:
            kind, x = err
            if kind == "dep2": qc.append(depolarizing_error(x, 2).to_instruction(), qs)
            elif kind == "dep1": qc.append(depolarizing_error(x, 1).to_instruction(), qs)
            elif kind == "flip": qc.append(pauli_error([("X", x), ("I", 1 - x)]).to_instruction(), qs)
        for q, pz in pending.get(i, []): qc.append(pauli_error([("Z", pz), ("I", 1 - pz)]).to_instruction(), [q])
    return qc


nm = NoiseModel()
if MODEL == "quantinuum-h2-1-2023": nm.add_all_qubit_readout_error(ReadoutError([[1 - 9e-4, 9e-4], [2.2e-3, 1 - 2.2e-3]]))
else: nm.add_all_qubit_readout_error(ReadoutError([[1 - 3.4e-3, 3.4e-3], [3.4e-3, 1 - 3.4e-3]]))
sim = AerSimulator(method="statevector", noise_model=nm)
out = []
for cid in ids:
    g = json.load(open(f"{BASE}/circuits/gates/{cid}.json")); c = C[cid]
    qc = build(g["gates"], g["qubits"], g["clbits"])
    cnt = sim.run(qc, shots=SHOTS, seed_simulator=11).result().get_counts()
    want = c["reference_bits_qiskit_order"]; ok = sum(v for k_, v in cnt.items() if k_.replace(" ", "") == want)
    out.append({"id": cid, "model": MODEL, "rzz": c["n2q"], "qubits": c["qubits"], "T": c["T"], "style": c["style"], "form": c["form"], "shots": SHOTS, "trace_fidelity": ok / SHOTS})
    print(cid, c["n2q"], ok / SHOTS, flush=True)
os.makedirs(f"{BASE}/models/sim", exist_ok=True)
json.dump(out, open(f"{BASE}/models/sim/aim2-{MODEL}-{k}of{m}.json", "w"), indent=1)

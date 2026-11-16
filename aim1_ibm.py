#!/usr/bin/env python3
"""Aim 1 QAOA circuits on IBM device topologies and calibration snapshots (qiskit-ibm-runtime fake backends).
Seed-0 instances at n = 12, cold and warm start, depths 1..3. Snapshots, not live devices."""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.abspath(__file__))
import os
import json, sys
import numpy as np
from qiskit import transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeTorino, FakeFez
sys.path.insert(0, ROOT)
from aim1_post import qaoa_circuit, diag_energy, EPS
R = os.path.join(ROOT, "results")
rows = []
for fam in "ABCD":
    d = json.load(open(f"{R}/aim1_{fam}_12_0.json")); post = json.load(open(f"{R}/post_{fam}_12_0.json")); gw = json.load(open(f"{R}/gw_{fam}_12_0.json"))
    n, h, edges = d["n"], d["h"], d["edges"]
    e = diag_energy(n, h, edges); e_min, e_max = float(e.min()), float(e.max())
    ground = set(int(g) for g in np.flatnonzero(e <= e_min + 1e-9 * (1 + abs(e_min))))
    x = np.array([(s + 1) // 2 for s in gw["gw16_state"]]); thetas = 2 * np.arcsin(np.sqrt(np.where(x == 1, 1 - EPS, EPS)))
    for bname, fb in (("ibm_torino_snapshot", FakeTorino()), ("ibm_fez_snapshot", FakeFez())):
        sim = AerSimulator.from_backend(fb)
        for kind, src in (("cold", d["qaoa"]), ("warm", post["ws"])):
            for q in src:
                qc = qaoa_circuit(n, h, edges, q["gamma"], q["beta"], thetas if kind == "warm" else None); qc.measure_all()
                best = None
                for seed in range(8):   # keep the best of 8 layout seeds, as a user would
                    tq = transpile(qc, backend=fb, optimization_level=3, seed_transpiler=seed)
                    two = sum(v for k, v in tq.count_ops().items() if k in ("cz", "ecr", "cx"))
                    if best is None or two < best[0]: best = (two, tq)
                two, tq = best
                active = len({qb for inst in tq.data for qb in inst.qubits})
                row = {"family": fam, "backend": bname, "kind": kind, "p": q["p"], "two_qubit_gates": int(two), "active_qubits": active, "ideal_p_gs": q["p_gs"]}
                if active <= 16:
                    shots = 1000
                    counts = sim.run(tq, shots=shots, seed_simulator=11).result().get_counts()
                    hit = sum(v for k, v in counts.items() if int(k.replace(" ", ""), 2) in ground)
                    emean = sum(v * e[int(k.replace(" ", ""), 2)] for k, v in counts.items()) / shots
                    row.update({"shots": shots, "p_gs": hit / shots, "ratio": float((e_max - emean) / (e_max - e_min))})
                rows.append(row); print(row, flush=True)
                json.dump(rows, open(f"{R}/aim1_ibm.json", "w"), indent=1)

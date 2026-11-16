#!/usr/bin/env python3
"""QCUP pre-submission, Aim 1 post-processing.

Reads the ferrotherm runner's JSON (exact spectrum, certified SDP bound, GW rounding, cold QAOA),
then: (1) cross-checks ferrotherm's QAOA expectation with an independent numpy state vector,
(2) runs warm-start QAOA (Egger, Marecek, Woerner 2021) seeded by ferrotherm's GW rounding,
(3) transpiles the QAOA circuits to a heavy-hex CZ target and an all-to-all RZZ target,
(4) for n <= 12, samples the transpiled circuits under a generic depolarizing noise model.
Nothing here knows the optimum except the scoring step.
"""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.abspath(__file__))
import os
import glob, json, math, os, sys
import numpy as np
from scipy.optimize import minimize

RES = os.path.join(ROOT, "results")
EPS = 0.25  # Egger et al. regularisation for rounded warm starts


def diag_energy(n, h, edges):
    z = np.arange(1 << n, dtype=np.uint32)
    s = [1.0 - 2.0 * (1 - ((z >> i) & 1)) for i in range(n)]  # bit set -> s = +1
    e = np.zeros(1 << n)
    for i in range(n):
        if h[i] != 0.0:
            e -= h[i] * s[i]
    for i, j, w in edges:
        e -= w * s[i] * s[j]
    return e


def apply_1q(psi, n, q, u):
    psi = psi.reshape([2] * n)
    ax = n - 1 - q  # qubit q is bit q of the index
    psi = np.moveaxis(np.tensordot(u, psi, axes=([1], [ax])), 0, ax)
    return psi.reshape(-1)


def qaoa_state(e, n, gam, bet, thetas=None):
    """Cold QAOA if thetas is None, else warm-start QAOA with per-qubit Ry(theta) init and mixer."""
    if thetas is None:
        psi = np.full(1 << n, 1 / math.sqrt(1 << n), dtype=complex)
    else:
        psi = np.ones(1, dtype=complex)
        for q in range(n - 1, -1, -1):
            psi = np.kron(psi, np.array([math.cos(thetas[q] / 2), math.sin(thetas[q] / 2)], dtype=complex))
    for g, b in zip(gam, bet):
        psi = psi * np.exp(-1j * g * e)
        for q in range(n):
            if thetas is None:
                c, s = math.cos(b), math.sin(b)
                u = np.array([[c, -1j * s], [-1j * s, c]])
            else:
                t = thetas[q]
                # exp(-i b H), H = -sin(t) X - cos(t) Z : ground state is the initial qubit state
                hm = np.array([[-math.cos(t), -math.sin(t)], [-math.sin(t), math.cos(t)]])
                u = math.cos(b) * np.eye(2) - 1j * math.sin(b) * hm
            psi = apply_1q(psi, n, q, u)
    return psi


def optimise(e, n, p, thetas, restarts, max_evals, seed, start=None):
    rng = np.random.default_rng(seed)
    best = None
    evals = 0

    def f(x):
        psi = qaoa_state(e, n, x[:p], x[p:], thetas)
        return float(np.dot(np.abs(psi) ** 2, e))

    starts = [] if start is None else [np.array(start)]
    scale = max(1e-9, float(np.max(np.abs(e))))
    while len(starts) < restarts:
        starts.append(np.concatenate([rng.uniform(0, 2 * math.pi / scale * 4, p), rng.uniform(0, math.pi, p)]))
    for x0 in starts:
        r = minimize(f, x0, method="Nelder-Mead", options={"maxfev": max_evals, "xatol": 1e-6, "fatol": 1e-10})
        evals += r.nfev
        if best is None or r.fun < best[0]:
            best = (r.fun, r.x)
    return best[0], best[1], evals


def qaoa_circuit(n, h, edges, gam, bet, thetas=None):
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(n)
    for q in range(n):
        if thetas is None:
            qc.h(q)
        else:
            qc.ry(thetas[q], q)
    for g, b in zip(gam, bet):
        # exp(-i g E), E = -sum w s_i s_j - sum h s_i, s = -Z (bit 1 -> s=+1): s_i s_j = Z_i Z_j, s_i = -Z_i
        for i, j, w in edges:
            qc.rzz(-2 * g * w, i, j)
        for i in range(n):
            if h[i] != 0.0:
                qc.rz(2 * g * h[i], i)
        for q in range(n):
            if thetas is None:
                qc.rx(2 * b, q)
            else:
                qc.ry(-thetas[q], q); qc.rz(-2 * b, q); qc.ry(thetas[q], q)
    return qc


def heavy_hex_patch(n):
    """A connected n-qubit patch of the distance-5 heavy-hex lattice (BFS from qubit 0), relabelled 0..n-1."""
    from qiskit.transpiler import CouplingMap
    full = CouplingMap.from_heavy_hex(5)
    adj = {}
    for a, b in full.get_edges():
        adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
    order, seen, queue = [], {0}, [0]
    while queue and len(order) < n:
        v = queue.pop(0); order.append(v)
        for w in sorted(adj[v]):
            if w not in seen:
                seen.add(w); queue.append(w)
    idx = {v: k for k, v in enumerate(order)}
    edges = sorted({(idx[a], idx[b]) for a in order for b in adj[a] if b in idx})
    return CouplingMap(edges)


def main():
    from qiskit import transpile
    from qiskit.transpiler import CouplingMap
    from qiskit.quantum_info import Statevector
    only = sys.argv[1:]
    for path in sorted(glob.glob(f"{RES}/aim1_[ABCDR]_*.json")):
        tag = os.path.basename(path)[5:-5]
        out = f"{RES}/post_{tag}.json"
        if os.path.exists(out) or (only and not any(tag.startswith(o) for o in only)):
            continue
        d = json.load(open(path))
        gw = json.load(open(f"{RES}/gw_{tag}.json"))
        n, h, edges = d["n"], d["h"], d["edges"]
        e = diag_energy(n, h, edges)
        e_min, e_max = float(e.min()), float(e.max())
        assert abs(e_min - d["e_min"]) < 1e-6 and abs(e_max - d["e_max"]) < 1e-6, "spectrum mismatch"
        ground = np.flatnonzero(e <= e_min + 1e-9 * (1 + abs(e_min)))
        assert len(ground) == d["n_ground"]
        rec = {"tag": tag, "family": d["family"], "n": n, "seed": d["seed"], "cross_check": [], "ws": [], "transpile": [], "noisy": []}

        # (1) independent cross-check of ferrotherm's cold QAOA at its own angles
        for q in d["qaoa"]:
            psi = qaoa_state(e, n, q["gamma"], q["beta"])
            pr = np.abs(psi) ** 2
            rec["cross_check"].append({"p": q["p"], "abs_diff_expectation": abs(float(pr @ e) - q["expectation"]),
                                       "abs_diff_p_gs": abs(float(pr[ground].sum()) - q["p_gs"])})

        # (2) warm-start QAOA from ferrotherm's best-of-16 GW rounding
        x = np.array([(s + 1) // 2 for s in gw["gw16_state"]])
        c = np.where(x == 1, 1 - EPS, EPS)
        thetas = 2 * np.arcsin(np.sqrt(c))
        psi0 = qaoa_state(e, n, [], [], thetas)
        pr0 = np.abs(psi0) ** 2
        rec["ws_p0"] = {"expectation": float(pr0 @ e), "ratio": float((e_max - pr0 @ e) / (e_max - e_min)), "p_gs": float(pr0[ground].sum())}
        rec["gw16_energy"] = gw["gw16_energy"]
        rec["gw16_is_optimal"] = bool(abs(gw["gw16_energy"] - e_min) < 1e-9 * (1 + abs(e_min)))
        prev = None
        R, M = d["opt_restarts"], d["opt_max_evals"]
        for p in (1, 2, 3):
            start = None if prev is None else np.concatenate([np.append(prev[:p - 1], 0.0), np.append(prev[p - 1:], 0.0)])
            val, xb, ev = optimise(e, n, p, thetas, R, M, 1000 + p, start)
            prev = xb
            pr = np.abs(qaoa_state(e, n, xb[:p], xb[p:], thetas)) ** 2
            rec["ws"].append({"p": p, "expectation": val, "ratio": float((e_max - val) / (e_max - e_min)),
                              "p_gs": float(pr[ground].sum()), "evaluations": ev, "gamma": list(map(float, xb[:p])), "beta": list(map(float, xb[p:]))})

        # (3) transpile (cold circuits; the warm-start circuit adds only single-qubit gates)
        hh = heavy_hex_patch(n)  # connected n-qubit patch of the heavy-hex lattice
        for q in d["qaoa"]:
            qc = qaoa_circuit(n, h, edges, q["gamma"], q["beta"])
            if q["p"] == 1:  # validate the circuit against the state vector once
                sv = np.abs(Statevector(qc).data) ** 2
                assert abs(float(sv @ e) - q["expectation"]) < 1e-6, "circuit does not reproduce the expectation"
            t_hh = transpile(qc, coupling_map=hh, basis_gates=["cz", "rz", "sx", "x"], optimization_level=3, seed_transpiler=7)
            t_aa = transpile(qc, basis_gates=["rzz", "rz", "rx", "ry"], optimization_level=3, seed_transpiler=7)
            rec["transpile"].append({"p": q["p"], "heavy_hex_cz": int(t_hh.count_ops().get("cz", 0)), "heavy_hex_2q_depth": int(t_hh.depth(lambda g: g.operation.num_qubits == 2)),
                                     "all_to_all_rzz": int(t_aa.count_ops().get("rzz", 0)), "all_to_all_2q_depth": int(t_aa.depth(lambda g: g.operation.num_qubits == 2))})

        # (4) noisy sampling, n <= 12 only: generic depolarizing model, NOT a device calibration
        if n <= 12 and d["seed"] == 0:
            from qiskit_aer import AerSimulator
            from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError
            models = {"sc_like": (3e-3, 3e-4, 1e-2, hh, ["cz", "rz", "sx", "x"]), "ion_like": (1e-3, 3e-5, 2e-3, None, ["rzz", "rz", "rx", "ry"])}
            for name, (p2, p1, pm, cmap, basis) in models.items():
                nm = NoiseModel(basis_gates=basis)
                nm.add_all_qubit_quantum_error(depolarizing_error(p2, 2), [basis[0]])
                nm.add_all_qubit_quantum_error(depolarizing_error(p1, 1), [b for b in basis[1:] if b != "rz"])
                nm.add_all_qubit_readout_error(ReadoutError([[1 - pm, pm], [pm, 1 - pm]]))
                sim = AerSimulator(noise_model=nm, method="statevector")
                for kind, src in (("cold", d["qaoa"]), ("warm", rec["ws"])):
                    for q in src:
                        qc = qaoa_circuit(n, h, edges, q["gamma"], q["beta"], thetas if kind == "warm" else None)
                        qc.measure_all()
                        tq = transpile(qc, coupling_map=cmap, basis_gates=basis, optimization_level=3, seed_transpiler=7)
                        shots = 2000
                        counts = sim.run(tq, shots=shots, seed_simulator=11).result().get_counts()
                        gset = set(int(g) for g in ground)
                        hit = sum(v for k, v in counts.items() if int(k.replace(" ", ""), 2) in gset)
                        emean = sum(v * e[int(k.replace(" ", ""), 2)] for k, v in counts.items()) / shots
                        rec["noisy"].append({"model": name, "kind": kind, "p": q["p"], "shots": shots, "p_gs": hit / shots,
                                             "ratio": float((e_max - emean) / (e_max - e_min)), "ideal_p_gs": q["p_gs"]})
        json.dump(rec, open(out, "w"))
        print(tag, "ok", [round(w["p_gs"], 4) for w in rec["ws"]], flush=True)


if __name__ == "__main__":
    main()

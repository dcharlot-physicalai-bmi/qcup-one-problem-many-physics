#!/usr/bin/env python3
"""Low-autocorrelation binary sequences (LABS): a problem family chosen because classical solvers run out early.

A sequence s in {+1,-1}^N has sidelobe energy E = sum_{k=1}^{N-1} C_k^2 with C_k = sum_i s_i s_{i+k}. Minimising E is the
design of pulse-compression codes for radar, sonar and ranging. It is one of the ten classes of the Quantum Optimization
Benchmarking Library (arXiv:2504.03832) and the problem with published evidence of a QAOA scaling advantage
(Shaydulin et al., Sci. Adv. 2024). The energy is quartic, so each substrate meets it differently:

  native    N spins, quartic energy: simulated annealing in the runner (LABS=1), the form a microcontroller would run
  quadratic N + N(N-1)/2 spins: one auxiliary w_ab = x_a x_b per pair, held by a Rosenberg penalty. This is what a
            pairwise fabric (p-bit array, spiking annealer) has to solve. Written here as Ising and QUBO files.
  quantum   N qubits, two- and four-body phase terms: exact state-vector QAOA, depths 1 to 3, and transpiled gate counts

Usage: labs.py gen | qaoa <N>... | circuits <N>... | request"""
import itertools, json, math, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
OUT = f"{ROOT}/results/labs"; LDIR = f"{ROOT}/labs"

def energies(N):
    """E of every sequence; bit i of the index set <-> s_i = +1."""
    x = np.arange(1 << N, dtype=np.uint64); e = np.zeros(1 << N, dtype=np.int64)
    for k in range(1, N):
        m = np.uint64((1 << (N - k)) - 1); c = (N - k) - 2 * np.bitwise_count((x ^ (x >> np.uint64(k))) & m).astype(np.int64); e += c * c
    return e

def spin_terms(N):
    """E as a polynomial in spins: {frozenset of sites: coefficient}, using s^2 = 1."""
    T = {}
    for k in range(1, N):
        for i in range(N - k):
            for j in range(N - k):
                key = frozenset({i, i + k}) ^ frozenset({j, j + k}); T[key] = T.get(key, 0) + 1
    return T

def quadratise(N, lam):
    """QUBO over x_0..x_{N-1} and one w per pair: returns (Q, const, index of w)."""
    pairs = list(itertools.combinations(range(N), 2)); widx = {p: N + t for t, p in enumerate(pairs)}; n = N + len(pairs)
    Q, const = {}, 0.0
    def add(i, j, c):
        if c: k = (min(i, j), max(i, j)); Q[k] = Q.get(k, 0.0) + c
    for k in range(1, N):
        lin, c0 = {}, 0.0                                  # C_k = c0 + sum_v lin[v] v, with s_a s_b = 4 w_ab - 2 x_a - 2 x_b + 1
        for i in range(N - k):
            a, b = i, i + k; c0 += 1; lin[widx[(a, b)]] = lin.get(widx[(a, b)], 0) + 4; lin[a] = lin.get(a, 0) - 2; lin[b] = lin.get(b, 0) - 2
        const += c0 * c0
        vs = list(lin.items())
        for u, au in vs: add(u, u, 2 * c0 * au + au * au)   # v^2 = v
        for (u, au), (v, av) in itertools.combinations(vs, 2): add(u, v, 2 * au * av)
    for (a, b), w in widx.items():                           # Rosenberg: x_a x_b - 2 x_a w - 2 x_b w + 3 w >= 0, zero iff w = x_a x_b
        add(a, b, lam); add(a, w, -2 * lam); add(b, w, -2 * lam); add(w, w, 3 * lam)
    return Q, const, widx, n

def qubo_value(Q, const, x): return const + sum(c * x[i] * x[j] for (i, j), c in Q.items())

def gen():
    # check the construction exhaustively at N = 5: the QUBO minimum equals the LABS optimum and is attained only at valid states
    N = 5; lam = 8 * N + 16; Q, const, widx, n = quadratise(N, lam); e = energies(N)
    z = np.arange(1 << n, dtype=np.uint32); bits = [((z >> i) & 1).astype(np.float64) for i in range(n)]; full = np.full(1 << n, const)
    for (i, j), c in Q.items(): full += c * bits[i] * bits[j]
    assert abs(full.min() - e.min()) < 1e-9, (full.min(), e.min())
    for zz in np.flatnonzero(full <= full.min() + 1e-9):
        assert all(((zz >> w) & 1) == (((zz >> a) & 1) & ((zz >> b) & 1)) for (a, b), w in widx.items())
    print("construction checked at N = 5:", n, "spins, minimum", full.min())
    meta = []
    for N in (8, 10, 12, 14, 16, 18, 20, 22):
        lam = 8 * N + 16; Q, const, widx, n = quadratise(N, lam); e_opt = int(energies(N).min())
        h = [0.0] * n; J = {}; off = const
        for (i, j), c in Q.items():
            c = c / lam
            if i == j: h[i] -= c / 2; off += lam * c / 2
            else: J[(i, j)] = -c / 4; h[i] -= c / 4; h[j] -= c / 4; off += lam * c / 4
        with open(f"{LDIR}/L_{n}_{N}.txt", "w") as f:
            f.write(f"{n}\n" + "".join(f"h {i} {v!r}\n" for i, v in enumerate(h) if v) + "".join(f"J {i} {j} {w!r}\n" for (i, j), w in sorted(J.items())))
        if n <= 64:   # the spiking annealer holds its state in one 64-bit word
            terms = sorted((i, j, c) for (i, j), c in Q.items())
            with open(f"{LDIR}/Lq_{N}.txt", "w") as f: f.write(f"{n} {float(e_opt)!r} {const!r} {len(terms)}\n" + "".join(f"{i} {j} {c!r}\n" for i, j, c in terms))
        meta.append({"N": N, "spins_quadratised": n, "couplings": len(J), "lambda": lam, "ising_scale": lam, "ising_offset": off, "labs_optimum": e_opt,
                     "ising_energy_of_optimum": (e_opt - off) / lam}); print(meta[-1])
    json.dump(meta, open(f"{OUT}/quadratised.json", "w"), indent=1)

def qaoa(Ns):
    from aim1_post import qaoa_state, optimise
    for N in Ns:
        e = energies(N).astype(np.float64); emin, emax = e.min(), e.max(); gs = e == emin; rec = {"N": N, "e_min": emin, "n_ground": int(gs.sum()), "depths": []}
        prev = None; R, M = (6, 400) if N <= 16 else (3, 250)
        for p in (1, 2, 3):
            start = None if prev is None else np.concatenate([np.append(prev[:p - 1], 0.0), np.append(prev[p - 1:], 0.0)])
            val, xb, ev = optimise(e, N, p, None, R, M, 7000 + p, start); prev = xb
            pr = np.abs(qaoa_state(e, N, xb[:p], xb[p:])) ** 2; pg = float(pr[gs].sum())
            rec["depths"].append({"p": p, "expectation": val, "ratio": float((emax - val) / (emax - emin)), "p_gs": pg, "uniform_p_gs": float(gs.sum() / gs.size),
                                  "shots_to_99pct": math.log(0.01) / math.log(1 - pg) if 0 < pg < 0.99 else None, "evaluations": ev, "gamma": list(map(float, xb[:p])), "beta": list(map(float, xb[p:]))})
            print(N, p, round(rec["depths"][-1]["ratio"], 4), pg, rec["depths"][-1]["uniform_p_gs"], flush=True)
        json.dump(rec, open(f"{OUT}/qaoa_{N}.json", "w"), indent=1)

def circuits(Ns):
    from qiskit import QuantumCircuit, transpile
    from qiskit.quantum_info import Statevector
    from aim1_post import heavy_hex_patch, qaoa_state
    for N in Ns:
        T = spin_terms(N); two = {k: c for k, c in T.items() if len(k) == 2}; four = {k: c for k, c in T.items() if len(k) == 4}
        assert set(map(len, T)) <= {0, 2, 4}
        def layer(qc, g):
            # exp(-i g E) with s = -Z (bit 1 <-> s = +1); even products of s equal the same products of Z
            for k, c in two.items(): a, b = sorted(k); qc.rzz(2 * g * c, a, b)
            for k, c in four.items():
                a, b, c2, d = sorted(k); qc.cx(a, b); qc.cx(b, c2); qc.cx(c2, d); qc.rz(2 * g * c, d); qc.cx(c2, d); qc.cx(b, c2); qc.cx(a, b)
        qc = QuantumCircuit(N); [qc.h(q) for q in range(N)]; layer(qc, 0.01); [qc.rx(0.4, q) for q in range(N)]
        if N <= 10:   # the circuit reproduces the state-vector expectation
            e = energies(N).astype(np.float64); ref = float(np.abs(qaoa_state(e, N, [0.01], [0.2])) ** 2 @ e); got = float(np.abs(Statevector(qc).data) ** 2 @ e)
            assert abs(ref - got) < 1e-6, (ref, got)
        t_hh = transpile(qc, coupling_map=heavy_hex_patch(N), basis_gates=["cz", "rz", "sx", "x"], optimization_level=3, seed_transpiler=7)
        t_aa = transpile(qc, basis_gates=["rzz", "rz", "rx", "ry"], optimization_level=3, seed_transpiler=7)
        rec = {"N": N, "two_body_terms": len(two), "four_body_terms": len(four), "heavy_hex_cz_per_layer": int(t_hh.count_ops().get("cz", 0)), "all_to_all_rzz_per_layer": int(t_aa.count_ops().get("rzz", 0))}
        json.dump(rec, open(f"{OUT}/circuit_{N}.json", "w"), indent=1); print(rec, flush=True)

def request():
    """Hardware circuits for this family: depth 1 at N = 8, 12, 16, 20 on the trapped-ion devices (all within 2,000 RZZ),
    and N = 8 at depths 1 and 2 on the superconducting devices (within 660 CZ). Cost by the public formulas used in cost.py."""
    from qiskit import QuantumCircuit, transpile
    out = {"trapped_ion": [], "superconducting": []}
    for N in (8, 12, 16, 20):
        T = spin_terms(N); qc = QuantumCircuit(N); [qc.h(q) for q in range(N)]
        for k, c in T.items():
            q = sorted(k)
            if len(q) == 2: qc.rzz(0.02 * c, q[0], q[1])
            elif len(q) == 4: qc.cx(q[0], q[1]); qc.cx(q[1], q[2]); qc.cx(q[2], q[3]); qc.rz(0.02 * c, q[3]); qc.cx(q[2], q[3]); qc.cx(q[1], q[2]); qc.cx(q[0], q[1])
        [qc.rx(0.4, q) for q in range(N)]
        t = transpile(qc, basis_gates=["rzz", "rz", "rx", "ry"], optimization_level=3, seed_transpiler=7); c = t.count_ops()
        n1, n2 = int(sum(c.get(g, 0) for g in ("rz", "rx", "ry"))), int(c.get("rzz", 0)); assert n2 <= 2000
        out["trapped_ion"].append({"N": N, "p": 1, "n1q": n1, "n2q": n2, "hqc_at_200_shots": round(5 + 200 * (n1 + 10 * n2 + 5 * 2 * N) / 5000), "ionq_two_qubit_gate_shots_at_500": 500 * n2})
    c8 = json.load(open(f"{OUT}/circuit_8.json"))["heavy_hex_cz_per_layer"]
    out["superconducting"] = [{"N": 8, "p": p, "heavy_hex_cz": p * c8} for p in (1, 2) if p * c8 <= 660]
    out["totals"] = {"quantinuum_hqc": sum(r["hqc_at_200_shots"] for r in out["trapped_ion"]), "ionq_two_qubit_gate_shots": sum(r["ionq_two_qubit_gate_shots_at_500"] for r in out["trapped_ion"]),
                     "circuits": {"IBM": len(out["superconducting"]), "IQM": len(out["superconducting"]), "IonQ": len(out["trapped_ion"]), "Quantinuum": len(out["trapped_ion"])}}
    json.dump(out, open(f"{OUT}/request.json", "w"), indent=1); print(out)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True); os.makedirs(LDIR, exist_ok=True)
    {"gen": lambda a: gen(), "qaoa": lambda a: qaoa(list(map(int, a))), "circuits": lambda a: circuits(list(map(int, a))), "request": lambda a: request()}[sys.argv[1]](sys.argv[2:])

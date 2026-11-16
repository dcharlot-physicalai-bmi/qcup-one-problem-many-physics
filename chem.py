#!/usr/bin/env python3
"""Chemistry: the problem class where a quantum processor has a physical reason to matter, because the object is quantum.

Scenario: a field lab has to judge candidate molecules and reaction steps with whatever computing it carries. Most
candidates are handled by cheap electronic-structure methods. Some are not: stretched and breaking bonds and other
strongly correlated cases, the prototypes of reaction barriers and correlated materials. The routing question is which
candidates the on-device estimate can be trusted for.

Tiers, all on the same Hamiltonian (STO-3G, core orbitals frozen):
  cheap      RHF, MP2, CCSD, CCSD(T) with PySCF: what an edge processor can afford
  diagnostic computed from the cheap run alone: the T1 diagnostic and the largest doubles amplitude. A case is routed
             to the quantum tier when T1 > 0.02 (Lee and Taylor 1989) or max |t2| > 0.1. Thresholds fixed before any run.
  exact      full configuration interaction: the answer, and what exact emulation of the quantum tier returns
  quantum    unitary coupled cluster with singles and doubles (UCCSD), one Trotter step, variationally optimised from zero
             amplitudes on an exact state vector; its circuit (Jordan-Wigner) transpiled to count two-qubit gates
A cheap answer is called wrong when it misses the exact energy by more than chemical accuracy, 1.6 millihartree.
Geometries were fixed before any run: each system near equilibrium and stretched. Hydrogen chains are the standard
small model of a correlated material.
Usage: chem.py classical | vqe <max qubits> | circuits <max qubits> | sqd <max qubits> | request"""
import itertools, json, math, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); OUT = f"{ROOT}/results/chem"
CHEM_ACC = 1.6e-3; T1_MAX, T2_MAX = 0.02, 0.1

def chain(n, r): return "; ".join(f"H 0 0 {k * r}" for k in range(n))
def h2o(scale):
    r, a = 0.9572 * scale, math.radians(104.52 / 2); return f"O 0 0 0; H {r * math.sin(a)} 0 {r * math.cos(a)}; H {-r * math.sin(a)} 0 {r * math.cos(a)}"
SYSTEMS = [("H2", chain(2, 0.74), "eq", 0), ("H2", chain(2, 1.5), "stretched", 0), ("H2", chain(2, 2.5), "broken", 0),
           ("H4 chain", chain(4, 0.9), "eq", 0), ("H4 chain", chain(4, 1.5), "stretched", 0), ("H4 chain", chain(4, 2.0), "broken", 0),
           ("H4 square", "H 0 0 0; H 1.2 0 0; H 1.2 1.2 0; H 0 1.2 0", "square", 0),
           ("H6 chain", chain(6, 0.9), "eq", 0), ("H6 chain", chain(6, 1.5), "stretched", 0), ("H6 chain", chain(6, 2.0), "broken", 0),
           ("LiH", "Li 0 0 0; H 0 0 1.6", "eq", 1), ("LiH", "Li 0 0 0; H 0 0 3.0", "stretched", 1),
           ("BeH2", "Be 0 0 0; H 0 0 1.33; H 0 0 -1.33", "eq", 1), ("BeH2", "Be 0 0 0; H 0 0 2.5; H 0 0 -2.5", "stretched", 1),
           ("H2O", h2o(1.0), "eq", 1), ("H2O", h2o(2.0), "stretched", 1),
           ("N2", "N 0 0 0; N 0 0 1.10", "eq", 2), ("N2", "N 0 0 0; N 0 0 1.80", "stretched", 2)]

def setup(atom, ncore):
    from pyscf import gto, scf, mcscf
    mol = gto.M(atom=atom, basis="sto-3g", verbose=0); mf = scf.RHF(mol); mf.conv_tol = 1e-10; mf.kernel()
    ncas = mol.nao - ncore; nel = mol.nelectron - 2 * ncore; mc = mcscf.CASCI(mf, ncas, nel); mc.fcisolver.conv_tol = 1e-11
    return mol, mf, mc, ncas, nel

def classical():
    from pyscf import cc, mp
    rows = []
    for name, atom, label, ncore in SYSTEMS:
        mol, mf, mc, ncas, nel = setup(atom, ncore); e_fci = float(mc.kernel()[0]); r = {"system": name, "geometry": label, "atom": atom, "frozen_core_orbitals": ncore, "orbitals": ncas, "electrons": nel, "qubits": 2 * ncas,
             "rhf_converged": bool(mf.converged), "e_rhf": float(mf.e_tot), "e_fci": e_fci}
        r["e_mp2"] = float(mp.MP2(mf, frozen=ncore).run().e_tot)
        c = cc.CCSD(mf, frozen=ncore); c.conv_tol = 1e-9; c.max_cycle = 200; c.kernel(); r["ccsd_converged"] = bool(c.converged); r["e_ccsd"] = float(c.e_tot)
        try: r["e_ccsd_t"] = float(c.e_tot + c.ccsd_t())
        except Exception as ex: r["e_ccsd_t"] = None
        ncorr = nel; r["t1_diagnostic"] = float(np.linalg.norm(c.t1) / math.sqrt(ncorr)); r["max_abs_t2"] = float(np.abs(c.t2).max())
        r["routed_to_quantum"] = bool(r["t1_diagnostic"] > T1_MAX or r["max_abs_t2"] > T2_MAX or not c.converged)
        for m in ("rhf", "mp2", "ccsd", "ccsd_t"): r[f"err_{m}_mha"] = None if r[f"e_{m}"] is None else 1000 * (r[f"e_{m}"] - e_fci)
        r["ccsd_wrong"] = bool(abs(r["err_ccsd_mha"]) > 1000 * CHEM_ACC)
        rows.append(r); print(name, label, r["qubits"], "q | err mHa: RHF %.1f MP2 %.1f CCSD %.2f CCSD(T) %s | T1 %.3f max|t2| %.3f | routed %s | CCSD wrong %s" % (
            r["err_rhf_mha"], r["err_mp2_mha"], r["err_ccsd_mha"], "%.2f" % r["err_ccsd_t_mha"] if r["e_ccsd_t"] is not None else "-", r["t1_diagnostic"], r["max_abs_t2"], r["routed_to_quantum"], r["ccsd_wrong"]), flush=True)
    json.dump(rows, open(f"{OUT}/classical.json", "w"), indent=1)

# ---- second quantisation on the fixed-particle-number sector (Jordan-Wigner order: spin orbital p = 2 * orbital + spin)
def sector(n, nel):
    import scipy.sparse as sp
    states = [z for z in range(1 << n) if bin(z).count("1") == nel and bin(z & 0x5555555555555555).count("1") == nel // 2]   # N electrons, Sz = 0
    index = {z: k for k, z in enumerate(states)}
    def apply(ops, z):      # ops: list of (p, dagger) applied right to left; returns (sign, state) or None
        s = 1
        for p, dag in reversed(ops):
            occ = (z >> p) & 1
            if occ == dag: return None
            s *= -1 if bin(z & ((1 << p) - 1)).count("1") & 1 else 1; z ^= 1 << p
        return s, z
    def matrix(terms):      # terms: list of (coefficient, ops)
        r_, c_, v_ = [], [], []
        for coef, ops in terms:
            if abs(coef) < 1e-12: continue
            for k, z in enumerate(states):
                o = apply(ops, z)
                if o is not None and o[1] in index: r_.append(index[o[1]]); c_.append(k); v_.append(coef * o[0])
        return sp.csr_matrix((v_, (r_, c_)), shape=(len(states), len(states)))
    return states, index, matrix

def hamiltonian(mc, ncas, matrix):
    h1, ecore = mc.get_h1eff(); from pyscf import ao2mo
    h2 = ao2mo.restore(1, mc.get_h2eff(), ncas); terms = []
    for p, q in itertools.product(range(ncas), repeat=2):
        for s in (0, 1): terms.append((h1[p, q], [(2 * p + s, 1), (2 * q + s, 0)]))
    for p, q, r, s in itertools.product(range(ncas), repeat=4):
        if abs(h2[p, q, r, s]) < 1e-12: continue
        for a, b in itertools.product((0, 1), repeat=2):
            if (2 * p + a) == (2 * r + b) or (2 * q + a) == (2 * s + b): continue
            terms.append((0.5 * h2[p, q, r, s], [(2 * p + a, 1), (2 * r + b, 1), (2 * s + b, 0), (2 * q + a, 0)]))
    return matrix(terms), float(ecore)

def excitations(ncas, nel):
    occ = [2 * i + s for i in range(nel // 2) for s in (0, 1)]; vir = [2 * i + s for i in range(nel // 2, ncas) for s in (0, 1)]; ex = []
    for i in occ:
        for a in vir:
            if i % 2 == a % 2: ex.append(((a,), (i,)))
    for i, j in itertools.combinations(occ, 2):
        for a, b in itertools.combinations(vir, 2):
            if (i % 2) + (j % 2) == (a % 2) + (b % 2): ex.append(((a, b), (i, j)))
    return ex

def vqe(maxq):
    from scipy.sparse.linalg import expm_multiply
    from scipy.optimize import minimize
    cl = {(r["system"], r["geometry"]): r for r in json.load(open(f"{OUT}/classical.json"))}
    rows = json.load(open(f"{OUT}/vqe.json")) if os.path.exists(f"{OUT}/vqe.json") else []; done = {(r["system"], r["geometry"]) for r in rows}
    for name, atom, label, ncore in SYSTEMS:
        mol, mf, mc, ncas, nel = setup(atom, ncore); n = 2 * ncas
        if n > maxq or (name, label) in done: continue
        states, index, matrix = sector(n, nel); H, ecore = hamiltonian(mc, ncas, matrix)
        e_exact = float(np.linalg.eigvalsh(H.toarray())[0] + ecore); assert abs(e_exact - cl[(name, label)]["e_fci"]) < 1e-7, (e_exact, cl[(name, label)]["e_fci"])
        ex = excitations(ncas, nel); G = []
        for cre, ann in ex:
            ops = [(p, 1) for p in cre] + [(q, 0) for q in reversed(ann)]; m = matrix([(1.0, ops)]); G.append((m - m.T).tocsc())
        hf = np.zeros(len(states)); hf[index[(1 << nel) - 1]] = 1.0
        def energy(th):
            psi = hf
            for g, t in zip(G, th):
                if t != 0.0: psi = expm_multiply(t * g, psi)
            return float(psi @ (H @ psi)) + ecore
        assert abs(energy(np.zeros(len(G))) - cl[(name, label)]["e_rhf"]) < 1e-7
        res = minimize(energy, np.zeros(len(G)), method="L-BFGS-B", options={"maxiter": 200 if n <= 8 else 80, "ftol": 1e-12, "gtol": 1e-7})
        r = {"system": name, "geometry": label, "qubits": n, "sector_dimension": len(states), "excitations": len(G), "e_uccsd": float(res.fun), "err_uccsd_mha": 1000 * (float(res.fun) - e_exact), "iterations": int(res.nit), "evaluations": int(res.nfev)}
        rows.append(r); print(name, label, n, "q", len(G), "excitations | UCCSD err %.3f mHa (CCSD %.3f) | iterations %d" % (r["err_uccsd_mha"], cl[(name, label)]["err_ccsd_mha"], res.nit), flush=True)
        json.dump(rows, open(f"{OUT}/vqe.json", "w"), indent=1)

def circuits(maxq):
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import PauliEvolutionGate
    from qiskit.quantum_info import SparsePauliOp
    from aim1_post import heavy_hex_patch
    rows = []; seen = set()
    for name, atom, label, ncore in SYSTEMS:
        mol, mf, mc, ncas, nel = setup(atom, ncore); n = 2 * ncas
        if n > maxq or (name, n, nel) in seen: continue
        seen.add((name, n, nel))
        def ladder(p, dag):   # Jordan-Wigner: a_p = Z...Z (X + iY)/2
            z = "I" * (n - p - 1); lo = "Z" * p
            return SparsePauliOp([z + "X" + lo, z + "Y" + lo], [0.5, -0.5j if dag else 0.5j])
        qc = QuantumCircuit(n)
        for q in range(nel): qc.x(q)
        for cre, ann in excitations(ncas, nel):
            op = None
            for p, dag in [(p, 1) for p in cre] + [(q, 0) for q in reversed(ann)]: op = ladder(p, dag) if op is None else op.compose(ladder(p, dag))
            gen = (op - op.adjoint()).simplify()                # anti-Hermitian generator; i * gen is Hermitian
            herm = SparsePauliOp(gen.paulis, (1j * gen.coeffs).real).simplify()
            qc.append(PauliEvolutionGate(herm, time=0.1), range(n))
        t_aa = transpile(qc, basis_gates=["rzz", "rz", "rx", "ry"], optimization_level=3, seed_transpiler=7)
        t_hh = transpile(qc, coupling_map=heavy_hex_patch(n), basis_gates=["cz", "rz", "sx", "x"], optimization_level=3, seed_transpiler=7)
        r = {"system": name, "qubits": n, "electrons": nel, "excitations": len(excitations(ncas, nel)), "all_to_all_rzz": int(t_aa.count_ops().get("rzz", 0)), "heavy_hex_cz": int(t_hh.count_ops().get("cz", 0))}
        rows.append(r); print(r, flush=True); json.dump(rows, open(f"{OUT}/circuits.json", "w"), indent=1)

def sqd(maxq):
    """What a sample from the quantum tier buys. Hardware cannot afford to measure every term of a molecular Hamiltonian, so
    the plan is the hybrid method used on today's largest chemistry runs: sample configurations from the circuit in the
    computational basis, then diagonalise the Hamiltonian classically in the space those configurations span.
    Emulated here in the best case for the quantum tier, sampling the exact ground state, and with the trapped-ion noise
    model as a mixture (with probability 1 - F the shot is a uniformly random configuration of the right particle number;
    F from the fitted fidelity law and the UCCSD gate count). Baseline: uniformly random configurations only.
    Reported: median energy error over 20 repeats against the number of shots."""
    cc_ = {r["system"]: r for r in json.load(open(f"{OUT}/circuits.json"))}; summ = json.load(open(f"{ROOT}/results/summary.json"))
    loss = summ["aim2"]["fidelity_fits"]["ion_like"]["loss_per_two_qubit_gate_pct"] / 100; rng = np.random.default_rng(20261114); rows = []
    for name, atom, label, ncore in SYSTEMS:
        mol, mf, mc, ncas, nel = setup(atom, ncore); n = 2 * ncas
        if n > maxq: continue
        states, index, matrix = sector(n, nel); H, ecore = hamiltonian(mc, ncas, matrix); Hd = H.toarray(); w, v = np.linalg.eigh(Hd); e0 = w[0]; p0 = v[:, 0] ** 2; D = len(states)
        F = (1 - loss) ** cc_[name]["all_to_all_rzz"]; uni = np.full(D, 1.0 / D); rec = {"system": name, "geometry": label, "qubits": n, "configurations": D, "modelled_fidelity": F, "curves": {}}
        for arm, p in (("ideal", p0), ("trapped_ion_model", F * p0 + (1 - F) * uni), ("uniform", uni)):
            curve = []
            for shots in (10, 30, 100, 300, 1000):
                errs = []
                for _ in range(20):
                    idx = np.unique(np.concatenate([[index[(1 << nel) - 1]], rng.choice(D, size=shots, p=p)]))      # the Hartree-Fock configuration is always included
                    errs.append(1000 * (np.linalg.eigvalsh(Hd[np.ix_(idx, idx)])[0] - e0))
                curve.append([shots, float(np.median(errs))])
            rec["curves"][arm] = curve; rec[f"{arm}_shots_to_chemical_accuracy"] = next((s for s, e in curve if e <= 1000 * CHEM_ACC), None)
        rows.append(rec); print(name, label, D, "configs, F %.2f |" % F, {a: rec[f"{a}_shots_to_chemical_accuracy"] for a in rec["curves"]}, flush=True)
    json.dump(rows, open(f"{OUT}/sqd.json", "w"), indent=1)

def request():
    """Hardware circuits for chemistry, one per case, sampled in the computational basis (see sqd). IonQ: every case up to
    10 qubits. Quantinuum: the 12-qubit cases the cheap method gets wrong. IBM and IQM: the 4-qubit cases, the only ones
    within 660 CZ. Costs by the public formulas used in cost.py; one-qubit counts from the transpiled circuits."""
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import PauliEvolutionGate
    from qiskit.quantum_info import SparsePauliOp
    cl = json.load(open(f"{OUT}/classical.json")); ops = {}
    for name, atom, label, ncore in SYSTEMS:
        mol, mf, mc, ncas, nel = setup(atom, ncore); n = 2 * ncas
        if n > 12 or name in ops: continue
        def ladder(p, dag):
            z = "I" * (n - p - 1); lo = "Z" * p; return SparsePauliOp([z + "X" + lo, z + "Y" + lo], [0.5, -0.5j if dag else 0.5j])
        qc = QuantumCircuit(n); [qc.x(q) for q in range(nel)]
        for cre, ann in excitations(ncas, nel):
            op = None
            for p, dag in [(p, 1) for p in cre] + [(q, 0) for q in reversed(ann)]: op = ladder(p, dag) if op is None else op.compose(ladder(p, dag))
            gen = (op - op.adjoint()).simplify(); qc.append(PauliEvolutionGate(SparsePauliOp(gen.paulis, (1j * gen.coeffs).real).simplify(), time=0.1), range(n))
        c = transpile(qc, basis_gates=["rzz", "rz", "rx", "ry"], optimization_level=3, seed_transpiler=7).count_ops()
        ops[name] = {"n": n, "n1q": int(sum(c.get(g, 0) for g in ("rz", "rx", "ry"))), "n2q": int(c.get("rzz", 0))}
    out = {"IonQ": [], "Quantinuum": [], "IBM": [], "IQM": []}
    for r in cl:
        if r["system"] not in ops: continue
        o = ops[r["system"]]; tag = f"{r['system']} {r['geometry']}"
        if o["n"] <= 10: out["IonQ"].append({"case": tag, **o, "shots": 1000, "two_qubit_gate_shots": 1000 * o["n2q"]})
        if o["n"] == 12 and r["ccsd_wrong"]: out["Quantinuum"].append({"case": tag, **o, "shots": 200, "hqc": round(5 + 200 * (o["n1q"] + 10 * o["n2q"] + 5 * 2 * o["n"]) / 5000)})
        if o["n"] == 4: out["IBM"].append({"case": tag, "shots": 4000}); out["IQM"].append({"case": tag, "shots": 2000})
    out["totals"] = {"circuits": {k: len(v) for k, v in out.items()}, "ionq_two_qubit_gate_shots": sum(x["two_qubit_gate_shots"] for x in out["IonQ"]), "quantinuum_hqc": sum(x["hqc"] for x in out["Quantinuum"]),
                     "shots": {k: sum(x["shots"] for x in out[k]) for k in ("IonQ", "Quantinuum", "IBM", "IQM")}}
    json.dump(out, open(f"{OUT}/request.json", "w"), indent=1); print(out["totals"])

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    {"classical": classical, "vqe": lambda: vqe(int(sys.argv[2])), "circuits": lambda: circuits(int(sys.argv[2])), "sqd": lambda: sqd(int(sys.argv[2])), "request": request}[sys.argv[1]]()

#!/usr/bin/env python3
"""Materials: the Fermi-Hubbard model, the standard minimal model of a correlated material, on small square lattices.

Chosen because it is the one family here whose quantum circuits stay inside device gate budgets at sizes exact emulation
cannot reach, and for which published classical benchmark energies exist (LeBlanc et al., Phys. Rev. X 5, 041041 (2015)).
H = -t sum_<ij>,s (c+_is c_js + h.c.) + U sum_i n_i,up n_i,down, open boundaries, half filling, t = 1, U = 2, 4, 8.

Tiers:
  cheap      restricted and unrestricted Hartree-Fock, and CCSD with its trust check (as in chem.py): an edge processor
  inspired   density-matrix renormalisation group (a tensor network: the quantum-inspired tier) at bond dimension 16, 64, 256;
             the change in energy between the last two bond dimensions is its own trust signal
  exact      exact diagonalisation up to 8 sites (16 qubits)
  quantum    Hamiltonian variational ansatz: from the non-interacting ground state, p layers of exp(-i a H_U) exp(-i b H_h)
             exp(-i c H_v), 3 angles per layer, emulated exactly up to 8 sites; one layer's circuit transpiled up to 6x6
Usage: hubbard.py cheap | exact | dmrg <max sites> | hva | hva_product | circuits | request"""
import itertools, json, math, os, sys, time, warnings
import numpy as np
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); OUT = f"{ROOT}/results/hubbard"
US = (2.0, 4.0, 8.0); LATTICES = [(2, 2), (2, 3), (2, 4), (3, 4), (4, 4), (4, 6)]

def bonds(Lx, Ly):
    h = [(x * Ly + y, (x + 1) * Ly + y) for x in range(Lx - 1) for y in range(Ly)]; v = [(x * Ly + y, x * Ly + y + 1) for x in range(Lx) for y in range(Ly - 1)]
    return h, v
def hop_matrix(Lx, Ly):
    L = Lx * Ly; T = np.zeros((L, L))
    for a, b in sum(bonds(Lx, Ly), []): T[a, b] = T[b, a] = -1.0
    return T

def cheap():
    from pyscf import gto, scf, cc, ao2mo
    rows = []
    for (Lx, Ly), U in itertools.product(LATTICES, US):
        L = Lx * Ly; T = hop_matrix(Lx, Ly); eps, C = np.linalg.eigh(T); occ = C[:, : L // 2]; dens = (occ ** 2).sum(1)
        r = {"lattice": f"{Lx}x{Ly}", "sites": L, "U": U, "e_rhf": float(2 * eps[: L // 2].sum() + U * (dens ** 2).sum()), "closed_shell": bool(eps[L // 2] - eps[L // 2 - 1] > 1e-8)}
        nu = np.array([0.9 if (i // Ly + i % Ly) % 2 == 0 else 0.1 for i in range(L)]); nd = 1.0 - nu
        for _ in range(2000):   # unrestricted Hartree-Fock from a staggered start, simple mixing
            eu, Cu = np.linalg.eigh(T + U * np.diag(nd)); ed, Cd = np.linalg.eigh(T + U * np.diag(nu)); nu2 = (Cu[:, : L // 2] ** 2).sum(1); nd2 = (Cd[:, : L // 2] ** 2).sum(1)
            if max(np.abs(nu2 - nu).max(), np.abs(nd2 - nd).max()) < 1e-10: break
            nu, nd = 0.5 * nu + 0.5 * nu2, 0.5 * nd + 0.5 * nd2
        r["e_uhf"] = float(eu[: L // 2].sum() + ed[: L // 2].sum() - U * (nu * nd).sum()); r["uhf_staggered_moment"] = float(np.abs(nu - nd).mean())
        try:
            mol = gto.M(verbose=0); mol.nelectron = L; mol.incore_anyway = True; mf = scf.RHF(mol); mf.get_hcore = lambda *a: T; mf.get_ovlp = lambda *a: np.eye(L)
            eri = np.zeros((L,) * 4); [eri.__setitem__((i, i, i, i), U) for i in range(L)]; mf._eri = ao2mo.restore(8, eri, L); mf.conv_tol = 1e-10; mf.kernel()
            c = cc.CCSD(mf); c.conv_tol = 1e-8; c.max_cycle = 300; c.kernel()
            r.update({"rhf_converged": bool(mf.converged), "e_rhf_pyscf": float(mf.e_tot), "ccsd_converged": bool(c.converged), "e_ccsd": float(c.e_tot), "t1_diagnostic": float(np.linalg.norm(c.t1) / math.sqrt(L)), "max_abs_t2": float(np.abs(c.t2).max())})
            r["routed_to_quantum"] = bool(r["t1_diagnostic"] > 0.02 or r["max_abs_t2"] > 0.1 or not c.converged)
        except Exception as ex: r["ccsd_error"] = str(ex)[:120]
        rows.append(r); print(r["lattice"], U, "RHF %.4f UHF %.4f CCSD %s routed %s" % (r["e_rhf"], r["e_uhf"], ("%.4f" % r["e_ccsd"]) if "e_ccsd" in r else "-", r.get("routed_to_quantum")), flush=True)
    json.dump(rows, open(f"{OUT}/cheap.json", "w"), indent=1)

def operators(Lx, Ly):
    from chem import sector
    L = Lx * Ly; n = 2 * L; states, index, matrix = sector(n, L); hb, vb = bonds(Lx, Ly)
    hop = lambda bs: matrix([(-1.0, [(2 * a + s, 1), (2 * b + s, 0)]) for a, b in bs for s in (0, 1)] + [(-1.0, [(2 * b + s, 1), (2 * a + s, 0)]) for a, b in bs for s in (0, 1)])
    HU = matrix([(1.0, [(2 * i, 1), (2 * i, 0), (2 * i + 1, 1), (2 * i + 1, 0)]) for i in range(L)])
    return states, hop(hb), hop(vb), HU

def exact():
    rows = []
    for (Lx, Ly), U in itertools.product([l for l in LATTICES if l[0] * l[1] <= 8], US):
        states, Hh, Hv, HU = operators(Lx, Ly); e = float(np.linalg.eigvalsh((Hh + Hv + U * HU).toarray())[0])
        rows.append({"lattice": f"{Lx}x{Ly}", "sites": Lx * Ly, "U": U, "dimension": len(states), "e_exact": e}); print(rows[-1], flush=True)
    json.dump(rows, open(f"{OUT}/exact.json", "w"), indent=1)

def dmrg_run(maxsites):
    from tenpy.models.hubbard import FermiHubbardModel
    from tenpy.networks.mps import MPS
    from tenpy.algorithms import dmrg
    rows = json.load(open(f"{OUT}/dmrg.json")) if os.path.exists(f"{OUT}/dmrg.json") else []; done = {(r["lattice"], r["U"]) for r in rows}
    for (Lx, Ly), U in itertools.product([l for l in LATTICES if l[0] * l[1] <= maxsites], US):
        if (f"{Lx}x{Ly}", U) in done: continue
        M = FermiHubbardModel(dict(lattice="Square", Lx=Lx, Ly=Ly, bc_x="open", bc_y="open", bc_MPS="finite", t=1.0, U=U, mu=0.0, cons_N="N", cons_Sz="Sz")); L = Lx * Ly
        psi = MPS.from_product_state(M.lat.mps_sites(), ["up", "down"] * (L // 2), bc="finite"); r = {"lattice": f"{Lx}x{Ly}", "sites": L, "U": U, "runs": []}
        for chi in (16, 64, 256):
            t0 = time.time(); info = dmrg.run(psi, M, dict(mixer=True, max_E_err=1e-8, max_trunc_err=None, trunc_params=dict(chi_max=chi, svd_min=1e-10), max_sweeps=24))
            r["runs"].append({"chi": chi, "energy": float(info["E"]), "max_bond": int(max(psi.chi)), "seconds": round(time.time() - t0, 1)})
        r["e_dmrg"] = r["runs"][-1]["energy"]; r["change_64_to_256"] = r["runs"][-1]["energy"] - r["runs"][-2]["energy"]; r["saturated"] = bool(r["runs"][-1]["max_bond"] < 256)
        rows.append(r); print(r["lattice"], U, [(x["chi"], round(x["energy"], 5), x["seconds"]) for x in r["runs"]], flush=True); json.dump(rows, open(f"{OUT}/dmrg.json", "w"), indent=1)

def hva():
    from scipy.sparse.linalg import expm_multiply
    from scipy.optimize import minimize
    rows = []; rng = np.random.default_rng(55)
    for (Lx, Ly), U in itertools.product([l for l in LATTICES if l[0] * l[1] <= 8], US):
        states, Hh, Hv, HU = operators(Lx, Ly); H = (Hh + Hv + U * HU).tocsr(); e0 = float(np.linalg.eigvalsh(H.toarray())[0])
        w, v = np.linalg.eigh((Hh + Hv + 1e-6 * HU).toarray()); psi0 = v[:, 0].astype(complex); degenerate = bool(w[1] - w[0] < 1e-4)   # a tiny U picks one state if the free ground state is degenerate
        Hh_, Hv_, HU_ = Hh.tocsc(), Hv.tocsc(), HU.tocsc(); r = {"lattice": f"{Lx}x{Ly}", "sites": Lx * Ly, "U": U, "free_ground_state_degenerate": degenerate, "e_exact": e0, "e_start": float((psi0.conj() @ (H @ psi0)).real), "depths": []}
        def energy(x):
            psi = psi0
            for k in range(len(x) // 3): psi = expm_multiply(-1j * x[3 * k + 2] * Hv_, expm_multiply(-1j * x[3 * k + 1] * Hh_, expm_multiply(-1j * x[3 * k] * HU_, psi)))
            return float((psi.conj() @ (H @ psi)).real)
        prev = np.zeros(0)
        for p in (1, 2, 3, 4):
            best = None
            for x0 in [np.concatenate([prev, np.zeros(3)])] + [rng.uniform(-0.5, 0.5, 3 * p) for _ in range(3)]:
                res = minimize(energy, x0, method="BFGS", options={"maxiter": 150, "gtol": 1e-6})
                if best is None or res.fun < best.fun: best = res
            prev = best.x; r["depths"].append({"p": p, "energy": float(best.fun), "error_per_site": float((best.fun - e0) / (Lx * Ly)), "relative_error": float((best.fun - e0) / abs(e0))})
        rows.append(r); print(r["lattice"], U, "start err/site %.4f" % ((r["e_start"] - e0) / (Lx * Ly)), [round(d["error_per_site"], 5) for d in r["depths"]], flush=True); json.dump(rows, open(f"{OUT}/hva.json", "w"), indent=1)

def hva_product():
    """The same ansatz started from a product state (the Neel pattern: one electron per site, spins alternating), which needs
    no two-qubit gates to prepare. These are the circuits the hardware request counts."""
    from scipy.sparse.linalg import expm_multiply
    from scipy.optimize import minimize
    rows = []; rng = np.random.default_rng(56)
    for (Lx, Ly), U in itertools.product([l for l in LATTICES if l[0] * l[1] <= 8], US):
        states, Hh, Hv, HU = operators(Lx, Ly); H = (Hh + Hv + U * HU).tocsr(); e0 = float(np.linalg.eigvalsh(H.toarray())[0])
        neel = sum(1 << (2 * (x * Ly + y) + ((x + y) % 2)) for x in range(Lx) for y in range(Ly)); psi0 = np.zeros(len(states), complex); psi0[list(states).index(neel)] = 1.0
        Hh_, Hv_, HU_ = Hh.tocsc(), Hv.tocsc(), HU.tocsc(); r = {"lattice": f"{Lx}x{Ly}", "sites": Lx * Ly, "U": U, "start": "neel_product_state", "e_exact": e0, "e_start": float((psi0.conj() @ (H @ psi0)).real), "depths": []}
        def energy(x):
            psi = psi0
            for k in range(len(x) // 3): psi = expm_multiply(-1j * x[3 * k + 2] * HU_, expm_multiply(-1j * x[3 * k + 1] * Hv_, expm_multiply(-1j * x[3 * k] * Hh_, psi)))
            return float((psi.conj() @ (H @ psi)).real)
        prev = np.zeros(0)
        for p in (1, 2, 3, 4):
            best = None
            for x0 in [np.concatenate([prev, np.zeros(3)])] + [rng.uniform(-0.5, 0.5, 3 * p) for _ in range(3)]:
                res = minimize(energy, x0, method="BFGS", options={"maxiter": 150, "gtol": 1e-6})
                if best is None or res.fun < best.fun: best = res
            prev = best.x; r["depths"].append({"p": p, "energy": float(best.fun), "error_per_site": float((best.fun - e0) / (Lx * Ly))})
        rows.append(r); print(r["lattice"], U, "start err/site %.4f" % ((r["e_start"] - e0) / (Lx * Ly)), [round(d["error_per_site"], 5) for d in r["depths"]], flush=True); json.dump(rows, open(f"{OUT}/hva_product.json", "w"), indent=1)

def circuits():
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import PauliEvolutionGate
    from qiskit.quantum_info import SparsePauliOp
    from aim1_post import heavy_hex_patch
    rows = []
    for Lx, Ly in LATTICES + [(6, 6)]:
        L = Lx * Ly; n = 2 * L; hb, vb = bonds(Lx, Ly); q = lambda i, s: i + s * L          # all spin-up modes, then all spin-down: hops within a spin species only
        qc = QuantumCircuit(n)
        for i in range(L): qc.rzz(0.1, q(i, 0), q(i, 1))                                      # on-site term: one ZZ per site (single-qubit parts omitted from the count)
        for a, b in hb + vb:
            for s in (0, 1):
                lo, hi = sorted((q(a, s), q(b, s))); lab = lambda P: "".join("I" if k < lo or k > hi else (P if k in (lo, hi) else "Z") for k in reversed(range(n)))
                qc.append(PauliEvolutionGate(SparsePauliOp([lab("X"), lab("Y")], [0.5, 0.5]), time=0.1), range(n))
        t_aa = transpile(qc, basis_gates=["rzz", "rz", "rx", "ry"], optimization_level=3 if n <= 48 else 1, seed_transpiler=7); r = {"lattice": f"{Lx}x{Ly}", "sites": L, "qubits": n, "rzz_per_layer": int(t_aa.count_ops().get("rzz", 0)), "state_preparation_two_qubit_gates": L * L}
        if n <= 32: r["cz_per_layer"] = int(transpile(qc, coupling_map=heavy_hex_patch(n) if n <= 57 else None, basis_gates=["cz", "rz", "sx", "x"], optimization_level=3, seed_transpiler=7).count_ops().get("cz", 0))
        rows.append(r); print(r, flush=True); json.dump(rows, open(f"{OUT}/circuits.json", "w"), indent=1)

def request():
    """Hardware circuits for the Hubbard family, by the admission rule (660 CZ heavy-hex, 2,000 RZZ all-to-all), at U = 4 and 8,
    measured in the computational basis (double occupancy, staggered spin correlations and
    particle-number conservation). IBM and IQM: every lattice and depth up to 4 that fits. IonQ (36 qubits): 4x4 at depths
    1 to 3. Quantinuum (98 qubits): 4x6 and 6x6, the sizes past exact emulation, at depths 1 and 2. Angles above 8 sites are
    transferred from the emulated lattices. Starting state: the Neel product state on IBM and IQM and on the 72-qubit lattice
    (no preparation gates); the free-fermion ground state on IonQ (4x4) and on the 48-qubit lattice, with preparation counted
    as L^2 two-qubit gates (Givens rotations; an estimate, not a transpiled count). HQC by the public formula, one-qubit gates counted from the transpiled layer."""
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import PauliEvolutionGate
    from qiskit.quantum_info import SparsePauliOp
    ci = {r["lattice"]: r for r in json.load(open(f"{OUT}/circuits.json"))}; out = {"IBM": [], "IQM": [], "IonQ": [], "Quantinuum": []}
    for lat, c in ci.items():
        for p in (1, 2, 3, 4):
            for U in (4.0, 8.0):
                if "cz_per_layer" in c and p * c["cz_per_layer"] <= 660: out["IBM"].append({"lattice": lat, "p": p, "U": U, "start": "neel_product_state", "cz": p * c["cz_per_layer"], "shots": 4000}); out["IQM"].append({"lattice": lat, "p": p, "U": U, "start": "neel_product_state", "cz": p * c["cz_per_layer"], "shots": 2000})
                if lat == "4x4" and p <= 3: g = p * c["rzz_per_layer"] + c["state_preparation_two_qubit_gates"]; out["IonQ"].append({"lattice": lat, "p": p, "U": U, "start": "free_fermion_ground_state", "rzz": g, "of_which_state_preparation_estimate": c["state_preparation_two_qubit_gates"], "shots": 500, "two_qubit_gate_shots": 500 * g})
    for Lx, Ly in ((4, 6), (6, 6)):
        L = Lx * Ly; n = 2 * L; hb, vb = bonds(Lx, Ly); q = lambda i, s: i + s * L; qc = QuantumCircuit(n)
        for i in range(L): qc.rzz(0.1, q(i, 0), q(i, 1)); qc.rz(0.1, q(i, 0)); qc.rz(0.1, q(i, 1))
        for a, b in hb + vb:
            for s_ in (0, 1):
                lo, hi = sorted((q(a, s_), q(b, s_))); lab = lambda P: "".join("I" if k < lo or k > hi else (P if k in (lo, hi) else "Z") for k in reversed(range(n)))
                qc.append(PauliEvolutionGate(SparsePauliOp([lab("X"), lab("Y")], [0.5, 0.5]), time=0.1), range(n))
        c = transpile(qc, basis_gates=["rzz", "rz", "rx", "ry"], optimization_level=1, seed_transpiler=7).count_ops(); n1, n2 = int(sum(c.get(g, 0) for g in ("rz", "rx", "ry"))), int(c.get("rzz", 0))
        prep = L * L if L * L + n2 <= 2000 else 0        # free-fermion start (about L^2 two-qubit gates by Givens rotations, an estimate) where one layer still fits; otherwise the product start
        for p in (1, 2):
            if p * n2 + prep > 2000: continue
            for U in (4.0, 8.0): g2, g1 = p * n2 + prep, p * n1 + L + 2 * prep; out["Quantinuum"].append({"lattice": f"{Lx}x{Ly}", "qubits": n, "p": p, "U": U, "start": "free_fermion_ground_state" if prep else "neel_product_state", "rzz": g2, "of_which_state_preparation_estimate": prep, "n1q": g1, "shots": 200, "hqc": round(5 + 200 * (g1 + 10 * g2 + 5 * n) / 5000)})
    out["totals"] = {"circuits": {k: len(v) for k, v in out.items()}, "shots": {k: sum(x["shots"] for x in v) for k, v in out.items()}, "ionq_two_qubit_gate_shots": sum(x["two_qubit_gate_shots"] for x in out["IonQ"]), "quantinuum_hqc": sum(x["hqc"] for x in out["Quantinuum"])}
    json.dump(out, open(f"{OUT}/request.json", "w"), indent=1); print(out["totals"]); print([(x["lattice"], x["p"], x["rzz"], x["hqc"]) for x in out["Quantinuum"] if x["U"] == 4.0])

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    {"cheap": cheap, "exact": exact, "dmrg": lambda: dmrg_run(int(sys.argv[2])), "hva": hva, "hva_product": hva_product, "circuits": circuits, "request": request}[sys.argv[1]]()

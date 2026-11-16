#!/usr/bin/env python3
"""Target chemistry: active-space models of species an autonomous lab would meet in the proposal's three settings, run
through every tier of the ladder. Supersedes the first exploratory pass.

  orbit / planetary surface   FeO, MnO, NiO: oxides of the metals a robotic chemist used from Martian meteorites to make
                              oxygen-evolution catalysts (Zhu et al., Nature Synthesis 2023)
  undersea                    FeS: iron-sulfur chemistry of hydrothermal vents and corrosion
  hazardous / nuclear sites   uranyl UO2(2+) and PuO2: actinide oxides of nuclear waste (plutonium oxides were run on
                              trapped ions at up to 19 qubits by Sorathia et al., arXiv:2510.25675)
Each at an equilibrium-like and a stretched (x1.4) bond length, fixed before any run. def2-SVP (CRENBL effective core
potentials and basis on U and Pu), ROHF in the stated spin state, then an active space chosen by the AVAS rule (Sayfutyarova
et al. 2017): the metal d (or f) shell and the oxygen or sulfur p shell. No orbital optimisation and no spin-orbit
coupling. For U and Pu, which the AVAS reference basis lacks, the highest occupied and lowest empty ROHF orbitals
with more than 40% metal-f plus oxygen-p character are taken instead (13 orbitals). These are models that pose the routing question, not predictions for the real molecules. Every tier works on
the same active-space Hamiltonian, which is what would cross the link (results/targets/<case>.npz).

Stages (targets.py model | ladder | sample | request):
  model     build and store each active-space Hamiltonian
  ladder    exact     lowest state at the stated S_z (full CI in the active space)
            cheap     UHF from the carried-over reference determinant, then CCSD on it
            check 1   amplitude diagnostics from that CCSD (T1 > 0.02 or max |t2| > 0.1 or no convergence), as in chem.py
            check 2   reference search: 8 UHF restarts from randomly rotated orbitals, each followed down by stability
                      analysis. Flag if any restart is lower than the reference by more than 1 mHa.
            cheap 2   CCSD on the lowest mean field found, with check 1 applied again
            strong    selected CI (the strong classical method an edge processor or a remote computer can run) at a
                      ladder of thresholds: subspace dimension needed for chemical accuracy
  sample    the remote tier as an untrusted proposer of configurations. Whatever proposes them, the edge diagonalises the
            Hamiltonian in their span, and that energy is a rigorous upper bound: the certificate for chemistry.
            Proposers: uniformly random configurations; the exact ground state (the best any quantum circuit could do);
            a one-layer unitary cluster Jastrow circuit built from the cheap-2 amplitudes (ffsim); the same at the
            modelled trapped-ion fidelity. Compared with selected CI at equal subspace dimension.
  request   the hardware circuits (results/targets/request.json)
Thresholds and seeds were fixed before the runs. A cheap answer is wrong when it misses by more than 1.6 mHa."""
import json, math, os, sys, time, warnings
os.environ.setdefault("OMP_NUM_THREADS", "1")       # one thread: several cases sit near mean-field instabilities and their energies depend on summation order
import numpy as np
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__)); OUT = os.environ.get("TARGETS_OUT", f"{ROOT}/results/targets"); CHEM_ACC = 1.6e-3; T1_MAX, T2_MAX = 0.02, 0.1; REF_GAP = 1e-3
def di(a, b, r): return f"{a} 0 0 0; {b} 0 0 {r}"
def tri(m, r): return f"{m} 0 0 0; O 0 0 {r}; O 0 0 {-r}"
# name, setting, builder, r_eq (angstrom), charge, 2S, AVAS labels
T = [("FeO", "orbit", lambda r: di("Fe", "O", r), 1.62, 0, 4, ["Fe 3d", "O 2p"]), ("MnO", "orbit", lambda r: di("Mn", "O", r), 1.65, 0, 5, ["Mn 3d", "O 2p"]),
     ("NiO", "orbit", lambda r: di("Ni", "O", r), 1.63, 0, 2, ["Ni 3d", "O 2p"]), ("FeS", "undersea", lambda r: di("Fe", "S", r), 2.02, 0, 4, ["Fe 3d", "S 3p"]),
     ("UO2(2+)", "hazard", lambda r: tri("U", r), 1.70, 2, 0, ["U 5f", "O 2p"]), ("PuO2", "hazard", lambda r: tri("Pu", r), 1.81, 0, 4, ["Pu 5f", "O 2p"])]
CASES = [(n, s, b, round(req * f, 3), c, sp, lab, g) for n, s, b, req, c, sp, lab in T for g, f in (("eq", 1.0), ("stretched", 1.4))]
key = lambda name, g: f"{name.replace('(', '').replace(')', '').replace('+', 'p')}_{g}"

def model():
    from pyscf import gto, scf, mcscf, ao2mo
    from pyscf.mcscf import avas
    os.makedirs(OUT, exist_ok=True); rows = []
    for name, setting, build, r, charge, spin, labels, g in CASES:
        np.random.seed(7); t0 = time.time(); heavy = name[:2] in ("UO", "Pu")
        mol = gto.M(atom=build(r), basis={"default": "def2-svp", "U": "crenbl", "Pu": "crenbl"} if heavy else "def2-svp", ecp={"U": "crenbl", "Pu": "crenbl"} if heavy else None, charge=charge, spin=spin, verbose=0)
        mf = scf.ROHF(mol); mf.max_cycle = 300; mf.level_shift = 0.3; mf.kernel()
        if not mf.converged: mf = scf.newton(mf); mf.kernel()
        e_first = float(mf.e_tot)
        for _ in range(4):                               # follow ROHF instabilities down, so the carried-over reference is at least a stable ROHF solution
            mo_new = mf.stability(verbose=0)[0]
            if np.allclose(mo_new, mf.mo_coeff): break
            mf.level_shift = 0.0; mf.kernel(dm0=mf.make_rdm1(mo_new, mf.mo_occ))
            if not mf.converged: mf = scf.newton(mf); mf.kernel()
        if heavy:      # AVAS's reference basis has no actinides: take the ROHF orbitals with the most metal-f plus oxygen-p character
            S = mf.get_ovlp(); C = mf.mo_coeff; lab = mol.ao_labels(); idx = [i for i, l in enumerate(lab) if (l.split()[1] in ("U", "Pu") and "f" in l.split()[2]) or (l.split()[1] == "O" and "2p" in l.split()[2])]
            w = np.einsum("ip,ip->p", C[idx], (S @ C)[idx]); nd = int((mf.mo_occ == 2).sum()); ns = int((mf.mo_occ == 1).sum()); docc = sorted([p for p in range(nd) if w[p] > 0.4][-6:]); virt = [p for p in range(nd + ns, C.shape[1]) if w[p] > 0.4][: 7 - ns]   # highest occupied and lowest empty orbitals of that character
            act = docc + list(range(nd, nd + ns)) + virt; core = [p for p in range(nd) if p not in docc]; rest = [p for p in range(nd + ns, C.shape[1]) if p not in virt]
            mo = C[:, core + act + rest]; ncas = len(act); nel = 2 * len(docc) + ns
        else: ncas, nel, mo = avas.avas(mf, labels, threshold=0.2, canonicalize=False, verbose=0)
        nel = int(round(nel)); na = (nel + spin) // 2; nb = nel - na
        mc = mcscf.CASCI(mf, ncas, (na, nb)); h1, ecore = mc.get_h1eff(mo); eri = ao2mo.restore(1, mc.get_h2eff(mo), ncas)
        np.savez_compressed(f"{OUT}/{key(name, g)}.npz", h1=h1, eri=eri, ecore=ecore, nelec=np.array([na, nb]))
        rows.append({"case": key(name, g), "system": name, "setting": setting, "geometry": g, "bond_angstrom": r, "charge": charge, "two_S": spin, "avas": labels, "rohf_converged": bool(mf.converged), "e_rohf": float(mf.e_tot), "rohf_lowered_by_stability_mha": 1000 * (e_first - float(mf.e_tot)),
                     "orbitals": int(ncas), "electrons": [int(na), int(nb)], "qubits": int(2 * ncas), "hamiltonian_bytes_compressed": os.path.getsize(f"{OUT}/{key(name, g)}.npz"), "seconds": round(time.time() - t0, 1)})
        print(rows[-1], flush=True); json.dump(rows, open(f"{OUT}/model.json", "w"), indent=1)

def load(case):
    d = np.load(f"{OUT}/{case}.npz"); return d["h1"], d["eri"], float(d["ecore"]), tuple(int(x) for x in d["nelec"])

def meanfield(h1, eri, ecore, nelec, dm0):
    from pyscf import gto, scf, ao2mo
    n = h1.shape[0]; mol = gto.M(verbose=0); mol.nelectron = sum(nelec); mol.spin = nelec[0] - nelec[1]; mol.incore_anyway = True; mol.nao_nr = lambda *a: n
    mf = scf.UHF(mol); mf.get_hcore = lambda *a: h1; mf.get_ovlp = lambda *a: np.eye(n); mf._eri = ao2mo.restore(8, eri, n); mf.energy_nuc = lambda *a: ecore; mf.max_cycle = 200; mf.conv_tol = 1e-10
    mf.kernel(dm0=dm0)
    for _ in range(4):                                   # follow internal instabilities down
        mo_new = mf.stability(verbose=0)[0]
        if all(np.allclose(a, b) for a, b in zip(mo_new, mf.mo_coeff)): break
        mf.kernel(dm0=mf.make_rdm1(mo_new, mf.mo_occ))
    return mf

def ccsd(mf, nelec):
    from pyscf import cc
    c = cc.UCCSD(mf); c.conv_tol = 1e-8; c.max_cycle = 300; c.verbose = 0
    try: c.kernel()
    except Exception as ex: return {"converged": False, "error": repr(ex)[:80]}, None
    t1a, t1b = c.t1; r = {"converged": bool(c.converged), "energy": float(c.e_tot), "t1_diagnostic": float(math.sqrt((np.linalg.norm(t1a) ** 2 + np.linalg.norm(t1b) ** 2) / sum(nelec))), "max_abs_t2": float(max([np.abs(x).max() for x in c.t2 if x.size] + [0.0]))}
    r["flag_amplitudes"] = bool(r["t1_diagnostic"] > T1_MAX or r["max_abs_t2"] > T2_MAX or not c.converged); return r, c

def references(h1, eri, ecore, nelec):
    """The carried-over reference and the lowest of 8 restarts from randomly rotated orbitals."""
    from scipy.linalg import expm
    n = h1.shape[0]; occ = lambda k: np.diag([1.0] * k + [0.0] * (n - k)); ref = meanfield(h1, eri, ecore, nelec, (occ(nelec[0]), occ(nelec[1]))); best = ref; rng = np.random.default_rng(2026); es = []
    for k in range(8):
        dm = []
        for ne in nelec:
            a = rng.normal(size=(n, n)) * 0.6; u = expm(a - a.T); dm.append(u @ occ(ne) @ u.T)
        m = meanfield(h1, eri, ecore, nelec, tuple(dm)); es.append(float(m.e_tot))
        if m.converged and m.e_tot < best.e_tot - 1e-7: best = m
    return ref, best, es

class Sector:
    """The active-space Hamiltonian on its fixed (N_alpha, N_beta) sector, applied without building the matrix."""
    def __init__(self, h1, eri, ecore, nelec):
        from pyscf import fci
        from pyscf.fci import cistring
        self.n = h1.shape[0]; self.nelec = nelec; self.ecore = ecore; self.fci = fci.direct_spin1; self.h2e = self.fci.absorb_h1e(h1, eri, self.n, nelec, 0.5)
        self.hdiag = self.fci.make_hdiag(h1, eri, self.n, nelec).ravel() + ecore; self.sa = cistring.make_strings(range(self.n), nelec[0]); self.sb = cistring.make_strings(range(self.n), nelec[1]); self.shape = (len(self.sa), len(self.sb)); self.dim = self.hdiag.size
    def apply(self, c): return self.fci.contract_2e(self.h2e, c.reshape(self.shape), self.n, self.nelec).ravel() + self.ecore * c
    def rayleigh(self, c, strs):
        """Energy of a product-space vector recomputed as a Rayleigh quotient with the full Hamiltonian: an upper bound that does not rely on the subspace solver."""
        v = np.zeros(self.shape); v[np.ix_(np.searchsorted(self.sa, strs[0]), np.searchsorted(self.sb, strs[1]))] = np.asarray(c); v = v.ravel(); return float(v @ self.apply(v) / (v @ v))
    def lowest_diagonal_strings(self, k=8):
        """Alpha and beta strings of the k determinants of lowest diagonal energy: a symmetry-agnostic starting space."""
        idx = np.argsort(self.hdiag)[:k]; db = self.shape[1]; return np.unique(self.sa[idx // db]), np.unique(self.sb[idx % db])
    def fixed_space(self, h1, eri, strs):
        """Lowest energy of the Hamiltonian in the product space of the given alpha and beta strings: a rigorous upper bound."""
        from pyscf.fci import selected_ci
        my = selected_ci.SCI(); my.conv_tol = 1e-9; my.verbose = 0
        if len(strs[0]) * len(strs[1]) == 1: return float(self.hdiag[np.searchsorted(self.sa, strs[0][0]) * self.shape[1] + np.searchsorted(self.sb, strs[1][0])])
        st = (np.asarray(strs[0], dtype=np.int64), np.asarray(strs[1], dtype=np.int64)); rng = np.random.default_rng(5); best = None
        for _ in range(2):          # random starting vectors, so the solver is not confined to the symmetry of one determinant
            g = rng.normal(size=(len(st[0]), len(st[1]))); e, c = selected_ci.kernel_fixed_space(my, h1, eri, self.n, self.nelec, st, ci0=selected_ci._as_SCIvector(g / np.linalg.norm(g), st), ecore=self.ecore); e = self.rayleigh(c, st); best = e if best is None else min(best, e)
        return best
    def selected_ci(self, h1, eri):
        """Selected CI (PySCF's product-space selection) at a ladder of thresholds, started from the 8 determinants of lowest diagonal energy."""
        from pyscf.fci import selected_ci
        sa, sb = self.lowest_diagonal_strings(); out = []; rng = np.random.default_rng(5); g = rng.normal(size=(len(sa), len(sb))); ci0 = selected_ci._as_SCIvector(g / np.linalg.norm(g), (sa.astype(np.int64), sb.astype(np.int64)))
        for cut in (1e-1, 3e-2, 1e-2, 3e-3, 1e-3, 3e-4, 1e-4):
            my = selected_ci.SCI(); my.select_cutoff = cut; my.ci_coeff_cutoff = cut; my.conv_tol = 1e-9; my.verbose = 0
            try: e, c = selected_ci.kernel_float_space(my, h1, eri, self.n, self.nelec, ci0=ci0, ecore=self.ecore); g = np.asarray(c) + 0.05 * rng.normal(size=np.asarray(c).shape) / math.sqrt(np.asarray(c).size); ci0 = selected_ci._as_SCIvector(g / np.linalg.norm(g), c._strs); out.append({"cutoff": cut, "dimension": int(len(c._strs[0]) * len(c._strs[1])), "energy": self.rayleigh(c, c._strs), "solver_energy": float(e)})
            except Exception as ex: out.append({"cutoff": cut, "error": repr(ex)[:80]})
            if out[-1].get("dimension", 0) >= self.dim: break
        return out

def exact(h1, eri, ecore, nelec):
    """Lowest of three Davidson roots of full CI at the stated S_z. Returns energy and vector."""
    from pyscf import fci
    n = h1.shape[0]; cis = fci.direct_spin1.FCI(); cis.conv_tol = 1e-10; cis.max_cycle = 400; cis.nroots = 3; cis.verbose = 0; es, cs = cis.kernel(h1, eri, n, nelec, ecore=ecore); k = int(np.argmin(es)); sec = Sector(h1, eri, ecore, nelec); v = cs[k].ravel(); return float(v @ sec.apply(v) / (v @ v)), cs[k]     # energy recomputed as a Rayleigh quotient

def ladder():
    from pyscf import fci
    meta = {r["case"]: r for r in json.load(open(f"{OUT}/model.json"))}; rows = []
    for case, m in meta.items():
        np.random.seed(7); t0 = time.time(); h1, eri, ecore, nelec = load(case); n = h1.shape[0]; r = {k: m[k] for k in ("case", "system", "setting", "geometry", "orbitals", "electrons", "qubits")}; tm = {}
        t = time.time(); e0, civ = exact(h1, eri, ecore, nelec); r["e_exact_davidson"] = e0; r["dimension"] = int(civ.size); tm["exact"] = time.time() - t
        t = time.time(); ref, best, es = references(h1, eri, ecore, nelec); tm["reference_search"] = time.time() - t
        r["e_uhf_reference"] = float(ref.e_tot); r["e_uhf_lowest"] = float(best.e_tot); r["restart_energies"] = es; r["flag_reference"] = bool(ref.e_tot - best.e_tot > REF_GAP)
        t = time.time(); c1, _ = ccsd(ref, nelec); tm["cheap"] = time.time() - t; t = time.time(); c2, _ = ccsd(best, nelec) if r["flag_reference"] else (c1, None); tm["cheap2"] = time.time() - t if r["flag_reference"] else 0.0
        t = time.time(); sec = Sector(h1, eri, ecore, nelec); sc = sec.selected_ci(h1, eri); tm["selected_ci"] = time.time() - t
        e0 = min([e0] + [x["energy"] for x in sc if "energy" in x]); r["e_exact"] = e0; r["exact_lowered_by_selected_ci_mha"] = 1000 * (r["e_exact_davidson"] - e0)     # every tier here is variational, so the lowest energy found is the reference
        for x in sc:
            if "energy" in x: x["error_mha"] = 1000 * (x["energy"] - e0)
        for tag, c in (("cheap", c1), ("cheap2", c2)):
            r[tag] = c; c["error_mha"] = 1000 * (c["energy"] - e0) if "energy" in c else None; c["wrong"] = bool(c["error_mha"] is None or abs(c["error_mha"]) > 1000 * CHEM_ACC or not c["converged"])
            if "flag_amplitudes" not in c: c["flag_amplitudes"] = True
        r["check1_flags"] = c1["flag_amplitudes"]; r["check12_flags"] = bool(c1["flag_amplitudes"] or r["flag_reference"]); r["cheap2_flags"] = c2["flag_amplitudes"]; r["selected_ci"] = sc
        ok = [x for x in sc if "error_mha" in x and x["error_mha"] <= 1000 * CHEM_ACC]; r["selected_ci_dimension_for_chemical_accuracy"] = min((x["dimension"] for x in ok), default=None)
        en = [x for x in sc if "energy" in x]; hit = next((c_ for a_, b_, c_ in zip(en, en[1:], en[2:]) if abs(a_["energy"] - b_["energy"]) < CHEM_ACC and abs(b_["energy"] - c_["energy"]) < CHEM_ACC and c_["dimension"] > a_["dimension"]), None)   # self-check, visible without the exact answer: two successive thresholds each move the energy by less than chemical accuracy while the space grows
        r["selected_ci_self_check_dimension"] = None if hit is None else hit["dimension"]; r["selected_ci_self_check_error_mha"] = None if hit is None else hit["error_mha"]
        r["seconds"] = {k: round(v, 2) for k, v in tm.items()}; rows.append(r)
        print(case, n, nelec, "dim", r["dimension"], "| cheap err %s flag1 %s | ref gap %.1f mHa flag2 %s | cheap2 err %s flag %s | SCI dim %s self-check dim %s err %s | %s" % (
            None if c1["error_mha"] is None else round(c1["error_mha"], 2), r["check1_flags"], 1000 * (ref.e_tot - best.e_tot), r["flag_reference"], None if c2["error_mha"] is None else round(c2["error_mha"], 2), r["cheap2_flags"], r["selected_ci_dimension_for_chemical_accuracy"], r["selected_ci_self_check_dimension"], None if r["selected_ci_self_check_error_mha"] is None else round(r["selected_ci_self_check_error_mha"], 2), {k: round(v, 2) for k, v in tm.items()}), flush=True)
        json.dump(rows, open(f"{OUT}/ladder.json", "w"), indent=1)

def lucj_state(sec, mf, c, count_gates=True):
    """One-layer unitary cluster Jastrow state from coupled-cluster amplitudes (ffsim), expressed in the stored orbital basis."""
    import ffsim
    n, nelec = sec.n, sec.nelec; op = ffsim.UCJOpSpinUnbalanced.from_t_amplitudes(c.t2, t1=c.t1, n_reps=1); Ca, Cb = mf.mo_coeff
    hf = ffsim.hartree_fock_state(n, nelec); rot = None
    for cand in ((Ca, Cb), (Ca.T.copy(), Cb.T.copy())):       # fix the rotation convention by checking the mean-field energy
        v = ffsim.apply_orbital_rotation(hf, cand, norb=n, nelec=nelec); e = float(np.real(np.vdot(v, sec.apply(np.real(v)) if np.abs(v.imag).max() < 1e-12 else sec.apply(v.real) + 1j * sec.apply(v.imag))))
        if abs(e - mf.e_tot) < 1e-6: rot = cand; break
    assert rot is not None, "orbital rotation convention not matched"
    v = ffsim.apply_orbital_rotation(ffsim.apply_unitary(hf, op, norb=n, nelec=nelec), rot, norb=n, nelec=nelec); e = float(np.real(np.vdot(v, sec.apply(v.real) + 1j * sec.apply(v.imag)))); out = {"energy": e}
    if count_gates:
        from qiskit import QuantumCircuit, QuantumRegister, transpile
        q = QuantumRegister(2 * n); qc = QuantumCircuit(q); qc.append(ffsim.qiskit.PrepareHartreeFockJW(n, nelec), q); qc.append(ffsim.qiskit.UCJOpSpinUnbalancedJW(op), q); qc.append(ffsim.qiskit.OrbitalRotationJW(n, rot), q)
        t = transpile(ffsim.qiskit.PRE_INIT.run(qc), basis_gates=["rzz", "rz", "rx", "ry"], optimization_level=1, seed_transpiler=7).count_ops(); out["rzz"] = int(t.get("rzz", 0)); out["one_qubit_gates"] = int(sum(t.get(g, 0) for g in ("rz", "rx", "ry")))
    return np.abs(v) ** 2, out

def sample():
    """Subspace energies from configurations proposed four ways, at 100 to 100,000 shots."""
    from pyscf import fci
    lad = {r["case"]: r for r in json.load(open(f"{OUT}/ladder.json"))}; rows = json.load(open(f"{OUT}/sample.json")) if os.path.exists(f"{OUT}/sample.json") else []; done = {r["case"] for r in rows}
    for case, L in lad.items():
        if case in done: continue
        np.random.seed(7); t0 = time.time(); h1, eri, ecore, nelec = load(case); sec = Sector(h1, eri, ecore, nelec); n = sec.n; _, civ = exact(h1, eri, ecore, nelec); e0 = L["e_exact"]; pex = civ.ravel() ** 2; pex /= pex.sum()
        r = {"case": case, "qubits": 2 * n, "dimension": sec.dim, "e_exact": e0, "proposers": {}}; ref, best, _ = references(h1, eri, ecore, nelec); cinfo, c = ccsd(best, nelec); props = {"random": None, "exact_state": pex}
        if c is not None and np.isfinite(c.e_tot):
            plu, info = lucj_state(sec, best, c); plu = plu / plu.sum(); F = math.exp(-0.0006 * info["rzz"]); r["lucj"] = {**info, "amplitudes_converged": bool(cinfo["converged"]), "error_mha": 1000 * (info["energy"] - e0), "modelled_fidelity": F, "overlap_with_exact": float(np.sum(np.sqrt(plu * pex)) ** 2)}; props["lucj_ideal"] = plu; props["lucj_noisy"] = plu
        else: r["lucj"] = {"skipped": "coupled cluster failed"}
        grid = (100, 1000, 10000, 100000) if sec.dim < 200000 else (100, 1000, 10000); db = sec.shape[1]
        for pname, p in props.items():
            rng = np.random.default_rng(11); pts = []
            for shots in grid:
                if pname == "random": idx = rng.integers(0, sec.dim, shots); kept = shots
                elif pname == "lucj_noisy":
                    good = rng.binomial(shots, r["lucj"]["modelled_fidelity"]); bad = rng.binomial(shots - good, sec.dim / 4.0 ** n); kept = int(good + bad)      # depolarised shots are uniform over all bitstrings; only those with the right particle numbers are kept
                    idx = np.concatenate([rng.choice(sec.dim, good, p=p), rng.integers(0, sec.dim, bad)])
                else: idx = rng.choice(sec.dim, shots, p=p); kept = shots
                if len(idx) == 0: pts.append({"shots": shots, "kept": 0}); continue
                A = np.unique(idx // db); B = np.unique(idx % db); d = len(A) * len(B); pt = {"shots": shots, "kept": kept, "distinct_configurations": int(len(np.unique(idx))), "dimension": int(d)}
                if d <= 300000: pt["error_mha"] = 1000 * (sec.fixed_space(h1, eri, (sec.sa[A], sec.sb[B])) - e0)
                pts.append(pt)
            r["proposers"][pname] = pts
        r["seconds"] = round(time.time() - t0, 1); rows.append(r); json.dump(rows, open(f"{OUT}/sample.json", "w"), indent=1)
        print(case, r["qubits"], "q", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r["lucj"].items()}, flush=True)
        for pname, pts in r["proposers"].items(): print("   ", pname, [(x["shots"], x.get("dimension"), None if "error_mha" not in x else round(x["error_mha"], 2)) for x in pts], flush=True)

def request():
    """Hardware circuits: the cluster-Jastrow circuit of each case, sampled in the computational basis. IonQ (36 qubits) runs
    the 8 transition-metal cases at 500 shots; Quantinuum runs the 4 actinide cases (24 and 26 qubits) at 200 shots."""
    S = json.load(open(f"{OUT}/sample.json")); out = {"IonQ": [], "Quantinuum": []}
    for r in S:
        lj = r["lucj"]; n = r["qubits"]
        if "rzz" not in lj or lj["rzz"] > 2000: continue
        if n <= 18: out["IonQ"].append({"case": r["case"], "qubits": n, "rzz": lj["rzz"], "shots": 500, "two_qubit_gate_shots": 500 * lj["rzz"], "modelled_fidelity": lj["modelled_fidelity"]})
        else: out["Quantinuum"].append({"case": r["case"], "qubits": n, "rzz": lj["rzz"], "n1q": lj["one_qubit_gates"], "shots": 200, "hqc": round(5 + 200 * (lj["one_qubit_gates"] + 10 * lj["rzz"] + 5 * n) / 5000), "modelled_fidelity": lj["modelled_fidelity"]})
    out["totals"] = {"circuits": {k: len(v) for k, v in out.items()}, "shots": {k: sum(x["shots"] for x in v) for k, v in out.items()}, "ionq_two_qubit_gate_shots": sum(x["two_qubit_gate_shots"] for x in out["IonQ"]), "quantinuum_hqc": sum(x["hqc"] for x in out["Quantinuum"])}
    json.dump(out, open(f"{OUT}/request.json", "w"), indent=1); print(out["totals"])

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True); {"model": model, "ladder": ladder, "sample": sample, "request": request}[sys.argv[1]]()

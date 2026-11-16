#!/usr/bin/env python3
"""Rebuild the trapped-ion request circuits of the QCUP pre-submission package and export them.

Run inside the package's own venv (requirements.txt), on a build host:
    python build_circuits.py PKG_DIR OUT_DIR

What is rebuilt, following the package's own scripts line for line:
  Aim 1 QAOA      cost.py's rows (seed 0 of each family and size; IonQ to 32 variables, Quantinuum from 40; depths 1-3,
                  family B at depth 1 above 20; cold and warm start; at most 2,000 RZZ), counted as cost.py counts them
                  (angles 0.3/0.2, warm start = cold + 2np one-qubit gates). Tiers as aim1_request.py, then the
                  application's tiering (program repair at 40 and 60 moved from the Quantinuum core to the extension).
  Aim 2           cost.py's rows (reset and in-place styles, first event stream, T = 1, 5 on IonQ and 1, 3, 5 on
                  Quantinuum, core up to 300 RZZ).
  Family E        labs.py request(): depth 1 at N = 8, 12, 16, 20 on both trapped-ion vendors.
  Sampling (Q7)   family B, warm temperature, 12 and 16 qubits, depths 1 and 2 (sampling.py angles), on IonQ.
  Family F        chem.py request(), hubbard.py request(), targets.py request().

Each request row is counted exactly as its script counts it. The circuit exported for a run carries the angles a
run would use: optimised angles where the package optimised them, else angles transferred within the family with the
cost angle rescaled (rule stated in each record). Exported per circuit: OpenQASM 3 of the transpiled circuit
(basis rzz, rz, rx, ry, plus measure and reset), a gate list for the device models, and IonQ QIS JSON where every
measurement is terminal. A SHA-256 manifest covers every exported file."""
import glob, hashlib, json, math, os, sys, time
import numpy as np

PKG, OUT = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
ONLY = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
sys.path.insert(0, PKG)
os.makedirs(f"{OUT}/qasm", exist_ok=True); os.makedirs(f"{OUT}/gates", exist_ok=True); os.makedirs(f"{OUT}/ionq", exist_ok=True); os.makedirs(f"{OUT}/score", exist_ok=True)
from qiskit import QuantumCircuit, transpile, qasm3
from qiskit.quantum_info import Statevector
R = f"{PKG}/results"
ION = ["rzz", "rz", "rx", "ry"]


def tr(qc, extra=(), opt=3):
    return transpile(qc, basis_gates=ION + list(extra), optimization_level=opt, seed_transpiler=7)


def cnt(t):
    c = t.count_ops()
    return {"n1q": int(sum(c.get(g, 0) for g in ("rz", "rx", "ry"))), "n2q": int(c.get("rzz", 0)), "resets": int(c.get("reset", 0)), "measure": int(c.get("measure", 0)), "qubits": t.num_qubits}


def gate_list(t):
    qi = {q: i for i, q in enumerate(t.qubits)}; ci = {c: i for i, c in enumerate(t.clbits)}; out = []
    for ins in t.data:
        n = ins.operation.name
        if n == "barrier": continue
        out.append([n, [qi[q] for q in ins.qubits], [float(x) for x in ins.operation.params], [ci[c] for c in ins.clbits]])
    return out


def terminal_measure_map(gl, nq):
    """clbit -> qubit if every measurement is terminal and there is no reset, else None."""
    last_gate = {}
    for k, (n, qs, ps, cs) in enumerate(gl):
        if n not in ("measure",):
            for q in qs: last_gate[q] = k
    mp = {}
    for k, (n, qs, ps, cs) in enumerate(gl):
        if n == "reset": return None
        if n == "measure":
            if last_gate.get(qs[0], -1) > k: return None
            if any(g[0] == "measure" and g[1][0] == qs[0] for g in gl[k + 1:]): return None
            mp[cs[0]] = qs[0]
    return mp


def ionq_json(gl):
    g = []
    for n, qs, ps, cs in gl:
        if n in ("rz", "rx", "ry"): g.append({"gate": n, "target": qs[0], "rotation": ps[0]})
        elif n == "rzz": g.append({"gate": "zz", "targets": [qs[0], qs[1]], "rotation": ps[0]})
        elif n == "measure": continue
        else: raise ValueError(n)
    return g


CIRC = {}      # circuit id -> metadata
ROWS = []      # request rows


def export(cid, t, meta):
    """t: transpiled circuit with its measurements. Writes qasm, gate list and IonQ JSON (if terminal)."""
    if cid in CIRC: return CIRC[cid]
    gl = gate_list(t); c = cnt(t)
    txt = qasm3.dumps(t)
    open(f"{OUT}/qasm/{cid}.qasm", "w").write(txt)
    json.dump({"id": cid, "qubits": t.num_qubits, "clbits": t.num_clbits, "gates": gl}, open(f"{OUT}/gates/{cid}.json", "w"))
    mp = terminal_measure_map(gl, t.num_qubits)
    rec = {"id": cid, **c, "mid_circuit_measure_or_reset": mp is None, **meta}
    if mp is not None:
        body = {"qubits": t.num_qubits, "circuit": ionq_json(gl)}
        json.dump({"id": cid, "input": body, "clbit_to_qubit": {str(k): v for k, v in sorted(mp.items())}, "clbits": t.num_clbits}, open(f"{OUT}/ionq/{cid}.json", "w"))
        rec["ionq_gate_entries"] = len(body["circuit"])
    CIRC[cid] = rec
    return rec


def row(**kw): ROWS.append(kw)


def scale_of(d):
    w = [hi * hi for hi in d["h"]]
    for i, j, v in d["edges"]: w[int(i)] += v * v; w[int(j)] += v * v
    return float(np.sqrt(np.mean(w)))


# ------------------------------------------------------------------ Aim 1 QAOA
def aim1():
    from aim1_post import qaoa_circuit, diag_energy, qaoa_state, EPS
    inst = {}
    for p in glob.glob(f"{R}/aim1_[ABCDR]_*.json") + glob.glob(f"{R}/scale/scale_*.json"):
        d = json.load(open(p))
        if d["seed"] == 0: inst[(d["family"], d["n"])] = (d, p)
    fg = {(r["family"], r["n"], r["seed"], r["set"]): r for r in json.load(open(f"{R}/feasible_gap.json"))}
    small = {k: v for k, v in inst.items() if k[1] <= 20}
    donor = {f: max((k for k in small if k[0] == f), key=lambda k: k[1]) for f in "ABCDR"}
    for (fam, n), (d, path) in sorted(inst.items()):
        vendor, shots = ("IonQ", 500) if n <= 32 else ("Quantinuum", 200)
        for p in (1, 2, 3):
            if fam == "B" and n > 20 and p > 1: continue
            o = cnt(tr(qaoa_circuit(n, d["h"], d["edges"], [0.3] * p, [0.2] * p)))
            if o["n2q"] > 2000: continue
            for kind in ("cold", "warm"):
                oo = dict(o); oo["n1q"] = o["n1q"] + (2 * n * p if kind == "warm" else 0)
                tier_pkg = ("core" if p == 1 else "extension") if vendor == "IonQ" else ("core" if (fam == "A" and n == 60 and p == 1) or fam == "R" else "extension")
                tier_app = tier_pkg if vendor == "IonQ" else ("core" if (fam == "A" and n == 60 and p == 1) else "extension")
                cid = f"qcup-a1-{fam}{n}-p{p}-{kind}"
                # the circuit a run would use
                small_inst = n <= 20
                meta = {"aim": 1, "family": fam, "n": n, "p": p, "kind": kind, "instance": os.path.relpath(path, PKG)}
                thetas = None
                if small_inst:
                    tag = f"{fam}_{n}_0"; post = json.load(open(f"{R}/post_{tag}.json"))
                    if kind == "cold": q = d["qaoa"][p - 1]; meta.update(angles="optimised (aim1 results)", ideal_p_gs=q["p_gs"])
                    else:
                        q = post["ws"][p - 1]; gw = json.load(open(f"{R}/gw_{tag}.json"))
                        x = np.array([(s + 1) // 2 for s in gw["gw16_state"]]); c = np.where(x == 1, 1 - EPS, EPS); thetas = list(map(float, 2 * np.arcsin(np.sqrt(c))))
                        meta.update(angles="optimised warm start (post results), GW16 seed", ideal_p_gs=q["p_gs"])
                    gam, bet = q["gamma"], q["beta"]
                    meta.update(e_min=d["e_min"], e_max=d["e_max"], sdp_bound=d["sdp_bound"], reference_energy=d["e_min"], feasible_mean=fg[(fam, n, 0, "small")].get("feasible_mean_energy", 0.0))
                else:
                    dk = donor[fam]; dd = small[dk][0]; f = scale_of(dd) / scale_of(d)
                    if kind == "warm":
                        # the package stores no Goemans-Williamson seed state above 20 variables (scale files keep its energy only):
                        # built for the device models with the donor's warm-start angles and a placeholder seed (all bits 0); not emulated
                        q = json.load(open(f"{R}/post_{dk[0]}_{dk[1]}_0.json"))["ws"][p - 1]; gam = [g * f for g in q["gamma"]]; bet = q["beta"]
                        thetas = [float(2 * np.arcsin(np.sqrt(EPS)))] * n
                        meta.update(emulable=False, angles=f"donor {dk[0]}_{dk[1]}_0 warm-start angles, cost angle rescaled ({f:.4f}); placeholder seed",
                                    not_emulated_reason="no Goemans-Williamson seed state is stored above 20 variables, so the warm-start circuit of the method cannot be built; the model uses a placeholder seed (two-qubit structure identical)")
                    else:
                        q = dd["qaoa"][p - 1]; gam = [g * f for g in q["gamma"]]; bet = q["beta"]
                        meta.update(angles=f"transferred from {dk[0]}_{dk[1]}_0 (largest optimised size in the family), cost angle rescaled by coupling scale ({f:.4f})")
                    key = (fam, n, 0, "scale")
                    meta.update(sdp_bound=d["sdp_bound"], reference_energy=d["reference_energy"], feasible_mean=fg[key].get("feasible_mean_energy", 0.0) if key in fg else None)
                if gam is not None:
                    qc = qaoa_circuit(n, d["h"], d["edges"], gam, bet, thetas); qc.measure_all()
                    t = tr(qc, ("measure",))
                    if not small_inst and n <= 24 and kind == "cold":
                        e = diag_energy(n, d["h"], d["edges"]); emin = float(e.min()); gs = e <= emin + 1e-9 * (1 + abs(emin))
                        pr = np.abs(qaoa_state(e, n, gam, bet)) ** 2; meta.update(ideal_p_gs=float(pr[gs].sum()), e_min=emin, e_max=float(e.max())); del e, pr
                    rec = export(cid, t, meta)
                else:
                    rec = {"id": cid, "qubits": n, **meta}; CIRC[cid] = rec
                row(aim=1, group="aim1_qaoa", vendor=vendor, tier_package=tier_pkg, tier_application=tier_app, circuit=f"{fam}_{n}_0_p{p}_{kind}", id=cid, shots=shots,
                    count_n1q=oo["n1q"], count_n2q=oo["n2q"], count_qubits=n, spam=2 * n)
        print("aim1", fam, n, flush=True)


# ------------------------------------------------------------------ Aim 2
def aim2():
    from aim2 import build, reference
    from aim2b import is_permutation, build_inplace
    forms = json.load(open(f"{PKG}/forms/selected.json"))
    for i, F in enumerate(forms):
        table, S, E = F["table"], F["states"], len(F["events"])
        sb = max(1, math.ceil(math.log2(S))); eb = math.ceil(math.log2(E)) if E > 1 else 0
        delta = lambda s, e, table=table, S=S, E=E: table[s][e] if s < S and e < E else s
        rng = np.random.default_rng([20261111, i]); stream = [int(x) for x in rng.integers(0, E, 5)] if E > 1 else [0] * 5
        perm = is_permutation(delta, sb, eb) and eb == 0
        for T in (1, 3, 5):
            for style in ["R"] + (["P"] if perm else []):
                qc = build_inplace(delta, sb, 0, T) if style == "P" else build(style, delta, sb, eb, 0, stream[:T])[0]
                t = tr(qc, ("reset", "measure")); o = cnt(t)
                if o["n2q"] > 2000: continue
                ref = reference(delta, 0, stream[:T]) if style == "R" else reference(lambda s, e: delta(s, 0), 0, [0] * T)
                want = "".join(format(s, f"0{sb}b") for s in reversed(ref))
                cid = f"qcup-a2-{F['name']}-{style}-T{T}".replace("_", "-").lower()
                meta = {"aim": 2, "form": F["name"], "style": style, "T": T, "state_bits": sb, "event_bits": eb, "events": stream[:T], "reference_trace": ref, "reference_bits_qiskit_order": want}
                rec = export(cid, t, meta)
                for vendor, shots, steps in (("IonQ", 500, (1, 5)), ("Quantinuum", 200, (1, 3, 5))):
                    if T in steps:
                        tier = "core" if o["n2q"] <= 300 else "extension"
                        row(aim=2, group="aim2", vendor=vendor, tier_package=tier, tier_application=tier, circuit=f"{F['name']}_{style}_T{T}", id=cid, shots=shots,
                            count_n1q=o["n1q"], count_n2q=o["n2q"], count_qubits=o["qubits"], spam=o["qubits"] + o["resets"] + o["measure"])
        print("aim2", F["name"], flush=True)


# ------------------------------------------------------------------ family E (pulse-code design)
def labs():
    import labs as L
    req = json.load(open(f"{R}/labs/request.json"))["trapped_ion"]
    for rq in req:
        N = rq["N"]; T = L.spin_terms(N)
        def circ(g, b):
            qc = QuantumCircuit(N); [qc.h(q) for q in range(N)]
            for k, c in T.items():
                q = sorted(k)
                if len(q) == 2: qc.rzz(2 * g * c, q[0], q[1])
                elif len(q) == 4: qc.cx(q[0], q[1]); qc.cx(q[1], q[2]); qc.cx(q[2], q[3]); qc.rz(2 * g * c, q[3]); qc.cx(q[2], q[3]); qc.cx(q[1], q[2]); qc.cx(q[0], q[1])
            [qc.rx(2 * b, q) for q in range(N)]; return qc
        o = cnt(tr(circ(0.01, 0.2)))
        assert (o["n1q"], o["n2q"]) == (rq["n1q"], rq["n2q"]), (N, o, rq)
        qa = json.load(open(f"{R}/labs/qaoa_{N}.json")); d1 = qa["depths"][0]
        qc = circ(d1["gamma"][0], d1["beta"][0])
        if N <= 12:
            e = L.energies(N).astype(np.float64); from aim1_post import qaoa_state
            ref = float(np.abs(qaoa_state(e, N, d1["gamma"], d1["beta"])) ** 2 @ e); got = float(np.abs(Statevector(qc).data) ** 2 @ e); assert abs(ref - got) < 1e-6, (ref, got)
        qc.measure_all(); t = tr(qc, ("measure",))
        cid = f"qcup-e-labs{N}-p1"
        export(cid, t, {"aim": 1, "family": "E", "n": N, "p": 1, "angles": "optimised depth-1 angles (results/labs/qaoa_N.json)", "ideal_p_gs": d1["p_gs"], "uniform_p_gs": d1["uniform_p_gs"], "e_min": qa["e_min"]})
        for vendor, shots in (("IonQ", 500), ("Quantinuum", 200)):
            row(aim=1, group="family_E", vendor=vendor, tier_package="core", tier_application="core", circuit=f"LABS_{N}_p1", id=cid, shots=shots, count_n1q=o["n1q"], count_n2q=o["n2q"], count_qubits=N, spam=2 * N)
        print("labs", N, o, flush=True)


# ------------------------------------------------------------------ sampling circuits (Q7)
def sampling():
    from aim1_post import qaoa_circuit
    qa = {(r["family"], r["n"], r["temperature"]): r for r in json.load(open(f"{R}/sampling/qaoa.json"))}
    tg = {(r["family"], r["n"], r["temperature"]): r for r in json.load(open(f"{R}/sampling/targets.json"))}
    for n in (12, 16):
        d = json.load(open(f"{R}/aim1_B_{n}_0.json")); q = qa[("B", n, "warm")]
        for p in (1, 2):
            dp = q["depths"][p - 1]; qc = qaoa_circuit(n, d["h"], d["edges"], dp["gamma"], dp["beta"])
            o = cnt(tr(qc)); qc.measure_all(); t = tr(qc, ("measure",))
            cid = f"qcup-q7-B{n}-warmT-p{p}"
            export(cid, t, {"aim": 1, "family": "Q7", "n": n, "p": p, "angles": "TVD-optimised (results/sampling/qaoa.json)", "ideal_tvd_floor": dp["tvd_floor"], "target_beta": tg[("B", n, "warm")]["beta"], "instance": f"results/aim1_B_{n}_0.json"})
            row(aim=1, group="sampling_Q7", vendor="IonQ", tier_package="core", tier_application="core", circuit=f"B_{n}_warm_p{p}", id=cid, shots=500, count_n1q=o["n1q"], count_n2q=o["n2q"], count_qubits=n, spam=2 * n)
        print("sampling", n, flush=True)


# ------------------------------------------------------------------ family F: small molecules
def chem():
    import chem as C
    from qiskit.circuit.library import PauliEvolutionGate
    from qiskit.quantum_info import SparsePauliOp
    req = json.load(open(f"{R}/chem/request.json")); built = {}
    for name, atom, label, ncore in C.SYSTEMS:
        mol, mf, mc, ncas, nel = C.setup(atom, ncore); n = 2 * ncas
        if n > 12 or name in built: continue
        def ladder(p, dag):
            z = "I" * (n - p - 1); lo = "Z" * p; return SparsePauliOp([z + "X" + lo, z + "Y" + lo], [0.5, -0.5j if dag else 0.5j])
        qc = QuantumCircuit(n); [qc.x(q) for q in range(nel)]
        for cre, ann in C.excitations(ncas, nel):
            op = None
            for p, dag in [(p, 1) for p in cre] + [(q, 0) for q in reversed(ann)]: op = ladder(p, dag) if op is None else op.compose(ladder(p, dag))
            gen = (op - op.adjoint()).simplify(); qc.append(PauliEvolutionGate(SparsePauliOp(gen.paulis, (1j * gen.coeffs).real).simplify(), time=0.1), range(n))
        t0 = tr(qc); o = cnt(t0)
        sv = np.abs(Statevector(t0).data) ** 2
        qm = qc.copy(); qm.measure_all(); t = tr(qm, ("measure",))
        cid = f"qcup-f-chem-{name.replace(' ', '').lower()}-n{n}"
        np.save(f"{OUT}/score/{cid}.ideal.npy", sv)
        export(cid, t, {"aim": 1, "family": "F-chem", "system": name, "n": n, "electrons": nel, "angles": "as chem.py request(): every excitation at time 0.1 (the request's circuit; identical for every geometry of one system)"})
        built[name] = (cid, o)
    for vendor in ("IonQ", "Quantinuum"):
        for r in req[vendor]:
            sysname = r["case"].rsplit(" ", 1)[0]; cid, o = built[sysname]
            assert (o["n1q"], o["n2q"]) == (r["n1q"], r["n2q"]), (r, o)
            row(aim=1, group="family_F_chem", vendor=vendor, tier_package="core", tier_application="core", circuit=r["case"], id=cid, shots=r["shots"], count_n1q=o["n1q"], count_n2q=o["n2q"], count_qubits=o["qubits"], spam=2 * o["qubits"])
    print("chem", {k: v[1] for k, v in built.items()}, flush=True)


# ------------------------------------------------------------------ family F: Hubbard
def hubbard():
    import hubbard as H
    from qiskit.circuit.library import PauliEvolutionGate
    from qiskit.quantum_info import SparsePauliOp
    req = json.load(open(f"{R}/hubbard/request.json")); ci = {r["lattice"]: r for r in json.load(open(f"{R}/hubbard/circuits.json"))}
    def layer(Lx, Ly, with_rz):
        L = Lx * Ly; n = 2 * L; hb, vb = H.bonds(Lx, Ly); q = lambda i, s: i + s * L; qc = QuantumCircuit(n)
        for i in range(L):
            qc.rzz(0.1, q(i, 0), q(i, 1))
            if with_rz: qc.rz(0.1, q(i, 0)); qc.rz(0.1, q(i, 1))
        for a, b in hb + vb:
            for s_ in (0, 1):
                lo, hi = sorted((q(a, s_), q(b, s_))); lab = lambda P: "".join("I" if k < lo or k > hi else (P if k in (lo, hi) else "Z") for k in reversed(range(n)))
                qc.append(PauliEvolutionGate(SparsePauliOp([lab("X"), lab("Y")], [0.5, 0.5]), time=0.1), range(n))
        return qc
    def prep(Lx, Ly):
        """Free-fermion ground state at half filling: ffsim's Slater-determinant preparation (Givens rotations) for the
        lowest orbitals of the hopping matrix, both spins. The package counts it as L^2 two-qubit gates (an estimate)."""
        import ffsim
        L = Lx * Ly; w, U = np.linalg.eigh(H.hop_matrix(Lx, Ly)); na = L // 2
        qc = QuantumCircuit(2 * L)
        qc.append(ffsim.qiskit.PrepareSlaterDeterminantJW(L, (list(range(na)), list(range(na))), orbital_rotation=U), qc.qubits)
        return ffsim.qiskit.PRE_INIT.run(qc), float(w[:na].sum() * 2)
    def neel(Lx, Ly):
        L = Lx * Ly; qc = QuantumCircuit(2 * L)
        for x in range(Lx):
            for y in range(Ly):
                i = x * Ly + y; qc.x(i if (x + y) % 2 == 0 else i + L)
        return qc
    # check the preparation on 2x2 against the free-fermion energy
    try:
        import ffsim
        pq, e0 = prep(2, 2); sv = Statevector(tr(pq, (), 1))
        L = 4; terms = []
        hb, vb = H.bonds(2, 2)
        from qiskit.quantum_info import SparsePauliOp as SPO
        ops = []
        for a, b in hb + vb:
            for s_ in (0, 1):
                lo, hi = sorted((a + s_ * L, b + s_ * L)); n = 2 * L
                lab = lambda P: "".join("I" if k < lo or k > hi else (P if k in (lo, hi) else "Z") for k in reversed(range(n)))
                ops += [(lab("X"), -0.5), (lab("Y"), -0.5)]
        e_prep = float(np.real(sv.expectation_value(SPO.from_list(ops))))
        prep_ok = abs(e_prep - e0) < 1e-6
        print("hubbard prep check 2x2:", e_prep, e0, prep_ok, flush=True)
    except Exception as ex:
        prep_ok = False; print("hubbard prep check failed:", repr(ex)[:300], flush=True)
    built = {}
    for r in req["IonQ"]:
        lat = r["lattice"]; Lx, Ly = map(int, lat.split("x")); p = r["p"]
        lay = tr(layer(Lx, Ly, False), (), 3); assert cnt(lay)["n2q"] == ci[lat]["rzz_per_layer"], (cnt(lay), ci[lat])
        cid = f"qcup-f-hub-{lat}-p{p}-free"
        if cid not in built:
            pq, _ = prep(Lx, Ly); qc = pq.copy()
            for _ in range(p): qc = qc.compose(layer(Lx, Ly, False))
            qc.measure_all(); t = tr(qc, ("measure",), 1); tp = cnt(tr(pq, (), 1))
            built[cid] = export(cid, t, {"aim": 1, "family": "F-hubbard", "lattice": lat, "p": p, "start": r["start"], "angles": "as hubbard.py: every term at 0.1 (placeholder; the request does not fix run angles above 8 sites)",
                                         "prep_rzz_transpiled": tp["n2q"], "prep_rzz_package_estimate": r["of_which_state_preparation_estimate"], "prep_checked_2x2": prep_ok, "emulable": False if 2 * Lx * Ly > 29 else None})
        row(aim=1, group="family_F_hubbard", vendor="IonQ", tier_package="core", tier_application="core", circuit=f"{lat}_p{p}_U{r['U']}", id=cid, shots=r["shots"],
            count_n1q=None, count_n2q=r["rzz"], count_qubits=2 * Lx * Ly, spam=4 * Lx * Ly, count_note="package count = p x one transpiled layer + L^2 estimate for preparation")
    for r in req["Quantinuum"]:
        lat = r["lattice"]; Lx, Ly = map(int, lat.split("x")); p = r["p"]; L = Lx * Ly
        lay = layer(Lx, Ly, True); o1 = cnt(tr(lay, (), 1)); prep_est = L * L if L * L + o1["n2q"] <= 2000 else 0
        g2 = p * o1["n2q"] + prep_est; g1 = p * o1["n1q"] + L + 2 * prep_est
        assert (g2, g1) == (r["rzz"], r["n1q"]), (r, g2, g1)
        cid = f"qcup-f-hub-{lat}-p{p}-{'free' if prep_est else 'neel'}"
        if cid not in built:
            if prep_est: pq, _ = prep(Lx, Ly)
            else: pq = neel(Lx, Ly)
            qc = pq.copy()
            for _ in range(p): qc = qc.compose(lay)
            qc.measure_all(); t = tr(qc, ("measure",), 1); tp = cnt(tr(pq, (), 1))
            built[cid] = export(cid, t, {"aim": 1, "family": "F-hubbard", "lattice": lat, "p": p, "start": r["start"], "angles": "as hubbard.py request(): every term at 0.1 (placeholder)",
                                         "prep_rzz_transpiled": tp["n2q"], "prep_rzz_package_estimate": prep_est, "prep_checked_2x2": prep_ok, "emulable": False})
        row(aim=1, group="family_F_hubbard", vendor="Quantinuum", tier_package="core", tier_application="core", circuit=f"{lat}_p{p}_U{r['U']}", id=cid, shots=r["shots"],
            count_n1q=g1, count_n2q=g2, count_qubits=2 * L, spam=2 * L, count_note="package count: p x one transpiled layer + L^2 estimate for preparation where used")
    print("hubbard", {k: (v.get("n2q"), v.get("prep_rzz_transpiled")) for k, v in built.items()}, flush=True)


# ------------------------------------------------------------------ family F: target chemistry
def targets():
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    import targets as TG
    import ffsim
    from qiskit import QuantumRegister
    req = json.load(open(f"{R}/targets/request.json"))
    want = {r["case"]: ("IonQ", r) for r in req["IonQ"]}; want.update({r["case"]: ("Quantinuum", r) for r in req["Quantinuum"]})
    for case, (vendor, r) in want.items():
        np.random.seed(7); h1, eri, ecore, nelec = TG.load(case); sec = TG.Sector(h1, eri, ecore, nelec); n = sec.n
        ref, best, _ = TG.references(h1, eri, ecore, nelec); cinfo, c = TG.ccsd(best, nelec)
        op = ffsim.UCJOpSpinUnbalanced.from_t_amplitudes(c.t2, t1=c.t1, n_reps=1); Ca, Cb = best.mo_coeff
        hf = ffsim.hartree_fock_state(n, nelec); rot = None
        for cand in ((Ca, Cb), (Ca.T.copy(), Cb.T.copy())):
            v = ffsim.apply_orbital_rotation(hf, cand, norb=n, nelec=nelec); e = float(np.real(np.vdot(v, sec.apply(np.real(v)) if np.abs(v.imag).max() < 1e-12 else sec.apply(v.real) + 1j * sec.apply(v.imag))))
            if abs(e - best.e_tot) < 1e-6: rot = cand; break
        assert rot is not None
        v = ffsim.apply_orbital_rotation(ffsim.apply_unitary(hf, op, norb=n, nelec=nelec), rot, norb=n, nelec=nelec); plu = np.abs(v) ** 2; plu /= plu.sum()
        q = QuantumRegister(2 * n); qc = QuantumCircuit(q); qc.append(ffsim.qiskit.PrepareHartreeFockJW(n, nelec), q); qc.append(ffsim.qiskit.UCJOpSpinUnbalancedJW(op), q); qc.append(ffsim.qiskit.OrbitalRotationJW(n, rot), q)
        base = ffsim.qiskit.PRE_INIT.run(qc); t0 = transpile(base, basis_gates=ION, optimization_level=1, seed_transpiler=7); o = cnt(t0)
        ok = o["n2q"] == r["rzz"] and (vendor == "IonQ" or o["n1q"] == r["n1q"])
        qm = base.copy(); qm.measure_all(); t = transpile(qm, basis_gates=ION + ["measure"], optimization_level=1, seed_transpiler=7)
        cid = f"qcup-f-tgt-{case.lower().replace('_', '-')}"
        bits = (sec.sa[:, None] | (sec.sb[None, :] << n)).ravel()
        np.savez_compressed(f"{OUT}/score/{cid}.ideal.npz", bitstrings=bits, prob=plu.ravel(), sa=sec.sa, sb=sec.sb)
        export(cid, t, {"aim": 1, "family": "F-targets", "case": case, "n_orbitals": n, "nelec": list(nelec), "rzz_package": r["rzz"], "counts_match_package": bool(ok), "angles": "from the cheap method's amplitudes (as targets.py)", "emulable": 2 * n <= 29})
        row(aim=1, group="family_F_targets", vendor=vendor, tier_package="core", tier_application="core", circuit=case, id=cid, shots=r["shots"], count_n1q=o["n1q"], count_n2q=o["n2q"], count_qubits=2 * n, spam=2 * n,
            package_n2q=r["rzz"], package_n1q=r.get("n1q"))
        print("targets", case, vendor, o, "package rzz", r["rzz"], "match", ok, flush=True)


STAGES = {"aim1": aim1, "aim2": aim2, "labs": labs, "sampling": sampling, "chem": chem, "hubbard": hubbard, "targets": targets}
for name, fn in STAGES.items():
    if ONLY and name not in ONLY: continue
    t0 = time.time(); fn(); print("stage", name, "done in", round(time.time() - t0, 1), "s", flush=True)
    json.dump({"circuits": CIRC, "rows": ROWS}, open(f"{OUT}/index-{','.join(sorted(ONLY)) if ONLY else 'all'}.json", "w"), indent=1)
man = {}
for sub in ("qasm", "gates", "ionq", "score"):
    for p in sorted(glob.glob(f"{OUT}/{sub}/*")): man[f"{sub}/{os.path.basename(p)}"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
json.dump(man, open(f"{OUT}/manifest_sha256-{','.join(sorted(ONLY)) if ONLY else 'all'}.json", "w"), indent=1)
print("done", len(CIRC), "circuits", len(ROWS), "rows")

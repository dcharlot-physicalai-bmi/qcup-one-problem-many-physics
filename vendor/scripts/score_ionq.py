#!/usr/bin/env python3
"""Score each IonQ simulator run (forte-1 noise model) as the application scores the circuit, beside the ideal figure
and, where the package sampled the same circuit under its generic trapped-ion model, that figure too.

    python score_ionq.py PKG_DIR BASE_DIR        (BASE_DIR holds circuits/ and ionq/)

Aim 1 (A-D, repair): fraction of shots on an optimum; best sampled energy, and its certified gap to the SDP bound as a
  share of the feasible-state spread (the package's certificate measure).
Family E: fraction of shots on an optimum. Sampling (Q7): total variation distance of the shots to the Boltzmann target.
Aim 2: trace fidelity (shots whose trace equals the reference trace).
Family F: share of shots with the right electron numbers; classical (Hellinger) fidelity to the circuit's ideal output;
  for the target-chemistry circuits, the energy from diagonalising the Hamiltonian in the span of the kept samples."""
import glob, json, math, os, sys
import numpy as np
PKG, BASE = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
sys.path.insert(0, PKG); R = f"{PKG}/results"
from aim1_post import diag_energy, qaoa_state
IDX = json.load(open(f"{BASE}/circuits/index.json")); C = IDX["circuits"]
L = json.load(open(f"{BASE}/ionq/ledger.json"))
rng = np.random.default_rng(20261115)


def counts_of(res, shots, nq):
    """IonQ legacy probabilities keyed by decimal index (bit q = qubit q), turned into shot counts by largest remainder."""
    h = res.get("histogram")
    if isinstance(h, dict) and h and abs(sum(h.values()) - shots) < 0.5 and all(float(v).is_integer() for v in h.values()):
        return {int(k): int(v) for k, v in h.items()}          # the service's histogram is shot counts
    pr = res.get("probabilities")
    keys = [int(k) for k in pr]; p = np.array([float(pr[str(k)]) for k in keys]); raw = p * shots; c = np.floor(raw).astype(int)
    for i in np.argsort(-(raw - c))[: shots - c.sum()]: c[i] += 1
    return dict(zip(keys, c.tolist()))


def energy_of(states, n, h, edges):
    s = np.array([[1.0 if (x >> i) & 1 else -1.0 for i in range(n)] for x in states])
    e = -(s @ np.array(h))
    for i, j, w in edges: e -= w * s[:, int(i)] * s[:, int(j)]
    return e


def hellinger(p, q):
    keys = set(p) | set(q); return float(sum(math.sqrt(p.get(k, 0) * q.get(k, 0)) for k in keys) ** 2)


aim2_pkg = {}
for p in glob.glob(f"{R}/aim2/*.json"):
    for r in json.load(open(p)): aim2_pkg[(r["form"], r["style"], r["T"], r["stream"])] = r
noisy_pkg = {}
for p in glob.glob(f"{R}/post_*_0.json"):
    d = json.load(open(p))
    for x in d.get("noisy", []): noisy_pkg[(d["family"], d["n"], x["kind"], x["p"], x["model"])] = x

out = []
for key, e in sorted(L.items()):
    if e.get("status") != "completed": out.append({"id": e["id"], "route": e.get("route", "qis"), "shots": e["shots"], "status": e.get("status"), "failure": e.get("failure")}); continue
    route = e.get("route", "qis"); sfx = f"-s{e['shots']}" + ("-native" if route == "native" else "")
    c = C[e["id"]]; resp = json.load(open(f"{BASE}/ionq/raw/results/results-{e['id']}{sfx}.json"))["answer"]
    nq = c["qubits"]; cnt = counts_of(resp, e["shots"], nq); shots = e["shots"]
    rec = {"id": e["id"], "route": route, "shots": shots, "qubits": nq, "rzz": c["n2q"], "one_qubit": c["n1q"], "ionq_gate_counts": (e.get("stats") or {}).get("gate_counts"),
           "compiled_gate_basis": e.get("compilation"), "noise_model": "forte-1 (IonQ cloud simulator)", "seed": e["seed"]}
    fam = c.get("family"); aim = c.get("aim")
    if aim == 1 and fam in ("A", "B", "C", "D", "R"):
        inst = json.load(open(f"{PKG}/{c['instance']}")); n = inst["n"]
        st = list(cnt); en = energy_of(st, n, inst["h"], inst["edges"]); ref = c["reference_energy"]; tol = 1e-6 * (1 + abs(ref))
        hits = sum(v for s_, v, x in zip(st, cnt.values(), en) if x <= ref + tol)
        ebest = float(en.min()); spread = (c["feasible_mean"] - ref) if c.get("feasible_mean") is not None else None
        rec.update(score="aim1", p_optimum=hits / shots, ideal_p_optimum=c.get("ideal_p_gs"), best_energy=ebest, reference_energy=ref, optimum_found=bool(ebest <= ref + tol),
                   certified_gap_best_pct_of_feasible_spread=(100 * (ebest - c["sdp_bound"]) / spread) if spread else None,
                   bound_gap_pct_of_feasible_spread=(100 * (ref - c["sdp_bound"]) / spread) if spread else None,
                   mean_energy=float(sum(x * v for x, v in zip(en, cnt.values())) / shots))
        g = noisy_pkg.get((fam, n, c["kind"], c["p"], "ion_like"))
        if g: rec["package_generic_model_p_optimum"] = g["p_gs"]; rec["package_generic_model_shots"] = g["shots"]
    elif fam == "E":
        import labs as LB
        N = c["n"]; e_all = LB.energies(N); emin = e_all.min(); hits = sum(v for s_, v in cnt.items() if e_all[s_] == emin)
        rec.update(score="labs", p_optimum=hits / shots, ideal_p_optimum=c["ideal_p_gs"], uniform_p_optimum=c["uniform_p_gs"])
    elif fam == "Q7":
        inst = json.load(open(f"{PKG}/{c['instance']}")); n = inst["n"]; e_all = diag_energy(n, inst["h"], inst["edges"])
        w = np.exp(-c["target_beta"] * (e_all - e_all.min())); pt = w / w.sum()
        emp = np.zeros(1 << n)
        for s_, v in cnt.items(): emp[s_] = v / shots
        qa = {(r["family"], r["n"], r["temperature"]): r for r in json.load(open(f"{R}/sampling/qaoa.json"))}[("B", n, "warm")]["depths"][c["p"] - 1]
        pid = np.abs(qaoa_state(e_all, n, qa["gamma"], qa["beta"])) ** 2
        draws = [0.5 * float(np.abs(rng.multinomial(shots, pid) / shots - pt).sum()) for _ in range(200)]
        rec.update(score="sampling", tvd_to_target=0.5 * float(np.abs(emp - pt).sum()), ideal_tvd_floor=c["ideal_tvd_floor"], ideal_circuit_tvd_at_these_shots_median=float(np.median(draws)))
    elif aim == 2:
        mp = json.load(open(f"{BASE}/circuits/ionq/{e['id']}.json"))["clbit_to_qubit"]; want = c["reference_bits_qiskit_order"]; nb = len(want)
        ok = 0
        for s_, v in cnt.items():
            bits = "".join(str((s_ >> mp[str(k)]) & 1) for k in reversed(range(nb)))
            if bits == want: ok += v
        rec.update(score="aim2", trace_fidelity=ok / shots, form=c["form"], style=c["style"], T=c["T"])
        g = aim2_pkg.get((c["form"], c["style"], c["T"], 0))
        if g and "trace_fidelity" in g.get("ion_like", {}):
            rec.update(package_generic_model_trace_fidelity=g["ion_like"]["trace_fidelity"], package_generic_model_rzz=g["ion_like"]["two_qubit_gates"])
    elif fam == "F-chem":
        sv = np.load(f"{BASE}/circuits/score/{e['id']}.ideal.npy"); n = c["n"]; nel = c["electrons"]
        ideal = {i: float(p) for i, p in enumerate(sv) if p > 1e-12}; emp = {s_: v / shots for s_, v in cnt.items()}
        right = sum(v for s_, v in cnt.items() if bin(s_).count("1") == nel and bin(s_ & int("01" * (n // 2), 2)).count("1") == nel // 2)
        rec.update(score="chem", hellinger_fidelity_to_ideal=hellinger(ideal, emp), right_electron_numbers=right / shots)
    elif fam == "F-targets":
        z = np.load(f"{BASE}/circuits/score/{e['id']}.ideal.npz"); n = c["n_orbitals"]; na, nb = c["nelec"]
        ideal = dict(zip(z["bitstrings"].tolist(), z["prob"].tolist())); emp = {s_: v / shots for s_, v in cnt.items()}
        mask = (1 << n) - 1
        keep = {s_: v for s_, v in cnt.items() if bin(s_ & mask).count("1") == na and bin(s_ >> n).count("1") == nb}
        rec.update(score="targets", hellinger_fidelity_to_ideal=hellinger(ideal, emp), right_electron_numbers=sum(keep.values()) / shots)
        try:
            os.environ.setdefault("OMP_NUM_THREADS", "1")
            import targets as TG
            h1, eri, ecore, nelec = TG.load(c["case"]); sec = TG.Sector(h1, eri, ecore, nelec)
            lad = {r["case"]: r for r in json.load(open(f"{R}/targets/ladder.json"))}[c["case"]]; e0 = lad["e_exact"]
            def sqd(states):
                A = np.unique([s_ & mask for s_ in states]); B = np.unique([s_ >> n for s_ in states])
                if len(A) * len(B) > 300000: return None, int(len(A) * len(B))
                return 1000 * (sec.fixed_space(h1, eri, (A, B)) - e0), int(len(A) * len(B))
            em, dim = sqd(list(keep)); rec.update(sqd_error_mha=em, sqd_dimension=dim, kept_shots=sum(keep.values()))
            p = np.array(z["prob"]); bits = np.array(z["bitstrings"]); draw = bits[rng.choice(len(p), size=shots, p=p / p.sum())]
            ei, di = sqd(list(set(draw.tolist()))); rec.update(ideal_sqd_error_mha_same_shots=ei, ideal_sqd_dimension=di, full_dimension=int(sec.dim), chemical_accuracy_mha=1.6)
        except Exception as ex:
            rec["sqd_error"] = repr(ex)[:200]
    out.append(rec); print(rec["id"], route, rec.get("score"), {k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items() if k in ("p_optimum", "ideal_p_optimum", "trace_fidelity", "package_generic_model_trace_fidelity", "tvd_to_target", "hellinger_fidelity_to_ideal", "right_electron_numbers", "sqd_error_mha", "certified_gap_best_pct_of_feasible_spread")}, flush=True)
json.dump(out, open(f"{BASE}/ionq/scores.json", "w"), indent=1)
print("scored", sum(1 for r in out if r.get("score")), "of", len(out))

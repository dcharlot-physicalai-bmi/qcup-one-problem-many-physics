#!/usr/bin/env python3
"""Sampling: draw states from the Boltzmann distribution of an energy model, p(s) ~ exp(-beta E(s)).

This is the native task of a thermodynamic p-bit fabric, and the task for which single-layer QAOA is argued to produce
thermal-like states that are hard to sample classically (Diez-Valle, Porras, Garcia-Ripoll, PRL 130, 050601 (2023)).
Targets: the seed-0 Aim 1 instances at 12 to 20 variables, each at two temperatures fixed by a rule that looks at no
result (entropy equal to one half and one quarter of n bits), and one learned model (a fully visible Boltzmann machine
trained on 4x4 bars and stripes, beta = 1). Everything is exact: distributions are full vectors over 2^n states.

  gibbs     a p-bit fabric at the target temperature: systematic-scan Gibbs sweeps from a uniform start
  annealed  the same fabric cooled linearly in beta from 0 to the target over the sweeps
  qaoa      cold QAOA at depths 1 to 3 with angles chosen to minimise total variation distance to the target
Reported: total variation distance (TVD) to the target after t sweeps, and the lowest TVD each QAOA depth can reach.
  tempering parallel tempering, the stronger classical sampler, on the cold targets (empirical)
  spiking   ferromorphic's fixed-temperature spiking sampler at 12 variables (empirical)
Usage: sampling.py targets | qaoa <max n> | tempering <max n> | spiking"""
import glob, json, math, os, sys
import numpy as np
from scipy.optimize import minimize
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); R = f"{ROOT}/results"; OUT = f"{R}/sampling"
from aim1_post import diag_energy, qaoa_state
LN2 = math.log(2)

def boltz(e, beta):
    w = np.exp(-beta * (e - e.min())); return w / w.sum()
def entropy(p):
    q = p[p > 0]; return float(-(q * np.log(q)).sum())
def beta_for_entropy(e, target):
    lo, hi = 0.0, 1.0
    while entropy(boltz(e, hi)) > target: hi *= 2
    for _ in range(60):
        mid = (lo + hi) / 2
        if entropy(boltz(e, mid)) > target: lo = mid
        else: hi = mid
    return (lo + hi) / 2
def tvd(p, q): return float(0.5 * np.abs(p - q).sum())

def gibbs_sweep(P, e, n, beta):
    """One systematic-scan Gibbs sweep applied exactly to the probability vector P."""
    for i in range(n):
        A = P.reshape(1 << (n - 1 - i), 2, 1 << i); E = e.reshape(1 << (n - 1 - i), 2, 1 << i)
        m = A[:, 0, :] + A[:, 1, :]; s1 = 1.0 / (1.0 + np.exp(np.clip(beta * (E[:, 1, :] - E[:, 0, :]), -700, 700)))
        P = np.stack([m * (1 - s1), m * s1], axis=1).reshape(-1)
    return P

def bars_and_stripes():
    """Fully visible pairwise Boltzmann machine fitted to 4x4 bars and stripes by exact maximum likelihood."""
    pats = set()
    for b in range(16):
        rows = [(b >> r) & 1 for r in range(4)]
        pats.add(tuple(rows[r] for r in range(4) for c in range(4))); pats.add(tuple(rows[c] for r in range(4) for c in range(4)))
    n = 16; X = np.array([[((z >> i) & 1) * 2 - 1 for i in range(n)] for z in range(1 << n)], dtype=np.float64)
    idx = [sum(v << i for i, v in enumerate(p)) for p in pats]; data = np.zeros(1 << n); data[idx] = 1 / len(idx)
    m_d = data @ X; c_d = (X * data[:, None]).T @ X
    h = np.zeros(n); J = np.zeros((n, n))
    for step in range(3000):
        logit = X @ h + 0.5 * np.einsum("zi,ij,zj->z", X, J, X); p = np.exp(logit - logit.max()); p /= p.sum()
        gh = m_d - p @ X; gJ = c_d - (X * p[:, None]).T @ X; np.fill_diagonal(gJ, 0)
        h += 0.1 * gh; J += 0.1 * gJ
    kl = float((data[idx] * np.log(data[idx] / p[idx])).sum())
    edges = [[i, j, float(J[i, j])] for i in range(n) for j in range(i + 1, n) if abs(J[i, j]) > 1e-12]
    return {"family": "BAS", "n": n, "seed": 0, "h": [float(v) for v in h], "edges": edges, "patterns": len(idx), "kl_data_to_model_nats": kl, "max_gradient": float(max(np.abs(gh).max(), np.abs(gJ).max()))}

def instances():
    inst = []
    for p in sorted(glob.glob(f"{R}/aim1_[ABCDR]_*_0.json")):
        d = json.load(open(p)); inst.append({"family": d["family"], "n": d["n"], "seed": 0, "h": d["h"], "edges": d["edges"]})
    return inst

def targets():
    os.makedirs(OUT, exist_ok=True); bas = bars_and_stripes(); json.dump(bas, open(f"{OUT}/bas_model.json", "w"))
    print("bars and stripes model: KL(data || model) =", round(bas["kl_data_to_model_nats"], 4), "nats, max gradient", bas["max_gradient"], flush=True)
    rows = []; T = [1 << k for k in range(11)]
    for d in instances() + [bas]:
        n = d["n"]; e = diag_energy(n, d["h"], d["edges"])
        for label, frac in ((("learned", None),) if d["family"] == "BAS" else (("warm", 0.5), ("cold", 0.25))):
            beta = 1.0 if frac is None else beta_for_entropy(e, frac * n * LN2); pt = boltz(e, beta)
            rec = {"family": d["family"], "n": n, "temperature": label, "beta": beta, "entropy_bits": entropy(pt) / LN2, "p_ground": float(pt[e <= e.min() + 1e-9 * (1 + abs(e.min()))].sum()), "uniform_tvd": tvd(np.full(1 << n, 1 / (1 << n)), pt)}
            for arm in ("gibbs", "annealed"):
                curve = []
                for t in T:
                    P = np.full(1 << n, 1.0 / (1 << n))
                    if arm == "gibbs":
                        # reuse: the chain is time-homogeneous, so continue from the previous length
                        P = prev if (curve and arm == "gibbs") else P
                        for _ in range(t - (T[len(curve) - 1] if curve else 0)): P = gibbs_sweep(P, e, n, beta)
                        prev = P
                    else:
                        for k in range(t): P = gibbs_sweep(P, e, n, beta * (k + 1) / t)
                    curve.append([t, tvd(P, pt)])
                    if arm == "annealed" and n >= 18 and t >= 256: break       # cost: each annealed length is a fresh chain
                rec[arm] = curve
                rec[f"{arm}_sweeps_to_tvd_0.1"] = next((t for t, v in curve if v <= 0.1), None); rec[f"{arm}_sweeps_to_tvd_0.05"] = next((t for t, v in curve if v <= 0.05), None)
            rows.append(rec); print(d["family"], n, label, "beta %.3f" % beta, "P_gs %.3f" % rec["p_ground"], "gibbs", rec["gibbs_sweeps_to_tvd_0.1"], rec["gibbs_sweeps_to_tvd_0.05"], "annealed", rec["annealed_sweeps_to_tvd_0.1"], rec["annealed_sweeps_to_tvd_0.05"], "gibbs tvd@1024 %.4f" % rec["gibbs"][-1][1], flush=True)
            json.dump(rows, open(f"{OUT}/targets.json", "w"), indent=1)

def qaoa(nmax):
    rows = json.load(open(f"{OUT}/qaoa.json")) if os.path.exists(f"{OUT}/qaoa.json") else []; done = {(r["family"], r["n"], r["temperature"]) for r in rows}
    bas = json.load(open(f"{OUT}/bas_model.json")); tg = {(r["family"], r["n"], r["temperature"]): r for r in json.load(open(f"{OUT}/targets.json"))}
    for d in instances() + [bas]:
        n = d["n"]
        if n > nmax: continue
        e = diag_energy(n, d["h"], d["edges"]); scale = max(1e-9, float(np.max(np.abs(e))))
        for label in (("learned",) if d["family"] == "BAS" else ("warm", "cold")):
            if (d["family"], n, label) not in tg or (d["family"], n, label) in done: continue
            t = tg[(d["family"], n, label)]; pt = boltz(e, t["beta"]); rec = {"family": d["family"], "n": n, "temperature": label, "depths": []}; prev = None
            for p in (1, 2, 3):
                f = lambda x: tvd(np.abs(qaoa_state(e, n, x[:p], x[p:])) ** 2, pt)
                rng = np.random.default_rng(9000 + p); starts = [] if prev is None else [np.concatenate([np.append(prev[:p - 1], 0.0), np.append(prev[p - 1:], 0.0)])]
                while len(starts) < 4: starts.append(np.concatenate([rng.uniform(0, 2 * math.pi / scale * 4, p), rng.uniform(0, math.pi, p)]))
                best = None
                for x0 in starts:
                    r = minimize(f, x0, method="Nelder-Mead", options={"maxfev": 300, "xatol": 1e-6, "fatol": 1e-9})
                    if best is None or r.fun < best[0]: best = (float(r.fun), r.x)
                prev = best[1]; rec["depths"].append({"p": p, "tvd_floor": best[0], "gamma": list(map(float, best[1][:p])), "beta": list(map(float, best[1][p:]))})
            rows.append(rec); print(d["family"], n, label, [round(x["tvd_floor"], 4) for x in rec["depths"]], "uniform", round(t["uniform_tvd"], 4), flush=True)
            json.dump(rows, open(f"{OUT}/qaoa.json", "w"), indent=1)

def tempering(nmax):
    """A stronger classical sampler for the cold targets: parallel tempering, 8 replicas on a geometric ladder from beta/64
    to beta, one Gibbs sweep per replica then neighbour swaps, each round. 20,000 independent runs from random states; the
    cold replica is read after t rounds. Empirical TVD, with the sampling noise floor estimated by drawing the same number
    of exact samples. Cost per sample: 8 n t flips."""
    rows = json.load(open(f"{OUT}/tempering.json")) if os.path.exists(f"{OUT}/tempering.json") else []; done = {(r["family"], r["n"]) for r in rows}
    tg = [r for r in json.load(open(f"{OUT}/targets.json")) if r["temperature"] == "cold" and r["n"] <= nmax and (r["family"], r["n"]) not in done]; inst = {(d["family"], d["n"]): d for d in instances()}
    rng = np.random.default_rng(424242); M, K = 20000, 8
    for t in tg:
        d = inst[(t["family"], t["n"])]; n = d["n"]; e = diag_energy(n, d["h"], d["edges"]); pt = boltz(e, t["beta"])
        h = np.array(d["h"]); J = np.zeros((n, n))
        for i, j, w in d["edges"]: J[int(i), int(j)] += w; J[int(j), int(i)] += w
        betas = t["beta"] * np.geomspace(1 / 64, 1, K); S = rng.choice([-1.0, 1.0], size=(K, M, n)); pw = 1 << np.arange(n)
        energy = lambda X: -(X @ h) - 0.5 * np.einsum("...i,ij,...j->...", X, J, X)
        noise = tvd(np.bincount(rng.choice(1 << n, size=M, p=pt), minlength=1 << n) / M, pt); curve = []; done_rounds = 0
        for rounds in (1, 4, 16, 64, 256, 1024):
            for _ in range(rounds - done_rounds):
                for i in range(n):
                    field = h[i] + S @ J[i]                                   # E = -sum h s - sum J s s: flipping to +1 is favoured by a positive field
                    p1 = 1.0 / (1.0 + np.exp(np.clip(-2.0 * betas[:, None] * field, -700, 700))); S[:, :, i] = np.where(rng.random((K, M)) < p1, 1.0, -1.0)
                E = energy(S)
                for k in range(K - 1):
                    acc = rng.random(M) < np.exp(np.clip((betas[k + 1] - betas[k]) * (E[k + 1] - E[k]), -700, 0)); tmp = S[k, acc].copy(); S[k, acc] = S[k + 1, acc]; S[k + 1, acc] = tmp
                    te = E[k, acc].copy(); E[k, acc] = E[k + 1, acc]; E[k + 1, acc] = te
            done_rounds = rounds
            idx = (((S[-1] + 1) / 2).astype(np.int64) @ pw); curve.append([rounds, tvd(np.bincount(idx, minlength=1 << n) / M, pt)])
        rows.append({"family": t["family"], "n": n, "temperature": "cold", "replicas": K, "runs": M, "noise_floor_tvd": noise, "curve": curve}); print(t["family"], n, "noise", round(noise, 4), [(r, round(v, 4)) for r, v in curve], flush=True)
        json.dump(rows, open(f"{OUT}/tempering.json", "w"), indent=1)

def spiking():
    """ferromorphic's fixed-temperature spiking sampler on the 12-variable targets: 20,000 fresh chains per setting."""
    import subprocess
    rows = json.load(open(f"{OUT}/spiking.json")) if os.path.exists(f"{OUT}/spiking.json") else []; done = {(r["family"], r["temperature"]) for r in rows}
    tg = [r for r in json.load(open(f"{OUT}/targets.json")) if r["n"] == 12 and (r["family"], r["temperature"]) not in done]; inst = {(d["family"], d["n"]): d for d in instances()}; rng = np.random.default_rng(31337); M = 20000
    for t in tg:
        d = inst[(t["family"], 12)]; e = diag_energy(12, d["h"], d["edges"]); pt = boltz(e, t["beta"]); curve = []
        noise = tvd(np.bincount(rng.choice(4096, size=M, p=pt), minlength=4096) / M, pt)
        for sweeps in (4, 16, 64, 256, 1024):
            out = subprocess.run([f"{ROOT}/neuro/target/release/neuro", f"{ROOT}/inst/{t['family']}_12_0.txt"], env={**os.environ, "SAMPLE": f"{t['beta']} {sweeps} {M}"}, capture_output=True, text=True, check=True)
            r = json.loads(out.stdout); curve.append([sweeps, tvd(np.array(r["counts"]) / M, pt), r["neuron_updates"] / M])
        rows.append({"family": t["family"], "n": 12, "temperature": t["temperature"], "runs": M, "noise_floor_tvd": noise, "curve": curve}); print(t["family"], t["temperature"], "noise", round(noise, 4), [(a, round(b, 4)) for a, b, _ in curve], flush=True)
        json.dump(rows, open(f"{OUT}/spiking.json", "w"), indent=1)

if __name__ == "__main__":
    {"targets": targets, "qaoa": lambda: qaoa(int(sys.argv[2])), "tempering": lambda: tempering(int(sys.argv[2])), "spiking": spiking}[sys.argv[1]]()

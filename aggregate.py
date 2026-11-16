#!/usr/bin/env python3
"""Aggregate Aim 1 and Aim 2 results into summary tables (medians over seeds). Reads only result files."""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.abspath(__file__))
import os
import glob, json, math, statistics as st, hashlib, os
RES = os.path.join(ROOT, "results")
med = lambda xs: st.median(xs) if xs else float("nan")

def r99(p):
    if p <= 0: return float("inf")
    if p >= 0.99: return 1.0
    return math.log(0.01) / math.log(1 - p)

rows = {}
for path in sorted(glob.glob(f"{RES}/aim1_[ABCDR]_*.json")):
    tag = os.path.basename(path)[5:-5]
    d = json.load(open(path))
    pp = f"{RES}/post_{tag}.json"
    post = json.load(open(pp)) if os.path.exists(pp) else None
    key = (d["family"], d["n"])
    g = rows.setdefault(key, {"k": 0, "gap_sdp": [], "gw16_opt": [], "gw16_ratio": [], "pt_tts": [], "pt_j": [], "cold": {1: [], 2: [], 3: []}, "warm": {1: [], 2: [], 3: []},
                              "cold_ratio": {1: [], 2: [], 3: []}, "warm_ratio": {1: [], 2: [], 3: []}, "ws0": [], "cz": {1: [], 2: [], 3: []}, "rzz": {1: [], 2: [], 3: []}, "xc": [], "nground": [], "posted": 0})
    g["k"] += 1
    span = d["e_max"] - d["e_min"]
    g["gap_sdp"].append((d["e_min"] - d["sdp_bound"]) / abs(d["e_min"]))
    g["gw16_ratio"].append((d["e_max"] - d["gw16_energy"]) / span)
    g["gw16_opt"].append(abs(d["gw16_energy"] - d["e_min"]) < 1e-9 * (1 + abs(d["e_min"])))
    g["nground"].append(d["n_ground"])
    if d["pt_tts99_proposals"] is not None:
        g["pt_tts"].append(d["pt_tts99_proposals"]); g["pt_j"].append(d["pt_tts99_proposals"] * d["kv260_writable_j_per_flip"])
    for q in d["qaoa"]:
        g["cold"][q["p"]].append(q["p_gs"]); g["cold_ratio"][q["p"]].append(q["ratio"])
    if post:
        g["posted"] += 1
        g["ws0"].append(post["ws_p0"]["p_gs"])
        for w in post["ws"]:
            g["warm"][w["p"]].append(w["p_gs"]); g["warm_ratio"][w["p"]].append(w["ratio"])
        for t in post["transpile"]:
            g["cz"][t["p"]].append(t["heavy_hex_cz"]); g["rzz"][t["p"]].append(t["all_to_all_rzz"])
        g["xc"].append(max(c["abs_diff_expectation"] for c in post["cross_check"]))

print("AIM 1 (medians over seeds; P = ideal ground-state probability per shot; R99 = shots for 99%)")
print("fam n  k | nGS | SDPgap% | GW16opt | cold P p1/p2/p3 | warm P p0/p1/p2/p3 | cold R99 p3 | warm R99 p3 | PT TTS99 props | PT J(KV260w) | CZ p1/p3 | RZZ p1/p3 | xcheck")
summary = []
for (fam, n), g in sorted(rows.items()):
    c = [med(g["cold"][p]) for p in (1, 2, 3)]; w = [med(g["warm"][p]) for p in (1, 2, 3)]
    rec = {"family": fam, "n": n, "instances": g["k"], "post_done": g["posted"], "median_n_ground": med(g["nground"]),
           "sdp_gap_pct_median": 100 * med(g["gap_sdp"]), "sdp_gap_pct_max": 100 * max(g["gap_sdp"]), "gw16_optimal": f"{sum(g['gw16_opt'])}/{g['k']}",
           "cold_pgs": c, "warm_pgs": w, "warm_p0_pgs": med(g["ws0"]), "cold_ratio": [med(g["cold_ratio"][p]) for p in (1, 2, 3)], "warm_ratio": [med(g["warm_ratio"][p]) for p in (1, 2, 3)],
           "cold_r99_p3": r99(c[2]), "warm_r99_p3": r99(w[2]) if g["posted"] else None,
           "pt_tts99_proposals": med(g["pt_tts"]), "pt_solved": f"{len(g['pt_tts'])}/{g['k']}", "pt_joules_kv260_writable": med(g["pt_j"]),
           "cz": [med(g["cz"][p]) for p in (1, 2, 3)], "rzz": [med(g["rzz"][p]) for p in (1, 2, 3)], "max_crosscheck_diff": max(g["xc"]) if g["xc"] else None}
    summary.append(rec)
    f = lambda xs: "/".join(f"{x:.4f}" for x in xs)
    print(f"{fam} {n:2d} {g['k']} | {rec['median_n_ground']:.0f} | {rec['sdp_gap_pct_median']:.3f} | {rec['gw16_optimal']} | {f(c)} | {rec['warm_p0_pgs']:.4f}/{f(w)} | {rec['cold_r99_p3']:.0f} | {rec['warm_r99_p3'] if (rec['warm_r99_p3'] is None or rec['warm_r99_p3'] != rec['warm_r99_p3'] or rec['warm_r99_p3'] == float('inf')) else round(rec['warm_r99_p3'])} | {rec['pt_tts99_proposals']:.0f} ({rec['pt_solved']}) | {rec['pt_joules_kv260_writable']:.2e} | {rec['cz'][0]:.0f}/{rec['cz'][2]:.0f} | {rec['rzz'][0]:.0f}/{rec['rzz'][2]:.0f} | {rec['max_crosscheck_diff']}")

print("\nNOISY (n=12, seed 0): model kind p -> P_gs noisy (ideal)")
noisy = []
for path in sorted(glob.glob(f"{RES}/post_*_12_0.json")):
    d = json.load(open(path))
    for x in d["noisy"]:
        noisy.append({"family": d["family"], **x})
        print(d["family"], x["model"], x["kind"], x["p"], f"{x['p_gs']:.4f} ({x['ideal_p_gs']:.4f}) ratio {x['ratio']:.3f}")

import numpy as np
a2 = [r for p in sorted(glob.glob(f"{RES}/aim2/*.json")) for r in json.load(open(p))]
aim2_sum = {}
if a2:
    forms = list(dict.fromkeys(r["form"] for r in a2))
    print(f"\nAIM 2: {len(forms)} Forms ({sum(1 for f in forms if [r for r in a2 if r['form'] == f][0]['kind'] == 'exact')} exact, rest truncated), {len(a2)} circuits")
    print("form | states events | ANF literals | R T=5: qubits resets CZ fid RZZ fid | G T=5 qubits | P T=5 qubits CZ | selene | Torino 2q fid | Fez 2q fid")
    per = []
    for f in forms:
        g = lambda style: [r for r in a2 if r["form"] == f and r["style"] == style and r["T"] == 5 and r["stream"] == 0]
        R, G, P = g("R")[0], g("G")[0], (g("P") or [None])[0]
        t, z = R.get("ibm_torino_snapshot", {}), R.get("ibm_fez_snapshot", {})
        per.append({"form": f, "source": R["source"], "kind": R["kind"].split()[0], "states": R["states"], "events": R["events"], "anf_literals": R["anf_literals"], "overwritten_bits": R["overwritten_bits"],
                    "reset_qubits": R["qubits"], "garbage_qubits": G["qubits"], "inplace_qubits": P["qubits"] if P else None, "reset_cz": R["sc_like"]["two_qubit_gates"], "reset_rzz": R["ion_like"]["two_qubit_gates"],
                    "inplace_cz": P["sc_like"]["two_qubit_gates"] if P else None, "selene": R.get("selene_replays_reference")})
        print(f, "|", R["states"], R["events"], "|", R["anf_literals"], "|", R["qubits"], R["resets"], R["sc_like"]["two_qubit_gates"], R["sc_like"].get("trace_fidelity"), R["ion_like"]["two_qubit_gates"], R["ion_like"].get("trace_fidelity"),
              "|", G["qubits"], "|", (P["qubits"], P["sc_like"]["two_qubit_gates"]) if P else "-", "|", R.get("selene_replays_reference"), "|", t.get("two_qubit_gates"), t.get("trace_fidelity"), "|", z.get("two_qubit_gates"), z.get("trace_fidelity"))
    fits = {}
    # log-linear fit on circuits with at least 20 correct traces (fidelity >= 0.01), so that shot noise near zero does not drive the fit; the all-points fit is kept beside it
    for b in ("sc_like", "ion_like", "ibm_torino_snapshot", "ibm_fez_snapshot"):
        allp = [(r[b]["two_qubit_gates"], r[b]["trace_fidelity"]) for r in a2 if b in r and r[b].get("trace_fidelity") is not None]
        def fit(pts):
            x = np.array([p[0] for p in pts]); y = np.log(np.array([p[1] for p in pts])); k, c = np.polyfit(x, y, 1)
            r2 = 1 - ((y - (k * x + c)) ** 2).sum() / ((y - y.mean()) ** 2).sum()
            return {"circuits": len(pts), "loss_per_two_qubit_gate_pct": round(100 * (1 - math.exp(k)), 4), "r2": round(float(r2), 4), "gates_at_30pct": round((math.log(0.3) - c) / k), "fidelity_at_zero_gates": round(math.exp(c), 4)}
        fits[b] = {"sampled_circuits": len(allp), **fit([p for p in allp if p[1] >= 0.01]), "all_nonzero_points": fit([p for p in allp if p[1] > 0])}
        print(b, fits[b])
    # Q4: what predicts two-qubit gate count (reset style, T = 5): transition complexity or overwritten bits?
    y = np.log(np.array([max(1, p["reset_cz"]) for p in per], dtype=float))
    def r2of(cols):
        X = np.column_stack([np.ones(len(per))] + cols); beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        return float(1 - ((y - X @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum())
    lit = np.log(np.array([max(1, p["anf_literals"]) for p in per], dtype=float)); eps = np.array([p["overwritten_bits"] for p in per], dtype=float)
    q4 = {"forms": len(per), "r2_log_cz_on_log_anf_literals": round(r2of([lit]), 4), "r2_log_cz_on_overwritten_bits": round(r2of([eps]), 4), "r2_both": round(r2of([lit, eps]), 4)}
    rng = np.random.default_rng(20261111); part = []
    for _ in range(10000):
        ix = rng.integers(0, len(per), len(per)); yb = y[ix]
        def rb(cols):
            X = np.column_stack([np.ones(len(ix))] + [c[ix] for c in cols]); beta, *_ = np.linalg.lstsq(X, yb, rcond=None)
            return 1 - ((yb - X @ beta) ** 2).sum() / ((yb - yb.mean()) ** 2).sum()
        part.append((rb([lit, eps]) - rb([lit])) / (1 - rb([lit])))
    q4["partial_r2_overwritten_bits_given_literals"] = round((q4["r2_both"] - q4["r2_log_cz_on_log_anf_literals"]) / (1 - q4["r2_log_cz_on_log_anf_literals"]), 4)
    q4["partial_r2_bootstrap_95pct"] = [round(float(np.percentile(part, 2.5)), 4), round(float(np.percentile(part, 97.5)), 4)]
    print("Q4 (reset style, T = 5):", q4)
    def loo(cols):
        e = []
        for i in range(len(per)):
            m = np.arange(len(per)) != i; X = np.column_stack([np.ones(len(per))] + cols); beta = np.linalg.lstsq(X[m], y[m], rcond=None)[0]; e.append(y[i] - X[i] @ beta)
        return round(float(np.sqrt(np.mean(np.square(e)))), 4)
    q4["leave_one_out_rms_log_error"] = {"literals": loo([lit]), "literals_and_overwritten_bits": loo([lit, eps]), "overwritten_bits": loo([eps])}
    q4["by_overwritten_bits"] = {int(e): {"forms": sum(1 for p in per if p["overwritten_bits"] == e), "reset_cz": [min(p["reset_cz"] for p in per if p["overwritten_bits"] == e), max(p["reset_cz"] for p in per if p["overwritten_bits"] == e)]} for e in sorted(set(eps))}
    print("Q4 held out:", q4["leave_one_out_rms_log_error"], q4["by_overwritten_bits"])
    # Q5 held out: fit on half of the Forms (alternating in name order), predict the other half; gates only against gates + resets + width
    q5 = {}
    for b in fits:
        P = [r for r in a2 if b in r and (r[b].get("trace_fidelity") or 0) >= 0.01]
        def XY(Q, full):
            cols = [[r[b]["two_qubit_gates"] for r in Q]] + ([[r["resets"] for r in Q], [r["qubits"] for r in Q]] if full else [])
            return np.column_stack([np.ones(len(Q))] + [np.array(c, float) for c in cols]), np.log([r[b]["trace_fidelity"] for r in Q])
        q5[b] = {}
        for full in (False, True):
            errs = []
            for fold in (0, 1):
                tr = [r for r in P if forms.index(r["form"]) % 2 == fold]; te = [r for r in P if forms.index(r["form"]) % 2 != fold]
                X, yy = XY(tr, full); beta = np.linalg.lstsq(X, yy, rcond=None)[0]; Xt, yt = XY(te, full); errs += list(np.abs(Xt @ beta - yt))
            q5[b]["gates_resets_width" if full else "gates_only"] = {"median_error_factor": round(float(np.exp(np.median(errs))), 3), "p90_error_factor": round(float(np.exp(np.percentile(errs, 90))), 3)}
    print("Q5 held out:", q5)
    cnt = {s: sum(1 for r in a2 if r["style"] == s) for s in "GRP"}
    chk = [r[t]["noiseless_trace_ok"] for r in a2 for t in ("sc_like", "ion_like") if "noiseless_trace_ok" in r[t]]
    Rr = [r for r in a2 if r["style"] == "R"]; Gg = [r for r in a2 if r["style"] == "G"]
    shape = {"circuits_by_style": cnt, "reset_width": [min(r["qubits"] for r in Rr), max(r["qubits"] for r in Rr)], "garbage_width": [min(r["qubits"] for r in Gg), max(r["qubits"] for r in Gg)],
             "reset_cz_T5": [min(p["reset_cz"] for p in per), max(p["reset_cz"] for p in per)], "reset_rzz_T5": [min(p["reset_rzz"] for p in per), max(p["reset_rzz"] for p in per)],
             "inplace_forms": sum(1 for p in per if p["inplace_qubits"]), "noiseless_checked": len(chk), "noiseless_ok": sum(1 for c in chk if c),
             "overwritten_bits_T5": sorted({p["overwritten_bits"] for p in per})}
    print("shape:", shape)
    sel = [p["selene"] for p in per] + [r.get("selene_replays_reference") for r in a2 if r["style"] == "P" and r["T"] == 5]
    sel = [x for x in sel if x is not None]
    selene = {"programs_run": len(sel), "replay_reference": sum(1 for x in sel if x is True), "other": sorted({str(x) for x in sel if x is not True})}
    print("Selene:", selene, "| noiseless replay checked on", sum(1 for r in a2 for t in ("sc_like", "ion_like") if r[t].get("noiseless_trace_ok")), "transpiled circuits")
    aim2_sum = {"forms": per, "circuits": len(a2), "shape": shape, "fidelity_fits": fits, "q5_held_out": q5, "q4": q4, "selene": selene,
                "qasm3_files": len(glob.glob(f"{RES}/aim2/qasm3/*.qasm")), "guppy_files": len(glob.glob(f"{RES}/aim2/guppy/*.py"))}

repairs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(ROOT, "repair", "R_*.json")))]
if repairs:
    print("\nPROGRAM REPAIR instances (tag R): tag | source | tests passed faulty -> optimum of total | optimal repairs | restores original")
    for m in repairs: print(m["tag"], "|", m["source"], "|", m["tests_passed_by_faulty_program"], "->", m["tests_passed_by_optimum"], "of", m["tests"], "|", m["optimal_repairs"], "|", m["optimum_restores_original"])

# warm start conditional on whether the classical seed (best of 16 GW roundings) is already optimal
split = {}
for path in sorted(glob.glob(f"{RES}/aim1_[ABCDR]_*.json")):
    tag = os.path.basename(path)[5:-5]; pp = f"{RES}/post_{tag}.json"
    if not os.path.exists(pp): continue
    d = json.load(open(path)); post = json.load(open(pp))
    split.setdefault(bool(post["gw16_is_optimal"]), []).append((d["n"], d["qaoa"][2]["p_gs"], post["ws"][2]["p_gs"]))
print("\nWARM vs COLD at p=3, split by whether the GW seed is optimal")
cond = []
for opt, v in sorted(split.items(), reverse=True):
    rec = {"gw_seed_optimal": opt, "instances": len(v), "warm_beats_cold": sum(w > c for _, c, w in v), "median_cold_pgs": med([c for _, c, _ in v]), "median_warm_pgs": med([w for _, _, w in v]),
           "by_n": {n: {"instances": sum(1 for x in v if x[0] == n), "warm_beats_cold": sum(w > c for m, c, w in v if m == n)} for n in sorted({x[0] for x in v})}}
    cond.append(rec); print(rec)

neuro = [json.loads(l) for l in open(f"{RES}/neuro.jsonl")] if os.path.exists(f"{RES}/neuro.jsonl") else []
ng = {}
for r in neuro:
    if r["tts99_neuron_updates"] is not None: ng.setdefault(f"{r['tag'][0]}_{r['n']}", []).append(r["tts99_neuron_updates"])
neuro_sum = {k: {"solved": len(v), "median_tts99_neuron_updates": med(v)} for k, v in sorted(ng.items())}
print("\nNEUROMORPHIC ARM (ferromorphic spiking annealer), median TTS99 neuron updates:", neuro_sum)

ibm = json.load(open(f"{RES}/aim1_ibm.json")) if os.path.exists(f"{RES}/aim1_ibm.json") else []
if ibm:
    print("\nAIM 1 on IBM calibration snapshots (n=12, seed 0): family backend kind p -> 2q gates, P_gs (ideal)")
    for x in ibm: print(x["family"], x["backend"], x["kind"], x["p"], x["two_qubit_gates"], x.get("p_gs"), f"({x['ideal_p_gs']:.4f})")

manifest = {os.path.basename(p): hashlib.sha256(open(p, "rb").read()).hexdigest() for p in sorted(glob.glob(f"{RES}/*.json") + glob.glob(f"{RES}/aim2/*.json") + glob.glob(f"{RES}/scale/*.json") + glob.glob(f"{RES}/labs/*.json") + glob.glob(f"{RES}/sampling/*.json") + glob.glob(f"{RES}/chem/*.json") + glob.glob(f"{RES}/hubbard/*.json") + glob.glob(f"{RES}/targets/*.json") + glob.glob(f"{RES}/iqm/*.json")) if "summary" not in p and "manifest" not in p}
# certified gap in problem units, scale-up set, angle transfer, hardware requests (each written by its own script)
extra = {}
if os.path.exists(f"{RES}/feasible_gap.json"):
    fg = json.load(open(f"{RES}/feasible_gap.json")); extra["feasible_gap"] = []
    print("\nCERTIFIED GAP as % of the spread among encoding-feasible states: set family instances | min median max | within 1%")
    for s_ in ("small", "scale"):
        for fam in "ABCDR":
            v = [r["gap_pct_of_feasible_spread"] for r in fg if r["family"] == fam and r["set"] == s_]
            if not v: continue
            rec = {"set": s_, "family": fam, "instances": len(v), "min": round(min(v), 4), "median": round(med(v), 4), "max": round(max(v), 4), "within_1pct": sum(1 for x in v if x <= 1)}
            extra["feasible_gap"].append(rec); print(s_, fam, len(v), "|", rec["min"], rec["median"], rec["max"], "|", rec["within_1pct"])
sc = [json.load(open(p)) for p in sorted(glob.glob(f"{RES}/scale/scale_*.json"))]
if sc and os.path.exists(f"{RES}/scale_post.json"):
    sp = {(r["family"], r["n"], r["seed"]): r for r in json.load(open(f"{RES}/scale_post.json"))}; extra["scale"] = []
    print("\nSCALE-UP (24 to 60 variables): family n instances | optimum proved by branch and bound | tempering reaches the reference | GW seed is the reference | median PT TTS99 | CZ heavy-hex p1/p2/p3 | RZZ p1/p2/p3")
    for fam in "ABCDR":
        for n in sorted({d["n"] for d in sc if d["family"] == fam}):
            g = [d for d in sc if d["family"] == fam and d["n"] == n]
            found = [abs(d["pt_best_energy"] - d["reference_energy"]) <= 1e-9 * (1 + abs(d["reference_energy"])) for d in g]
            tt = [d["pt_tts99_proposals"] for d in g if d["pt_tts99_proposals"] is not None]
            t = [sp[(fam, n, d["seed"])]["transpile"] for d in g]
            rec = {"family": fam, "n": n, "instances": len(g), "proved_optimal": sum(1 for d in g if d["bnb_proved_optimal"]), "tempering_reaches_reference": sum(found),
                   "gw_seed_is_reference": sum(1 for d in g if abs(d["gw16_energy"] - d["reference_energy"]) <= 1e-6), "median_pt_tts99": med(tt) if tt else None,
                   "heavy_hex_cz": [med([x[p]["heavy_hex_cz"] for x in t]) for p in range(3)], "all_to_all_rzz": [med([x[p]["all_to_all_rzz"] for x in t]) for p in range(3)]}
            extra["scale"].append(rec); print(fam, n, len(g), "|", rec["proved_optimal"], "|", rec["tempering_reaches_reference"], "|", rec["gw_seed_is_reference"], "|", rec["median_pt_tts99"], "|", rec["heavy_hex_cz"], "|", rec["all_to_all_rzz"])
    tot = {k: sum(r[k] for r in extra["scale"]) for k in ("instances", "proved_optimal", "tempering_reaches_reference", "gw_seed_is_reference")}; extra["scale_totals"] = tot; print("totals:", tot)
if os.path.exists(f"{RES}/transfer.json"):
    tr = json.load(open(f"{RES}/transfer.json")); extra["transfer"] = []
    print("\nANGLE TRANSFER from 12 variables to 15-20 (cold QAOA): family p cases | median ratio own, unchanged, gamma rescaled | median P_gs own, rescaled | rescaled/own ratio median, min")
    for fam in "ABCDR":
        for p in (1, 2, 3):
            v = [r for r in tr if r["family"] == fam and r["p"] == p]
            if not v: continue
            rel = [r["median_ratio_rescaled"] / r["own_ratio"] for r in v]
            rec = {"family": fam, "p": p, "cases": len(v), "ratio_own": round(med([r["own_ratio"] for r in v]), 4), "ratio_unchanged": round(med([r["median_ratio_unchanged"] for r in v]), 4),
                   "ratio_rescaled": round(med([r["median_ratio_rescaled"] for r in v]), 4), "p_gs_own": med([r["own_p_gs"] for r in v]), "p_gs_rescaled": med([r["median_p_gs_rescaled"] for r in v]),
                   "rescaled_over_own_median": round(med(rel), 4), "rescaled_over_own_min": round(min(rel), 4)}
            extra["transfer"].append(rec); print(fam, p, len(v), "|", rec["ratio_own"], rec["ratio_unchanged"], rec["ratio_rescaled"], "|", f"{rec['p_gs_own']:.4f} {rec['p_gs_rescaled']:.4f}", "|", rec["rescaled_over_own_median"], rec["rescaled_over_own_min"])
    rel = [r["median_ratio_rescaled"] / r["own_ratio"] for r in tr]
    extra["transfer_totals"] = {"cases": len(tr), "rescaled_ratio_at_least_95pct_of_own": sum(1 for x in rel if x >= 0.95), "rescaled_p_gs_at_least_half_of_own": sum(1 for r in tr if r["median_p_gs_rescaled"] >= 0.5 * r["own_p_gs"])}
    print("totals:", extra["transfer_totals"])
for name in ("aim1_request", "aim2_request"):
    if os.path.exists(f"{RES}/{name}.json"):
        extra[name] = json.load(open(f"{RES}/{name}.json")); print(f"\n{name.upper()}:"); [print(" ", r["vendor"], r.get("tier", ""), r["circuits"], "circuits,", r["qubits"], "qubits,", r["shots_per_circuit"], "shots each,", r["total_shots"], "shots") for r in extra[name]]
if os.path.exists(f"{RES}/cost.json"):
    cj = json.load(open(f"{RES}/cost.json")); extra["cost"] = {"trapped_ion": cj["trapped_ion"], "ibm_time_estimate": cj["ibm_time_estimate"]}
    print("\nCOST ESTIMATE (public formulas; to be replaced by vendor emulator figures):")
    for r in cj["trapped_ion"]: print(" ", r)
    print(" ", cj["ibm_time_estimate"])
if os.path.exists(f"{RES}/qaoa24.json"):
    extra["qaoa24"] = json.load(open(f"{RES}/qaoa24.json")); print("\nPROGRAM REPAIR AT 24 VARIABLES, ideal cold QAOA with transferred angles: seed p donor P_gs shots x RZZ | PT TTS99")
    for r in extra["qaoa24"]:
        for d_ in r["depths"]: print(" ", r["seed"], d_["p"], d_["donor"], f"{d_['p_gs']:.5f}", None if d_["shots_times_gates"] is None else round(d_["shots_times_gates"]), "|", r["pt_tts99_proposals"])
LB = f"{RES}/labs"
if os.path.exists(f"{LB}/quadratised.json"):
    nat = sorted((json.load(open(p)) for p in glob.glob(f"{LB}/native_*.json")), key=lambda d: d["n"])
    quad = {m["N"]: m for m in json.load(open(f"{LB}/quadratised.json"))}
    circ = {c["N"]: c for c in (json.load(open(p)) for p in glob.glob(f"{LB}/circuit_*.json"))}
    qa = {q["N"]: q for q in (json.load(open(p)) for p in glob.glob(f"{LB}/qaoa_*.json"))}
    neu = {int(r["tag"].split("_")[1]): r for r in (json.loads(l) for l in open(f"{LB}/neuro.jsonl"))} if os.path.exists(f"{LB}/neuro.jsonl") else {}
    def expfit(xs, ys):
        x = np.array(xs, float); y = np.log(np.array(ys, float)); k, c = np.polyfit(x, y, 1)
        return {"base": round(float(math.exp(k)), 4), "r2": round(float(1 - ((y - (k * x + c)) ** 2).sum() / ((y - y.mean()) ** 2).sum()), 4), "points": len(xs)}
    rows = []
    print("\nLABS (sequence design): N | optimum | native SA TTS99 flips | quadratised spins | PT TTS99 on quadratised (reaches optimum, proved) | certified bound in LABS units | spiking TTS99 | QAOA P_gs p1/p2/p3 (uniform) | best shots x RZZ | RZZ, CZ per layer")
    for d in nat:
        N = d["n"]; r = {"N": N, "optimum": d["e_min"], "n_ground": d["n_ground"], "merit_factor": d["merit_factor"], "native_sa_tts99_flips": d["sa_tts99_flips"]}
        if N in quad and os.path.exists(f"{LB}/scale_L_{N}.json") and os.path.getsize(f"{LB}/scale_L_{N}.json"):
            m = quad[N]; sc_ = json.load(open(f"{LB}/scale_L_{N}.json")); to = lambda e: e * m["lambda"] + m["ising_offset"]
            target = m["ising_energy_of_optimum"]; tol = 1e-6
            assert min(min(es) for es in sc_["pt_energies"]) >= target - tol and sc_["bnb_energy"] >= target - tol, "a pairwise solver went below the LABS optimum: penalty too weak"
            lengths = [c[0] for c in sc_["pt_curve"]]; best = None
            for L, es in zip(lengths, sc_["pt_energies"]):
                p_ = sum(1 for e in es if e <= target + tol) / len(es)
                if p_ > 0:
                    w = L * (1.0 if p_ >= 0.99 else math.log(0.01) / math.log(1 - p_))
                    if best is None or w < best: best = w
            r.update({"spins_quadratised": m["spins_quadratised"], "couplings_quadratised": m["couplings"], "pt_quadratised_tts99_proposals": best,
                      "pt_reaches_optimum": abs(sc_["pt_best_energy"] - target) <= tol, "bnb_proved_optimal": sc_["bnb_proved_optimal"], "bnb_reaches_optimum": abs(sc_["bnb_energy"] - target) <= tol,
                      "certified_bound_labs_units": round(to(sc_["sdp_bound"]), 2), "feasible_mean_energy": N * (N - 1) / 2})
        if N in neu: r["spiking_quadratised_tts99_neuron_updates"] = neu[N]["tts99_neuron_updates"]
        if N in circ: r.update({"rzz_per_layer": circ[N]["all_to_all_rzz_per_layer"], "cz_per_layer": circ[N]["heavy_hex_cz_per_layer"], "four_body_terms": circ[N]["four_body_terms"]})
        if N in qa:
            ds = qa[N]["depths"]; r["qaoa_p_gs"] = [x["p_gs"] for x in ds]; r["uniform_p_gs"] = ds[0]["uniform_p_gs"]
            if N in circ: r["qaoa_best_shots_times_rzz"] = min(x["shots_to_99pct"] * x["p"] * circ[N]["all_to_all_rzz_per_layer"] for x in ds if x["shots_to_99pct"])
        rows.append(r)
        print(N, "|", r["optimum"], "|", r["native_sa_tts99_flips"], "|", r.get("spins_quadratised"), "|", r.get("pt_quadratised_tts99_proposals") and round(r["pt_quadratised_tts99_proposals"]), (r.get("pt_reaches_optimum"), r.get("bnb_proved_optimal")), "|", r.get("certified_bound_labs_units"),
              "|", r.get("spiking_quadratised_tts99_neuron_updates"), "|", [round(x, 5) for x in r.get("qaoa_p_gs", [])], r.get("uniform_p_gs") and round(r["uniform_p_gs"], 5), "|", r.get("qaoa_best_shots_times_rzz") and round(r["qaoa_best_shots_times_rzz"]), "|", r.get("rzz_per_layer"), r.get("cz_per_layer"))
    fits = {"native_sa_tts": expfit([r["N"] for r in rows if r["native_sa_tts99_flips"]], [r["native_sa_tts99_flips"] for r in rows if r["native_sa_tts99_flips"]])}
    q3 = [(r["N"], 1 / r["qaoa_p_gs"][2]) for r in rows if "qaoa_p_gs" in r]
    if len(q3) >= 3: fits["qaoa_p3_inverse_p_gs"] = expfit([a for a, _ in q3], [b for _, b in q3])
    cs = sorted(circ.values(), key=lambda c: c["N"]); xs = np.log([c["N"] for c in cs]); ys = np.log([c["all_to_all_rzz_per_layer"] for c in cs]); kk, cc = np.polyfit(xs, ys, 1)
    fits["rzz_per_layer_power_law"] = {"exponent": round(float(kk), 3), "prefactor": round(float(math.exp(cc)), 4)}
    fits["rzz_per_layer_extrapolated"] = {n_: int(round(math.exp(cc) * n_ ** kk)) for n_ in (40, 64, 100)}
    fits["largest_N_admitted_depth1"] = {"all_to_all_2000_rzz": max((c["N"] for c in cs if c["all_to_all_rzz_per_layer"] <= 2000), default=None), "heavy_hex_660_cz": max((c["N"] for c in cs if c["heavy_hex_cz_per_layer"] <= 660), default=None)}
    print("fits:", fits); extra["labs"] = {"rows": rows, "fits": fits}
SM = f"{RES}/sampling"
if os.path.exists(f"{SM}/targets.json"):
    tg = json.load(open(f"{SM}/targets.json")); qa = {(r["family"], r["n"], r["temperature"]): r for r in json.load(open(f"{SM}/qaoa.json"))} if os.path.exists(f"{SM}/qaoa.json") else {}
    ptm = {(r["family"], r["n"]): r for r in json.load(open(f"{SM}/tempering.json"))} if os.path.exists(f"{SM}/tempering.json") else {}
    spk = {(r["family"], r["temperature"]): r for r in json.load(open(f"{SM}/spiking.json"))} if os.path.exists(f"{SM}/spiking.json") else {}
    rzz = {}
    for p_ in glob.glob(f"{RES}/post_*_0.json"):
        d_ = json.load(open(p_)); rzz[(d_["family"], d_["n"])] = [t_["all_to_all_rzz"] for t_ in d_["transpile"]]
    ION_LOSS = aim2_sum["fidelity_fits"]["ion_like"]["loss_per_two_qubit_gate_pct"] / 100 if aim2_sum else None
    rows = []
    print("\nSAMPLING: family n temperature | P_gs | Gibbs sweeps to TVD 0.1 / 0.05, TVD at 1024 | annealed TVD at longest | tempering rounds to TVD 0.1 (noise floor) | spiking TVD at 1024 sweeps | QAOA TVD floor p1/p2/p3 | Gibbs sweeps to match the best QAOA floor")
    for t in tg:
        k = (t["family"], t["n"], t["temperature"]); r = {"family": t["family"], "n": t["n"], "temperature": t["temperature"], "beta": t["beta"], "p_ground": t["p_ground"],
             "gibbs_sweeps_to_tvd_0.1": t["gibbs_sweeps_to_tvd_0.1"], "gibbs_sweeps_to_tvd_0.05": t["gibbs_sweeps_to_tvd_0.05"], "gibbs_tvd_at_1024": t["gibbs"][-1][1], "annealed_tvd_at_longest": t["annealed"][-1]}
        if (t["family"], t["n"]) in ptm and t["temperature"] == "cold":
            c = ptm[(t["family"], t["n"])]; r["tempering_rounds_to_tvd_0.1"] = next((a for a, b in c["curve"] if b <= 0.1), None); r["tempering_best_tvd"] = min(b for _, b in c["curve"]); r["tempering_noise_floor"] = c["noise_floor_tvd"]
        if t["n"] == 12 and (t["family"], t["temperature"]) in spk:
            c = spk[(t["family"], t["temperature"])]; r["spiking_tvd_at_1024"] = c["curve"][-1][1]; r["spiking_sweeps_to_tvd_0.1"] = next((a for a, b, _ in c["curve"] if b <= 0.1), None); r["spiking_noise_floor"] = c["noise_floor_tvd"]
        if k in qa:
            fl = [x["tvd_floor"] for x in qa[k]["depths"]]; r["qaoa_tvd_floor"] = fl; best = min(fl); r["gibbs_sweeps_to_match_qaoa"] = next((a for a, b in t["gibbs"] if b <= best), None)
            if (t["family"], t["n"]) in rzz and ION_LOSS:
                # global depolarising approximation: the device returns the ideal distribution with probability F and a uniform state otherwise
                g = rzz[(t["family"], t["n"])]; r["qaoa_rzz"] = g; r["qaoa_tvd_trapped_ion_model"] = [round((1 - ION_LOSS) ** g[i] * fl[i] + (1 - (1 - ION_LOSS) ** g[i]) * t["uniform_tvd"], 4) for i in range(3)]
        rows.append(r)
        print(*k, "|", round(r["p_ground"], 3), "|", r["gibbs_sweeps_to_tvd_0.1"], r["gibbs_sweeps_to_tvd_0.05"], round(r["gibbs_tvd_at_1024"], 4), "|", [r["annealed_tvd_at_longest"][0], round(r["annealed_tvd_at_longest"][1], 4)], "|", r.get("tempering_rounds_to_tvd_0.1"), r.get("tempering_noise_floor") and round(r["tempering_noise_floor"], 4),
              "|", r.get("spiking_tvd_at_1024") and round(r["spiking_tvd_at_1024"], 4), "|", [round(x, 3) for x in r.get("qaoa_tvd_floor", [])], "|", r.get("gibbs_sweeps_to_match_qaoa"))
    tot = {"targets": len(rows), "gibbs_reaches_0.1": sum(1 for r in rows if r["gibbs_sweeps_to_tvd_0.1"]), "with_qaoa": sum(1 for r in rows if "qaoa_tvd_floor" in r),
           "qaoa_floor_below_0.1": sum(1 for r in rows if "qaoa_tvd_floor" in r and min(r["qaoa_tvd_floor"]) <= 0.1), "qaoa_floor_below_gibbs_at_1024": sum(1 for r in rows if "qaoa_tvd_floor" in r and min(r["qaoa_tvd_floor"]) < r["gibbs_tvd_at_1024"]),
           "cold_with_tempering": sum(1 for r in rows if "tempering_best_tvd" in r), "tempering_reaches_0.1": sum(1 for r in rows if r.get("tempering_rounds_to_tvd_0.1")),
           "qaoa_floor_below_tempering_best": sum(1 for r in rows if "tempering_best_tvd" in r and "qaoa_tvd_floor" in r and min(r["qaoa_tvd_floor"]) < r["tempering_best_tvd"])}
    print("totals:", tot); extra["sampling"] = {"rows": rows, "totals": tot}
    if os.path.exists(f"{SM}/bas_model.json"): extra["sampling"]["bars_and_stripes_kl_nats"] = json.load(open(f"{SM}/bas_model.json"))["kl_data_to_model_nats"]
CH = f"{RES}/chem"
if os.path.exists(f"{CH}/classical.json"):
    cl = json.load(open(f"{CH}/classical.json")); vq = {(r["system"], r["geometry"]): r for r in json.load(open(f"{CH}/vqe.json"))} if os.path.exists(f"{CH}/vqe.json") else {}
    cc_ = {r["system"]: r for r in json.load(open(f"{CH}/circuits.json"))} if os.path.exists(f"{CH}/circuits.json") else {}
    ION = aim2_sum["fidelity_fits"]["ion_like"]["loss_per_two_qubit_gate_pct"] / 100 if aim2_sum else None
    rows = []
    print("\nCHEMISTRY: system geometry qubits | error vs exact, mHa: RHF MP2 CCSD CCSD(T) UCCSD | T1, max|t2| | routed | CCSD wrong | UCCSD gates RZZ / CZ | modelled trapped-ion circuit fidelity")
    for r in cl:
        k = (r["system"], r["geometry"]); row = {x: r[x] for x in ("system", "geometry", "qubits", "err_rhf_mha", "err_mp2_mha", "err_ccsd_mha", "err_ccsd_t_mha", "t1_diagnostic", "max_abs_t2", "routed_to_quantum", "ccsd_wrong")}
        if k in vq: row["err_uccsd_mha"] = vq[k]["err_uccsd_mha"]; row["uccsd_within_chemical_accuracy"] = abs(vq[k]["err_uccsd_mha"]) <= 1.6
        if r["system"] in cc_:
            row["uccsd_rzz"] = cc_[r["system"]]["all_to_all_rzz"]; row["uccsd_cz"] = cc_[r["system"]]["heavy_hex_cz"]
            if ION: row["trapped_ion_circuit_fidelity"] = round((1 - ION) ** row["uccsd_rzz"], 3)
        rows.append(row)
        print(*k, r["qubits"], "|", round(r["err_rhf_mha"], 1), round(r["err_mp2_mha"], 1), round(r["err_ccsd_mha"], 2), None if r["err_ccsd_t_mha"] is None else round(r["err_ccsd_t_mha"], 2), None if "err_uccsd_mha" not in row else round(row["err_uccsd_mha"], 2),
              "|", round(r["t1_diagnostic"], 3), round(r["max_abs_t2"], 3), "|", r["routed_to_quantum"], "|", r["ccsd_wrong"], "|", row.get("uccsd_rzz"), row.get("uccsd_cz"), "|", row.get("trapped_ion_circuit_fidelity"))
    wrong = [r for r in rows if r["ccsd_wrong"]]; right = [r for r in rows if not r["ccsd_wrong"]]; both = [r for r in rows if "err_uccsd_mha" in r]
    tot = {"cases": len(rows), "ccsd_wrong": len(wrong), "ccsd_wrong_and_routed": sum(1 for r in wrong if r["routed_to_quantum"]), "ccsd_right": len(right), "ccsd_right_but_routed": sum(1 for r in right if r["routed_to_quantum"]),
           "ccsd_error_range_when_wrong_mha": [round(min(abs(r["err_ccsd_mha"]) for r in wrong), 2), round(max(abs(r["err_ccsd_mha"]) for r in wrong), 2)],
           "with_uccsd": len(both), "uccsd_closer_than_ccsd_where_ccsd_wrong": sum(1 for r in both if r["ccsd_wrong"] and abs(r["err_uccsd_mha"]) < abs(r["err_ccsd_mha"])), "ccsd_wrong_with_uccsd": sum(1 for r in both if r["ccsd_wrong"]),
           "uccsd_within_chemical_accuracy": sum(1 for r in both if r["uccsd_within_chemical_accuracy"]),
           "systems_within_2000_rzz": sum(1 for c in cc_.values() if c["all_to_all_rzz"] <= 2000), "systems_within_660_cz": sum(1 for c in cc_.values() if c["heavy_hex_cz"] <= 660), "systems_with_circuits": len(cc_)}
    if os.path.exists(f"{CH}/sqd.json"):
        sq = json.load(open(f"{CH}/sqd.json")); f_ = lambda v: 10 ** 9 if v is None else v
        tot["sqd_cases"] = len(sq); tot["sqd_ideal_sample_reaches_chemical_accuracy_sooner_than_random"] = sum(1 for r in sq if f_(r["ideal_shots_to_chemical_accuracy"]) < f_(r["uniform_shots_to_chemical_accuracy"]))
        tot["sqd_random_sooner_than_ideal"] = sum(1 for r in sq if f_(r["uniform_shots_to_chemical_accuracy"]) < f_(r["ideal_shots_to_chemical_accuracy"]))
        tot["modelled_trapped_ion_fidelity_range"] = [round(min(r["modelled_fidelity"] for r in sq), 3), round(max(r["modelled_fidelity"] for r in sq), 3)]
    if os.path.exists(f"{CH}/request.json"): tot["request"] = json.load(open(f"{CH}/request.json"))["totals"]
    print("totals:", tot); extra["chemistry"] = {"rows": rows, "totals": tot}
HB = f"{RES}/hubbard"
if os.path.exists(f"{HB}/cheap.json"):
    ld = lambda f: json.load(open(f"{HB}/{f}.json")) if os.path.exists(f"{HB}/{f}.json") else []
    ch_ = {(r["lattice"], r["U"]): r for r in ld("cheap")}; ex_ = {(r["lattice"], r["U"]): r for r in ld("exact")}; dm = {(r["lattice"], r["U"]): r for r in ld("dmrg")}; hv = {(r["lattice"], r["U"]): r for r in ld("hva")}; hp = {(r["lattice"], r["U"]): r for r in ld("hva_product")}; ci = {r["lattice"]: r for r in ld("circuits")}
    rows = []
    print("\nHUBBARD (materials): lattice U | reference energy (source) | error per site: RHF UHF CCSD | routed | DMRG change chi 64 to 256 per site | HVA error per site p1..p4 from the free-fermion start | the same from the Neel product start | RZZ per layer")
    for k, c in ch_.items():
        L = c["sites"]; ref = ex_[k]["e_exact"] if k in ex_ else (dm[k]["e_dmrg"] if k in dm else None); src = "exact" if k in ex_ else ("dmrg_chi256" if k in dm else None)
        r = {"lattice": k[0], "sites": L, "U": k[1], "reference": ref, "reference_source": src, "routed_to_quantum": c.get("routed_to_quantum"), "ccsd_converged": c.get("ccsd_converged")}
        if ref is not None:
            for m in ("rhf", "uhf", "ccsd"):
                if f"e_{m}" in c: r[f"err_{m}_per_site"] = (c[f"e_{m}"] - ref) / L
        if k in dm: r["dmrg_change_64_to_256_per_site"] = dm[k]["change_64_to_256"] / L; r["dmrg_saturated_below_256"] = dm[k]["saturated"]
        if k in ex_ and k in dm: r["dmrg_err_per_site"] = (dm[k]["e_dmrg"] - ex_[k]["e_exact"]) / L
        if k in hv: r["hva_err_per_site"] = [d_["error_per_site"] for d_ in hv[k]["depths"]]; r["hva_start_err_per_site"] = (hv[k]["e_start"] - hv[k]["e_exact"]) / L
        if k in hp: r["hva_product_start_err_per_site"] = [d_["error_per_site"] for d_ in hp[k]["depths"]]
        if k[0] in ci: r["rzz_per_layer"] = ci[k[0]]["rzz_per_layer"]
        rows.append(r)
        f3 = lambda v: None if v is None else round(v, 4)
        print(*k, "|", f3(ref), src, "|", f3(r.get("err_rhf_per_site")), f3(r.get("err_uhf_per_site")), f3(r.get("err_ccsd_per_site")), "|", r["routed_to_quantum"], "|", f3(r.get("dmrg_change_64_to_256_per_site")), "|", [round(x, 4) for x in r.get("hva_err_per_site", [])], "|", [round(x, 4) for x in r.get("hva_product_start_err_per_site", [])], "|", r.get("rzz_per_layer"))
    ev = [r for r in rows if r.get("hva_err_per_site")]; evp = [r for r in rows if r.get("hva_product_start_err_per_site")]
    tot = {"free_start_p4_beats_uhf": sum(1 for r in ev if r["hva_err_per_site"][-1] < r["err_uhf_per_site"]), "free_start_cases": len(ev), "product_start_p4_beats_uhf": sum(1 for r in evp if r["hva_product_start_err_per_site"][-1] < r["err_uhf_per_site"]), "product_start_cases": len(evp)}
    if os.path.exists(f"{HB}/request.json"): tot["request"] = json.load(open(f"{HB}/request.json"))["totals"]
    print("totals:", tot); print("circuits:", list(ci.values())); extra["hubbard"] = {"rows": rows, "totals": tot, "circuits": list(ci.values())}

TG = f"{RES}/targets"
if os.path.exists(f"{TG}/ladder.json"):
    lad = json.load(open(f"{TG}/ladder.json")); smp = {r["case"]: r for r in json.load(open(f"{TG}/sample.json"))} if os.path.exists(f"{TG}/sample.json") else {}
    print("\nTARGET CHEMISTRY: case qubits dimension | cheap error mHa, wrong | check 1, check 2 | cheap on lower reference error | selected CI dimension for 1.6 mHa | circuit RZZ, overlap with exact | shots to 1.6 mHa: random, exact state, circuit ideal, circuit noisy")
    f1 = lambda v: None if v is None else round(v, 2); rows = []
    def first(pts): return next((p["shots"] for p in pts if p.get("error_mha") is not None and abs(p["error_mha"]) <= 1.6), None)
    for r in lad:
        S = smp.get(r["case"], {}); P = S.get("proposers", {}); lj = S.get("lucj", {})
        row = {"case": r["case"], "qubits": r["qubits"], "dimension": r["dimension"], "cheap_error_mha": r["cheap"]["error_mha"], "cheap_wrong": r["cheap"]["wrong"], "check1": r["check1_flags"], "check2": r["flag_reference"], "cheap2_error_mha": r["cheap2"]["error_mha"] if r["flag_reference"] else None,
               "cheap2_wrong": r["cheap2"]["wrong"] if r["flag_reference"] else None, "selected_ci_dimension": r["selected_ci_dimension_for_chemical_accuracy"], "exact_lowered_by_selected_ci_mha": r["exact_lowered_by_selected_ci_mha"], "rzz": lj.get("rzz"), "overlap": lj.get("overlap_with_exact"), "shots": {k: first(v) for k, v in P.items()}}
        rows.append(row); print(row["case"], row["qubits"], row["dimension"], "|", f1(row["cheap_error_mha"]), row["cheap_wrong"], "|", row["check1"], row["check2"], "|", f1(row["cheap2_error_mha"]), "|", row["selected_ci_dimension"], "|", row["rzz"], f1(row["overlap"]), "|", row["shots"])
    wrong = [x for x in rows if x["cheap_wrong"]]; right = [x for x in rows if not x["cheap_wrong"]]; c2 = [x for x in rows if x["check2"]]; sm = [x for x in rows if x["shots"]]
    tt = {"cases": len(rows), "cheap_wrong": len(wrong), "wrong_flagged_by_check1": sum(x["check1"] for x in wrong), "wrong_flagged_by_either": sum(x["check1"] or x["check2"] for x in wrong), "wrong_unflagged": [x["case"] for x in wrong if not (x["check1"] or x["check2"])],
          "right_but_flagged": sum(x["check1"] or x["check2"] for x in right), "right": len(right), "check2_flags": len(c2), "check2_repairs": sum(1 for x in c2 if not x["cheap2_wrong"]), "cheap_wrong_error_range_mha": [round(min(abs(x["cheap_error_mha"]) for x in wrong), 1), round(max(abs(x["cheap_error_mha"]) for x in wrong), 1)] if wrong else None,
          "sampled": len(sm), "reach_1.6mHa": {k: sum(1 for x in sm if x["shots"].get(k)) for k in ("random", "exact_state", "lucj_ideal", "lucj_noisy")}, "circuits": sum(1 for x in rows if x["rzz"]), "rzz_range": [min(x["rzz"] for x in rows if x["rzz"]), max(x["rzz"] for x in rows if x["rzz"])] if any(x["rzz"] for x in rows) else None,
          "circuit_overlap_below_0.5": [x["case"] for x in rows if x["overlap"] is not None and x["overlap"] < 0.5]}
    if os.path.exists(f"{TG}/workflow.json"): tt["workflow"] = json.load(open(f"{TG}/workflow.json"))["totals"]
    print("totals:", tt); extra["target_chemistry"] = {"rows": rows, "totals": tt}

if os.path.exists(f"{RES}/iqm/check.json"):
    iq = json.load(open(f"{RES}/iqm/check.json"))["totals"]; print("\nIQM DEVICE MODEL CHECK (Aim 1 circuits requested on IQM, transpiled to IQM's fake backend):", iq); extra["iqm_check"] = iq
json.dump({**extra, "aim1": summary, "noisy": noisy, "warm_vs_cold_p3": cond, "neuromorphic": neuro_sum, "aim1_ibm_snapshots": ibm, "aim2": aim2_sum, "program_repair": repairs}, open(f"{RES}/summary.json", "w"), indent=1)
json.dump(manifest, open(f"{RES}/manifest_sha256.json", "w"), indent=1)

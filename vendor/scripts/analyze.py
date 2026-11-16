#!/usr/bin/env python3
"""Summaries for the report, from the result files only (circuits/index.json, ionq/scores.json, ionq/cost_comparison.json,
models/predictions.json, models/admission.json, models/sim/*.json). Writes analysis.json and prints the tables."""
import glob, json, math, os, sys, collections, statistics as st
B = os.path.abspath(sys.argv[1]); PKG = sys.argv[2]
IDX = json.load(open(f"{B}/circuits/index.json")); C, ROWS = IDX["circuits"], IDX["rows"]
S = json.load(open(f"{B}/ionq/scores.json")); P = json.load(open(f"{B}/models/predictions.json")); A = json.load(open(f"{B}/models/admission.json"))
SUM = json.load(open(f"{PKG}/results/summary.json")); LOSS = SUM["aim2"]["fidelity_fits"]["ion_like"]["loss_per_two_qubit_gate_pct"] / 100
out = {}
by = {(r["id"], r["route"]): r for r in S}

# ---- 1. counts against the application's table
tab = collections.defaultdict(lambda: [0, 0])
for r in ROWS: k = f"{r['aim']}|{r['vendor']}|{r['tier_application']}"; tab[k][0] += 1; tab[k][1] += r["shots"]
out["counts"] = dict(tab)

# ---- 2. IonQ emulator: Aim 2 native traces, the per-RZZ loss as the package fits it
a2 = []
for (i, rt), r in by.items():
    if rt == "native" and r.get("score") == "aim2":
        c = C[i]; bits = len(c["reference_bits_qiskit_order"]); a2.append({"id": i, "rzz": r["rzz"], "trace_fidelity": r["trace_fidelity"], "floor": 2.0 ** -bits, "generic": r.get("package_generic_model_trace_fidelity"),
                                                                                    "rule_generic": (1 - LOSS) ** r["rzz"], "rule_forte": ((1 - LOSS) ** r["rzz"]) ** (P[i]["ionq-forte-1"]["total"] / P[i]["generic"]["total"])})
def fit(pts):
    xs = [x for x, y in pts]; ys = [math.log(y) for x, y in pts]; n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    k = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs); c = my - k * mx
    ss = sum((y - (k * x + c)) ** 2 for x, y in zip(xs, ys)); tot = sum((y - my) ** 2 for y in ys)
    return {"loss_per_rzz": 1 - math.exp(k), "intercept": math.exp(c), "r2": 1 - ss / tot if tot else None, "points": n}
use = [(x["rzz"], x["trace_fidelity"]) for x in a2 if x["trace_fidelity"] * 500 >= 20 and x["trace_fidelity"] >= 2 * x["floor"] and x["rzz"] > 0]
f_emu = fit(use); f_emu["n30"] = math.log(0.3 / f_emu["intercept"]) / math.log(1 - f_emu["loss_per_rzz"])
out["aim2_ionq_emulator"] = {"circuits": len(a2), "fit": f_emu, "rows": sorted(a2, key=lambda x: x["rzz"])}
# the same fit on the device-model simulations
sims = [r for p in glob.glob(f"{B}/models/sim/*.json") for r in json.load(open(p))]
for m in sorted({r["model"] for r in sims}):
    pts = [(r["rzz"], r["trace_fidelity"]) for r in sims if r["model"] == m and r["trace_fidelity"] * r["shots"] >= 20 and r["rzz"] > 0 and r["trace_fidelity"] >= 2 * 2.0 ** -len(C[r["id"]]["reference_bits_qiskit_order"])]
    if len(pts) > 3:
        f = fit(pts); f["n30"] = math.log(0.3 / f["intercept"]) / math.log(1 - f["loss_per_rzz"]); out[f"aim2_sim_{m}"] = f
    # the rule carried over, against the simulation
    dev = "ionq-forte-1" if m.startswith("ionq") else "quantinuum-h2-1-2023"
    cmp_ = []
    for r in sims:
        if r["model"] != m: continue
        i = r["id"]; rule = (1 - LOSS) ** r["rzz"]; ratio = P[i][dev]["total"] / P[i]["generic"]["total"]; pred = rule ** ratio
        if r["trace_fidelity"] > 0 and r["rzz"] > 0 and r["trace_fidelity"] >= 2 * 2.0 ** -len(C[i]["reference_bits_qiskit_order"]):
            cmp_.append({"id": i, "rzz": r["rzz"], "simulated": r["trace_fidelity"], "rule_carried_over": pred, "ratio_neglog": (-math.log(pred)) / (-math.log(r["trace_fidelity"])) if r["trace_fidelity"] < 1 else None})
    rs = [x["ratio_neglog"] for x in cmp_ if x["ratio_neglog"]]
    out[f"aim2_rule_vs_sim_{m}"] = {"circuits": len(cmp_), "median_ratio_pred_over_sim_neglog": st.median(rs) if rs else None, "iqr": [sorted(rs)[len(rs) // 4], sorted(rs)[3 * len(rs) // 4]] if len(rs) > 3 else None, "rows": cmp_}
# emulator against the published-figure model (rule carried over), per circuit, the factor in -ln F
em = [x for x in a2 if 0 < x["trace_fidelity"] < 1 and x["trace_fidelity"] >= 2 * x["floor"] and x["rzz"] > 0]
for x in em: x["factor_model_over_emulator_neglog"] = math.log(x["rule_forte"]) / math.log(x["trace_fidelity"])
fs = [x["factor_model_over_emulator_neglog"] for x in em]
out["aim2_emulator_vs_model"] = {"circuits": len(em), "median_factor": st.median(fs), "range": [min(fs), max(fs)]}

# ---- 3. Aim 1 QAOA on the emulator
rows = []
for (i, rt), r in by.items():
    if r.get("score") == "aim1" and r.get("ideal_p_optimum"):
        rows.append({"id": i, "route": rt, "rzz": r["rzz"], "p": C[i]["p"], "family": C[i]["family"], "n": C[i]["n"], "kind": C[i]["kind"], "emu": r["p_optimum"], "ideal": r["ideal_p_optimum"], "optimum_found": r["optimum_found"]})
def ratio_stats(L):
    rr = [x["emu"] / x["ideal"] for x in L if x["ideal"] >= 0.05]
    return {"circuits_with_ideal_ge_0.05": len(rr), "median_emu_over_ideal": st.median(rr) if rr else None, "min": min(rr) if rr else None, "max": max(rr) if rr else None}
out["aim1_emulator"] = {rt: {"circuits": sum(1 for x in rows if x["route"] == rt), "optimum_found": sum(1 for x in rows if x["route"] == rt and x["optimum_found"]),
                             "by_depth": {p: ratio_stats([x for x in rows if x["route"] == rt and x["p"] == p]) for p in (1, 2, 3)}} for rt in ("qis", "native")}
eff = []
for x in rows:
    if x["route"] == "native" and x["ideal"] >= 0.05 and x["emu"] > 0:
        F = x["emu"] / x["ideal"]; i = x["id"]; rule = (1 - LOSS) ** x["rzz"]; pr = rule ** (P[i]["ionq-forte-1"]["total"] / P[i]["generic"]["total"]); eb = P[i]["ionq-forte-1"]["fidelity"]
        eff.append({"id": i, "rzz": x["rzz"], "effective_fidelity_emulator": F, "rule_carried_over_forte": pr, "e_minus_b_forte": eb, "generic_rule": rule,
                    "factor_rule_neglog": (math.log(pr) / math.log(F)) if 0 < F < 1 else None, "factor_eb_neglog": (math.log(eb) / math.log(F)) if 0 < F < 1 else None})
fr = [e["factor_rule_neglog"] for e in eff if e["factor_rule_neglog"]]; fe = [e["factor_eb_neglog"] for e in eff if e["factor_eb_neglog"]]
out["aim1_emulator_vs_model"] = {"circuits": len(eff), "median_factor_rule": st.median(fr) if fr else None, "median_factor_eb": st.median(fe) if fe else None, "rows": eff}
fam = collections.defaultdict(lambda: [0, 0])
for x in rows:
    if x["route"] == "native": fam[x["family"]][0] += 1; fam[x["family"]][1] += x["optimum_found"]
out["aim1_emulator"]["optimum_found_by_family_native"] = dict(fam)

# ---- 4. IonQ compiled counts (QIS route)
cc = json.load(open(f"{B}/ionq/compiled_counts.json"))
red = collections.defaultdict(list)
for k, v in cc.items():
    if v.get("route", "qis") == "qis" and v.get("input_2q"): red[v["id"].split("-")[1] if not v["id"].startswith("qcup-f") else "f-" + v["id"].split("-")[2]].append(v["native_2q"] / v["input_2q"])
out["ionq_compiler"] = {g: {"jobs": len(L), "median_compiled_over_sent_2q": st.median(L), "min": min(L), "max": max(L), "compiled_to_no_2q_gate": sum(1 for x in L if x == 0)} for g, L in red.items()}
nat_same = sum(1 for k, v in cc.items() if v.get("route") == "native" and v.get("native_2q") == v.get("input_2q") and v.get("native_1q") == v.get("input_1q"))
out["ionq_native_as_written"] = {"jobs": sum(1 for v in cc.values() if v.get("route") == "native"), "compiled_equals_sent": nat_same}

# ---- 5. cost
cost = json.load(open(f"{B}/ionq/cost_comparison.json"))
agg = collections.defaultdict(collections.Counter)
for r in cost:
    a = agg[r["tier"]]; a["rows"] += 1; a["two_qubit_gate_shots"] += r["package_2q_gate_shots"]; a["list_price_usd"] += r["package_list_price_usd"]; a["ionq_credits"] += r["ionq_estimate_credits"]; a["ionq_qpu_seconds"] += r["ionq_estimate_qpu_seconds"]
out["ionq_cost"] = {k: dict(v) for k, v in agg.items()}

# ---- 6. admission re-check
def hqc(r): return 5 + r["shots"] * ((r["count_n1q"] or 0) + 10 * r["count_n2q"] + 5 * r["spam"]) / 5000
N30_EMU = out["aim2_ionq_emulator"]["fit"]["n30"]
for x in A:
    # the figure the application scores: Aim 2 trace fidelity (the application's law carried over, checked against simulation);
    # every other circuit e^-b under the device model (WAI Quantum's figure; IonQ's emulator tracks it for QAOA)
    x["figure_device"] = x["rule_fidelity_device"] if x["aim"] == 2 else x["fidelity_device"]
    x["admitted_figure"] = x["figure_device"] >= 0.30
    x["admitted_emulator"] = (x["count_n2q"] <= N30_EMU) if x["aim"] == 2 else x["fidelity_device"] >= 0.30
json.dump(A, open(f"{B}/models/admission.json", "w"), indent=1)
adm = {}
for v in ("IonQ", "Quantinuum"):
    for t in ("core", "extension"):
        L = [x for x in A if x["vendor"] == v and x["tier_application"] == t]
        for key, flag in (("published", "admitted_device"), ("alternative", "admitted_device_alt"), ("most_favourable", "admitted_device_low"), ("figure", "admitted_figure")) + ((("emulator", "admitted_emulator"),) if v == "IonQ" else ()):
            keep = [x for x in L if x[flag] and not x["ionq_mid_circuit_unsupported"]]
            rec = {"requested": len(L), "admitted": sum(1 for x in L if x[flag]), "admitted_and_runnable": len(keep), "shots": sum(x["shots"] for x in keep)}
            if v == "IonQ": rec["two_qubit_gate_shots"] = sum(x["shots"] * x["count_n2q"] for x in keep); rec["requested_two_qubit_gate_shots"] = sum(x["shots"] * x["count_n2q"] for x in L)
            else: rec["hqc"] = round(sum(hqc(x) for x in keep)); rec["requested_hqc"] = round(sum(hqc(x) for x in L))
            rec["by_group"] = dict(collections.Counter(x["group"] for x in keep)); rec["dropped"] = sorted(x["circuit"] for x in L if not x[flag])
            adm[f"{v}|{t}|{key}"] = rec
        adm[f"{v}|{t}|mid_circuit_unsupported"] = sum(1 for x in L if x["ionq_mid_circuit_unsupported"])
out["admission"] = adm
# where the carried-over rule crosses 30% per vendor (median per-RZZ visible loss among requested circuits)
for v, dev in (("IonQ", "ionq-forte-1"), ("Quantinuum", "quantinuum-h2-1-2023")):
    per = [(-math.log(x["rule_fidelity_device"])) / x["count_n2q"] for x in A if x["vendor"] == v and x["count_n2q"] > 0]
    out[f"rule_crossing_{v}"] = {"median_visible_loss_per_rzz": st.median(per), "n30_at_median": 1.2039728 / st.median(per)}
json.dump(out, open(f"{B}/analysis.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ("aim2_ionq_emulator",) and not k.startswith("aim2_rule_vs_sim")}, indent=1)[:12000])
print("aim2 emulator fit", out["aim2_ionq_emulator"]["fit"])
for k in out:
    if k.startswith("aim2_rule_vs_sim"): print(k, {kk: vv for kk, vv in out[k].items() if kk != "rows"})

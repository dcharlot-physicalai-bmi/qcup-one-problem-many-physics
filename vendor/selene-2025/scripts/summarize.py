"""Every figure the draft text quotes, from results/selene_results.json (this run) and the 2024 run's summary.json, with
the key it comes from.
    python3 -I summarize.py BASE OLD      (writes BASE/results/summary.json and prints it)"""
import json, os, statistics as st, sys
B, OLD = sys.argv[1:3]
o = json.load(open(os.path.join(B, "results", "selene_results.json")))
O24 = json.load(open(os.path.join(OLD, "results", "summary.json")))
C = o["circuits"]
SETS = ("H2-1E_2025-07-16", "H2-2E_2025-07-16", "Helios-1E_2025-11-18")
H2 = SETS[:2]
VARIANTS = ("docs", "docs_dephasing")
S = {"controls": o["controls"], "angle_scaling_check": o["angle_scaling_check"], "hqc": o["hqc"]}
for s in SETS:
    d = {"model_set": o["fits"][s]["core_71_programs"]["model_set"]}
    for scope in ("core_71_programs", "all_115_quantinuum_programs"):
        f = o["fits"][s][scope]
        d[scope] = {"model_rule_median_point_final_request_method": f["model_rule_median_per_gate"], "model_rule_lsq_point": f["model_rule_lsq"]["gates_at_30pct"],
                    "final_request_json_point": f["final_request_json_aim2_programs"],
                    "model_defaults": {v: {"median_point": f["model_defaults"][v]["rule_median_per_gate"], "lsq_point": f["model_defaults"][v]["rule_lsq"]["gates_at_30pct"]} for v in VARIANTS}}
        for v in VARIANTS:
            if v not in f: continue
            L = f[v]["lsq_at_least_20_correct"]
            d[scope][v] = {"loss_pct": L["loss_per_two_qubit_gate_pct"], "point": L["gates_at_30pct"], "point_exact": L["gates_at_30pct_exact"], "r2": L["r2"],
                           "programs_fitted": L["points"], "median_method_point": f[v]["median_per_gate"], "median_error_ratio_selene_over_model": f[v]["median_error_ratio_selene_over_model"],
                           "programs_in_ratio": f[v]["programs_in_error_ratio"], "vs_model_programs_20_plus": f[v]["vs_model_programs_20_plus"]}
    for v in VARIANTS:
        g = {}
        for grp in ("program", "labs", "transition_metal", "actinide"):
            rs = [r for r in C.values() if r["group"] == grp and r.get("tier", "core") == "core" and v in r[s]]
            if not rs: continue
            sc = [r[s][v]["score"] for r in rs]; nf = [r[s][v]["no_fault_fraction"] for r in rs]
            e = {"circuits": len(rs), "shots": sorted({r[s][v]["shots"] for r in rs}), "score_min": min(sc), "score_max": max(sc), "no_fault_min": min(nf), "no_fault_max": max(nf)}
            if grp in ("transition_metal", "actinide"):
                ms = [r[s]["model"]["share"] for r in rs]; rat = [a / b for a, b in zip(sc, ms)]
                md = [r[s]["model_defaults"][v]["share"] for r in rs]
                e.update(model_share_min=min(ms), model_share_max=max(ms), ratio_to_model_min=min(rat), ratio_to_model_max=max(rat), ratio_to_model_median=st.median(rat),
                         model_e_minus_b_min=min(r[s]["model"]["e_minus_b"] for r in rs), model_e_minus_b_max=max(r[s]["model"]["e_minus_b"] for r in rs),
                         model_defaults_share_min=min(md), model_defaults_share_max=max(md),
                         model_admission_set_e_minus_b_min=min(r["model_admission_set"]["e_minus_b"] for r in rs),
                         model_admission_set_e_minus_b_max=max(r["model_admission_set"]["e_minus_b"] for r in rs),
                         model_defaults_e_minus_b_min=min(r[s]["model_defaults"][v]["e_minus_b"] for r in rs), model_defaults_e_minus_b_max=max(r[s]["model_defaults"][v]["e_minus_b"] for r in rs),
                         per_circuit={r["id"]: {"share": r[s][v]["score"], "ci95": r[s][v]["score_ci95"], "error_free": r[s][v]["no_fault_fraction"],
                                                "error_free_ci95": r[s][v]["no_fault_ci95"], "model_share": r[s]["model"]["share"], "model_e_minus_b": r[s]["model"]["e_minus_b"],
                                                "shots": r[s][v]["shots"], "selene_2024": r[s].get("selene_2024")} for r in rs})
            if grp == "labs":
                r = rs[0]; e.update(model_optimum_probability=r[s]["model"]["optimum_probability"], model_e_minus_b=r[s]["model"]["e_minus_b"])
            if grp == "program":
                e["model_rule_min"] = min(r[s]["model"]["trace_fidelity_rule"] for r in rs)
                lo = min(((r[s][v]["score"], r["id"], r["n2q"], r[s]["model"]["trace_fidelity_rule"]) for r in rs))
                e["lowest"] = {"score": lo[0], "id": lo[1], "n2q": lo[2], "model": lo[3]}
            g[grp] = e
        a = o["admission"][f"{s}|{v}"]
        g["admission"] = {"circuits": a["circuits"], "pass": a["pass"], "fail": [x["id"] for x in a["fail"]], "admitted_80_present": a["admitted_80_present"],
                          "admitted_80_pass": a["admitted_80_pass"], "admitted_80_fail": a["admitted_80_fail"], "straddle_30pct": a["interval_straddles_30pct"],
                          "straddle_30pct_admitted": [x for x in a["interval_straddles_30pct"] if C[x]["group"] != "actinide"]}
        # memory events per shot on the programs with more than 100 two-qubit gates, and on the transition-metal circuits
        big = [r[s][v]["per_shot"]["memory_z"] for r in C.values() if r["kind"] == "program" and r["n2q"] > 100 and v in r[s]]
        g["memory_z_per_shot_programs_over_100_gates_mean"] = sum(big) / len(big) if big else None
        g["leak_events_per_shot_max"] = max((r[s][v]["per_shot"].get("leak_1q", 0) + r[s][v]["per_shot"].get("leak_2q", 0) + r[s][v]["per_shot"].get("leak_init", 0)
                                             for r in C.values() if v in r[s]), default=None)
        g["mean_rzz_scale_on_chemistry"] = {r["id"]: r[s][v]["angle_scaling_check"]["mean_scale"] for r in C.values() if r["kind"] == "chem" and v in r[s]}
        d[v] = g
    S[s] = d


def both(sets, v, g, k, f):
    vals = [S[s][v][g][k] for s in sets if g in S[s].get(v, {})]
    return f(vals) if vals else None


def agg(sets, v):
    if not all(v in S[s] and "program" in S[s][v] for s in sets): return None
    progs = [r for r in C.values() if r["kind"] == "program"]
    x = {"sets": list(sets),
         "program_trace_min": both(sets, v, "program", "score_min", min), "program_trace_max": both(sets, v, "program", "score_max", max),
         "labs_no_fault_min": both(sets, v, "labs", "no_fault_min", min), "labs_no_fault_max": both(sets, v, "labs", "no_fault_max", max),
         "tm_no_fault_min": both(sets, v, "transition_metal", "no_fault_min", min), "tm_no_fault_max": both(sets, v, "transition_metal", "no_fault_max", max),
         "tm_share_min": both(sets, v, "transition_metal", "score_min", min), "tm_share_max": both(sets, v, "transition_metal", "score_max", max),
         "tm_model_share_min": both(sets, v, "transition_metal", "model_share_min", min), "tm_model_share_max": both(sets, v, "transition_metal", "model_share_max", max),
         "tm_ratio_min": both(sets, v, "transition_metal", "ratio_to_model_min", min), "tm_ratio_max": both(sets, v, "transition_metal", "ratio_to_model_max", max),
         "act_share_min": both(sets, v, "actinide", "score_min", min), "act_share_max": both(sets, v, "actinide", "score_max", max),
         "act_model_share_min": both(sets, v, "actinide", "model_share_min", min), "act_model_share_max": both(sets, v, "actinide", "model_share_max", max),
         "act_no_fault_min": both(sets, v, "actinide", "no_fault_min", min), "act_no_fault_max": both(sets, v, "actinide", "no_fault_max", max),
         "act_shots": sorted({n for s in sets if "actinide" in S[s][v] for n in S[s][v]["actinide"]["shots"]}),
         "admitted_80_passing": [S[s][v]["admission"]["admitted_80_pass"] for s in sets], "admitted_80_present": [S[s][v]["admission"]["admitted_80_present"] for s in sets],
         "straddles_admitted": {s: S[s][v]["admission"]["straddle_30pct_admitted"] for s in sets},
         "loss_pct_115": [S[s]["all_115_quantinuum_programs"][v]["loss_pct"] for s in sets], "point_115": [S[s]["all_115_quantinuum_programs"][v]["point"] for s in sets],
         "r2_115": [S[s]["all_115_quantinuum_programs"][v]["r2"] for s in sets], "fitted_115": [S[s]["all_115_quantinuum_programs"][v]["programs_fitted"] for s in sets],
         "median_point_115": [S[s]["all_115_quantinuum_programs"][v]["median_method_point"] for s in sets],
         "point_core_71": [S[s]["core_71_programs"][v]["point"] for s in sets],
         "model_median_point_115": [S[s]["all_115_quantinuum_programs"]["model_rule_median_point_final_request_method"] for s in sets],
         "model_lsq_point_115": [S[s]["all_115_quantinuum_programs"]["model_rule_lsq_point"] for s in sets],
         "model_defaults_median_point_115": [S[s]["all_115_quantinuum_programs"]["model_defaults"][v]["median_point"] for s in sets],
         "programs_in_fit": len(progs), "programs_max_two_qubit_gates": max(r["n2q"] for r in progs),
         "core_programs": sum(1 for r in progs if r.get("tier") == "core"), "extension_programs": sum(1 for r in progs if r.get("tier") == "extension")}
    pairs = [v2["error_free"] for s in sets if "actinide" in S[s][v] for v2 in S[s][v]["actinide"]["per_circuit"].values()]
    x["act_pairs"] = len(pairs); x["act_pairs_at_or_above_30"] = sum(f >= 0.30 for f in pairs); x["act_pairs_below_30"] = sum(f < 0.30 for f in pairs)
    if x["tm_ratio_min"] is not None:
        x["tm_ratio_max_distance_from_1_pct"] = 100 * max(1 - x["tm_ratio_min"], x["tm_ratio_max"] - 1)
    return x


for v in VARIANTS:
    S["all_sets|" + v] = agg(SETS, v)
    S["h2_sets|" + v] = agg(H2, v)
# the 2024 Selene run on the same machines (its summary.json, the plugin with every term it could hold)
S["selene_2024"] = {"source": "qcup-selene-params/results/summary.json", "both_sets_published": O24["both_sets_published"],
                    "fits_115": {k: O24[k]["all_115_quantinuum_programs"]["published"] for k in ("H2-1_2024-05-20", "H2-2_2024-12-06")},
                    "fits_core_71": {k: O24[k]["core_71_programs"]["published"] for k in ("H2-1_2024-05-20", "H2-2_2024-12-06")},
                    "admission": {k: O24[k]["published"]["admission"] for k in ("H2-1_2024-05-20", "H2-2_2024-12-06")}}
# the assumed duration of the docs_dephasing variant and what it gives per layer (params/, make_params_2025.py)
S["dephasing_assumption"] = {}
for s in SETS:
    pj = json.load(open(os.path.join(B, "params", s + ".json"))); d = pj["dephasing_assumption"]
    S["dephasing_assumption"][s] = {"ms_per_two_qubit_layer": 1000 * d["seconds_per_two_qubit_layer"], "memory_pz": d["memory_pz"], "p_linear": d["p_linear"],
                                    "p_quadratic_incoherent": d["p_quadratic_incoherent"], "selene_2024_memory_pz": None}
for s, old in (("H2-1E_2025-07-16", "H2-1_2024-05-20"), ("H2-2E_2025-07-16", "H2-2_2024-12-06")):
    S["dephasing_assumption"][s]["selene_2024_memory_pz"] = json.load(open(os.path.join(OLD, "params", old + ".json")))["selene"]["memory_pz"]
# the positive controls (controls/controls.json and the C3 re-run with fresh seeds, controls/controls_recheck.json)
CJ = json.load(open(os.path.join(B, "controls", "controls.json"))); CR = json.load(open(os.path.join(B, "controls", "controls_recheck.json")))
S["positive_controls"] = dict(CJ["summary"], recheck_c3_max_abs_z=max(abs(v[k]) for v in CR.values() for k in ("z", "z_read_0")),
                              recheck_c3_shots=sum(v["shots"] for v in CR.values()),
                              angle_max_abs_z=max(CJ["C7_angle_documented"]["max_abs_z"], CJ["C7_angle_unequal_fit"]["max_abs_z"]),
                              angle_scale_sum_max_abs_difference=max(CJ["C7_angle_documented"]["scale_sum_plugin_max_abs_difference"], CJ["C7_angle_unequal_fit"]["scale_sum_plugin_max_abs_difference"]))
# Q8 by shot noise with this rerun's shares as the truth (scripts/q8_power.py), when it has been run
qp = os.path.join(B, "results", "q8_power.json")
if os.path.exists(qp):
    Q = json.load(open(qp)); S["q8"] = {"controls_equal_final_request": all(c["equal"] for c in Q["controls"].values())}
    for g, G in Q["groups"].items():
        for k, c in G["cases"].items():
            s_, v_, lab = k.split("|")
            S["q8"].setdefault(g, {}).setdefault(lab, {}).setdefault(v_, {})[s_] = {
                "nearer": c["noise_free"]["nearer"], "median_ratio_to_nearer": c["noise_free"]["median_ratio_to_nearer"],
                "p_generic": c["shot_noise"]["verdict_generic"], "p_published_within_1.5": c["shot_noise"]["published_within_1.5"],
                "p_published_within_1.25": c["shot_noise"]["published_within_1.25"], "p_generic_within_1.5": c["shot_noise"]["generic_within_1.5"],
                "p_generic_within_1.25": c["shot_noise"]["generic_within_1.25"], "p_rejected_both_1.5": c["shot_noise"]["rejected_both_at_1.5"],
                "p_rejected_both_1.25": c["shot_noise"]["rejected_both_at_1.25"], "true_share": c["true_share"], "published_share": c["published_share"],
                "generic_share": c["generic_share"]}
    for g in ("transition_metal", "actinide"):
        for lab in ("admission_set", "closest_2025_set"):
            for v_ in ("docs", "docs_dephasing"):
                d = S["q8"].get(g, {}).get(lab, {}).get(v_)
                if not d: continue
                d["all_sets"] = {k: (min if k.startswith("min_") else max)(x[k[4:]] for x in d.values() if isinstance(x, dict) and k[4:] in x)
                                 for k in ("min_p_generic", "max_p_generic", "min_p_published_within_1.25", "max_p_published_within_1.25",
                                           "min_p_published_within_1.5", "max_p_published_within_1.5", "min_p_generic_within_1.25", "max_p_generic_within_1.25", "min_p_generic_within_1.5", "max_p_generic_within_1.5",
                                           "min_median_ratio_to_nearer", "max_median_ratio_to_nearer")}
                d["all_sets"]["nearer"] = sorted({x["nearer"] for k, x in d.items() if k != "all_sets"})
# gates the device's documented minimum angles drop (gen_guppy.py, min_angles), over the 84 core circuits and 44 extension programs
st_ = [r["program_stats"] for r in C.values() if r.get("program_stats")]
S["min_angle_rounding"] = {"rzz_dropped": sum(x.get("rzz_dropped_min_angle", 0) for x in st_), "rxy_dropped": sum(x.get("rxy_dropped_min_angle", 0) for x in st_),
                           "circuits_affected": sum(1 for x in st_ if x.get("rzz_dropped_min_angle", 0) + x.get("rxy_dropped_min_angle", 0) > 0)}
json.dump(S, open(os.path.join(B, "results", "summary.json"), "w"), indent=1)
print(json.dumps({k: S[k] for k in S if k.startswith("all_sets") or k.startswith("h2_sets")}, indent=1))

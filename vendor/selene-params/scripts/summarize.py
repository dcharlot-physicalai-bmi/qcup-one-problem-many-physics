"""Every figure the draft text quotes, from results/selene_results.json, with the key it comes from.
    python3 -I summarize.py BASE      (writes BASE/results/summary.json and prints it)"""
import json, os, statistics as st, sys
B = sys.argv[1]
o = json.load(open(os.path.join(B, "results", "selene_results.json")))
C = o["circuits"]; SETS = ("H2-1_2024-05-20", "H2-2_2024-12-06")
S = {"controls": o["controls"], "hqc": {k: v for k, v in o["hqc"].items() if not k.startswith("if_")}}
for s in SETS:
    d = {}
    for scope in ("core_71_programs", "all_115_quantinuum_programs"):
        f = o["fits"][s][scope]
        d[scope] = {"model_rule_median_point_final_request_method": f["model_rule_median_per_gate"], "model_rule_lsq_point": f["model_rule_lsq"]["gates_at_30pct"],
                    **{v: {"loss_pct": f[v]["lsq_at_least_20_correct"]["loss_per_two_qubit_gate_pct"], "point": f[v]["lsq_at_least_20_correct"]["gates_at_30pct"],
                           "r2": f[v]["lsq_at_least_20_correct"]["r2"], "programs_fitted": f[v]["lsq_at_least_20_correct"]["points"], "median_method_point": f[v]["median_per_gate"],
                           "median_error_ratio_selene_over_model": f[v]["median_error_ratio_selene_over_model"], "programs_in_ratio": f[v]["programs_in_error_ratio"]}
                       for v in ("published", "depolarizing")}}
    for v in ("published", "depolarizing"):
        g = {}
        for grp in ("program", "labs", "transition_metal", "actinide"):
            rs = [r for r in C.values() if r["group"] == grp and r.get("tier", "core") == "core" and v in r[s]]
            if not rs: continue
            sc = [r[s][v]["score"] for r in rs]; nf = [r[s][v]["no_fault_fraction"] for r in rs]
            e = {"circuits": len(rs), "shots": sorted({r[s][v]["shots"] for r in rs}), "score_min": min(sc), "score_max": max(sc), "no_fault_min": min(nf), "no_fault_max": max(nf)}
            if grp in ("transition_metal", "actinide"):
                ms = [r[s]["model"]["share"] for r in rs]; rat = [a / b for a, b in zip(sc, ms)]
                fs = [r[s][v]["fidelity_from_share"] for r in rs]
                e.update(model_share_min=min(ms), model_share_max=max(ms), ratio_to_model_min=min(rat), ratio_to_model_max=max(rat), ratio_to_model_median=st.median(rat),
                         fidelity_from_share_min=min(fs), fidelity_from_share_max=max(fs),
                         model_e_minus_b_min=min(r[s]["model"]["e_minus_b"] for r in rs), model_e_minus_b_max=max(r[s]["model"]["e_minus_b"] for r in rs),
                         per_circuit={r["id"]: {"share": r[s][v]["score"], "ci95": r[s][v]["score_ci95"], "no_fault": r[s][v]["no_fault_fraction"], "model_share": r[s]["model"]["share"],
                                                "model_e_minus_b": r[s]["model"]["e_minus_b"]} for r in rs})
            if grp == "labs":
                r = rs[0]; e.update(model_optimum_probability=r[s]["model"]["optimum_probability"], model_e_minus_b=r[s]["model"]["e_minus_b"])
            if grp == "program":
                e["model_rule_min"] = min(r[s]["model"]["trace_fidelity_rule"] for r in rs)
                e["lowest"] = min(((r[s][v]["score"], r["id"], r["n2q"], r[s]["model"]["trace_fidelity_rule"]) for r in rs))
            g[grp] = e
        d[v] = g
        a = o["admission"][f"{s}|{v}"]
        d[v]["admission"] = {"circuits": a["circuits"], "pass": a["pass"], "fail": [x["id"] for x in a["fail"]], "straddle_30pct": a["interval_straddles_30pct"]}
    S[s] = d
# both parameter sets together, under the plugin (every term), as the draft text quotes them
P = [S[s]["published"] for s in SETS]
def mn(g, k): return min(p[g][k] for p in P)
def mx(g, k): return max(p[g][k] for p in P)
progs = [r for r in C.values() if r["kind"] == "program"]
S["both_sets_published"] = {
    "program_trace_min": mn("program", "score_min"), "program_trace_max": mx("program", "score_max"),
    "labs_and_tm_no_fault_min": min(mn("labs", "no_fault_min"), mn("transition_metal", "no_fault_min")),
    "labs_and_tm_no_fault_max": max(mx("labs", "no_fault_max"), mx("transition_metal", "no_fault_max")),
    "tm_share_min": mn("transition_metal", "score_min"), "tm_share_max": mx("transition_metal", "score_max"),
    "tm_model_share_min": mn("transition_metal", "model_share_min"), "tm_model_share_max": mx("transition_metal", "model_share_max"),
    "tm_ratio_min": mn("transition_metal", "ratio_to_model_min"), "tm_ratio_max": mx("transition_metal", "ratio_to_model_max"),
    "tm_ratio_max_distance_from_1_pct": 100 * max(1 - mn("transition_metal", "ratio_to_model_min"), mx("transition_metal", "ratio_to_model_max") - 1),
    "act_share_min": mn("actinide", "score_min"), "act_share_max": mx("actinide", "score_max"),
    "act_model_share_min": mn("actinide", "model_share_min"), "act_model_share_max": mx("actinide", "model_share_max"),
    "act_no_fault_min": mn("actinide", "no_fault_min"), "act_no_fault_max": mx("actinide", "no_fault_max"),
    "admitted_circuits_passing": [S[s]["published"]["admission"]["pass"] for s in SETS],
    "programs_in_fit": len(progs), "programs_max_two_qubit_gates": max(r["n2q"] for r in progs),
    "core_programs": sum(1 for r in progs if r.get("tier") == "core"), "extension_programs": sum(1 for r in progs if r.get("tier") == "extension"),
    "model_about": [S[s]["all_115_quantinuum_programs"]["model_rule_median_point_final_request_method"] for s in SETS]}
json.dump(S, open(os.path.join(B, "results", "summary.json"), "w"), indent=1)
print(json.dumps(S, indent=1))

"""IBM sample: the generic superconducting-like budget on the heavy-hex patch against WAI Quantum's forecast from each
device's calibration (ibm/wai/fc-<backend>), and the admission rule carried over. Usage: ibm_analyze.py BASE"""
import json, math, sys, statistics as st
B = sys.argv[1]; S = json.load(open(f"{B}/ibm/out/ibm_sample.json"))
LOSS = 0.001595
out = {"rows": []}
fc = {}
for b in ("ibm_kingston", "ibm_fez", "ibm_marrakesh"):
    try: fc[b] = {c["id"]: c for c in json.load(open(f"{B}/ibm/wai/fc-{b}-small"))["result"]["circuits"]}
    except FileNotFoundError: pass
SCRIPT = json.load(open(f"{B}/ibm/ibm_budget_script.json"))
for s in S:
    g = s["patch"]; row = {"id": s["id"], "family": s["family"], "package_cz": s["package_cz"], "patch_cz": g["cz"], "generic_budget": g["budget"], "generic_rule_fidelity": (1 - LOSS) ** g["cz"], "devices": {}}
    for b, F in fc.items():
        c = F.get(s["id"]); d = s["devices"][b]; sc = SCRIPT[b].get(s["id"])
        if c is None and sc is None: row["devices"][b] = {"cz": d["cz"], "forecast": None}; continue
        if c is None: c = {"predicted": math.exp(-sc["total"]), "method": "script (wider than WAI's forecast takes)", "budget": sc["budget"]}
        tot = sum(c["budget"].values()); ratio = tot / g["budget"]
        row["devices"][b] = {"script_total": sc["total"] if sc else None, "cz": d["cz"], "wai_predicted": c["predicted"], "wai_method": c["method"], "wai_budget_total": tot, "wai_budget": c["budget"], "budget_ratio_device_over_generic": ratio,
                             "rule_fidelity_carried_over": row["generic_rule_fidelity"] ** ratio, "e_minus_b_device": math.exp(-tot), "e_minus_b_generic": math.exp(-g["budget"])}
    out["rows"].append(row)
for b in fc:
    rs = [r["devices"][b] for r in out["rows"] if r["devices"].get(b, {}).get("wai_budget_total") is not None]
    ratios = [x["budget_ratio_device_over_generic"] for x in rs]
    per_cz = [-math.log(x["rule_fidelity_carried_over"]) / r["patch_cz"] for r in out["rows"] for x in [r["devices"].get(b, {})] if x.get("rule_fidelity_carried_over") and r["patch_cz"]]
    out[b] = {"circuits": len(rs), "median_budget_ratio": st.median(ratios), "range": [min(ratios), max(ratios)], "median_visible_loss_per_patch_cz": st.median(per_cz), "cz_at_30pct": 1.2039728 / st.median(per_cz),
              "generic_cz_at_30pct": 1.2039728 / -math.log(1 - LOSS), "below_30pct_carried_over": sum(1 for x in rs if x["rule_fidelity_carried_over"] < 0.3)}
    print(b, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out[b].items()})
json.dump(out, open(f"{B}/ibm/ibm_analysis.json", "w"), indent=1)
for r in out["rows"]:
    print("%-36s pkgCZ %s patch %d gen-rule %.3f | %s" % (r["id"], r["package_cz"], r["patch_cz"], r["generic_rule_fidelity"], " ".join("%s cz %d ratio %.2f rule %.3f" % (b[4:], v["cz"], v.get("budget_ratio_device_over_generic") or -1, v.get("rule_fidelity_carried_over") or -1) for b, v in r["devices"].items())))

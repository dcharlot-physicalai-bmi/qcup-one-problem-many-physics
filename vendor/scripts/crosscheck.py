"""Compare models.py's budgets with WAI Quantum's forecast budgets for the same circuits (models/wai/*.json, the sealed
forecasts). Usage: crosscheck.py BASE"""
import json, math, sys, statistics as st
B = sys.argv[1]; P = json.load(open(f"{B}/models/predictions.json"))
out = {}
for tgt, mine in (("h2-1-2023-03-10-published-32q", "quantinuum-h2-1-2023-gpi-one-qubit"), ("forte-1-2026-11-14-any-angle", "ionq-forte-1")):
    try: d = json.load(open(f"{B}/models/wai/fc-{tgt}"))
    except FileNotFoundError: continue
    rows = []
    for c in d["result"]["circuits"]:
        i = next(k for k in P if k.lower() == c["id"]); w = c["budget"]; m = P[i][mine]
        wtot = sum(v for k, v in w.items()); mtot = m["total"]
        rows.append({"id": i, "wai_budget": w, "wai_total": wtot, "wai_predicted": c["predicted"], "wai_method": c["method"], "mine_terms": m["terms"], "mine_total": mtot, "ratio_mine_over_wai": mtot / wtot if wtot else None,
                     "wai_memory": w.get("memory", 0.0), "mine_memory": m["terms"].get("memory", 0.0)})
    r = [x["ratio_mine_over_wai"] for x in rows if x["ratio_mine_over_wai"]]
    out[tgt] = {"circuits": len(rows), "median_ratio_total": st.median(r), "min": min(r), "max": max(r), "rows": rows}
    print(tgt, len(rows), "median mine/WAI total budget %.3f (%.3f to %.3f)" % (st.median(r), min(r), max(r)))
    for x in rows: print("   %-40s WAI %.4f (mem %.4f) mine %.4f (mem %.4f) WAI F %.4g %s" % (x["id"], x["wai_total"], x["wai_memory"], x["mine_total"], x["mine_memory"], x["wai_predicted"], x["wai_method"][:14]))
json.dump(out, open(f"{B}/models/crosscheck_wai.json", "w"), indent=1)

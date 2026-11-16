#!/usr/bin/env python3
"""Score the device runs and test them against the pre-registered predictions. Offline, pure Python.
Reads predictions.json, design/design.json (ground sets), run/job-*.json and run/raw/results-*.json.
Writes run/counts-<arm>.json and analysis.json, and prints a summary.
Usage: python3 -I analyze.py BASE"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitlib
BASE = os.path.abspath(sys.argv[1])
pred = json.load(open(f"{BASE}/predictions.json")); design = json.load(open(f"{BASE}/design/design.json"))
GROUND = {c["id"]: set(c["ground_states"]) for c in design["circuits"] if c["kind"] == "aim1"}
C = pred["circuits"]; ORDER = [c["id"] for c in C]
MODELS = ["generic_aer", "generic_law_intercept", "generic_law_no_intercept", "cal_idle_aer", "cal_noidle_aer", "script_e_minus_b", "script_e_minus_b_no_leading", "script_law_carried", "script_law_carried_no_leading"]


def decode(pub, creg):
    """Sampler V2 result for one PUB -> counts {bitstring: n}, bit 0 rightmost (qiskit order)."""
    d = pub["data"][creg]
    if isinstance(d, dict) and "samples" in d:
        nb = d["num_bits"]; cnt = {}
        for h in d["samples"]:
            k = format(int(h, 16), f"0{nb}b"); cnt[k] = cnt.get(k, 0) + 1
        return cnt
    raise SystemExit(f"unrecognised result format for register {creg}: {str(d)[:200]}")


def score(meta, counts):
    tot = sum(counts.values())
    if meta["kind"] == "aim1":
        g = GROUND[meta["id"]]; return sum(v for k, v in counts.items() if int(k, 2) in g) / tot, sum(v for k, v in counts.items() if int(k, 2) in g), tot
    hit = counts.get(meta["want"], 0); return hit / tot, hit, tot


def pv(v): return v["score"] if isinstance(v, dict) and v else v


ana = {"arms": {}}
for arm in ("dd_off", "dd_on"):
    jp, rp = f"{BASE}/run/job-{arm}.json", f"{BASE}/run/raw/results-{arm}.json"
    if not (os.path.exists(jp) and os.path.exists(rp)): continue
    job = json.load(open(jp)); B = job["backend"]; res = json.load(open(rp))["results"]
    assert len(res) == len(C)
    counts = {meta["id"]: decode(pub, meta["creg"]) for meta, pub in zip(C, res)}
    json.dump({"backend": B, "job": job["job"], "arm": arm, "counts": counts}, open(f"{BASE}/run/counts-{arm}.json", "w"))
    rows = []
    for meta in C:
        s, hit, tot = score(meta, counts[meta["id"]]); bk = meta["backends"][B]
        r = {"id": meta["id"], "kind": meta["kind"], "cz": bk["executed_cz"], "measured": s, "hits": hit, "shots": tot, "se": math.sqrt(max(s * (1 - s), 1 / tot) / tot),
             "floor": meta["uniform_floor"], "predicted": {m: pv(bk["predictions"][m]) for m in MODELS}}
        if meta["kind"] == "aim1": r["ideal"] = meta["ideal_p_gs"]
        r["neglog_ratio"] = {m: (-math.log(s) / -math.log(p) if s > 0 and p and 0 < p < 1 else None) for m, p in r["predicted"].items()}
        rows.append(r)
    prog = [(r, meta) for r, meta in zip(rows, C) if meta["kind"] in ("aim2", "control_zero_cz")]
    pts = [(r["cz"], r["measured"], r["floor"]) for r, _ in prog]; pc = [(r["cz"], r["hits"], r["shots"], r["floor"]) for r, _ in prog]
    fits = {rule: fitlib.fit(pts, rule) for rule in ("package", "no_intercept", "floor_corrected")}
    boot = {rule: fitlib.bootstrap_30(pc, rule) for rule in ("package", "no_intercept", "floor_corrected")}
    imp = pred["implied_by_predictions"][B]
    consistent = {}
    for m in MODELS:
        consistent[m] = {}
        for rule in ("package", "no_intercept", "floor_corrected"):
            v = (imp.get(m, {}).get(rule) or {}).get("cz_at_30pct"); b = boot[rule]
            consistent[m][rule] = {"model_30pct": v, "inside_device_95pct": (v is not None and b["p2.5"] <= v <= b["p97.5"])}
    med = {}
    for m in MODELS:
        xs = sorted(x["neglog_ratio"][m] for x, _ in prog if x["neglog_ratio"][m] is not None and x["cz"] > 0 and x["measured"] >= 0.01)
        med[m] = xs[len(xs) // 2] if xs else None
    order40 = sorted(json.load(open(f"{BASE}/design/package_form_order.json")))
    q5 = fitlib.held_out([(meta["form"], r["cz"], r["measured"]) for r, meta in prog], order40)
    ana["arms"][arm] = {"backend": B, "job": job["job"], "rows": rows, "fits": fits, "bootstrap_30pct": boot, "model_consistency": consistent,
                        "median_measured_over_predicted_neglogF_programs": med, "q5_held_out": q5}
    print(f"\n== {arm} on {B} (job {job['job']})")
    for r in rows:
        print("%-36s cz %4d measured %.3f±%.3f | %s" % (r["id"], r["cz"], r["measured"], r["se"], " ".join(f"{m.split('_')[0][:3]}{'I' if m == 'cal_idle_aer' else ''}{'N' if m == 'cal_noidle_aer' else ''}:{(r['predicted'][m] or 0):.3f}" for m in ("generic_aer", "cal_idle_aer", "cal_noidle_aer", "script_e_minus_b"))))
    for rule in fits: print(rule, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in (fits[rule] or {}).items()}, "bootstrap", {k: (round(v) if isinstance(v, float) and math.isfinite(v) else v) for k, v in boot[rule].items()})
    print("Q5 held out", q5); print("median measured/predicted -lnF", {m: (round(v, 2) if v else None) for m, v in med.items()})
if "dd_off" in ana["arms"] and "dd_on" in ana["arms"]:
    a, b = ana["arms"]["dd_off"]["rows"], ana["arms"]["dd_on"]["rows"]
    ana["dd_on_minus_dd_off"] = [{"id": x["id"], "cz": x["cz"], "dd_off": x["measured"], "dd_on": y["measured"], "diff": y["measured"] - x["measured"], "se": math.hypot(x["se"], y["se"])} for x, y in zip(a, b)]
json.dump(ana, open(f"{BASE}/analysis.json", "w"), indent=1)

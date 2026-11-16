#!/usr/bin/env python3
"""Independent refit of the device data (stdlib only; does not import the package's fitlib).

Input: rescore_device.json from rescore.py, predictions.json, design/package_form_order.json.
Fit set (preregistered): the 16 Aim 2 programs and the 0-CZ program.
Rules:  package  = OLS of ln F on CZ with free intercept, points F >= 0.01
        no_int   = OLS through the origin (F(0) = 1), same points
        floor    = F' = (F - f)/(1 - f), f = 2^-(trace bits), points F' >= 0.01, free intercept
Bootstrap: resample programs with replacement and each program's hits from Binomial(shots, hits/shots), 4,000 draws,
own RNG and seed (so percentiles differ from fitlib's by Monte Carlo noise only).
Q5: fit (package rule) on programs at even positions of the package's sorted 40-form order, predict the odd ones, and the
reverse; error factor = exp(|ln F_pred - ln F|); median over all held-out predictions.
Usage: fits.py RESCORE_JSON HW_BASE OUT_JSON"""
import json, math, random, sys
RS, HW, OUT = sys.argv[1:4]
rs = json.load(open(RS)); pred = json.load(open(f"{HW}/predictions.json"))
P = {c["id"]: c for c in pred["circuits"]}
ORDER = sorted(json.load(open(f"{HW}/design/package_form_order.json")))
MODELS = ["generic_aer", "generic_law_intercept", "generic_law_no_intercept", "cal_idle_aer", "cal_noidle_aer", "script_e_minus_b",
          "script_e_minus_b_no_leading", "script_law_carried", "script_law_carried_no_leading"]
LN3 = math.log(0.3)


def ols(xs, ys, intercept=True):
    n = len(xs)
    if intercept:
        mx, my = sum(xs) / n, sum(ys) / n; sxx = sum((x - mx) ** 2 for x in xs)
        if sxx == 0: return None
        k = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx; c = my - k * mx
    else:
        sxx = sum(x * x for x in xs)
        if sxx == 0: return None
        k = sum(x * y for x, y in zip(xs, ys)) / sxx; c = 0.0
    my = sum(ys) / n; sst = sum((y - my) ** 2 for y in ys); sse = sum((y - c - k * x) ** 2 for x, y in zip(xs, ys))
    return k, c, (1 - sse / sst) if sst > 0 else None


def fit(pts, rule):
    """pts: (cz, F, floor)."""
    if rule == "floor":
        q = [(cz, (F - f) / (1 - f)) for cz, F, f in pts]
    else:
        q = [(cz, F) for cz, F, f in pts]
    q = [(cz, F) for cz, F in q if F >= 0.01]
    if len(q) < 3: return None
    r = ols([a for a, _ in q], [math.log(b) for _, b in q], intercept=(rule != "no_int"))
    if r is None: return None
    k, c, r2 = r
    return {"n": len(q), "slope": k, "loss_pct_per_cz": 100 * (1 - math.exp(k)), "F0": math.exp(c), "r2": r2, "cz30": (LN3 - c) / k if k < 0 else None}


def binom(rng, n, p):
    if p <= 0: return 0
    if p >= 1: return n
    if p > 0.5: return n - binom(rng, n, 1 - p)
    # geometric skips: O(n p)
    k, i, lq = 0, 0, math.log(1 - p)
    while True:
        i += int(math.log(1 - rng.random()) / lq) + 1
        if i > n: return k
        k += 1


def boot(rows, rule, reps=4000, seed=7741):
    rng = random.Random(seed); v30, slopes = [], []
    for _ in range(reps):
        d = [rows[rng.randrange(len(rows))] for _ in rows]
        pts = [(r["cz"], binom(rng, r["shots"], r["hits"] / r["shots"]) / r["shots"], r["floor"]) for r in d]
        f = fit(pts, rule)
        slopes.append(f["slope"] if f else float("nan"))
        v30.append(f["cz30"] if f and f["cz30"] is not None else float("inf"))
    v30.sort(); q = lambda a: v30[min(len(v30) - 1, int(a * len(v30)))]
    s = [x for x in slopes if x == x]
    return {"reps": reps, "p2.5": q(0.025), "p16": q(0.16), "median": q(0.5), "p84": q(0.84), "p97.5": q(0.975),
            "share_slope_nonnegative": sum(1 for x in s if x >= 0) / len(s), "share_no_fit": (len(slopes) - len(s)) / len(slopes)}


def q5(rows, keep):
    errs = []
    for fold in (0, 1):
        tr = [r for r in rows if ORDER.index(r["form"]) % 2 == fold and keep(r)]
        te = [r for r in rows if ORDER.index(r["form"]) % 2 != fold and keep(r)]
        if len(tr) < 2 or not te: continue
        k, c, _ = ols([r["cz"] for r in tr], [math.log(r["measured"]) for r in tr])
        errs += [abs(c + k * r["cz"] - math.log(r["measured"])) for r in te]
    if not errs: return None
    e = sorted(errs); m = len(e)
    med = e[m // 2] if m % 2 else 0.5 * (e[m // 2 - 1] + e[m // 2])
    return {"median_error_factor": math.exp(med), "n_predictions": m, "train_test": None}


out = {}
for arm in ("dd_off", "dd_on"):
    rows = []
    for r in rs[arm]:
        if r["kind"] in ("aim2", "control_zero_cz"):
            r = dict(r); r["form"] = P[r["id"]]["form"]; rows.append(r)
    pts = [(r["cz"], r["measured"], r["floor"]) for r in rows]
    A = {"fits": {}, "boot": {}}
    for rule in ("package", "no_int", "floor"):
        A["fits"][rule] = fit(pts, rule); A["boot"][rule] = boot(rows, rule)
    # Q5 as preregistered (F >= 0.01) and as the application now words it (exclude programs below twice the guessing floor)
    A["q5_prereg"] = q5(rows, lambda r: r["measured"] >= 0.01)
    A["q5_twice_floor"] = q5(rows, lambda r: r["measured"] >= 2 * r["floor"])
    # model comparisons on the fit set
    mc = {}
    for m in MODELS:
        pr = {r["id"]: (P[r["id"]]["backends"]["ibm_marrakesh"]["predictions"][m]) for r in rows}
        pr = {k: (v["score"] if isinstance(v, dict) else v) for k, v in pr.items()}
        use = [r for r in rows if r["measured"] >= 0.01 and r["cz"] > 0 and pr[r["id"]] and 0 < pr[r["id"]] < 1]
        ratios = sorted(math.log(r["measured"]) / math.log(pr[r["id"]]) for r in use)
        lr = [math.log(r["measured"] / pr[r["id"]]) for r in use]
        a = sum((-math.log(pr[r["id"]])) * (-math.log(r["measured"])) for r in use) / sum(math.log(pr[r["id"]]) ** 2 for r in use)
        res_a = [(-math.log(r["measured"])) - a * (-math.log(pr[r["id"]])) for r in use]
        imp = pred["implied_by_predictions"]["ibm_marrakesh"].get(m, {})
        cons = {}
        for rule, key in (("package", "package"), ("no_int", "no_intercept"), ("floor", "floor_corrected")):
            v = (imp.get(key) or {}).get("cz_at_30pct"); b = A["boot"][rule]
            cons[rule] = {"model_30": v, "inside_95": v is not None and b["p2.5"] <= v <= b["p97.5"], "inside_68": v is not None and b["p16"] <= v <= b["p84"]}
        mc[m] = {"n": len(use), "median_neglog_ratio": ratios[len(ratios) // 2], "rms_log_error_unscaled": math.sqrt(sum(x * x for x in lr) / len(lr)),
                 "median_abs_log_error_factor": math.exp(sorted(abs(x) for x in lr)[len(lr) // 2]), "alpha": a,
                 "rms_after_alpha": math.sqrt(sum(x * x for x in res_a) / len(res_a)), "consistency": cons, "q5_implied": imp.get("held_out_q5", {}).get("median_error_factor")}
    A["models"] = mc
    # Aim 1
    aim1 = []
    for r in rs[arm]:
        if r["kind"] == "aim1":
            pp = P[r["id"]]["backends"]["ibm_marrakesh"]["predictions"]
            aim1.append({"id": r["id"], "cz": r["cz"], "measured": r["measured"], "ideal": r["ideal"], "retained": r["measured"] / r["ideal"],
                         "pred": {m: (pp[m]["score"] if isinstance(pp[m], dict) else pp[m]) for m in MODELS if m in pp}})
    A["aim1"] = aim1
    out[arm] = A
# DD effect
dd = []
for a, b in zip(rs["dd_off"], rs["dd_on"]):
    se = math.sqrt(a["measured"] * (1 - a["measured"]) / a["shots"] + b["measured"] * (1 - b["measured"]) / b["shots"])
    dd.append({"id": a["id"], "cz": a["cz"], "off": a["measured"], "on": b["measured"], "diff": b["measured"] - a["measured"], "z": (b["measured"] - a["measured"]) / se if se > 0 else None})
out["dd"] = dd
json.dump(out, open(OUT, "w"), indent=1)

f2 = lambda v: "-" if v is None else (f"{v:.0f}" if abs(v) >= 10 else f"{v:.3f}")
for arm in ("dd_off", "dd_on"):
    A = out[arm]; print(f"\n==== {arm}")
    for rule in ("package", "no_int", "floor"):
        f, b = A["fits"][rule], A["boot"][rule]
        print(f"{rule:8s} n={f['n']:2d} loss/CZ {f['loss_pct_per_cz']:.3f}%  F0 {f['F0']:.3f}  R2 {f['r2']:.3f}  30% at {f2(f['cz30'])}  | boot 95% [{f2(b['p2.5'])}, {f2(b['p97.5'])}] 68% [{f2(b['p16'])}, {f2(b['p84'])}] median {f2(b['median'])}  slope>=0 share {b['share_slope_nonnegative']:.4f}")
    print("Q5 prereg (F>=0.01):", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in A["q5_prereg"].items()})
    print("Q5 application wording (F >= 2 x floor):", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in A["q5_twice_floor"].items()})
    print("model | n | median -lnF ratio | median |log err| factor | RMS log err | alpha | RMS after alpha | 30% pt pkg/noint/floor inside95")
    for m, v in A["models"].items():
        c = v["consistency"]
        print(f"{m:30s} {v['n']:2d} {v['median_neglog_ratio']:.2f} {v['median_abs_log_error_factor']:.2f} {v['rms_log_error_unscaled']:.2f} {v['alpha']:.2f} {v['rms_after_alpha']:.2f}  " +
              " ".join(f"{f2(c[r]['model_30'])}{'*' if c[r]['inside_95'] else ''}" for r in ("package", "no_int", "floor")) + f"  q5_implied {v['q5_implied']:.2f}")
    for x in A["aim1"]:
        print(f"  {x['id']:16s} cz {x['cz']:3d} meas {x['measured']:.4f} ideal {x['ideal']:.3f} kept {x['retained']:.3f} | " + " ".join(f"{m[:10]}:{x['pred'][m]:.3f}" for m in ("generic_aer", "cal_idle_aer", "cal_noidle_aer", "script_e_minus_b")))
print("\nDD on - off:")
for x in out["dd"]: print(f"  {x['id']:36s} cz {x['cz']:4d} off {x['off']:.3f} on {x['on']:.3f} diff {x['diff']:+.3f} z {x['z']:+.1f}" if x["z"] is not None else x)

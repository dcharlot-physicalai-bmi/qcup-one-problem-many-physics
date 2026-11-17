"""Figures the application quotes after the review round of 17 November 2026 that no earlier script stored, each recomputed
from the package's own result files (writes vendor/results/review_figures.json). Read-only on every input.

1. Wrong acceptances in the worked mission example (results/targets/workflow.json totals): 2 of 10, with the exact
   (Clopper-Pearson) 95% interval, computed here by bisection on the binomial distribution.
2. The checks' false alarms (results/summary.json): the chemistry trust check's routing of the cases CCSD gets right
   (README finding 14) and check 1's flags on the target cases CCSD gets right (finding 16).
3. Q9: the IBM and IQM Hubbard circuits (results/hubbard/request.json, those under the 117-CZ cap) start from the product
   state; their noiseless energy error per site against the exact ground state (results/hubbard/hva_product.json).
4. Q7: the exact total-variation distance of the ideal sampling circuits IonQ admits (vendor/results/ionq/scores.json
   `ideal_tvd_floor`, native route).
5. Q1: family C's certified bound as a share of the feasible spread at 24 to 60 variables (results/summary.json
   `feasible_gap`, set "scale"); branch and bound's proofs on the scale-up set (`scale`).
6. The IonQ emulator's 30% point by fit (vendor/results/verify/refit_ionq.json `native`): the fits that handle programs at
   the guessing floor (every variant not named for the package's plain rule) and the plain rule.
7. Pulse-code design (results/summary.json `labs.fits`): the growth of ideal depth-3 QAOA's inverse success against the
   native annealer's time to solution.
Usage, from the package root: python3 -I vendor/scripts/review_figures.py ."""
import json, math, os, sys
B = sys.argv[1] if len(sys.argv) > 1 else "."
def load(*p): return json.load(open(os.path.join(B, *p)))
out = {"note": "Every figure below is computed by vendor/scripts/review_figures.py from the files named in its docstring."}

# 1. Clopper-Pearson
def binom_cdf(k, n, p): return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
def bisect(f, lo=0.0, hi=1.0):
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid): hi = mid
        else: lo = mid
    return (lo + hi) / 2
def clopper_pearson(k, n, a=0.05):
    lo = 0.0 if k == 0 else bisect(lambda p: 1 - binom_cdf(k - 1, n, p) >= a / 2)      # P(X >= k) = a/2
    hi = 1.0 if k == n else bisect(lambda p: binom_cdf(k, n, p) <= a / 2)             # P(X <= k) = a/2
    return lo, hi
W = load("results", "targets", "workflow.json")["totals"]
wrong = len(W["accepted_wrong"]); acc = W["accepted"]
assert acc - W["accepted_right"] == wrong
lo, hi = clopper_pearson(wrong, acc)
out["worked_example_wrong_acceptances"] = {"accepted": acc, "right": W["accepted_right"], "wrong": wrong, "cases": W["cases"], "escalated": W["escalated"],
                                           "clopper_pearson_95": [round(lo, 4), round(hi, 4)]}
# positive control: the textbook interval for 0 of 10 is [0, 0.3085]
assert abs(clopper_pearson(0, 10)[1] - 0.30850) < 1e-4

# 2. false alarms
S = load("results", "summary.json")
ch = S["chemistry"]["rows"]
out["trust_check_finding_14"] = {"cases": len(ch), "ccsd_wrong": sum(r["ccsd_wrong"] for r in ch), "wrong_routed": sum(r["ccsd_wrong"] and r["routed_to_quantum"] for r in ch),
                                 "ccsd_right": sum(not r["ccsd_wrong"] for r in ch), "right_routed": sum((not r["ccsd_wrong"]) and r["routed_to_quantum"] for r in ch)}
tg = S["target_chemistry"]["rows"]
out["check_1_finding_16"] = {"cases": len(tg), "cheap_wrong": sum(r["cheap_wrong"] for r in tg), "wrong_flagged": sum(r["cheap_wrong"] and r["check1"] for r in tg),
                             "cheap_right": sum(not r["cheap_wrong"] for r in tg), "right_flagged": sum((not r["cheap_wrong"]) and r["check1"] for r in tg)}

# 3. Q9
HUBREQ = load("results", "hubbard", "request.json"); PROD = load("results", "hubbard", "hva_product.json")
rows = []
for v in ("IBM", "IQM"):
    for r in HUBREQ[v]:
        if r["cz"] > 117: continue
        m = next(x for x in PROD if x["lattice"] == r["lattice"] and x["U"] == r["U"] and x["start"] == r["start"])
        rows.append({"vendor": v, "lattice": r["lattice"], "p": r["p"], "U": r["U"], "start": r["start"], "cz": r["cz"],
                     "error_per_site": next(d["error_per_site"] for d in m["depths"] if d["p"] == r["p"])})
out["q9_product_state_error_per_site"] = {"circuits": rows, "starts": sorted({r["start"] for r in rows}),
                                          "range": [min(r["error_per_site"] for r in rows), max(r["error_per_site"] for r in rows)]}

# 4. Q7
SC = load("vendor", "results", "ionq", "scores.json")
q7 = [r for r in SC if r["score"] == "sampling" and r["route"] == "native"]
out["q7_ideal_exact_tvd"] = {"circuits": len(q7), "ids": [r["id"] for r in q7], "range": [min(r["ideal_tvd_floor"] for r in q7), max(r["ideal_tvd_floor"] for r in q7)]}

# 5. family C's certified gap at 24 to 60 variables; proofs on the scale-up set
fg = next(r for r in S["feasible_gap"] if r["set"] == "scale" and r["family"] == "C")
out["family_C_scale_gap_pct_of_feasible_spread"] = {"instances": fg["instances"], "range": [fg["min"], fg["max"]], "within_1pct": fg["within_1pct"],
    "proved_optimal_by_size": {str(r["n"]): r["proved_optimal"] for r in S["scale"] if r["family"] == "C"}}

# 5b. which scale-up instances the router sends out: not proved by branch and bound, and the edge answer (tempering's
# best, results/scale/scale_*.json pt_best_energy) more than 1% of the feasible spread above the certified bound. The
# spread is results/feasible_gap.json's (feasible mean minus the reference energy; where the mean is not stored, from
# the stored gap: (reference - bound) / gap). The stored gap is reproduced from the same fields as a positive control.
import glob
FG = {(r["family"], r["n"], r["seed"]): r for r in load("results", "feasible_gap.json") if r["set"] == "scale"}
sent = []; rows5 = []
for pth in sorted(glob.glob(os.path.join(B, "results", "scale", "scale_*.json"))):
    d = json.load(open(pth)); k = (d["family"], d["n"], d["seed"]); g = FG[k]
    if "feasible_mean_energy" in g:
        spread = g["feasible_mean_energy"] - g["reference_energy"]
        assert abs(100 * (g["reference_energy"] - g["sdp_bound"]) / spread - g["gap_pct_of_feasible_spread"]) < 1e-6
    elif g["gap_pct_of_feasible_spread"] > 0:
        spread = (g["reference_energy"] - g["sdp_bound"]) / (g["gap_pct_of_feasible_spread"] / 100)
    else:
        spread = None
    edge = None if spread is None else 100 * (d["pt_best_energy"] - d["sdp_bound"]) / spread
    out_ = (not d["bnb_proved_optimal"]) and (edge is None or edge > 1)
    rows5.append({"family": k[0], "n": k[1], "seed": k[2], "proved": d["bnb_proved_optimal"], "edge_gap_pct": None if edge is None else round(edge, 4), "sent_out": out_})
    if out_: sent.append(k)
out["router_sends_out_scale_up"] = {"sent": [list(k) for k in sent], "smallest_size_sent": min(k[1] for k in sent), "families_sent": sorted({k[0] for k in sent}),
                                    "unproved": [[r["family"], r["n"], r["seed"], r["edge_gap_pct"]] for r in rows5 if not r["proved"]]}

# 6. IonQ emulator 30% point by fit
RF = load("vendor", "results", "verify", "refit_ionq.json")["native"]
floor_fits = {k: v["n30"] for k, v in RF.items() if isinstance(v, dict) and not k.startswith("package")}
plain = RF["package aggregate.py rule (>=20 correct traces, i.e. y>=0.04 at 500 shots; rzz 0 included)"]["n30"]
out["ionq_emulator_30pct_point_by_fit"] = {"fits_handling_the_floor": floor_fits, "range_handling_the_floor": [min(floor_fits.values()), max(floor_fits.values())],
                                           "plain_rule": plain, "builder": RF["builder (>=20 correct, >=2x floor, rzz>0)"]["n30"]}

# 7. pulse-code growth
LF = S["labs"]["fits"]
out["pulse_code_growth"] = {"qaoa_depth3_inverse_success_base": LF["qaoa_p3_inverse_p_gs"]["base"], "native_annealer_tts_base": LF["native_sa_tts"]["base"],
                            "qaoa_grows_faster": LF["qaoa_p3_inverse_p_gs"]["base"] > LF["native_sa_tts"]["base"]}

json.dump(out, open(os.path.join(B, "vendor", "results", "review_figures.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "q9_product_state_error_per_site"}, indent=1))

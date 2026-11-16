"""Fit the trace-fidelity law to the Selene runs with H2-matched depolarizing noise (results/models/selene/selene_noisy.json),
by the package's own method (aggregate.py): log-linear least squares of trace fidelity against two-qubit gate count.
Points kept: programs at 5 steps up to 2,000 two-qubit gates with at least 20 correct traces in 200 shots
(fidelity >= 0.1); the fit on every non-zero point up to 2,000 gates is written beside it.
Usage, from the package root: python3 vendor/scripts/selene_fit.py .   (writes vendor/results/models/selene/selene_fit.json)"""
import json, math, os, sys
B = sys.argv[1] if len(sys.argv) > 1 else "."
P = os.path.join(B, "vendor", "results", "models", "selene")
rows = json.load(open(os.path.join(P, "selene_noisy.json")))
def fit(pts):
    x = [float(p[0]) for p in pts]; y = [math.log(p[1]) for p in pts]; n = len(x); mx = sum(x) / n; my = sum(y) / n
    k = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sum((a - mx) ** 2 for a in x); c = my - k * mx      # least squares, as np.polyfit(x, y, 1)
    r2 = 1 - sum((b - (k * a + c)) ** 2 for a, b in zip(x, y)) / sum((b - my) ** 2 for b in y)
    return {"circuits": len(pts), "loss_per_two_qubit_gate_pct": round(100 * (1 - math.exp(k)), 4), "r2": round(r2, 4),
            "gates_at_30pct": round((math.log(0.3) - c) / k), "fidelity_at_zero_gates": round(math.exp(c), 4)}
under = [r for r in rows if r["ion_like_rzz"] <= 2000]
kept = [(r["ion_like_rzz"], r["trace_fidelity_selene_depolarizing"]) for r in under if r["trace_fidelity_selene_depolarizing"] * r["shots"] >= 20]
nonzero = [(r["ion_like_rzz"], r["trace_fidelity_selene_depolarizing"]) for r in under if r["trace_fidelity_selene_depolarizing"] > 0]
door = next(r for r in rows if r["program"] == "door_R_T5")
out = {"programs_in_file": len(rows), "programs_up_to_2000_gates": len(under), "fit_at_least_20_correct": fit(kept), "fit_all_nonzero": fit(nonzero),
       "door_R_T5": {"rzz": door["ion_like_rzz"], "selene": door["trace_fidelity_selene_depolarizing"], "generic": door["package_generic_trace_fidelity"]}}
json.dump(out, open(os.path.join(P, "selene_fit.json"), "w"), indent=1); print(json.dumps(out, indent=1))

"""Independent refit of the IonQ emulator Aim 2 trace-fidelity law from ionq/scores.json (native and QIS routes),
under the builder's filter, the package's aggregate.py filter and variants. Light: reads JSON only."""
import json, math, sys
import numpy as np
B = sys.argv[1]
S = json.load(open(f"{B}/ionq/scores.json")); C = json.load(open(f"{B}/circuits/index.json"))["circuits"]
pts = {}
for r in S:
    if r.get("score") != "aim2": continue
    c = C[r["id"]]; nb = len(c["reference_bits_qiskit_order"])
    pts.setdefault(r["route"], []).append(dict(id=r["id"], x=r["rzz"], y=r["trace_fidelity"], floor=2.0 ** -nb, shots=r["shots"], gen=r.get("package_generic_model_trace_fidelity")))

def fit(P):
    x = np.array([p["x"] for p in P], float); y = np.log(np.array([p["y"] for p in P], float))
    k, c = np.polyfit(x, y, 1); r2 = 1 - ((y - (k * x + c)) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return dict(n=len(P), loss_pct=round(100 * (1 - math.exp(k)), 4), r2=round(float(r2), 4), F0=round(math.exp(c), 4), n30=round((math.log(0.3) - c) / k, 1), xmax=max(p["x"] for p in P))

out = {}
for route in ("native", "qis"):
    P = pts[route]
    variants = {
        "builder (>=20 correct, >=2x floor, rzz>0)": [p for p in P if p["y"] * p["shots"] >= 20 and p["y"] >= 2 * p["floor"] and p["x"] > 0],
        "package aggregate.py rule (>=20 correct traces, i.e. y>=0.04 at 500 shots; rzz 0 included)": [p for p in P if p["y"] * p["shots"] >= 20],
        "package rule, rzz>0": [p for p in P if p["y"] * p["shots"] >= 20 and p["x"] > 0],
        "package literal threshold y>=0.01": [p for p in P if p["y"] >= 0.01],
        ">=2x floor incl rzz 0": [p for p in P if p["y"] >= 2 * p["floor"] and p["y"] * p["shots"] >= 20],
        "rzz<=147 only": [p for p in P if 0 < p["x"] <= 147],
        "rzz<=300 (IonQ core cap) all": [p for p in P if 0 < p["x"] <= 300 and p["y"] > 0],
        "floor-corrected y'=(y-floor)/(1-floor), y'>0.04, rzz>0": [dict(p, y=(p["y"] - p["floor"]) / (1 - p["floor"])) for p in P if (p["y"] - p["floor"]) / (1 - p["floor"]) > 0.04 and p["x"] > 0],
    }
    out[route] = {k: fit(v) if len(v) > 2 else None for k, v in variants.items()}
    out[route]["builder_ids"] = sorted((p["x"], p["id"]) for p in variants["builder (>=20 correct, >=2x floor, rzz>0)"])
# the package's own generic-model figures for the same 44 circuits (same filter as the builder)
G = [dict(p, y=p["gen"]) for p in pts["native"] if p["gen"]]
out["generic_model_same_44"] = fit([p for p in G if p["x"] > 0])
json.dump(out, open(f"{B}/verify/refit_ionq.json", "w"), indent=1)
for route in ("native", "qis"):
    print("ROUTE", route)
    for k, v in out[route].items():
        if k != "builder_ids": print("  ", k, v)
print("builder ids", out["native"]["builder_ids"])
print("generic same circuits", out["generic_model_same_44"])

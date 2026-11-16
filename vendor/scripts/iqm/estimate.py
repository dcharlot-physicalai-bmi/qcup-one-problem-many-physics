"""IQM credit estimate for the QCUP request, from files only (writes ../estimate.json and prints a summary).

Inputs
- The IQM rows of the request, recomputed from the package: results/aim1_request.json (QAOA), results/hubbard/request.json,
  results/chem/request.json (H2, three rows merged into one circuit), results/labs/request.json, the Q7 sampling rows of
  vendor/results/models/admission.json, results/aim2_request.json; checked against vendor/results/final_request.json.
- IQM's Resource Calculator (https://www.iqmacademy.com/qpu/resourceCalculator/), transcribed from the page's own script
  (sources/iqmacademy_js/calc_0fw-zv5wrs59w.js). For Garnet and Emerald, with J jobs of C circuits at S shots:
      runtime_s = 0.948749148221405 ** min(J, 10) * J * C * (0.022 + 0.00041 * S + 0.000301 * S) + 3.8
      credits   = runtime_s * rate   (rate 0.5 Garnet, 0.75 Emerald, 0.3 Sirius credits per second, as the page states)
- IQM Resonance's price list as read from its API (prices.json): emerald 0.75 per second, emerald:mock 0.00.
- 17 jobs of request circuits on emerald:mock (mock/jobs.json, mock/runtime_estimates.json): IQM's runtime estimate for
  each job, split by the server into QPU execution and the whole sweep.
- The package's IQM device-model counts (results/iqm/check.json) for the sensitivity of the Aim 1 set to the CZ line.
"""
import json, math, os, statistics, sys
HERE = os.path.join(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")), "vendor", "results", "iqm")   # package copy: inputs and outputs in vendor/results/iqm/
PKG = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))   # package root (package copy: vendor/scripts/iqm/)
def load(*p): return json.load(open(os.path.join(*p)))

# ---- 1. the IQM rows of the request ----
a1 = [r for r in load(PKG, "results", "aim1_request.json") if r["vendor"] == "IQM"][0]
hub = load(PKG, "results", "hubbard", "request.json")
chem = load(PKG, "results", "chem", "request.json")
labs = load(PKG, "results", "labs", "request.json")
adm = load(PKG, "vendor", "results", "models", "admission.json")
a2 = [r for r in load(PKG, "results", "aim2_request.json") if r["vendor"] == "IQM"]
fr = load(PKG, "vendor", "results", "final_request.json")
A1_SHOTS = a1["shots_per_circuit"]                                   # 2,000
h2 = [r for r in chem["IQM"] if r["case"].startswith("H2 ")]
n_samp = sum(1 for x in adm if x["vendor"] == "IonQ" and x["group"] == "sampling_Q7")   # the same 4 circuits run on IBM, IQM and IonQ
groups = [  # (name, aim, circuits, shots per circuit)
    ("Aim 1 QAOA", 1, a1["circuits"], A1_SHOTS),
    ("Aim 1 Hubbard", 1, len(hub["IQM"]), hub["IQM"][0]["shots"]),
    ("Aim 1 LABS", 1, labs["totals"]["circuits"]["IQM"], A1_SHOTS),
    ("Aim 1 Q7 sampling", 1, n_samp, A1_SHOTS),
    ("Aim 1 H2 (3 rows merged)", 1, 1, sum(r["shots"] for r in h2)),
    ("Aim 2 programs", 2, sum(r["circuits"] for r in a2), a2[0]["shots_per_circuit"]),
]
assert all(r["shots"] == A1_SHOTS for r in hub["IQM"])
rows = [{"group": g, "aim": a, "circuits": c, "shots_per_circuit": s, "shots": c * s} for g, a, c, s in groups]
# Package copy: this script prices the IQM set of the revision of 15 November 2026 (956 circuits, 1,581,000 shots), before
# the IBM device check re-set the superconducting request. final_request.json now holds the revised set and prices it with
# the same calculator formula; it reproduces this script's 873.1 credits for the earlier set as a positive control. The
# original check against final_request.json's table is therefore replaced by a check of the earlier set's size.
assert (sum(r["circuits"] for r in rows), sum(r["shots"] for r in rows)) == (956, 1581000)
TOT_C = sum(r["circuits"] for r in rows); TOT_S = sum(r["shots"] for r in rows)

# ---- 2. prices and limits as read from the API ----
pr = {c["alias"]: c for c in load(HERE, "prices.json")["computers"]}
RATE = float(pr["emerald"]["pricing"]["payg_price_per_second"]); assert RATE == 0.75
assert float(pr["emerald:mock"]["pricing"]["payg_price_per_second"]) == 0.0
MAXC = pr["emerald"]["limits"]["max_circuits_per_job"]; MAXEX = pr["emerald"]["limits"]["max_executions_per_job"]; MAXSH = pr["emerald"]["limits"]["max_shots_per_circuit"]
assert all(r["shots_per_circuit"] <= MAXSH and MAXC * r["shots_per_circuit"] <= MAXEX for r in rows)

# ---- 3. the Resource Calculator ----
def calc(J, C, S, discount=True):
    f = 0.948749148221405 ** min(J, 10) if discount else 1.0
    return f * J * C * (0.022 + 0.00041 * S + 0.000301 * S) + 3.8
# entries the calculator takes: one per shot count (circuits sharing a shot count can share jobs)
by_shots = {}
for r in rows: by_shots.setdefault((r["aim"], r["shots_per_circuit"]), 0); by_shots[(r["aim"], r["shots_per_circuit"])] += r["circuits"]
def entries_natural():          # jobs of Emerald's maximum of 100 circuits, the remainder as its own entry
    e = []
    for (aim, S), C in sorted(by_shots.items()):
        full, rest = divmod(C, MAXC)
        if full: e.append((aim, full, MAXC, S))
        if rest: e.append((aim, 1, rest, S))
    return e
def entries_one_job(): return [(aim, 1, C, S) for (aim, S), C in sorted(by_shots.items())]
def entries_ten_jobs():          # the calculator's discount stops growing at 10 jobs; circuits spread over 10 jobs per shot count
    return [(aim, 10, C / 10, S) for (aim, S), C in sorted(by_shots.items())]
def run_entries(es, discount=True):
    per = [{"aim": a, "jobs": J, "circuits_per_job": C, "shots": S, "runtime_s": calc(J, C, S, discount)} for a, J, C, S in es]
    tot = sum(p["runtime_s"] for p in per)
    return {"entries": per, "runtime_s": round(tot, 1), "minutes": round(tot / 60, 2), "credits_emerald": round(tot * RATE, 1),
            "aim1_credits": round(sum(p["runtime_s"] for p in per if p["aim"] == 1) * RATE, 1), "aim2_credits": round(sum(p["runtime_s"] for p in per if p["aim"] == 2) * RATE, 1)}
calc_out = {"formula": "runtime_s = 0.948749148221405**min(J,10) * J * C * (0.022 + 0.00041*S + 0.000301*S) + 3.8; credits = runtime_s * 0.75 (Emerald)",
            "source": "https://www.iqmacademy.com/qpu/resourceCalculator/ (page script, saved as sources/iqmacademy_js/calc_0fw-zv5wrs59w.js)",
            "undiscounted_upper": run_entries(entries_natural(), discount=False),
            "as_entered_jobs_of_100": run_entries(entries_natural()),
            "as_entered_one_job_per_shot_count": run_entries(entries_one_job()),
            "as_entered_ten_jobs_per_shot_count": run_entries(entries_ten_jobs())}

# ---- 4. IQM's runtime estimates from the mock ----
est_all = load(HERE, "mock", "runtime_estimates.json")["rows"]
est = [r for r in est_all if r["in_iqm_request"]]                         # jobs whose every circuit is an IQM request circuit
outside = [r for r in est_all if not r["in_iqm_request"]]
per_us = {r["job"]: r["qpu_us_per_circuit_shot"] for r in est}
batch_a1 = [r for r in est if r["label"].startswith("batch") and "Aim 1" in r["label"]]
batch_a2 = [r for r in est if r["label"].startswith("batch") and "Aim 2" in r["label"]]
big = lambda xs: max(xs, key=lambda r: r["circuits"])
US_A1, US_A2 = big(batch_a1)["qpu_us_per_circuit_shot"], big(batch_a2)["qpu_us_per_circuit_shot"]
US_MIN, US_MAX = min(per_us.values()), max(per_us.values())
OH_SMALL = min(r["overhead_s"] for r in est); OH_BIG = max(r["overhead_s"] for r in est)
JOBS_MIN = sum(math.ceil(C / MAXC) for C in by_shots.values())
JOBS_GENEROUS = 60
s_a1 = sum(r["shots"] for r in rows if r["aim"] == 1); s_a2 = sum(r["shots"] for r in rows if r["aim"] == 2)
def mock_proj(us_a1, us_a2, jobs, oh):
    t = s_a1 * us_a1 * 1e-6 + s_a2 * us_a2 * 1e-6 + jobs * oh
    return {"runtime_s": round(t, 1), "minutes": round(t / 60, 2), "credits_emerald": round(t * RATE, 1)}
jobs_a1 = sum(math.ceil(C / MAXC) for (aim, S), C in by_shots.items() if aim == 1); jobs_a2 = JOBS_MIN - jobs_a1
mock_out = {"jobs_run": len(est_all), "jobs_of_request_circuits": len(est),
            "outside_request": [{"label": r["label"], "qpu_us_per_circuit_shot": r["qpu_us_per_circuit_shot"], "cz": r["cz_total_after_iqm_transpile"]} for r in outside], "us_per_circuit_shot_range_singles_and_batches": [US_MIN, US_MAX], "us_per_circuit_shot_aim1_batch": US_A1, "us_per_circuit_shot_aim2_batch": US_A2,
            "overhead_s_per_job_range": [OH_SMALL, OH_BIG], "jobs_minimum_at_100_circuits": JOBS_MIN,
            "central": mock_proj(US_A1, US_A2, JOBS_MIN, OH_BIG),
            "aim1": {"credits_emerald": round((s_a1 * US_A1 * 1e-6 + jobs_a1 * OH_BIG) * RATE, 1)}, "aim2": {"credits_emerald": round((s_a2 * US_A2 * 1e-6 + jobs_a2 * OH_BIG) * RATE, 1)},
            "low": mock_proj(US_MIN, US_MIN, JOBS_MIN, OH_SMALL), "high_slowest_circuit_and_60_jobs": mock_proj(US_MAX, US_MAX, JOBS_GENEROUS, OH_BIG),
            "high_outside_program_rate_and_60_jobs": mock_proj(max(r["qpu_us_per_circuit_shot"] for r in est_all), max(r["qpu_us_per_circuit_shot"] for r in est_all), JOBS_GENEROUS, OH_BIG)}

# ---- 5. sensitivity of the Aim 1 QAOA set to the CZ line (package's IQM device-model counts) ----
chk = load(PKG, "results", "iqm", "check.json")["rows"]
assert 2 * len(chk) == a1["circuits"]
per_circ_a1 = 0.022 + 0.000711 * A1_SHOTS
sens = []
for line in (660, 415, 284, 224):
    n = 2 * sum(1 for r in chk if r["iqm_cz"] <= line)
    dc = (a1["circuits"] - n) * per_circ_a1 * RATE
    sens.append({"cz_line": line, "qaoa_circuits": n, "credits_saved_vs_660_undiscounted": round(dc, 1),
                 "request_credits_undiscounted": round(calc_out["undiscounted_upper"]["credits_emerald"] - dc, 1)})

out = {"note": "Every figure is computed by scripts/estimate.py from the files named in its docstring.", "request_rows": rows,
       "totals": {"circuits": TOT_C, "shots": TOT_S, "aim1": {"circuits": sum(r["circuits"] for r in rows if r["aim"] == 1), "shots": s_a1}, "aim2": {"circuits": sum(r["circuits"] for r in rows if r["aim"] == 2), "shots": s_a2}},
       "emerald": {"rate_credits_per_second": RATE, "max_circuits_per_job": MAXC, "max_shots_per_circuit": MAXSH, "max_executions_per_job": MAXEX,
                   "timeslot": pr["emerald"]["pricing"].get("timeslot")},
       "resource_calculator": calc_out, "mock_runtime_estimate": mock_out, "aim1_qaoa_cz_line_sensitivity": sens,
       "default_credits_new_project": 400}
json.dump(out, open(os.path.join(HERE, "estimate.json"), "w"), indent=1)
print("IQM request:", TOT_C, "circuits,", TOT_S, "shots;", [(r["group"], r["circuits"], r["shots_per_circuit"]) for r in rows])
for k in ("undiscounted_upper", "as_entered_jobs_of_100", "as_entered_one_job_per_shot_count", "as_entered_ten_jobs_per_shot_count"):
    v = calc_out[k]; print(f"calculator {k}: {v['runtime_s']} s = {v['minutes']} min = {v['credits_emerald']} credits (Aim 1 {v['aim1_credits']}, Aim 2 {v['aim2_credits']})")
print("mock: us/circuit-shot", US_MIN, "to", US_MAX, "batches A1", US_A1, "A2", US_A2, "overhead", OH_SMALL, "to", OH_BIG, "jobs", JOBS_MIN)
print("outside request:", mock_out["outside_request"])
for k in ("central", "low", "high_slowest_circuit_and_60_jobs", "high_outside_program_rate_and_60_jobs"): print("mock", k, mock_out[k])
print("mock by aim:", mock_out["aim1"], mock_out["aim2"])
for s in sens: print("sensitivity", s)

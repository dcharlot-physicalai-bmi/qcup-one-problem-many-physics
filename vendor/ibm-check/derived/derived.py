"""Figures the application quotes from the IBM device check that the analysis and the re-score print but do not store,
recomputed from the sealed predictions and the re-score's per-circuit output, as-compiled arm (dd_off) only. The decoupled
arm (dd_on) is not used: its zero-CZ control failed the preregistered pass mark, so the preregistration does not interpret it.

1. Excess loss over the calibration simulation with idle error (cal_idle_aer): measured -ln F over predicted -ln F per
   circuit. Programs: F is the trace fidelity. QAOA: F is the optimum probability retained, measured / ideal and
   predicted / ideal. Circuits whose score is within twice the uniform floor are left out (the re-score's convention).
2. Reset failure on the zero-CZ control (thermostat, five steps, a reset before each of steps 2 to 5): the chance that
   step t+1 is right given step t was right.
3. QAOA: optimum probability kept, as a share of the ideal value.
4. Five-step programs against the budget script (not preregistered): measured -ln F over the budget script's -ln e^-b,
   the model that admits the Aim 2 ladder's mid-circuit programs. Added after the final independent check.
5. Q5's gate-count form under the second form's exclusions (not preregistered; added 17 November 2026): the sealed held-out
   rule (fit on programs at even positions of the package's sorted form order, predict the odd ones, and the reverse;
   ln F on CZ with a free intercept; the 16 programs and the zero-CZ control), keeping programs with F >= 0.01 and
   F >= twice their guessing floor. The re-score's fits.py gives 2.19 on 13 with F >= 0.01 alone and 157 on 11 with the
   twice-floor rule alone; this is both together, on F and on the floor-corrected F' = (F - f)/(1 - f) that the second
   form uses (points F' >= 0.01 and F >= 2f).
6. The calibration's age at the run: design-time calibration last_update_date (prereg.txt) to the job's start
   (run/raw/metrics-dd_off.json timestamps.running), in days.
Usage: python3 -I derived.py IBM_CHECK_DIR   (writes IBM_CHECK_DIR/derived/derived.json)"""
import json, math, os, sys
D = sys.argv[1]
pred = {c["id"]: c for c in json.load(open(os.path.join(D, "predictions.json")))["circuits"]}
res = json.load(open(os.path.join(D, "rescore", "out", "rescore_device.json")))["dd_off"]
out = {"arm": "dd_off", "excess_over_cal_idle": [], "reset_control": {}, "qaoa_kept_share_of_ideal": []}
for r in res:
    c = pred[r["id"]]; p = c["backends"]["ibm_marrakesh"]["predictions"]["cal_idle_aer"]; p = p["score"] if isinstance(p, dict) else p
    m = r["measured"]; floor = r.get("floor") or c.get("uniform_floor")
    if c["kind"] == "aim1":
        ideal = c["ideal_p_gs"]; num, den = -math.log(m / ideal) if m > 0 else None, -math.log(p / ideal)
        out["qaoa_kept_share_of_ideal"].append({"id": r["id"], "cz": c["cz"], "kept": round(m / ideal, 4)})
    else:
        num, den = (-math.log(m) if m > 0 else None), -math.log(p)
    above = m > 2 * floor
    mcm = (c.get("mid_circuit_measurements") or 0) > 0
    out["excess_over_cal_idle"].append({"id": r["id"], "kind": c["kind"], "cz": c["cz"], "T": c.get("T"), "mid_circuit_measurement": mcm,
                                        "measured": m, "above_twice_floor": above, "ratio": round(num / den, 3) if (num is not None and den > 0) else None})
rows = [x for x in out["excess_over_cal_idle"] if x["above_twice_floor"] and x["ratio"] is not None and x["kind"] != "control_zero_cz"]
five = [x["ratio"] for x in rows if x["kind"] == "aim2" and x["T"] == 5]
# circuits without mid-circuit measurement whose score is well clear of a scrambled output: the mirror control, the one-step
# program under 200 CZ and the QAOA circuits above twice their floor (one-step programs above 200 CZ score 1.4 to 2.0 times
# what a scrambled output hits, so their ratio measures the floor, not the loss; the re-score's convention)
without = [x["ratio"] for x in rows if not x["mid_circuit_measurement"] and (x["kind"] in ("aim1", "control_mirror") or x["cz"] <= 200)]
out["summary"] = {"five_step_programs": [min(five), max(five), len(five)], "circuits_without_mid_circuit_measurement": [min(without), max(without), len(without)]}
# reset failure on the zero-CZ control
r = next(x for x in res if x["id"] == "ctl-zero-cz-thermostat-r5")
out["reset_control"] = {"cond_step": [round(v, 4) for v in r["cond_step"]], "failure_steps_3_to_5": [round(1 - v, 4) for v in r["cond_step"][2:]]}
five_script = []
for r in res:
    c = pred[r["id"]]
    if c["kind"] != "aim2" or c.get("T") != 5: continue
    s = c["backends"]["ibm_marrakesh"]["predictions"]["script_e_minus_b"]
    five_script.append({"id": r["id"], "cz": c["cz"], "script_e_minus_b": round(s, 4), "measured": r["measured"], "ratio": round(math.log(r["measured"]) / math.log(s), 3)})
out["five_step_over_budget_script"] = five_script
out["summary"]["five_step_over_budget_script"] = [min(x["ratio"] for x in five_script), max(x["ratio"] for x in five_script), len(five_script)]
# 5. Q5, gate count alone, with F >= 0.01 and F >= 2 x floor (the rule of rescore/scripts/fits.py q5())
ORDER = sorted(json.load(open(os.path.join(D, "design", "package_form_order.json"))))
q5rows = [dict(r, form=pred[r["id"]]["form"], fc=(r["measured"] - r["floor"]) / (1 - r["floor"])) for r in res if r["kind"] in ("aim2", "control_zero_cz")]
def _ols(xs, ys):
    n = len(xs); mx, my = sum(xs) / n, sum(ys) / n; k = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs); return k, my - k * mx
def q5(keep, key="measured"):
    errs = []
    for fold in (0, 1):
        tr = [r for r in q5rows if ORDER.index(r["form"]) % 2 == fold and keep(r)]; te = [r for r in q5rows if ORDER.index(r["form"]) % 2 != fold and keep(r)]
        if len(tr) < 2 or not te: continue
        k, c = _ols([r["cz"] for r in tr], [math.log(r[key]) for r in tr]); errs += [abs(c + k * r["cz"] - math.log(r[key])) for r in te]
    e = sorted(errs); m = len(e); med = e[m // 2] if m % 2 else 0.5 * (e[m // 2 - 1] + e[m // 2])
    return {"median_error_factor": round(math.exp(med), 4), "predictions": m}
out["q5_gate_count"] = {"preregistered_F_ge_0.01": q5(lambda r: r["measured"] >= 0.01), "twice_floor_alone": q5(lambda r: r["measured"] >= 2 * r["floor"]),
                        "F_ge_0.01_and_twice_floor": q5(lambda r: r["measured"] >= 0.01 and r["measured"] >= 2 * r["floor"]),
                        "floor_corrected_Fc_ge_0.01_and_twice_floor": q5(lambda r: r["fc"] >= 0.01 and r["measured"] >= 2 * r["floor"], "fc")}
out["summary"]["q5_gate_count_with_second_form_exclusions"] = out["q5_gate_count"]["F_ge_0.01_and_twice_floor"]
out["summary"]["q5_gate_count_with_second_form_exclusions_floor_corrected"] = out["q5_gate_count"]["floor_corrected_Fc_ge_0.01_and_twice_floor"]
# 6. calibration age at the run
import datetime as _dt, re as _re
_cal = _re.search(r"last_update_date (\S+?)Z", open(os.path.join(D, "prereg.txt")).read()).group(1)
_run = json.load(open(os.path.join(D, "run", "raw", "metrics-dd_off.json")))["timestamps"]["running"].rstrip("Z")
_age = (_dt.datetime.fromisoformat(_run) - _dt.datetime.fromisoformat(_cal)).total_seconds() / 86400
out["summary"]["calibration_age_days_at_run"] = {"calibration": _cal + "Z", "run_started": _run + "Z", "days": round(_age, 3)}
os.makedirs(os.path.join(D, "derived"), exist_ok=True)
json.dump(out, open(os.path.join(D, "derived", "derived.json"), "w"), indent=1)
print(json.dumps(out["summary"]), json.dumps(out["reset_control"]), json.dumps(out["qaoa_kept_share_of_ideal"]))

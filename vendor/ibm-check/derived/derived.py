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
os.makedirs(os.path.join(D, "derived"), exist_ok=True)
json.dump(out, open(os.path.join(D, "derived", "derived.json"), "w"), indent=1)
print(json.dumps(out["summary"]), json.dumps(out["reset_control"]), json.dumps(out["qaoa_kept_share_of_ideal"]))

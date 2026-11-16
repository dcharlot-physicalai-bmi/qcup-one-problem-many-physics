#!/usr/bin/env python3
"""Assemble the pre-registered predictions (predictions.json) from the design and the model runs. Pure Python.
Usage: python3 -I assemble.py DESIGN_DIR PRED_DIR CAL_DIR OUT_JSON"""
import glob, hashlib, json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitlib
DES, PRED, CAL, OUTF = sys.argv[1:5]
design = json.load(open(f"{DES}/design.json")); C = design["circuits"]
budget = json.load(open(f"{PRED}/budget_script.json"))
aer = {}
for p in glob.glob(f"{PRED}/ibm_*-*-*.json"):
    d = json.load(open(p)); aer.setdefault(d["backend"], {}).setdefault(d["model"], {}).update(d["results"])
BACKS = ["ibm_marrakesh"]
sha = lambda path: hashlib.sha256(open(path, "rb").read()).hexdigest()

GEN_A, GEN_LOSS = 0.8588, 0.001595            # package results/summary.json, aim2.fidelity_fits.sc_like (310 circuits)
PKG_FORM_ORDER = sorted(["03_distributed_accept", "17_traffic_light_accept", "account", "card", "ch07_form_bytes_not_rfc8785", "ch07_form_injective_f64",
    "ch17_callee_requires_at_run_time", "climate", "counter", "counter_flag", "crossing", "door", "elevator", "equivalent", "f6_signed_zero_state", "flag_walls",
    "handshake", "hc_11_fabric_caps_logged", "hc_21_kept_step_is_input", "lobby", "parking", "phase", "player", "printer", "queue_sim", "reconcile",
    "reservoir", "ring_buffer", "s1_guard_trap_keeps", "session", "t59_distinguish_mod2_mod3", "t59_distinguish_mod3_mod4", "t59_distinguish_mod5_mod4",
    "t60_dim_redundant_k4", "t60_dim_redundant_k5", "t62_dependent_differ", "t62_independent_commute", "thermostat", "vending", "washer"])
assert len(PKG_FORM_ORDER) == 40


def mix(F, meta):
    """Score from a whole-circuit fidelity F: for a trace, F itself (the application's law ignores the guessing floor);
    for Aim 1, F x ideal + (1 - F) x the uniform chance of an optimum (a depolarised remainder)."""
    if meta["kind"] == "aim1": return F * meta["ideal_p_gs"] + (1 - F) * meta["uniform_floor"]
    return F


out = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
       "what": "Pre-registered predictions for the first device runs of the QCUP application's Aim 2 reversible programs and Aim 1 QAOA circuits on an IBM Heron device (open plan). Fixed before any submission; never edited after.",
       "backend": "ibm_marrakesh",
       "backend_rule": "Fixed to ibm_marrakesh at sealing: at the final design check it was online with 4 jobs queued, ibm_fez was in maintenance (105 queued) and ibm_kingston's free queue had held another job for more than 8.7 h (292 queued). Its calibration then was byte-identical to the design-time read used here. If marrakesh is offline at submission, nothing is sent. design.json also holds layouts for kingston and fez; they are not pre-registered.",
       "calibration_at_design": {b: {"last_update_date": v["calibration_last_update_date"], "properties_sha256": sha(glob.glob(f"{CAL}/{b}-properties-*.json")[0]),
                                     "configuration_sha256": sha(glob.glob(f"{CAL}/{b}-configuration-*.json")[0]), "excluded_qubits": v["excluded_qubits"]} for b, v in design["backends"].items() if b in BACKS},
       "arms": {"dd_off": "ISA circuits exactly as placed, no delays and no dynamical decoupling (the application's assumption). Sampler V2, no twirling, no readout mitigation, server-side DD off.",
                "dd_on": "The same ISA circuits scheduled ALAP with the device's durations and padded with XX dynamical decoupling (tau/2 X tau X tau/2, qiskit PadDynamicalDecoupling, skip_reset_qubits) before submission; server-side DD off. Runs only if the DD-off arm fits the remaining allowance with 30 s to spare."},
       "transpilation": "Each circuit is transpiled exactly as the package does (heavy_hex_patch(n), CZ basis, optimisation level 3, seed 7; CZ counts checked equal to the package's result files). Embedded circuits are placed on the device unchanged by a noise-aware subgraph embedding (VF2Layout on the design-time calibration), so the executed CZ count equals the admission count. The one QAOA circuit whose patch circuit uses the patch's 10-cycle (no Heron lattice has one) is transpiled to the device as aim1_ibm.py does (level 3, best of 8 seeds). Executed CZ counts are read from the submitted OpenQASM 3.",
       "models": {
           "generic_aer": "The application's generic model, aim2.noise('sc_like'): depolarising 3e-3 per CZ, 3e-4 per sx and x, 1e-2 per reset, 1e-2 readout, no idle term. Aer simulation of the submitted circuit. Layout-blind.",
           "generic_law_intercept": "The package's fitted trace law, F = 0.8588 x (1 - 0.001595)^CZ (aggregate.py rule, free intercept). 30% at 659 CZ.",
           "generic_law_no_intercept": "F = (1 - 0.001595)^CZ, F(0) = 1. 30% at 754 CZ. The convention of the qcup-emulators IBM comparison.",
           "cal_idle_aer": "Design-time calibration as qiskit-aer builds a noise model from a backend (gate error as depolarising plus thermal relaxation over the gate duration, readout assignment error, T1/T2). Circuit scheduled ALAP with the device durations and padded with delays, which relax under T1/T2. Idle convention: the leading delay before a qubit's first gate is in the schedule, but relaxation of a qubit in |0> does nothing, so leading idle costs nothing here. No static ZZ, leakage or crosstalk.",
           "cal_noidle_aer": "The same noise model on the unscheduled circuit: no idle relaxation at all (the idle-suppressed variant).",
           "script_e_minus_b": "Port of qcup-emulators/scripts/ibm_budget.py to these circuits (scripts/budget.py): gate, relaxation, ASAP idle and readout terms, plus mid-circuit measure and reset terms these circuits need. No ZZ. Idle convention: charged from t = 0, including before a qubit's first gate, as the original script does. Prediction = e^-budget (mixed with the uniform optimum chance for Aim 1).",
           "script_e_minus_b_no_leading": "As script_e_minus_b without idle before a qubit's first operation.",
           "script_law_carried": "The application's trace law carried over by this circuit's budget ratio (script budget / generic budget), (1 - 0.001595)^(CZ x ratio), as ibm_analyze.py derives its 30% points. Leading idle charged.",
           "script_law_carried_no_leading": "As script_law_carried without leading idle."},
       "reference_30pct_points_cz": {
           "generic_application": {"intercept": 659, "no_intercept": 754},
           "wai_quantum_forecast_qcup_emulators_sample": {"implementation": "WAI Quantum forecast (idle term about 1.3x the script's, with static ZZ), qcup-emulators IBM sample of 29 circuits, calibrations of 2026-11-13, no-intercept carried-over convention; verify/ibm_analysis_rerun.json", "ibm_marrakesh": 256, "ibm_kingston": 284, "ibm_fez": 224},
           "budget_script_qcup_emulators_sample": {"implementation": "qcup-emulators/scripts/ibm_budget.py budgets alone (no ZZ; leading idle charged), same sample and convention", "ibm_marrakesh": 344, "ibm_kingston": 415, "ibm_fez": 324},
           "wai_quantum_without_idle": {"range_over_three_devices": [483, 635]}},
       "scoring": {"aim2": "trace fidelity exactly as aim2.trace_prob: the share of shots whose whole trace register equals the reference trace",
                   "control_zero_cz": "the same, on the 0-CZ program", "control_mirror": "the share of shots equal to the known string",
                   "aim1": "the share of shots that are an optimal assignment (the package's ground set, ties included)"},
       "fit_rules": fitlib.__doc__,
       "fit_set": "The 16 Aim 2 programs and the 0-CZ program (17 programs from the application's Aim 2 set). Not the mirror or the QAOA circuits.",
       "analysis_plan": [
           "Primary: the device 30% point by the package rule (free intercept, F >= 0.01) on the DD-off arm, compared with 659 (generic) and with each calibration model's implied 30% point under the same rule (below).",
           "Also reported: the no-intercept rule (compared with 754 and with the qcup-emulators sample values, which use that convention) and the floor-corrected rule.",
           "Uncertainty: 2,000 bootstrap draws that resample programs and each program's counts (fitlib.bootstrap_30); 68% and 95% intervals.",
           "A model is consistent with the device if its implied 30% point (same rule) lies inside the device's 95% interval. Per circuit, the ratio of measured to predicted -ln F is reported for every model, with its median.",
           "Q5 held-out on the device: fit on half the programs (the package's alternating order over all 40 forms), predict the other half; falsified if the median error factor exceeds 1.25.",
           "DD-on against DD-off: per-circuit difference and the 30% point of each arm.",
           "Aim 1: measured optimum probability against each prediction and against the ideal value.",
           "Guard against gates not running as sent: the executed CZ count is the count in the submitted OpenQASM 3; if trace fidelity shows no fall with CZ (package-rule slope not negative at 95%), the run is reported as not measuring the device.",
           "Positive controls (pipeline check, decided before submission): the 0-CZ program passes at trace fidelity >= 0.85 and the mirror circuit at >= 0.80 (models predict 0.86 to 0.99 and 0.83 to 0.93). A wrong bit order or register decoding gives about 0.03 and 0.016. If a control fails, no other result is interpreted until the cause is found.",
           "Expectation fixed in advance for Q5 held-out: every calibration model here implies a median held-out factor above 1.25 on these 17 programs (see implied_by_predictions.held_out_q5), because gate count alone does not carry idle time and mid-circuit measurement. A device factor above 1.25 is therefore what the calibration models expect, and is reported as such, not only as a falsification of the generic law.",
           "Every outcome is reported, including one that contradicts the calibration models or the application."],
       "circuits": []}

PROGRAMS = [c for c in C if c["kind"] in ("aim2", "control_zero_cz")]
for meta in C:
    row = {k: v for k, v in meta.items() if k not in ("ground_states",)}
    if meta["kind"] == "aim1": row["ground_state_count"] = len(meta["ground_states"])
    row["backends"] = {}
    for b in BACKS:
        bud = budget[b][meta["id"]]; cz = design["backends"][b]["device_cz"][meta["id"]]
        pr = {}
        for model in ("generic", "cal_idle", "cal_noidle"):
            r = aer.get(b, {}).get(model, {}).get(meta["id"])
            pr[{"generic": "generic_aer", "cal_idle": "cal_idle_aer", "cal_noidle": "cal_noidle_aer"}[model]] = {"score": r["score"], "se": r["se"], "shots": r["shots"]} if r else None
        pr["generic_law_intercept"] = mix(GEN_A * (1 - GEN_LOSS) ** cz, meta)
        pr["generic_law_no_intercept"] = mix((1 - GEN_LOSS) ** cz, meta)
        pr["script_e_minus_b"] = mix(bud["e_minus_b_script"], meta); pr["script_e_minus_b_no_leading"] = mix(bud["e_minus_b_no_leading"], meta)
        pr["script_law_carried"] = mix(bud["law_carried_over_script"], meta); pr["script_law_carried_no_leading"] = mix(bud["law_carried_over_no_leading"], meta)
        row["backends"][b] = {"layout": design["backends"][b]["layouts"][meta["id"]], "executed_cz": cz, "schedule": design["backends"][b]["durations_us"][meta["id"]],
                              "script_budget": bud["budget"], "predictions": pr}
    out["circuits"].append(row)

implied = {}
MODELS = ["generic_aer", "generic_law_intercept", "generic_law_no_intercept", "cal_idle_aer", "cal_noidle_aer", "script_e_minus_b", "script_e_minus_b_no_leading", "script_law_carried", "script_law_carried_no_leading"]
for b in BACKS:
    implied[b] = {}
    for m in MODELS:
        pts = []
        for row in out["circuits"]:
            if row["kind"] not in ("aim2", "control_zero_cz"): continue
            v = row["backends"][b]["predictions"][m]; v = v["score"] if isinstance(v, dict) and v else v
            if v is None: break
            pts.append((row["backends"][b]["executed_cz"], v, row["uniform_floor"]))
        else:
            implied[b][m] = {rule: fitlib.fit(pts, rule) for rule in ("package", "no_intercept", "floor_corrected")}
            implied[b][m]["held_out_q5"] = fitlib.held_out([(row["form"], row["backends"][b]["executed_cz"], p[1]) for row, p in zip([r for r in out["circuits"] if r["kind"] in ("aim2", "control_zero_cz")], pts)], PKG_FORM_ORDER)
out["implied_by_predictions"] = implied
rc = [(r["id"], r["backends"]["ibm_marrakesh"]["predictions"]["generic_aer"]["score"], r["package_generic_trace_fidelity_2000_shots"]) for r in out["circuits"] if r.get("package_generic_trace_fidelity_2000_shots") is not None]
dz = sorted(abs(a - b) / math.sqrt(max(b * (1 - b), 1e-6) / 2000) for _, a, b in rc)
out["reproduction_check"] = {"what": "generic_aer (20,000 shots, the submitted circuit) against the package's own generic trace fidelity for the same circuit (2,000 shots, results/aim2)", "circuits": len(rc),
                             "median_abs_difference_in_package_standard_errors": dz[len(dz) // 2], "max_abs_difference_in_package_standard_errors": dz[-1], "pairs": rc,
                             "explanation": "Rerunning the package's own call (patch circuit, 2,000 shots, seed_simulator=11) reproduces its values, so the circuits are identical. The package drew every circuit from the same seed, so its generic values share one correlated draw: with 20,000 shots (seed 11 or 12345) they come out 0.00 to 0.03 higher on 14 of 17 programs. Prediction generic_aer uses the 20,000-shot values."}

shots = {c["id"]: c["shots"] for c in C}
est = {}
for b in BACKS:
    circ_s = sum(shots[k] * budget[b][k]["duration_ns_asap"] * 1e-9 for k in shots)
    est[b] = {"shots_per_arm": sum(shots.values()), "circuits_per_arm": len(shots), "shot_seconds_at_ibm_rate": round(sum(shots.values()) * 44.897588452 / 176000, 2), "circuit_seconds": round(circ_s, 2),
              "per_job_overhead_assumed_s": [2, 6], "estimate_per_arm_s": [round(sum(shots.values()) * 44.897588452 / 176000 + circ_s + 2, 1), round(sum(shots.values()) * 44.897588452 / 176000 + circ_s + 6, 1)]}
out["qpu_seconds_estimate"] = {"method": "IBM's own estimator is only shown once a job exists. Its estimate for the other agent's queued job on this account (176,000 shots of short circuits, 44.9 s) gives 0.255 ms per shot (the 250 us default repetition delay plus about 5 us). Per arm: shots x 0.255 ms + shots x each circuit's ASAP duration + 2 to 6 s per job. IBM's estimate for the DD-off job is read when it is created, before the DD-on job is sent.",
                               "per_backend": est, "max_execution_time_cap_per_job_s": 45, "budget_rule": "Read usage just before each submission and reserve the hard cost cap of every job already pending on the instance (300 s if none is stated). Send an arm only if what remains covers its own 45 s cap plus 30 s. Send DD-on only if both arms together are estimated at 100 s or less (IBM's estimate for DD-off once it exists). Open plan only; each job carries the 45 s cap as a hard stop."}
json.dump(out, open(OUTF, "w"), indent=1)
for b in implied:
    print(b, {m: {r: (round(v["cz_at_30pct"]) if v and v.get("cz_at_30pct") else None) for r, v in implied[b][m].items() if r != "held_out_q5"} for m in implied[b]})

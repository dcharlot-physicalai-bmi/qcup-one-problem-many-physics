"""Score the 2025 Selene runs the 2024 run's way (qcup-selene-params/scripts/analyze.py: the same scores, intervals, fits,
admission rule and HQC formula) and set them beside the 2024 Selene runs and the application's device model.

    python3 -I analyze.py BASE PKG OLD SCRATCH
        BASE = this folder, PKG = the final package, OLD = the 2024 run folder (qcup-selene-params), SCRATCH = a scratch
        folder (models.py is imported from PKG and wants a BASE of its own at import; nothing is written to PKG or OLD)

Scores (unchanged):
  Aim 2 programs   trace fidelity: shots whose classical bits equal the reference trace (reference_bits_qiskit_order).
  family E         optimum probability: shots on a LABS ground state (labs.energies).
  chemistry        share of shots with the right electron numbers (alpha = qubits 0..n-1, beta = n..2n-1).
  every circuit    error-free fraction: shots in which the error model applied no fault at all (its own per-shot counts).
Model (the application's, vendor/results/models/quantinuum_sets.json), each 2025 set beside the closest of the model's
2025 documentation-page figure sets:
  H2-1E 2025-07-16      -> "docs 2025-04-30 H2-1"  (1Q 1.9e-5, 2Q 1.1e-3, SPAM 6.0e-4 / 1.4e-3; the defaults are 1.89e-5,
                                                     1.05e-3, 6e-4 / 1.39e-3)
  H2-2E 2025-07-16      -> "docs 2025-05-29 H2-2"  (the latest H2-2 set dated before 2025-07-16, and the closest in two-qubit
                                                     error among the 2025 H2-2 sets: 1.1e-3 against 1.29e-3)
  Helios-1E 2025-11-18  -> "docs 2025-08-28 H2-2"  (the model has no Helios set; this H2-2 set is the closest in two-qubit
                                                     error: 8.3e-4 against 8.0e-4)
  and, as a second reading, the model with the defaults themselves in its terms ("model_defaults": two-qubit error p2 on
  models.py's angle line, one-qubit error p1, readout and reset (p_meas_0 + p_meas_1) / 2, memory 0 for the docs variant
  and memory_pz / 1.5 for the docs_dephasing variant, so that models.py's Z per layer, 1.5 x memory, equals memory_pz).
  Programs: the admission rule carried over, F_rule ** (b_set / b_generic); family E and chemistry: e^-b, share
  F + (1 - F) pN, optimum probability F p_ideal + (1 - F) p_uniform.
30% point on the programs: least squares of ln F on two-qubit gate count (programs with at least 20 correct traces), and
final_request.py's median per-gate loss, on the 71 core programs and on all 115 Quantinuum Aim 2 programs.
HQC: cost.py's hqc() = 5 + shots (n1q + 10 n2q + 5 spam) / 5000, as final_request.py sums it."""
import glob, importlib.util, json, math, os, statistics as st, sys
from collections import defaultdict
BASE, PKG, OLD, SCR = sys.argv[1:5]
V = os.path.join(PKG, "vendor", "results")
sys.path.insert(0, PKG)
import labs as LB
sys.path.insert(0, os.path.join(BASE, "scripts"))
from gen_guppy import guppy_text

IDX = json.load(open(os.path.join(BASE, "builder", "index.json")))["circuits"]
ids = json.load(open(os.path.join(BASE, "params", "core84_ids.json")))
EXT = json.load(open(os.path.join(BASE, "params", "ext_aim2_ids.json")))
A = {x["id"]: x for x in json.load(open(os.path.join(V, "models", "admission.json"))) if x["vendor"] == "Quantinuum"}
QS = json.load(open(os.path.join(V, "models", "quantinuum_sets.json")))["sets"]
PRED = json.load(open(os.path.join(V, "models", "predictions.json")))
TGT = json.load(open(os.path.join(PKG, "results", "targets", "request.json")))
MODEL = {r["case"]: r for r in json.load(open(os.path.join(PKG, "results", "targets", "model.json")))}
FR = json.load(open(os.path.join(V, "final_request.json")))
SETMAP = {"H2-1E_2025-07-16": "docs 2025-04-30 H2-1", "H2-2E_2025-07-16": "docs 2025-05-29 H2-2", "Helios-1E_2025-11-18": "docs 2025-08-28 H2-2"}
OLDMAP = {"H2-1E_2025-07-16": "H2-1_2024-05-20", "H2-2E_2025-07-16": "H2-2_2024-12-06"}
ADMIT_SET = "docs 2026-10-20 H2-1"
PJ = {s: json.load(open(os.path.join(BASE, "params", s + ".json"))) for s in SETMAP}
VARIANTS = ("docs", "docs_dephasing")
ACT = {"qcup-f-tgt-" + r["case"].lower().replace("_", "-"): r for r in TGT["Quantinuum"]}
TM = {"qcup-f-tgt-" + r["case"].lower().replace("_", "-"): r for r in TGT["IonQ"]}
PI = math.pi


def hqc(n1q, n2q, spam, shots): return 5 + shots * (n1q + 10 * n2q + 5 * spam) / 5000


def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pN(cid):
    c = IDX[cid]; m = MODEL[c["case"]]; na, nb = m["electrons"]; q = c["qubits"]
    return math.comb(m["orbitals"], na) * math.comb(m["orbitals"], nb) / 2 ** q


# ---- the model with the 2025 defaults in its terms (models.py's budget(), imported; its main() is not run) ----
os.makedirs(os.path.join(SCR, "circuits"), exist_ok=True)
json.dump({"circuits": {}, "rows": []}, open(os.path.join(SCR, "circuits", "index.json"), "w"))
sys.argv = [os.path.join(V, "..", "scripts", "models.py"), SCR]
spec = importlib.util.spec_from_file_location("qcup_models", os.path.join(PKG, "vendor", "scripts", "models.py")); qm = importlib.util.module_from_spec(spec); spec.loader.exec_module(qm)


def model_of(e2q, e1q, mem, p0, p1):
    s = e2q / 1.93e-3; f = qm.line([(0.0, 0.46e-3 * s), (PI / 2, 1.91e-3 * s)]); ro = (p0 + p1) / 2
    return {"two": (lambda t, f=f: (f(t), "r")), "one": e1q, "readout": ro, "reset": ro, "memory": mem, "count_1q": "transpiled", "drop_local_rzz": True}


def qs_model(k):
    """A figure set of quantinuum_sets.json as a models.py model, rebuilt from its stored terms (positive control below)."""
    t = QS[k]["terms"]
    return model_of(t["two_qubit_error"], t["one_qubit_error"], t["memory"], t["p_meas_0"], t["p_meas_1"])


MD = {}
for s in SETMAP:
    T = PJ[s]["table"]
    MD[(s, "docs")] = model_of(T["p2"], T["p1"], 0.0, T["p_meas_0"], T["p_meas_1"])
    MD[(s, "docs_dephasing")] = model_of(T["p2"], T["p1"], PJ[s]["plugin_docs_dephasing"]["memory_pz"] / 1.5, T["p_meas_0"], T["p_meas_1"])
GATES = {cid: json.load(open(os.path.join(BASE, "builder", "gates", cid + ".json"))) for cid in ids + EXT}
model_ctrl = {}
for k in set(SETMAP.values()):
    M = qs_model(k); d = [abs(qm.budget(GATES[c]["gates"], M)["total"] - QS[k]["circuits"][c][0]) for c in ids + EXT]
    model_ctrl[k] = {"circuits": len(d), "max_abs_difference_nats": max(d)}


def s_doc(T, theta):
    t = theta - round(theta / (2 * PI)) * 2 * PI; x = (abs(t) / PI) ** T["przz_power"]
    return T["przz_a"] * x + T["przz_b"] if t < 0 else (T["przz_c"] * x + T["przz_d"] if t > 0 else (T["przz_b"] + T["przz_d"]) / 2)


def native_rzz_angles(cid):
    """The rzz angles the program sends to Selene (gen_guppy's rules, min_angles on), read from the gate list."""
    out = []
    for name, qs, ps, cs in GATES[cid]["gates"]:
        if name != "rzz": continue
        t = abs(math.remainder(float(ps[0]), 2 * PI))
        if t < 1e-4 or abs(t - PI) < 1e-12: continue
        out.append(float(ps[0]))
    return out


# ---- load runs (chunks merged) ----
runs = defaultdict(lambda: {"bits": [], "metrics": [], "seconds": 0.0, "stats": None, "chunks": 0})
for p in sorted(glob.glob(os.path.join(BASE, "runs", "*.json"))):
    o = json.load(open(p)); key = (o["id"], o["set"], o["variant"]); r = runs[key]
    r["bits"] += o["bits"]; r["metrics"] += o["metrics"]; r["seconds"] += o["seconds"]["run"]; r["stats"] = o["program_stats"]; r["chunks"] += 1
OLDR = json.load(open(os.path.join(OLD, "results", "selene_results.json")))

ENERGY8 = LB.energies(8)
out = {"circuits": {}, "controls": {"model_rebuilt_from_stored_terms": model_ctrl}, "fits": {}, "admission": {}, "hqc": {}, "angle_scaling_check": {}}
ctrl_fail = []
AGG_KEYS = ("memory_z", "memory_units", "leak_1q", "leak_2q", "leak_as_depolar_1q", "leak_as_depolar_2q", "leak_init", "seep_1q", "seep_2q", "pauli_1q",
            "pauli_2q", "emission_xy_1q", "emission_xy_2q", "meas_flips", "leaked_reads", "crosstalk_meas", "crosstalk_init", "init_errors", "gates_1q",
            "gates_2q", "leaked_partner", "skipped_gates", "faults_total", "inits", "clock_max", "rzz_scale_sum", "rzz_dep_prob_sum", "rzz_emis_prob_sum")
for cid in ids + EXT:
    c = IDX[cid]; a = A.get(cid)
    kind = "program" if c.get("aim") == 2 else ("labs" if c.get("family") == "E" else "chem")
    rec = {"id": cid, "kind": kind, "qubits": c["qubits"], "n2q": c["n2q"], "n1q": c["n1q"],
           "request_shots": (a["shots"] if a else (100 if cid in ACT else 200)), "tier": "extension" if cid in EXT else "core",
           "group": ("actinide" if cid in ACT else "transition_metal" if cid in TM else kind)}
    if kind == "chem":
        na, nb = c["nelec"]; n = c["n_orbitals"]; mask = (1 << n) - 1; rec["pN"] = pN(cid)
    def score(bits):
        if kind == "program":
            ref = c["reference_bits_qiskit_order"]; return sum(b == ref for b in bits)
        if kind == "labs":
            return sum(ENERGY8[int(b, 2)] == c["e_min"] for b in bits)
        return sum(bin(int(b, 2) & mask).count("1") == na and bin(int(b, 2) >> n).count("1") == nb for b in bits)
    ri = runs.get((cid, "none", "ideal"))
    if ri:
        k = score(ri["bits"]); rec["ideal"] = {"shots": len(ri["bits"]), "score": k / len(ri["bits"])}
        if kind in ("program", "chem") and k != len(ri["bits"]): ctrl_fail.append((cid, "ideal", k))
    angles = native_rzz_angles(cid)
    for s, mk in SETMAP.items():
        T = PJ[s]["table"]
        def mrec(F_b, ratio_budget=None):
            m = {"e_minus_b": F_b}
            if kind == "program": m["trace_fidelity_rule"] = A[cid]["rule_fidelity_generic"] ** ratio_budget
            if kind == "chem": m["share"] = F_b + (1 - F_b) * rec["pN"]
            if kind == "labs": m["optimum_probability"] = F_b * c["ideal_p_gs"] + (1 - F_b) * c["uniform_p_gs"]
            return m
        b_set, F_set = QS[mk]["circuits"][cid]
        rs = {"model": mrec(F_set, b_set / PRED[cid]["generic"]["total"]), "model_set": mk, "model_defaults": {}}
        for v in VARIANTS:
            bd = qm.budget(GATES[cid]["gates"], MD[(s, v)])
            rs["model_defaults"][v] = mrec(bd["fidelity"], bd["total"] / PRED[cid]["generic"]["total"]) | {"budget_terms": bd["terms"]}
        for v in VARIANTS:
            r = runs.get((cid, s, v))
            if not r: continue
            N = len(r["bits"]); k = score(r["bits"]); f = [m.get("e:faults_total", 0) for m in r["metrics"]]
            nf = [b for b, x in zip(r["bits"], f) if x == 0]; knf = score(nf)
            if len(nf) and knf != len(nf) and kind in ("program", "chem"): ctrl_fail.append((cid, s, v, "no-fault shots", knf, len(nf)))
            e = {"shots": N, "score": k / N, "score_ci95": wilson(k, N), "no_fault_fraction": len(nf) / N, "no_fault_ci95": wilson(len(nf), N),
                 "mean_faults": sum(f) / N, "run_seconds": round(r["seconds"], 1), "chunks": r["chunks"]}
            agg = defaultdict(float)
            for m in r["metrics"]:
                for kk in AGG_KEYS: agg[kk] += m.get("e:" + kk, 0)
            e["per_shot"] = {kk: vv / N for kk, vv in agg.items()}
            if kind == "chem": e["fidelity_from_share"] = (e["score"] - rec["pN"]) / (1 - rec["pN"])
            # positive control on the real circuit: the plugin's per-shot sum of s(theta) against the closed form over the
            # program's own rzz angles, on every shot with no leaked qubit (a leaked qubit skips gates). Selene's soft-RZ
            # runtime executes only the operations queued up to the last measurement it has to force, and clears the rest at
            # shot end (shot_end: operation_queue.clear()); those last gates act only on qubits never measured again, so they
            # cannot change a result. Where the plugin saw fewer rzz than the program holds (gates_2q < native), the
            # difference must equal the scale of the unexecuted gates; every such gate found here is at +-pi/2 (scale 1).
            want = sum(s_doc(T, t) for t in angles)
            full = [(m.get("e:rzz_scale_sum", 0.0), len(angles) - m.get("e:gates_2q", 0)) for m in r["metrics"] if m.get("e:skipped_gates", 0) == 0]
            exact = [abs(x - want) for x, d in full if d == 0]
            short = [abs(want - x - d * 1.0) for x, d in full if d > 0]
            e["angle_scaling_check"] = {"closed_form_sum": want, "shots_without_skipped_gates": len(full), "native_rzz": len(angles),
                                        "max_abs_difference": max(exact, default=None), "shots_all_rzz_executed": len(exact),
                                        "shots_with_unexecuted_trailing_rzz": len(short), "max_unexecuted_trailing_rzz": max((d for _, d in full), default=0),
                                        "max_abs_difference_after_unexecuted_at_scale_1": max(short, default=None),
                                        "mean_scale": want / len(angles) if angles else None}
            rs[v] = e
        old = OLDMAP.get(s)
        if old and old in OLDR["circuits"].get(cid, {}):
            o2 = OLDR["circuits"][cid][old].get("published")
            if o2: rs["selene_2024"] = {"set": old, "score": o2["score"], "score_ci95": o2["score_ci95"], "no_fault_fraction": o2["no_fault_fraction"], "shots": o2["shots"]}
        rec[s] = rs
    # the figure set the application admits on (H2-1, 20 October 2026), for reference: not simulated here
    bA, FA = QS[ADMIT_SET]["circuits"][cid]
    rec["model_admission_set"] = {"set": ADMIT_SET, "e_minus_b": FA} | ({"trace_fidelity_rule": A[cid]["rule_fidelity_generic"] ** (bA / PRED[cid]["generic"]["total"])} if kind == "program" else {}) \
        | ({"share": FA + (1 - FA) * rec["pN"]} if kind == "chem" else {})
    rec["program_stats"] = next((runs[(cid, s, v)]["stats"] for s in SETMAP for v in VARIANTS if (cid, s, v) in runs), None)
    out["circuits"][cid] = rec
out["controls"]["failures"] = ctrl_fail
out["controls"]["ideal_runs"] = sum(1 for r in out["circuits"].values() if "ideal" in r)
out["controls"]["ideal_programs_all_exact"] = all(r["ideal"]["score"] == 1.0 for r in out["circuits"].values() if r["kind"] == "program" and "ideal" in r)
out["controls"]["ideal_chem_all_right_numbers"] = all(r["ideal"]["score"] == 1.0 for r in out["circuits"].values() if r["kind"] == "chem" and "ideal" in r)
out["controls"]["ideal_chem_runs"] = {g: sum(1 for r in out["circuits"].values() if r["group"] == g and "ideal" in r) for g in ("transition_metal", "actinide")}
lab = out["circuits"].get("qcup-e-labs8-p1", {}).get("ideal")
out["controls"]["labs8_ideal_optimum_probability"] = {"selene_200_shots": lab and lab["score"], "builder_exact": IDX["qcup-e-labs8-p1"]["ideal_p_gs"]}
for s in SETMAP:
    for v in VARIANTS:
        es = [r[s][v]["angle_scaling_check"] for r in out["circuits"].values() if v in r[s]]
        d = [x["max_abs_difference"] for x in es if x["max_abs_difference"] is not None]
        d2 = [x["max_abs_difference_after_unexecuted_at_scale_1"] for x in es if x["max_abs_difference_after_unexecuted_at_scale_1"] is not None]
        out["angle_scaling_check"][f"{s}|{v}"] = {"runs": len(es), "shots_checked": sum(x["shots_without_skipped_gates"] for x in es),
                                                   "max_abs_difference_all_rzz_executed": max(d) if d else None,
                                                   "shots_all_rzz_executed": sum(x["shots_all_rzz_executed"] for x in es),
                                                   "runs_with_unexecuted_trailing_rzz": sum(1 for x in es if x["shots_with_unexecuted_trailing_rzz"]),
                                                   "max_unexecuted_trailing_rzz": max((x["max_unexecuted_trailing_rzz"] for x in es), default=0),
                                                   "max_abs_difference_after_unexecuted_at_scale_1": max(d2) if d2 else None}


# ---- fits ----
def lsq(pts):
    x = [float(p[0]) for p in pts]; y = [math.log(p[1]) for p in pts]; n = len(x); mx = sum(x) / n; my = sum(y) / n
    k = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sum((a - mx) ** 2 for a in x); c = my - k * mx
    r2 = 1 - sum((b - (k * a + c)) ** 2 for a, b in zip(x, y)) / sum((b - my) ** 2 for b in y)
    return {"points": n, "loss_per_two_qubit_gate_pct": round(100 * (1 - math.exp(k)), 4), "r2": round(r2, 3), "gates_at_30pct": round((math.log(0.3) - c) / k),
            "gates_at_30pct_exact": (math.log(0.3) - c) / k, "fidelity_at_zero_gates": round(math.exp(c), 4)}


def median_point(pts):
    return round(-math.log(0.3) / st.median(-math.log(f) / n for n, f in pts if n > 0 and 0 < f < 1), 1)


def fitset(progs, s, mk):
    pm = [(A[r["id"]]["count_n2q"], r[s]["model"]["trace_fidelity_rule"]) for r in progs]
    rec = {"model_set": mk, "model_rule_lsq": lsq(pm), "model_rule_median_per_gate": median_point(pm),
           "final_request_json_aim2_programs": FR["steps"]["quantinuum_30pct_point"][mk]["aim2_programs"], "model_defaults": {}}
    for v in VARIANTS:
        pd = [(A[r["id"]]["count_n2q"], r[s]["model_defaults"][v]["trace_fidelity_rule"]) for r in progs]
        rec["model_defaults"][v] = {"rule_lsq": lsq(pd), "rule_median_per_gate": median_point(pd)}
        pr = [r for r in progs if v in r[s]]
        pts = [(A[r["id"]]["count_n2q"], r[s][v]["score"]) for r in pr]
        if not pts: continue
        keep = [(n, f) for (n, f), r in zip(pts, pr) if f * r[s][v]["shots"] >= 20]
        rec[v] = {"lsq_at_least_20_correct": lsq(keep), "lsq_all_nonzero": lsq([p for p in pts if p[1] > 0]), "median_per_gate": median_point(pts), "programs": len(pts)}
        ratios = [math.log(r[s][v]["score"]) / math.log(r[s]["model"]["trace_fidelity_rule"]) for r in progs
                  if v in r[s] and 0 < r[s][v]["score"] < 1 and r[s]["model"]["trace_fidelity_rule"] < 1 and A[r["id"]]["count_n2q"] >= 20]
        rec[v]["median_error_ratio_selene_over_model"] = round(st.median(ratios), 3) if ratios else None
        rec[v]["programs_in_error_ratio"] = len(ratios)
        # circuit by circuit against the model (programs with at least 20 two-qubit gates)
        big = [r for r in progs if v in r[s] and A[r["id"]]["count_n2q"] >= 20]
        below = [r for r in big if r[s][v]["score"] < r[s]["model"]["trace_fidelity_rule"]]
        beyond = [r for r in below if r[s][v]["score_ci95"][1] < r[s]["model"]["trace_fidelity_rule"]]
        rec[v]["vs_model_programs_20_plus"] = {"programs": len(big), "below_model": len(below), "below_beyond_95ci": len(beyond),
                                               "max_shortfall_pct": round(100 * max((1 - r[s][v]["score"] / r[s]["model"]["trace_fidelity_rule"] for r in below), default=0.0), 2),
                                               "min_score": min(r[s][v]["score"] for r in big)}
    return rec


for s, mk in SETMAP.items():
    core_p = [r for r in out["circuits"].values() if r["kind"] == "program" and r["tier"] == "core"]
    all_p = [r for r in out["circuits"].values() if r["kind"] == "program"]
    out["fits"][s] = {"core_71_programs": fitset(core_p, s, mk), "all_115_quantinuum_programs": fitset(all_p, s, mk)}

# ---- admission: the 30% rule on Selene's figures ----
for s in SETMAP:
    for v in VARIANTS:
        rows = []
        for cid in ids:
            r = out["circuits"][cid]; e = r[s].get(v)
            if not e: continue
            fig = e["score"] if r["kind"] == "program" else e["no_fault_fraction"]
            lo, hi = e["score_ci95"] if r["kind"] == "program" else e["no_fault_ci95"]
            rows.append({"id": cid, "group": r["group"], "figure": fig, "ci95": [lo, hi], "passes": fig >= 0.30, "clearly_below": hi < 0.30, "clearly_above": lo >= 0.30,
                         "figure_kind": "trace fidelity" if r["kind"] == "program" else "error-free fraction"})
        adm = [x for x in rows if x["group"] != "actinide"]
        out["admission"][f"{s}|{v}"] = {"circuits": len(rows), "pass": sum(x["passes"] for x in rows), "fail": [x for x in rows if not x["passes"]],
                                        "admitted_80_present": len(adm), "admitted_80_pass": sum(x["passes"] for x in adm),
                                        "admitted_80_fail": [x["id"] for x in adm if not x["passes"]],
                                        "interval_straddles_30pct": [x["id"] for x in rows if not x["clearly_below"] and not x["clearly_above"]],
                                        "by_group": {g: {"n": sum(1 for x in rows if x["group"] == g), "pass": sum(1 for x in rows if x["group"] == g and x["passes"]),
                                                         "min": round(min(x["figure"] for x in rows if x["group"] == g), 4), "max": round(max(x["figure"] for x in rows if x["group"] == g), 4)}
                                                     for g in ("program", "labs", "transition_metal", "actinide") if any(x["group"] == g for x in rows)}}

# ---- HQC by the package's formula (unchanged by this rerun) ----
core72 = [cid for cid in ids if cid not in ACT and cid not in TM]
h72 = round(sum(hqc(A[c]["count_n1q"] or 0, A[c]["count_n2q"], A[c]["spam"], A[c]["shots"]) for c in core72), 1)
htm = round(sum(hqc(IDX[c]["n1q"], IDX[c]["n2q"], 2 * IDX[c]["qubits"], 200) for c in TM), 1)
hact = round(sum(hqc(r["n1q"], r["rzz"], 2 * r["qubits"], 100) for r in TGT["Quantinuum"]), 1)
out["hqc"] = {"programs_and_labs8_72_rows": h72, "transition_metal_8_at_200": htm, "actinides_4_at_100": hact, "total": round(h72 + htm + hact, 1),
              "final_request_json": FR["costs"]["per_vendor"]["Quantinuum"]["hqc"], "matches_final_request": abs(h72 + htm + hact - FR["costs"]["per_vendor"]["Quantinuum"]["hqc"]) < 0.05}
json.dump(out, open(os.path.join(BASE, "results", "selene_results.json"), "w"), indent=1)

# ---- flat table ----
import csv
with open(os.path.join(BASE, "results", "per_circuit.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "group", "tier", "qubits", "n2q", "request_shots", "set", "variant", "shots", "score_kind", "selene_score", "ci95_lo", "ci95_hi", "error_free_fraction",
                "model_set", "model_score", "model_e_minus_b", "model_defaults_score", "model_defaults_e_minus_b", "selene_2024_set", "selene_2024_score",
                "selene_2024_error_free", "ideal_score"])
    for cid in ids + EXT:
        r = out["circuits"][cid]
        sk = {"program": "trace fidelity", "labs": "optimum probability", "chem": "right electron numbers"}[r["kind"]]
        for s in SETMAP:
            m = r[s]["model"]; ms = m.get("trace_fidelity_rule", m.get("share", m.get("optimum_probability")))
            o2 = r[s].get("selene_2024", {})
            for v in VARIANTS:
                e = r[s].get(v)
                if not e: continue
                md = r[s]["model_defaults"][v]; mds = md.get("trace_fidelity_rule", md.get("share", md.get("optimum_probability")))
                w.writerow([cid, r["group"], r["tier"], r["qubits"], r["n2q"], r["request_shots"], s, v, e["shots"], sk, round(e["score"], 4), round(e["score_ci95"][0], 4),
                            round(e["score_ci95"][1], 4), round(e["no_fault_fraction"], 4), r[s]["model_set"], round(ms, 4), round(m["e_minus_b"], 4), round(mds, 4),
                            round(md["e_minus_b"], 4), o2.get("set", ""), "" if not o2 else round(o2["score"], 4), "" if not o2 else round(o2["no_fault_fraction"], 4),
                            r.get("ideal", {}).get("score")])
print(json.dumps({"controls": out["controls"], "angle_scaling_check": out["angle_scaling_check"],
                  "fits": {s: {sc: {v: d.get(v, {}).get("lsq_at_least_20_correct") for v in VARIANTS} for sc, d in f.items()} for s, f in out["fits"].items()},
                  "hqc": out["hqc"],
                  "admission": {k: {kk: vv for kk, vv in v.items() if kk != "fail"} for k, v in out["admission"].items()}}, indent=1))

"""Feed Quantinuum figure sets (published, and fitted from the published raw data) into the application's own error
model, without changing it, and recompute what the application quotes.

    python3 -I model_drive.py MODELS_PY EMU_BASE PKG_ROOT FITS_JSON OUT_JSON

MODELS_PY  the application's models.py (qcup-emulators/scripts/models.py, unchanged; imported, its main() not called)
EMU_BASE   the directory models.py reads (circuits/index.json and circuits/gates/)
PKG_ROOT   the application package (vendor/results/models/admission.json and predictions.json,
           vendor/results/circuits/index.json, results/targets/request.json and model.json)
FITS_JSON  output of qrb_fit.py

Every figure set is turned into a models.py device model by the rules models.py's docstring states for its two
Quantinuum models: each rzz costed on the 2023 angle line (2.9 theta/pi + 0.46)e-3 scaled by (2Q error / 1.93e-3);
one-qubit gate error = the 1Q error (leakage included); memory = transport 1Q error - 1Q error (legacy);
readout = (p_meas_0 + p_meas_1) / 2; a reset charged as a readout. Admission, the 30% point, the chemistry fidelities
and shares, HQC and the Q8 rule are recomputed by the formulas of vendor/scripts/final_request.py and
verify/delta_check.py, re-typed here."""
import importlib.util, json, math, os, random, statistics as st, sys

MODELS_PY, EMU, PKG, FITS, OUT = sys.argv[1:6]
sys.argv = [MODELS_PY, EMU]                                   # models.py reads its BASE from argv at import
spec = importlib.util.spec_from_file_location("qcup_models", MODELS_PY); qm = importlib.util.module_from_spec(spec); spec.loader.exec_module(qm)
PI = math.pi
V = os.path.join(PKG, "vendor", "results")
A = json.load(open(os.path.join(V, "models", "admission.json")))
P = json.load(open(os.path.join(V, "models", "predictions.json")))
C = json.load(open(os.path.join(V, "circuits", "index.json")))["circuits"]
TGT = json.load(open(os.path.join(PKG, "results", "targets", "request.json")))
MODEL = {r["case"]: r for r in json.load(open(os.path.join(PKG, "results", "targets", "model.json")))}
FIT = json.load(open(FITS))["dates"]


def make_model(e2q, e1q, e1q_legacy, transport, p0, p1):
    s = e2q / 1.93e-3
    f = qm.line([(0.0, 0.46e-3 * s), (PI / 2, 1.91e-3 * s)])
    ro = (p0 + p1) / 2
    return {"two": (lambda t, f=f: (f(t), "r")), "one": e1q, "readout": ro, "reset": ro, "memory": transport - e1q_legacy,
            "count_1q": "transpiled", "drop_local_rzz": True,
            "_terms": {"two_qubit_error": e2q, "angle_line_scale": s, "one_qubit_error": e1q, "one_qubit_error_legacy": e1q_legacy,
                       "transport_1q_error": transport, "memory": transport - e1q_legacy, "p_meas_0": p0, "p_meas_1": p1, "readout_and_reset": ro}}


SETS = {}
# published figures: repository spec-sheet and emulator-parameter tables (commit 59e68bb)
SETS["pub 2023-03-10 H2-1"] = make_model(1.93e-3, 2.7e-5, 2.5e-5, 2.2e-4, 9e-4, 2.2e-3)
SETS["pub 2024-05-20 H2-1"] = make_model(1.36e-3, 3.4e-5, 2.9e-5, 5.0e-4, 5e-4, 2.5e-3)
SETS["pub 2024-12-06 H2-2"] = make_model(1.4e-3, 8e-5, 7e-5, 5.3e-4, 9e-4, 1.8e-3)
# published figures: Quantinuum documentation, Performance Validation page (archived copies; live copy of 2026-11-16).
# 1Q legacy = 1Q error - 1Q leakage / 2 (the definition the repository's columns follow)
def docs(e1, l1, e2, mem, s0, s1): return make_model(e2, e1, e1 - l1 / 2, mem, s0, s1)
SETS["docs 2025-04-30 H2-1"] = docs(1.9e-5, 4.8e-6, 1.1e-3, 2.0e-4, 6.0e-4, 1.4e-3)
SETS["docs 2025-05-29 H2-2"] = docs(3.5e-5, 9.6e-6, 1.1e-3, 2.3e-4, 6.0e-4, 1.8e-3)
SETS["docs 2025-08-28 H2-2"] = docs(2.8e-5, 6.1e-6, 8.3e-4, 1.2e-4, 6.7e-4, 1.2e-3)
SETS["docs 2026-10-20 H2-1"] = docs(4.7e-5, 8.8e-6, 1.2e-3, 3.1e-4, 6.5e-4, 3.2e-3)
SETS["docs 2026-10-06 H2-2"] = docs(3.9e-5, 1.2e-5, 8.3e-4, 1.8e-4, 6.7e-4, 1.9e-3)
# our fits of the raw data
for dt, r in FIT.items():
    m = r["model_terms"]; mach, d = dt.split("/")
    SETS[f"fit {d.replace('_', '-')} {mach}"] = make_model(m["two_qubit_error"], m["one_qubit_error"], m["one_qubit_error_legacy"], m["transport_1q_error"], m["p_meas_0"], m["p_meas_1"])
    if d.startswith("2025"):
        # one bootstrap standard deviation on every fitted term at once, all against the device (+) or all for it (-)
        for sgn, lab in ((+1, "+1sd"), (-1, "-1sd")):
            sp0 = r["SPAM"]["p_meas_0_sd"]; sp1 = r["SPAM"]["p_meas_1_sd"]
            SETS[f"fit {d.replace('_', '-')} {mach} {lab}"] = make_model(
                m["two_qubit_error"] + sgn * m["two_qubit_error_sd"], m["one_qubit_error"] + sgn * m["one_qubit_error_sd"], m["one_qubit_error_legacy"],
                m["transport_1q_error"] + sgn * m["transport_1q_error_sd"], m["p_meas_0"] + sgn * sp0, m["p_meas_1"] + sgn * sp1)

# ---- budgets for every circuit under every set ----
B = {}
for cid in C:
    p = os.path.join(EMU, "circuits", "gates", f"{cid}.json")
    if not os.path.exists(p): continue
    g = json.load(open(p))["gates"]
    B[cid] = {k: qm.budget(g, M) for k, M in SETS.items()}

# positive control: the 2023 and 2024 published sets, built here, against models.py's own entries as stored in predictions.json
ctrl = {}
for mine, theirs in (("pub 2023-03-10 H2-1", "quantinuum-h2-1-2023"), ("pub 2024-12-06 H2-2", "quantinuum-h2-2-2024")):
    d = [abs(B[c][mine]["total"] - P[c][theirs]["total"]) / max(P[c][theirs]["total"], 1e-300) for c in B if c in P]
    ctrl[mine] = {"vs": theirs, "circuits": len(d), "max_relative_difference": max(d)}


def hqc(n1, n2, nm, c): return 5 + c * (n1 + 10 * n2 + 5 * nm) / 5000


def rule_fid(x, k):            # the application's rule carried over: F_rule ** (b_device / b_generic)
    return x["rule_fidelity_generic"] ** (B[x["id"]][k]["total"] / P[x["id"]]["generic"]["total"])


def keep(x, k):                # final_request.py admit() for Quantinuum rows
    return (rule_fid(x, k) if x["aim"] == 2 else B[x["id"]][k]["fidelity"]) >= 0.30


def pN(case, q):
    m = MODEL[case]; na, nb = m["electrons"]; return math.comb(m["orbitals"], na) * math.comb(m["orbitals"], nb) / 2 ** q


Q = [x for x in A if x["vendor"] == "Quantinuum"]
# control of the carried-over rule against admission.json
ctrl["rule_2023_vs_admission_json_max_abs"] = max(abs(rule_fid(x, "pub 2023-03-10 H2-1") - x["rule_fidelity_device"]) for x in Q)
ctrl["rule_2024_vs_admission_json_max_abs"] = max(abs(rule_fid(x, "pub 2024-12-06 H2-2") - x["rule_fidelity_device_alt"]) for x in Q)

ACT_IDS = {"qcup-f-tgt-" + r["case"].lower().replace("_", "-") for r in TGT["Quantinuum"]}
res = {}
for k, M in SETS.items():
    out = {"terms": M["_terms"]}
    for t in ("core", "extension"):
        L = [x for x in Q if x["tier_application"] == t]; K = [x for x in L if keep(x, k)]
        out[t] = {"requested": len(L), "kept": len(K), "hqc_kept": round(sum(hqc(x["count_n1q"] or 0, x["count_n2q"], x["spam"], x["shots"]) for x in K), 1),
                  "kept_actinide_rows": sorted(x["id"] for x in K if x["id"] in ACT_IDS)}
    for lab, f in (("all_quantinuum_rows", lambda x: True), ("aim2_programs", lambda x: x["aim"] == 2)):
        R = [x for x in Q if x["count_n2q"] > 0 and f(x)]
        out[f"n30_{lab}"] = round(-math.log(0.3) / st.median(-math.log(rule_fid(x, k)) / x["count_n2q"] for x in R), 1); out[f"n30_{lab}_rows"] = len(R)
    tm, ac = [], []
    for r in TGT["IonQ"] + TGT["Quantinuum"]:
        cid = "qcup-f-tgt-" + r["case"].lower().replace("_", "-"); q = C[cid]["qubits"]; F = B[cid][k]["fidelity"]; p = pN(r["case"], q); g = r["modelled_fidelity"]
        row = {"case": r["case"], "fidelity": F, "share": F + (1 - F) * p, "generic_share": g + (1 - g) * p}
        (ac if r in TGT["Quantinuum"] else tm).append(row)
    for lab, rows in (("transition_metal", tm), ("actinides", ac)):
        out[lab] = {"fidelity_min": min(r["fidelity"] for r in rows), "fidelity_max": max(r["fidelity"] for r in rows),
                    "share_min": min(r["share"] for r in rows), "share_max": max(r["share"] for r in rows),
                    "generic_share_min": min(r["generic_share"] for r in rows), "generic_share_max": max(r["generic_share"] for r in rows),
                    "above_30pct": sum(r["fidelity"] >= 0.30 for r in rows), "rows": rows}
    out["family_A_60"] = {x["id"]: B[x["id"]][k]["fidelity"] for x in Q if x["circuit"].startswith("A_60")}
    # core HQC as final_request.py composes it: kept core rows + the 4 actinides at 50 shots + the 8 transition-metal circuits at 200
    act_hqc = sum(hqc(r["n1q"], r["rzz"], 2 * r["qubits"], 50) for r in TGT["Quantinuum"])
    tm_hqc = 0.0
    for r in TGT["IonQ"]:
        cid = "qcup-f-tgt-" + r["case"].lower().replace("_", "-"); c = C[cid]; tm_hqc += hqc(c["n1q"], c["n2q"], 2 * c["qubits"], 200)
    core_kept = [x for x in Q if x["tier_application"] == "core" and keep(x, k)]
    core_kept_rows_hqc = sum(hqc(x["count_n1q"] or 0, x["count_n2q"], x["spam"], x["shots"]) for x in core_kept)
    dup = [x for x in core_kept if x["id"] in ACT_IDS]
    out["core_total"] = {"circuits_as_final_request": len(core_kept) + 4 + 8, "hqc_as_final_request": round(core_kept_rows_hqc + act_hqc + tm_hqc, 1),
                         "actinide_rows_also_kept_at_200_shots": len(dup),
                         "circuits_without_double_count": len(core_kept) - len(dup) + 4 + 8,
                         "hqc_without_double_count": round(core_kept_rows_hqc - sum(hqc(x["count_n1q"] or 0, x["count_n2q"], x["spam"], x["shots"]) for x in dup) + act_hqc + tm_hqc, 1),
                         "rows_hqc": round(core_kept_rows_hqc, 1), "actinide_hqc_50_shots": round(act_hqc, 1), "transition_metal_hqc": round(tm_hqc, 1)}
    # Q8 nearest-model rule, final_request.py's method and seed (reset per figure set)
    random.seed(20261115)
    def verdict(true, pub, gen, shots):
        return st.median(sum(random.random() < p for _ in range(shots)) / shots / math.sqrt(a * b) for p, a, b in zip(true, pub, gen)) > 1.0
    def power(rows, shots, N=2000):
        pub = [r["share"] for r in rows]; gen = [r["generic_share"] for r in rows]
        return {"false_alarm_if_published_true": sum(verdict(pub, pub, gen, shots) for _ in range(N)) / N,
                "power_if_generic_true": sum(verdict(gen, pub, gen, shots) for _ in range(N)) / N}
    out["q8_rule"] = {"transition_metal_200_shots": power(tm, 200), "actinides_50_shots": power(ac, 50)}
    res[k] = out
    print(f"{k:22s} 2Q {M['_terms']['two_qubit_error']:.2e} mem {M['_terms']['memory']:.2e} | N30 all {out['n30_all_quantinuum_rows']:6.1f} programs {out['n30_aim2_programs']:6.1f} | "
          f"core {out['core']['kept']}/{out['core']['requested']} {out['core']['hqc_kept']:.1f} | ext {out['extension']['kept']}/{out['extension']['requested']} {out['extension']['hqc_kept']:.1f} | "
          f"TM {out['transition_metal']['fidelity_min']:.3f}-{out['transition_metal']['fidelity_max']:.3f} | act {out['actinides']['fidelity_min']:.3f}-{out['actinides']['fidelity_max']:.3f} "
          f"(share {out['actinides']['share_min']:.3f}-{out['actinides']['share_max']:.3f}) | core total {out['core_total']['hqc_as_final_request']:.1f} ({out['core_total']['actinide_rows_also_kept_at_200_shots']} dup) | "
          f"Q8 {out['q8_rule']}", flush=True)
json.dump({"controls": ctrl, "sets": res}, open(OUT, "w"), indent=1, default=float)
print("controls:", json.dumps(ctrl))

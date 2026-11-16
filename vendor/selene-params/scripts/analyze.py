"""Score the Selene runs the application's way and set them beside the application's published-figure model.

    python3 -I analyze.py BASE PKG          (BASE = the original run folder, PKG = the final package)

Scores:
  Aim 2 programs   trace fidelity: shots whose classical bits equal the reference trace (the builder's
                   reference_bits_qiskit_order).
  family E         optimum probability: shots on a LABS ground state (labs.energies).
  chemistry        share of shots with the right electron numbers (alpha = qubits 0..n-1, beta = n..2n-1).
  every circuit    no-fault fraction: shots in which the error model applied no fault at all (its own per-shot counts):
                   the emulator's measure of the application's e^-b, "the chance the whole circuit runs with no error event".
Model (the application's, vendor/results/models/quantinuum_sets.json, figure sets "pub 2024-05-20 H2-1" and
"pub 2024-12-06 H2-2", the same machine-dates as the emulator parameter rows):
  programs         the admission rule carried over, F_rule ** (b_device / b_generic) (final_request.py rule_fid)
  family E, chem.  e^-b; predicted chemistry share F + (1 - F) pN (final_request.py chem_rows); predicted optimum
                   probability F p_ideal + (1 - F) p_uniform (the same mixing form).
30% point on the programs: the package's fit (selene_fit.py: least squares of ln F on two-qubit gate count, programs with
at least 20 correct traces) and final_request.py's median per-gate loss, on the 71 core programs and on all 115
Quantinuum Aim 2 programs (the 44 of the extension tier, to 1,995 gates, run for the fit only).
HQC: cost.py's hqc() = 5 + shots (n1q + 10 n2q + 5 spam) / 5000, as final_request.py sums it."""
import glob, json, math, os, statistics as st, sys
from collections import defaultdict
BASE, PKG = sys.argv[1], sys.argv[2]
V = os.path.join(PKG, "vendor", "results")
sys.path.insert(0, PKG)
import labs as LB

IDX = json.load(open(os.path.join(BASE, "builder", "index.json")))["circuits"]
ids = json.load(open(os.path.join(BASE, "params", "core84_ids.json")))
EXT = json.load(open(os.path.join(BASE, "params", "ext_aim2_ids.json")))      # extension-tier programs, for the fit only
A = {x["id"]: x for x in json.load(open(os.path.join(V, "models", "admission.json"))) if x["vendor"] == "Quantinuum"}
QS = json.load(open(os.path.join(V, "models", "quantinuum_sets.json")))["sets"]
PRED = json.load(open(os.path.join(V, "models", "predictions.json")))
TGT = json.load(open(os.path.join(PKG, "results", "targets", "request.json")))
MODEL = {r["case"]: r for r in json.load(open(os.path.join(PKG, "results", "targets", "model.json")))}
FR = json.load(open(os.path.join(V, "final_request.json")))
SETMAP = {"H2-1_2024-05-20": "pub 2024-05-20 H2-1", "H2-2_2024-12-06": "pub 2024-12-06 H2-2"}
ADMIT_SET = "docs 2026-10-20 H2-1"
VARIANTS = ("published", "depolarizing")
ACT = {"qcup-f-tgt-" + r["case"].lower().replace("_", "-"): r for r in TGT["Quantinuum"]}
TM = {"qcup-f-tgt-" + r["case"].lower().replace("_", "-"): r for r in TGT["IonQ"]}


def hqc(n1q, n2q, spam, shots): return 5 + shots * (n1q + 10 * n2q + 5 * spam) / 5000


def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def faults(m, variant):
    if variant == "published": return m.get("e:faults_total", 0)
    return sum(v for k, v in m.items() if k.startswith("e:errors_") or k in ("e:measurement_errors", "e:init_errors"))


def rule_fid(cid, k):
    x = A[cid]; return x["rule_fidelity_generic"] ** (QS[k]["circuits"][cid][0] / PRED[cid]["generic"]["total"])


def pN(cid):
    c = IDX[cid]; m = MODEL[c["case"]]; na, nb = m["electrons"]; q = c["qubits"]
    return math.comb(m["orbitals"], na) * math.comb(m["orbitals"], nb) / 2 ** q


# ---- load runs (chunks merged) ----
runs = defaultdict(lambda: {"bits": [], "metrics": [], "seconds": 0.0, "stats": None, "chunks": 0, "em": None})
for p in sorted(glob.glob(os.path.join(BASE, "runs", "*.json"))):
    o = json.load(open(p)); key = (o["id"], o["set"], o["variant"]); r = runs[key]
    r["bits"] += o["bits"]; r["metrics"] += o["metrics"]; r["seconds"] += o["seconds"]["run"]; r["stats"] = o["program_stats"]; r["chunks"] += 1
    r["em"] = o["error_model"]; r["rt"] = o["runtime"]

ENERGY8 = LB.energies(8)
out = {"circuits": {}, "controls": {}, "fits": {}, "admission": {}, "hqc": {}}
ctrl_fail = []
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
    # ideal positive control
    ri = runs.get((cid, "none", "ideal"))
    if ri:
        k = score(ri["bits"]); rec["ideal"] = {"shots": len(ri["bits"]), "score": k / len(ri["bits"])}
        if kind in ("program", "chem") and k != len(ri["bits"]): ctrl_fail.append((cid, "ideal", k))
    for s, mk in SETMAP.items():
        F_b = QS[mk]["circuits"][cid][1]
        model = {"e_minus_b": F_b}
        if kind == "program": model["trace_fidelity_rule"] = rule_fid(cid, mk)
        if kind == "chem": model["share"] = F_b + (1 - F_b) * rec["pN"]
        if kind == "labs": model["optimum_probability"] = F_b * c["ideal_p_gs"] + (1 - F_b) * c["uniform_p_gs"]
        rs = {"model": model}
        for v in VARIANTS:
            r = runs.get((cid, s, v))
            if not r: continue
            N = len(r["bits"]); k = score(r["bits"]); f = [faults(m, v) for m in r["metrics"]]
            nf = [b for b, x in zip(r["bits"], f) if x == 0]; knf = score(nf)
            if len(nf) and knf != len(nf) and kind in ("program", "chem"): ctrl_fail.append((cid, s, v, "no-fault shots", knf, len(nf)))
            e = {"shots": N, "score": k / N, "score_ci95": wilson(k, N), "no_fault_fraction": len(nf) / N, "no_fault_ci95": wilson(len(nf), N),
                 "mean_faults": sum(f) / N, "run_seconds": round(r["seconds"], 1), "chunks": r["chunks"]}
            if v == "published":
                agg = defaultdict(int)
                for m in r["metrics"]:
                    for kk in ("e:memory_z", "e:memory_units", "e:leak_1q", "e:leak_2q", "e:pauli_1q", "e:pauli_2q", "e:emission_xy_1q", "e:emission_xy_2q", "e:meas_flips", "e:leaked_reads", "e:crosstalk_meas", "e:gates_1q", "e:gates_2q", "e:leaked_partner", "e:skipped_gates", "e:faults_total"):
                        agg[kk[2:]] += m.get(kk, 0)
                e["per_shot"] = {kk: vv / N for kk, vv in agg.items()}
            if kind == "chem":
                e["fidelity_from_share"] = (e["score"] - rec["pN"]) / (1 - rec["pN"])
            rs[v] = e
        rec[s] = rs
    rec["program_stats"] = next((runs[(cid, s, "published")]["stats"] for s in SETMAP if (cid, s, "published") in runs), None)
    out["circuits"][cid] = rec
out["controls"]["failures"] = ctrl_fail
out["controls"]["ideal_runs"] = sum(1 for r in out["circuits"].values() if "ideal" in r)
out["controls"]["ideal_programs_all_exact"] = all(r["ideal"]["score"] == 1.0 for r in out["circuits"].values() if r["kind"] == "program" and "ideal" in r)
out["controls"]["ideal_chem_all_right_numbers"] = all(r["ideal"]["score"] == 1.0 for r in out["circuits"].values() if r["kind"] == "chem" and "ideal" in r)
lab = out["circuits"].get("qcup-e-labs8-p1", {}).get("ideal")
out["controls"]["labs8_ideal_optimum_probability"] = {"selene_200_shots": lab and lab["score"], "builder_exact": IDX["qcup-e-labs8-p1"]["ideal_p_gs"]}


# ---- fits: the 30% point on the programs ----
def lsq(pts):
    x = [float(p[0]) for p in pts]; y = [math.log(p[1]) for p in pts]; n = len(x); mx = sum(x) / n; my = sum(y) / n
    k = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sum((a - mx) ** 2 for a in x); c = my - k * mx
    r2 = 1 - sum((b - (k * a + c)) ** 2 for a, b in zip(x, y)) / sum((b - my) ** 2 for b in y)
    return {"points": n, "loss_per_two_qubit_gate_pct": round(100 * (1 - math.exp(k)), 4), "r2": round(r2, 3), "gates_at_30pct": round((math.log(0.3) - c) / k),
            "fidelity_at_zero_gates": round(math.exp(c), 4)}


def median_point(pts):
    return round(-math.log(0.3) / st.median(-math.log(f) / n for n, f in pts if n > 0 and 0 < f < 1), 1)


def fitset(progs, s, mk):
    rec = {"model_rule_lsq": lsq([(A[r["id"]]["count_n2q"], r[s]["model"]["trace_fidelity_rule"]) for r in progs]),
           "model_rule_median_per_gate": median_point([(A[r["id"]]["count_n2q"], r[s]["model"]["trace_fidelity_rule"]) for r in progs]),
           "final_request_json_aim2_programs": FR["steps"]["quantinuum_30pct_point"][mk]["aim2_programs"]}
    for v in VARIANTS:
        pts = [(A[r["id"]]["count_n2q"], r[s][v]["score"]) for r in progs if v in r[s]]
        if not pts: continue
        keep = [(n, f) for (n, f), r in zip(pts, progs) if f * r[s][v]["shots"] >= 20]
        rec[v] = {"lsq_at_least_20_correct": lsq(keep), "lsq_all_nonzero": lsq([p for p in pts if p[1] > 0]), "median_per_gate": median_point(pts),
                  "programs": len(pts)}
        # emulator against model, in -ln F (the error each predicts), per program with gates
        ratios = [math.log(r[s][v]["score"]) / math.log(r[s]["model"]["trace_fidelity_rule"]) for r in progs
                  if v in r[s] and 0 < r[s][v]["score"] < 1 and r[s]["model"]["trace_fidelity_rule"] < 1 and A[r["id"]]["count_n2q"] >= 20]
        rec[v]["median_error_ratio_selene_over_model"] = round(st.median(ratios), 3) if ratios else None
        rec[v]["programs_in_error_ratio"] = len(ratios)
    return rec


for s, mk in SETMAP.items():
    core_p = [r for r in out["circuits"].values() if r["kind"] == "program" and r["tier"] == "core"]
    all_p = [r for r in out["circuits"].values() if r["kind"] == "program"]
    out["fits"][s] = {"core_71_programs": fitset(core_p, s, mk), "all_115_quantinuum_programs": fitset(all_p, s, mk) if len(all_p) > len(core_p) else None}

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
                         "figure_kind": "trace fidelity" if r["kind"] == "program" else "no-fault fraction"})
        out["admission"][f"{s}|{v}"] = {"circuits": len(rows), "pass": sum(x["passes"] for x in rows), "fail": [x for x in rows if not x["passes"]],
                                        "interval_straddles_30pct": [x["id"] for x in rows if not x["clearly_below"] and not x["clearly_above"]],
                                        "by_group": {g: {"n": sum(1 for x in rows if x["group"] == g), "pass": sum(1 for x in rows if x["group"] == g and x["passes"]),
                                                          "min": round(min(x["figure"] for x in rows if x["group"] == g), 4), "max": round(max(x["figure"] for x in rows if x["group"] == g), 4)}
                                                     for g in ("program", "labs", "transition_metal", "actinide") if any(x["group"] == g for x in rows)}}

# ---- HQC by the package's formula ----
core72 = [cid for cid in ids if cid not in ACT and cid not in TM]
h72 = round(sum(hqc(A[c]["count_n1q"] or 0, A[c]["count_n2q"], A[c]["spam"], A[c]["shots"]) for c in core72), 1)
htm = round(sum(hqc(IDX[c]["n1q"], IDX[c]["n2q"], 2 * IDX[c]["qubits"], 200) for c in TM), 1)
hact = round(sum(hqc(r["n1q"], r["rzz"], 2 * r["qubits"], 100) for r in TGT["Quantinuum"]), 1)
out["hqc"] = {"programs_and_labs8_72_rows": h72, "transition_metal_8_at_200": htm, "actinides_4_at_100": hact, "total": round(h72 + htm + hact, 1),
              "final_request_json": FR["costs"]["per_vendor"]["Quantinuum"]["hqc"], "matches_final_request": abs(h72 + htm + hact - FR["costs"]["per_vendor"]["Quantinuum"]["hqc"]) < 0.05}
for key, adm in out["admission"].items():
    failed = {x["id"] for x in adm["fail"]}
    kept = round(sum(hqc(A[c]["count_n1q"] or 0, A[c]["count_n2q"], A[c]["spam"], A[c]["shots"]) for c in core72 if c not in failed)
                 + sum(hqc(IDX[c]["n1q"], IDX[c]["n2q"], 2 * IDX[c]["qubits"], 200) for c in TM if c not in failed) + hact, 1)
    out["hqc"]["if_failing_non_actinide_rows_dropped|" + key] = {"hqc": kept, "dropped": sorted(failed - set(ACT))}
json.dump(out, open(os.path.join(BASE, "results", "selene_results.json"), "w"), indent=1)

# ---- flat table ----
import csv
with open(os.path.join(BASE, "results", "per_circuit.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "group", "qubits", "n2q", "request_shots", "set", "variant", "shots", "score_kind", "selene_score", "ci95_lo", "ci95_hi", "no_fault_fraction",
                "model_score", "model_e_minus_b", "ideal_score"])
    for cid in ids:
        r = out["circuits"][cid]
        sk = {"program": "trace fidelity", "labs": "optimum probability", "chem": "right electron numbers"}[r["kind"]]
        for s, mk in SETMAP.items():
            m = r[s]["model"]; ms = m.get("trace_fidelity_rule", m.get("share", m.get("optimum_probability")))
            for v in VARIANTS:
                e = r[s].get(v)
                if not e: continue
                w.writerow([cid, r["group"], r["qubits"], r["n2q"], r["request_shots"], s, v, e["shots"], sk, round(e["score"], 4), round(e["score_ci95"][0], 4), round(e["score_ci95"][1], 4),
                            round(e["no_fault_fraction"], 4), round(ms, 4), round(m["e_minus_b"], 4), r.get("ideal", {}).get("score")])
print(json.dumps({"controls": out["controls"], "fits": out["fits"], "hqc": {k: v for k, v in out["hqc"].items() if not k.startswith("if_")},
                  "admission": {k: {kk: vv for kk, vv in v.items() if kk != "fail"} | {"fail": [x["id"] for x in v["fail"]]} for k, v in out["admission"].items()}}, indent=1))

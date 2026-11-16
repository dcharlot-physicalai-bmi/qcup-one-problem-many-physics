"""The hardware request as the final application states it, from result files only (writes vendor/results/final_request.json).

Changes from the revision of 15 November 2026 (each from a file in this package):
  - IBM and IQM. The first IBM device check (vendor/ibm-check) bounds the 30% point; its preregistered rule gives 117 CZ.
    Aim 1 (QAOA, Hubbard, H2, pulse-code and sampling circuits) is admitted at IBM_CAP = 117 CZ on the heavy-hex patch,
    the count the device ran (the patch circuit is placed unchanged). Aim 2 is a ladder that spans the line, so the
    fidelity law is measured on both sides: programs to LADDER_CAP = 234 CZ (twice the cap), and a program that
    measures or resets qubits mid-circuit only if the budget script's per-circuit e^-b on ibm_marrakesh is at least
    MCM_FLOOR = 0.30 (vendor/results/ibm/ladder_budget.json, by vendor/scripts/ladder_budget.py and the check's sealed
    budget.py). IQM has no device data yet: it takes the same circuits (Aim 2 in the R and P styles, as before) until
    its own device check, of the IBM design, re-sets its cap. IQM credits by IQM's Resource Calculator formula at Emerald's price (vendor/results/iqm/prices.json).
  - Quantinuum. Admission on a published figure set chosen by --qset, default H2-1 of 20 October 2026, the newest
    Quantinuum has published (vendor/results/models/quantinuum_sets.json, by vendor/scripts/quantinuum_sets.py). The
    actinide circuits are Q8's test across the line and are counted once, in step 2, at ACT_SHOTS = 100 shots; the
    re-admission of step 1 leaves them out, so a figure set that admits some of them does not count them twice.
  - IonQ unchanged.

Steps:
1. Re-admission of the trapped-ion rows of models/admission.json: kept if the figure clears 30% under the device model.
   Quantinuum: Aim 2 rows by the application's rule carried over, F_rule ** (b_device / b_generic); Aim 1 rows by
   e^-b_device. IonQ: Aim 2 held to one-step programs within the emulator's 147 two-qubit gates; rows with mid-circuit
   measurement or reset are not requested on IonQ because they could not be run under IonQ's noise model.
2. Q8's actinide circuits on Quantinuum at ACT_SHOTS, with the nearest-model rule's wrong-verdict rate by shot noise at
   50, 100 and 200 shots on every published figure set (seed 20261115, reset per set and shot count).
3. The 8 transition-metal circuits on Quantinuum at 200 shots (gate counts of the circuits built for IonQ).
4. The three identical H2 rows merged into one circuit per vendor with their shots combined.
Then IBM minutes by cost.py's timing formula (cross-checked against the device check's charged time), IQM credits by
the Resource Calculator, IonQ credits from IonQ's estimates, Quantinuum HQC by cost.py's hqc(), and totals per period.

Usage, from the package root: python3 vendor/scripts/final_request.py . [--qset "docs 2026-10-20 H2-1"]
"""
import argparse, collections, glob, json, math, os, random, statistics as st

ap = argparse.ArgumentParser()
ap.add_argument("root", nargs="?", default=".")
ap.add_argument("--qset", default="docs 2026-10-20 H2-1", help="Quantinuum figure set to admit on (a key of quantinuum_sets.json)")
ap.add_argument("--ibm-cap", type=int, default=117)
ap.add_argument("--ladder-cap", type=int, default=234)
ap.add_argument("--mcm-floor", type=float, default=0.30)
ap.add_argument("--act-shots", type=int, default=100)
args = ap.parse_args()
B = args.root; V = os.path.join(B, "vendor", "results")
QSET, IBM_CAP, LADDER_CAP, MCM_FLOOR, ACT_SHOTS = args.qset, args.ibm_cap, args.ladder_cap, args.mcm_floor, args.act_shots
def load(*p): return json.load(open(os.path.join(*p)))

A = load(V, "models", "admission.json")
C = load(V, "circuits", "index.json")["circuits"]
CC = {(r["id"], r["shots"]): r for r in load(V, "ionq", "cost_comparison.json")}
EST = {}
for r in load(V, "ionq", "estimates.json"):
    if r.get("status") == 200 and r.get("counts") == "package_counts": EST[(r["id"], r["shots"])] = r
COST = load(B, "results", "cost.json")
TGT = load(B, "results", "targets", "request.json")
MODEL = {r["case"]: r for r in load(B, "results", "targets", "model.json")}
CHEM = load(B, "results", "chem", "request.json"); CHEMC = load(B, "results", "chem", "circuits.json")
HUB = load(B, "results", "hubbard", "request.json")
LABS = load(B, "results", "labs", "request.json")
AIM1 = load(B, "results", "aim1_request.json")
AIM2REQ = load(B, "results", "aim2_request.json")
PRED = load(V, "models", "predictions.json")
QS = load(V, "models", "quantinuum_sets.json")["sets"]
LAD = load(V, "ibm", "ladder_budget.json")["ibm_marrakesh"]
LADD = load(V, "ibm", "ladder_design.json")
IQMC = load(B, "results", "iqm", "check.json")["rows"]
METRICS = load(B, "vendor", "ibm-check", "run", "raw", "metrics-dd_off.json")
assert QSET in QS, f"unknown figure set {QSET}; choose from {list(QS)}"
PUBLISHED = [k for k in QS]                     # every set in quantinuum_sets.json is a published figure set

def hqc(n1q, n2q, spam, shots): return 5 + shots * (n1q + 10 * n2q + 5 * spam) / 5000      # cost.py hqc()
def T(x): return C.get(x["id"], {}).get("T")
N30_ION_EMULATOR = 147.2      # verify/refit_ionq.json, builder's fit (21 programs at least twice the guessing floor)
ACT_IDS = {"qcup-f-tgt-" + r["case"].lower().replace("_", "-") for r in TGT["Quantinuum"]}

def qtot(cid, k): return QS[k]["circuits"][cid][0]
def qfid(cid, k): return QS[k]["circuits"][cid][1]
def rule_fid(x, k): return x["rule_fidelity_generic"] ** (qtot(x["id"], k) / PRED[x["id"]]["generic"]["total"])
# positive control: the 2023 and 2024 sets reproduce admission.json's carried-over rule
QA = [x for x in A if x["vendor"] == "Quantinuum"]
CTRL = {"rule_2023_vs_admission_json_max_abs": max(abs(rule_fid(x, "pub 2023-03-10 H2-1") - x["rule_fidelity_device"]) for x in QA),
        "rule_2024_vs_admission_json_max_abs": max(abs(rule_fid(x, "pub 2024-12-06 H2-2") - x["rule_fidelity_device_alt"]) for x in QA)}
assert max(CTRL.values()) < 1e-9, CTRL

def admit(x, k=QSET):
    if x["vendor"] == "IonQ":
        if x["ionq_mid_circuit_unsupported"]: return False
        if x["aim"] == 2: return T(x) == 1 and x["count_n2q"] <= N30_ION_EMULATOR and x["rule_fidelity_device"] >= 0.30
        return x["fidelity_device"] >= 0.30
    if x["id"] in ACT_IDS: return False          # Q8's actinide test is counted once, in step 2
    return (rule_fid(x, k) if x["aim"] == 2 else qfid(x["id"], k)) >= 0.30

def qhqc(xs): return round(sum(hqc(x["count_n1q"] or 0, x["count_n2q"], x["spam"], x["shots"]) for x in xs), 1)

out = {"note": "Every figure below is computed by this script from the files named in its docstring.",
       "parameters": {"quantinuum_figure_set": QSET, "ibm_cap_cz": IBM_CAP, "ladder_cap_cz": LADDER_CAP, "mcm_e_minus_b_floor": MCM_FLOOR, "actinide_shots": ACT_SHOTS},
       "controls": CTRL, "steps": {}}

# ---- step 1: trapped-ion re-admission ----
kept = {}
for v in ("IonQ", "Quantinuum"):
    for t in ("core", "extension"):
        L = [x for x in A if x["vendor"] == v and x["tier_application"] == t]
        kept[(v, t)] = [x for x in L if admit(x)]
        rec = {"requested_rows": len(L), "kept_rows": len(kept[(v, t)])}
        if v == "Quantinuum":
            rec["hqc_requested"] = qhqc(L); rec["hqc_kept"] = qhqc(kept[(v, t)]); rec["model"] = QSET
            rec["by_figure_set"] = {k: {"kept_rows": len([x for x in L if admit(x, k)]), "hqc_kept": qhqc([x for x in L if admit(x, k)])} for k in PUBLISHED}
        else:
            rec["credits_requested"] = round(sum(CC[(x["id"], x["shots"])]["ionq_estimate_credits"] for x in L), 1)
            rec["credits_kept"] = round(sum(CC[(x["id"], x["shots"])]["ionq_estimate_credits"] for x in kept[(v, t)]), 1)
            ms_kept = [EST[(x["id"], x["shots"])]["estimated_execution_time_ms"] for x in kept[(v, t)] if (x["id"], x["shots"]) in EST]
            rec["ionq_execution_hours_kept"] = round(sum(ms_kept) / 3.6e6, 2)
        out["steps"].setdefault("1_readmission", {})[f"{v}|{t}"] = rec
core72 = {x["id"] for x in kept[("Quantinuum", "core")]}
out["steps"]["1_readmission"]["Quantinuum|core"]["same_rows_on_every_figure_set"] = all(
    {x["id"] for x in A if x["vendor"] == "Quantinuum" and x["tier_application"] == "core" and admit(x, k)} >= core72 for k in PUBLISHED)

# ---- the 30% point on Quantinuum programs and on all its rows, per figure set (median per-gate loss of the carried-over rule) ----
n30 = {}
for k in PUBLISHED:
    rec = {}
    for lab, f in (("aim2_programs", lambda x: x["aim"] == 2), ("all_quantinuum_rows", lambda x: True)):
        R = [x for x in QA if x["count_n2q"] > 0 and f(x)]
        rec[lab] = round(-math.log(0.3) / st.median(-math.log(rule_fid(x, k)) / x["count_n2q"] for x in R), 1)
    n30[k] = rec
out["steps"]["quantinuum_30pct_point"] = n30

# ---- step 2: actinide test on Quantinuum, across the line ----
def pN(case, q):
    m = MODEL[case]; na, nb = m["electrons"]; return math.comb(m["orbitals"], na) * math.comb(m["orbitals"], nb) / 2 ** q
def chem_rows(src, k):
    rows = []
    for r in src:
        cid = "qcup-f-tgt-" + r["case"].lower().replace("_", "-"); q = C[cid]["qubits"]; F = qfid(cid, k); p = pN(r["case"], q); g = r["modelled_fidelity"]
        rows.append({"case": r["case"], "id": cid, "fidelity": F, "share": F + (1 - F) * p, "generic_share": g + (1 - g) * p})
    return rows
def q8_power(rows, shots, N=2000):
    random.seed(20261115)
    def verdict(true, pub, gen):
        return st.median(sum(random.random() < p for _ in range(shots)) / shots / math.sqrt(a * b) for p, a, b in zip(true, pub, gen)) > 1.0
    pub = [r["share"] for r in rows]; gen = [r["generic_share"] for r in rows]
    return {"false_alarm_if_published_true": sum(verdict(pub, pub, gen) for _ in range(N)) / N,
            "power_if_generic_true": sum(verdict(gen, pub, gen) for _ in range(N)) / N}
act_hqc = {s: round(sum(hqc(r["n1q"], r["rzz"], 2 * r["qubits"], s) for r in TGT["Quantinuum"]), 1) for s in (50, 100, 200)}
act_by_set = {}
for k in PUBLISHED:
    rows = chem_rows(TGT["Quantinuum"], k)
    act_by_set[k] = {"fidelity": [round(min(r["fidelity"] for r in rows), 4), round(max(r["fidelity"] for r in rows), 4)],
                     "share": [round(min(r["share"] for r in rows), 4), round(max(r["share"] for r in rows), 4)],
                     "above_30pct": sum(r["fidelity"] >= 0.30 for r in rows),
                     "q8_rule": {f"{s}_shots": q8_power(rows, s) for s in (50, 100, 200)}}
gen_act = chem_rows(TGT["Quantinuum"], QSET)
out["steps"]["2_actinide_test"] = {"shots": ACT_SHOTS, "hqc_total": act_hqc[ACT_SHOTS], "hqc_by_shots": act_hqc,
    "circuits": [{"case": r["case"], "fidelity": round(r["fidelity"], 4), "share": round(r["share"], 4), "generic_share": round(r["generic_share"], 4)} for r in gen_act],
    "generic_share": [round(min(r["generic_share"] for r in gen_act), 4), round(max(r["generic_share"] for r in gen_act), 4)],
    "by_figure_set": act_by_set,
    "max_false_alarm_over_published_sets": {f"{s}_shots": max(act_by_set[k]["q8_rule"][f"{s}_shots"]["false_alarm_if_published_true"] for k in PUBLISHED) for s in (50, 100, 200)}}

h2 = next(a for a in A if a["vendor"] == "IonQ" and a["circuit"] == "H2 eq")
out["steps"]["2_h2_prediction_ionq"] = {"fidelity_published_figures_e_minus_b": round(h2["fidelity_device"], 4),
    "predicted_share_with_chance": round(h2["fidelity_device"] + (1 - h2["fidelity_device"]) * 4 / 16, 4)}

# ---- step 3: transition-metal circuits on Quantinuum ----
tm_hqc = 0.0; tm_by_set = {}
for r in TGT["IonQ"]:
    c = C["qcup-f-tgt-" + r["case"].lower().replace("_", "-")]; tm_hqc += hqc(c["n1q"], c["n2q"], 2 * c["qubits"], 200)
tm_hqc = round(tm_hqc, 1)
for k in PUBLISHED:
    rows = chem_rows(TGT["IonQ"], k)
    tm_by_set[k] = {"fidelity": [round(min(r["fidelity"] for r in rows), 4), round(max(r["fidelity"] for r in rows), 4)],
                    "share": [round(min(r["share"] for r in rows), 4), round(max(r["share"] for r in rows), 4)],
                    "above_30pct": sum(r["fidelity"] >= 0.30 for r in rows)}
tm_rows = chem_rows(TGT["IonQ"], QSET)
out["steps"]["3_transition_metal_on_quantinuum"] = {"hqc_total": tm_hqc, "by_figure_set": tm_by_set,
    "generic_share": [round(min(r["generic_share"] for r in tm_rows), 4), round(max(r["generic_share"] for r in tm_rows), 4)],
    "q8_rule_200_shots": q8_power(tm_rows, 200)}
fa60 = {k: [round(qfid(x["id"], k), 4) for x in QA if x["circuit"].startswith("A_60")] for k in PUBLISHED}
out["steps"]["family_A_60_fidelity"] = fa60

# ---- step 4: identical H2 rows merged ----
h2_rows = {v: [r for r in CHEM[v] if r["case"].startswith("H2 ")] for v in ("IonQ", "IBM", "IQM")}
merged = {v: {"rows_before": len(rs), "circuits_after": 1, "shots_after": sum(r["shots"] for r in rs)} for v, rs in h2_rows.items()}
out["steps"]["4_h2_merged"] = merged

# ---- IBM and IQM, Aim 1: admitted at IBM_CAP on the heavy-hex patch ----
CI = []
for pth in sorted(glob.glob(os.path.join(B, "results", "post_*.json"))):
    d = json.load(open(pth)); CI += [(d["family"], d["n"], d["seed"], t["p"], t["heavy_hex_cz"]) for t in d["transpile"]]
for d in load(B, "results", "scale_post.json"): CI += [(d["family"], d["n"], d["seed"], t["p"], t["heavy_hex_cz"]) for t in d["transpile"]]
def qaoa_sel(cap): return [c for c in CI if c[1] <= 156 and c[4] <= cap and not (c[0] == "B" and c[1] > 20 and c[3] > 1)]
def ibm_count(cap): return 2 * len(qaoa_sel(cap))
out["steps"]["ibm_aim1_qaoa_at_caps"] = {str(cap): ibm_count(cap) for cap in (660, 415, 284, 258, 234, 224, 117)}
sel = qaoa_sel(IBM_CAP)
hh = lambda f, n, p: next(c[4] for c in CI if c[0] == f and c[1] == n and c[2] == 0 and c[3] == p)
SAMPLING_CZ = {f"B{n}_p{p}": hh("B", n, p) for n in (12, 16) for p in (1, 2)}     # Q7: the seed-0 B12 and B16 instances, depths 1 and 2, TVD-tuned angles; counted as that instance's QAOA circuit
H2_CZ = next(c["heavy_hex_cz"] for c in CHEMC if c["system"] == "H2")
def sc_aim1(vendor, cap, shots, h2_shots):
    q = qaoa_sel(cap)
    hub = [r for r in HUB[vendor] if r["cz"] <= cap]
    labs = [r for r in LABS["superconducting"] if r["heavy_hex_cz"] <= cap]
    samp = [k for k, cz in SAMPLING_CZ.items() if cz <= cap]
    h2n = 1 if H2_CZ <= cap else 0
    groups = {"qaoa": (2 * len(q), shots), "hubbard": (len(hub), shots), "pulse_code": (len(labs), shots), "sampling_q7": (len(samp), shots), "h2_merged": (h2n, h2_shots)}
    qubits = [c[1] for c in q] + [2 * int(r["lattice"].split("x")[0]) * int(r["lattice"].split("x")[1]) for r in hub] + ([4] if h2n else []) + [8 for _ in labs] + [int(k[1:3]) for k in samp]
    return {"groups": {g: {"circuits": n, "shots_per_circuit": s, "shots": n * s} for g, (n, s) in groups.items()},
            "circuits": sum(n for n, s in groups.values()), "shots": sum(n * s for n, s in groups.values()), "qubits": [min(qubits), max(qubits)],
            "hubbard_lattices": sorted({(r["lattice"], r["p"]) for r in hub})}
ibm_a1 = sc_aim1("IBM", IBM_CAP, 4000, merged["IBM"]["shots_after"])
iqm_a1 = sc_aim1("IQM", IBM_CAP, 2000, merged["IQM"]["shots_after"])
# IQM's own device-model counts for the same QAOA circuits (results/iqm/check.json)
iq = {(r["family"], r["n"], r["seed"], r["p"]): r for r in IQMC}
sel_iqm = [iq[(c[0], c[1], c[2], c[3])] for c in sel if (c[0], c[1], c[2], c[3]) in iq]
out["steps"]["iqm_device_model_counts_of_admitted_qaoa"] = {"distinct_circuits": len(sel_iqm), "of": len(sel),
    "iqm_cz_max": max(r["iqm_cz"] for r in sel_iqm), "within_cap_on_iqm_model": sum(r["iqm_cz"] <= IBM_CAP for r in sel_iqm),
    "median_ratio_iqm_to_heavy_hex": round(st.median(r["iqm_cz"] / r["heavy_hex_cz"] for r in sel_iqm), 3),
    "qaoa_at_cap_by_iqm_counts": 2 * sum(1 for r in IQMC if r["iqm_cz"] <= IBM_CAP)}

# ---- IBM and IQM, Aim 2: the ladder ----
a2 = [r for p in sorted(glob.glob(os.path.join(B, "results", "aim2", "*.json"))) for r in json.load(open(p))]
streams = collections.defaultdict(set)
for r in a2: streams[r["form"]].add(r["stream"])
meta = {m["id"]: m for m in LADD["circuits"]}
def lid(r): return f"a2-{r['form']}-{r['style']}{r['T']}".lower().replace("_", "-")
def mcm(r): m = meta.get(lid(r)); return m is not None and (m["mid_circuit_measurements"] > 0 or m["resets"] > 0)
s0 = [r for r in a2 if r["stream"] == 0]
def ladder(styles, cap=LADDER_CAP, floor=MCM_FLOOR):
    rows = [r for r in s0 if r["style"] in styles and r["sc_like"]["two_qubit_gates"] <= cap]
    keep, drop = [], []
    for r in rows:
        if r["T"] >= 2 and r["style"] in "RP":
            assert lid(r) in meta, f"{lid(r)}: a mid-circuit program with no placement"
            (keep if LAD[lid(r)]["e_minus_b_script"] >= floor else drop).append(r)
        else: keep.append(r)
    n = lambda xs: sum(len(streams[r["form"]]) for r in xs)
    allrows = [x for x in a2 if any(x["form"] == r["form"] and x["style"] == r["style"] and x["T"] == r["T"] for r in keep)]
    return {"rows": len(keep), "circuits": n(keep), "dropped_rows": [lid(r) for r in drop], "dropped_circuits": n(drop),
            "mcm_rows_kept": sum(1 for r in keep if r["T"] >= 2 and r["style"] in "RP"), "mcm_circuits_kept": n([r for r in keep if r["T"] >= 2 and r["style"] in "RP"]),
            "circuits_above_ibm_cap": n([r for r in keep if r["sc_like"]["two_qubit_gates"] > IBM_CAP]),
            "qubits": [min(r["qubits"] for r in keep), max(r["qubits"] for r in keep)],
            "mean_sc_depth_all_streams": round(float(st.mean(x["sc_like"]["depth"] for x in allrows)), 1),
            "not_embedded_on_device_as_counted": [x["id"] for x in LADD.get("not_embedded", []) if any(lid(r) == x["id"] for r in keep)]}
ibm_a2 = ladder("GRP"); iqm_a2 = ladder("RP")
lad_e = {lid(r): round(LAD[lid(r)]["e_minus_b_script"], 3) for r in s0 if lid(r) in LAD and r["T"] >= 2 and r["style"] in "RP" and r["sc_like"]["two_qubit_gates"] <= LADDER_CAP}
out["steps"]["ibm_aim2_ladder"] = {"IBM": ibm_a2, "IQM": iqm_a2, "mcm_e_minus_b": lad_e,
    "before_at_660": {"IBM": next(r for r in AIM2REQ if r["vendor"] == "IBM")["circuits"], "IQM": next(r for r in AIM2REQ if r["vendor"] == "IQM")["circuits"]}}

# ---- IBM minutes: cost.py's formula; cross-check: the check's charged QPU time per shot (DD-off arm) ----
it = COST["ibm_time_estimate"]
def ibm_minutes(a1_shots, a2_shots, a2_depth):
    return round((a1_shots * (it["assumed_repetition_delay_s"] + it["aim1_assumed_depth"] * it["assumed_seconds_per_depth_layer"])
                  + a2_shots * (it["assumed_repetition_delay_s"] + a2_depth * it["assumed_seconds_per_depth_layer"])) / 60, 1)
ibm_a2_shots = ibm_a2["circuits"] * 1000
check_rate = METRICS["usage"]["qpu_charge_time_seconds"] / 42000         # 42,000 shots per arm (prereg.txt)
ibm = {"minutes_cost_py_formula": ibm_minutes(ibm_a1["shots"], ibm_a2_shots, ibm_a2["mean_sc_depth_all_streams"]),
       "minutes_at_check_charge_rate": round((ibm_a1["shots"] + ibm_a2_shots) * check_rate / 60, 1),
       "check_charge_seconds_per_42000_shots": METRICS["usage"]["qpu_charge_time_seconds"],
       "minutes_before": ibm_minutes(2492000, 655000, it["aim2_mean_depth_admitted"])}

# ---- IQM credits: IQM's Resource Calculator (iqmacademy.com/qpu/resourceCalculator/, the page's own formula), Emerald 0.75/s ----
PRICES = {c["alias"]: c for c in load(V, "iqm", "prices.json")["computers"]}          # IQM Resonance price list as read on 16 Nov 2026
RATE, MAXC = float(PRICES["emerald"]["pricing"]["payg_price_per_second"]), PRICES["emerald"]["limits"]["max_circuits_per_job"]
def calc(J, Cn, S, discount=True):
    f = 0.948749148221405 ** min(J, 10) if discount else 1.0
    return f * J * Cn * (0.022 + 0.00041 * S + 0.000301 * S) + 3.8
def entries(groups):               # groups: list of (circuits, shots); jobs of at most 100 circuits per shot count
    by = collections.Counter()
    for n, s in groups: by[s] += n
    e = []
    for S, Cn in sorted(by.items()):
        full, rest = divmod(Cn, MAXC)
        if full: e.append((full, MAXC, S))
        if rest: e.append((1, rest, S))
    return e
def credits(groups, discount):
    return round(sum(calc(J, Cn, S, discount) for J, Cn, S in entries(groups)) * RATE, 1)
iqm_groups_a1 = [(g["circuits"], g["shots_per_circuit"]) for g in iqm_a1["groups"].values() if g["circuits"]]
iqm_groups_a2 = [(iqm_a2["circuits"], 1000)]
check_groups = [(18, 1000), (6, 4000)]          # the IBM check's design: 16 programs and 2 controls at 1,000 shots, 6 QAOA circuits at 4,000; per arm
iqm = {"provisional_set_undiscounted": credits(iqm_groups_a1 + iqm_groups_a2, False),
       "provisional_set_as_entered_jobs_of_100": credits(iqm_groups_a1 + iqm_groups_a2, True),
       "provisional_aim1_undiscounted": credits(iqm_groups_a1, False), "provisional_aim2_undiscounted": credits(iqm_groups_a2, False),
       "device_check_two_arms_undiscounted": round(2 * sum(calc(1, Cn, S, False) for Cn, S in check_groups) * RATE, 1),
       "before_undiscounted": credits([(588, 2000), (26, 2000), (2, 2000), (4, 2000), (1, 6000), (335, 1000)], False),
       "default_credits_new_project": 400, "emerald_rate_credits_per_second": RATE, "max_circuits_per_job": MAXC}
iqm["check_plus_provisional_undiscounted"] = round(iqm["device_check_two_arms_undiscounted"] + iqm["provisional_set_undiscounted"], 1)

# ---- the table ----
ion_core = kept[("IonQ", "core")]; qtm_core = kept[("Quantinuum", "core")]
def qrange(xs): q = [x["count_qubits"] for x in xs]; return [min(q), max(q)]
ion_a1 = [x for x in ion_core if x["aim"] == 1]; ion_a2 = [x for x in ion_core if x["aim"] == 2]
qtm_a1 = [x for x in qtm_core if x["aim"] == 1]; qtm_a2 = [x for x in qtm_core if x["aim"] == 2]
act_q = [r["qubits"] for r in TGT["Quantinuum"]]; tm_q = [C["qcup-f-tgt-" + r["case"].lower().replace("_", "-")]["qubits"] for r in TGT["IonQ"]]
table = [
    {"aim": 1, "vendor": "IBM", "qubits": ibm_a1["qubits"], "circuits": ibm_a1["circuits"], "shots_per_circuit": "4,000 (12,000 for H2)", "total_shots": ibm_a1["shots"]},
    {"aim": 1, "vendor": "IQM", "qubits": iqm_a1["qubits"], "circuits": iqm_a1["circuits"], "shots_per_circuit": "2,000 (6,000 for H2)", "total_shots": iqm_a1["shots"]},
    {"aim": 1, "vendor": "IonQ", "qubits": qrange(ion_a1), "circuits": len(ion_a1) - merged["IonQ"]["rows_before"] + 1, "total_shots": sum(x["shots"] for x in ion_a1)},
    {"aim": 1, "vendor": "Quantinuum", "qubits": [min(qrange(qtm_a1)[0], min(act_q + tm_q)), max(qrange(qtm_a1)[1], max(act_q + tm_q))],
     "circuits": len(qtm_a1) + len(TGT["Quantinuum"]) + len(TGT["IonQ"]), "shots_per_circuit": f"200 ({ACT_SHOTS} for actinides)",
     "total_shots": sum(x["shots"] for x in qtm_a1) + ACT_SHOTS * len(TGT["Quantinuum"]) + 200 * len(TGT["IonQ"])},
    {"aim": 2, "vendor": "IBM", "qubits": ibm_a2["qubits"], "circuits": ibm_a2["circuits"], "shots_per_circuit": "1,000", "total_shots": ibm_a2_shots},
    {"aim": 2, "vendor": "IQM", "qubits": iqm_a2["qubits"], "circuits": iqm_a2["circuits"], "shots_per_circuit": "1,000", "total_shots": iqm_a2["circuits"] * 1000},
    {"aim": 2, "vendor": "IonQ", "qubits": qrange(ion_a2), "circuits": len(ion_a2), "total_shots": sum(x["shots"] for x in ion_a2)},
    {"aim": 2, "vendor": "Quantinuum", "qubits": qrange(qtm_a2), "circuits": len(qtm_a2), "total_shots": sum(x["shots"] for x in qtm_a2)},
]
out["table"] = table
out["totals"] = {"circuits": sum(r["circuits"] for r in table), "shots": sum(r["total_shots"] for r in table)}
out["totals_before"] = {"circuits": 2380, "shots": 4778700, "from": "the revision of 15 November 2026 (its final_request.json)"}

# ---- costs, per vendor and per period ----
ion_core_credits = round(sum(CC[(x["id"], x["shots"])]["ionq_estimate_credits"] for x in ion_core), 1)
qtm_core_hqc = round(qhqc(qtm_core) + act_hqc[ACT_SHOTS] + tm_hqc, 1)
r1 = out["steps"]["1_readmission"]
per_vendor = {
    "IBM": {"circuits": ibm_a1["circuits"] + ibm_a2["circuits"], "shots": ibm_a1["shots"] + ibm_a2_shots, **ibm},
    "IQM": {"circuits": iqm_a1["circuits"] + iqm_a2["circuits"], "shots": iqm_a1["shots"] + iqm_a2["circuits"] * 1000, **iqm},
    "IonQ": {"circuits": table[2]["circuits"] + table[6]["circuits"], "credits": ion_core_credits, "execution_hours": r1["IonQ|core"]["ionq_execution_hours_kept"],
             "two_qubit_gate_shots": sum(x["shots"] * x["count_n2q"] for x in ion_core), "credits_as_first_requested": r1["IonQ|core"]["credits_requested"]},
    "Quantinuum": {"circuits": len(qtm_core) + len(TGT["Quantinuum"]) + len(TGT["IonQ"]), "hqc": qtm_core_hqc, "hqc_readmitted_rows": qhqc(qtm_core),
                   "hqc_transition_metal": tm_hqc, "hqc_actinides": act_hqc[ACT_SHOTS], "hqc_as_first_requested": r1["Quantinuum|core"]["hqc_requested"],
                   "hqc_before": 4309.3, "figure_set": QSET},
}
out["costs"] = {"per_vendor": per_vendor,
    "period_1_core": {"IBM_minutes": ibm["minutes_cost_py_formula"], "IQM_credits": iqm["check_plus_provisional_undiscounted"], "IonQ_credits": ion_core_credits, "Quantinuum_hqc": qtm_core_hqc,
                      "circuits": out["totals"]["circuits"], "shots": out["totals"]["shots"]},
    "period_2_extension_if_midterm_passes": {"circuits": r1["IonQ|extension"]["kept_rows"] + r1["Quantinuum|extension"]["kept_rows"],
                      "ionq_circuits": r1["IonQ|extension"]["kept_rows"], "IonQ_credits": r1["IonQ|extension"]["credits_kept"],
                      "quantinuum_circuits": r1["Quantinuum|extension"]["kept_rows"], "Quantinuum_hqc": r1["Quantinuum|extension"]["hqc_kept"],
                      "shots": sum(x["shots"] for x in kept[("IonQ", "extension")] + kept[("Quantinuum", "extension")])}}
out["steps"]["ibm_aim1"] = ibm_a1; out["steps"]["iqm_aim1"] = iqm_a1
json.dump(out, open(os.path.join(V, "final_request.json"), "w"), indent=1)
print(json.dumps({"table": table, "totals": out["totals"], "costs": out["costs"], "controls": CTRL}, indent=1))

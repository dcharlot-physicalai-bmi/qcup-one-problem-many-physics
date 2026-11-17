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
    actinide circuits are Q8's test across the line and are counted once, in step 2, at ACT_SHOTS shots (100 until the
    review round; now set by Q8's range rule, 150); the
    re-admission of step 1 leaves them out, so a figure set that admits some of them does not count them twice.
  - IonQ unchanged.

Changes of 17 November 2026 (review round; package v1.0.2):
  - IBM Aim 1 QAOA shots (Q1 and Q2 count only circuits with at least Q12_TARGET = 20 expected successes). A circuit
    whose ideal optimum probability times the device check's measured retention times 4,000 shots falls short of 20 gets
    the shots that reach 20, rounded up to SHOT_STEP = 1,000, but only if its ideal success is at least FLOOR_MULT = 2
    times a uniformly random guess's (n_ground / 2^n; 1/4096 on these 12-qubit, one-optimum problems): circuits nearer
    the guessing floor stay at 4,000 shots and serve Q3 alone (after an independent check of the
    application, 17 November 2026). `shots_without_floor_rule` records what the rule without the floor gave. The retention is the check's QAOA circuit nearest the cap
    (a1-b12-p1-warm, 130 CZ: measured / ideal optimum probability, vendor/ibm-check/rescore/out/rescore_device.json over
    predictions.json). IBM's documented limits (quantum.cloud.ibm.com/docs/en/guides/job-limits, read 17 November 2026):
    at most 10 million executions (circuits times shots) per Sampler job, per job and not per PUB; at most 3 hours of QPU
    time per job (guides/max-execution-time); OLCF's default 400 minutes per 28 days. The raised shots are split into
    jobs under those limits; the minutes are recomputed at cost.py's formula and at the check's charged rate. IQM keeps
    2,000 shots; its circuits short of 20 serve Q3 alone.
  - Figures the revised text quotes, recomputed here: the IBM circuits short of 20 expected successes; Q1 and Q2
    eligibility per vendor; IonQ's emulator coverage of the 64 requested circuits; the composition of period 2 and its
    HQC over the eight published sets; family C at 60 variables admitted only in the extension; the ladder's
    mid-circuit programs under the check's excess over the budget script (vendor/ibm-check/derived/derived.json); the
    kept IonQ QAOA rows that fall below 0.30 on the emulator; Q1's scored circuits and Q2's eligible instances under the
    guessing-floor rule (both circuits >= 20 expected successes and >= twice a random guess's success); what separates step
    count, gate count and mid-circuit measurement in the Aim 2 ladder (Q5); the recorded reason, and the stored files,
    behind each IonQ circuit not emulated.
  - Q8's bands (after the Selene runs under Quantinuum's 2025 emulator defaults, vendor/selene-2025/): the two groups are
    decided separately, the 8 transition-metal circuits at 200 shots within a factor of Q8_BAND_TM = 1.25, the 4 actinide
    circuits at ACT_SHOTS within Q8_BAND_ACT = 1.5. q8_power() now also reports, from the same draws (seed 20261115 reset
    per call, 2,000 draws with the published shares as the truth and then 2,000 with the generic shares), how often shot
    noise alone rejects both predictions at the group's band (the median over circuits of measured over nearer predicted
    share outside [1/band, band]) and the wrong-verdict rate with the generic shares as the truth. Every earlier key keeps
    its value; the draws are the same, so the verdict rates repeat (asserted). The transition-metal circuits are also
    scored on every published set (`by_figure_set[*].q8_rule_200_shots`), and `steps.q8_bands` holds the maxima.
  - Q8's range design (decisions 45, 49 and 50, after an independent check of the Selene 2025 round): each prediction is a
    range over the circuit's count-keeping term k (k_min to k_max over the six Selene settings, read from
    vendor/selene-2025/results/selene_results.json), with a verdict only when the group's median range gap is at least G,
    G found where shot noise alone first gives a wrong verdict in more than 1% of draws, and the smallest listed band with
    rejection at most 1% (`steps.q8_ranges`; the block before step 2 says how). It sets the actinide shots: 150, the
    smallest of 100, 150 and 200 at which the admitted figures get a verdict. Every earlier key keeps its value except
    those that follow the actinide shots (parameters.actinide_shots, step 2's shots and HQC, the Quantinuum table row,
    costs and totals); the point-prediction summary `steps.q8_bands` stays at its recorded 100 shots, and
    `hqc_by_shots` gains 150.

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
import argparse, bisect, collections, glob, json, math, os, random, statistics as st

ap = argparse.ArgumentParser()
ap.add_argument("root", nargs="?", default=".")
ap.add_argument("--qset", default="docs 2026-10-20 H2-1", help="Quantinuum figure set to admit on (a key of quantinuum_sets.json)")
ap.add_argument("--ibm-cap", type=int, default=117)
ap.add_argument("--ladder-cap", type=int, default=234)
ap.add_argument("--mcm-floor", type=float, default=0.30)
ap.add_argument("--act-shots", type=int, default=None, help="actinide shots; default: the smallest Q8 range-rule count at which the admitted figures get a verdict")
ap.add_argument("--q12-target", type=int, default=20, help="expected successes an IBM QAOA circuit is raised to (0 keeps 4,000 shots)")
ap.add_argument("--shot-step", type=int, default=1000)
ap.add_argument("--floor-mult", type=float, default=2.0, help="raise only circuits whose ideal success is at least this many times a random guess's")
ap.add_argument("--q8-band-tm", type=float, default=1.25, help="Q8: factor within which the nearer prediction must lie, transition-metal circuits")
ap.add_argument("--q8-band-act", type=float, default=1.5, help="Q8: factor within which the nearer prediction must lie, actinide circuits")
ap.add_argument("--q8-g-tm", type=float, default=1.065, help="Q8 range rule: frozen minimum gap G, transition-metal circuits (derived on 17 November 2026; a new --qset does not move it)")
ap.add_argument("--q8-g-act", type=float, default=1.193, help="Q8 range rule: frozen minimum gap G, actinide circuits")
ap.add_argument("--q8-precise-draws", type=int, default=40000, help="draws for the 40,000-draw precision estimates of Q8 (0 skips them)")
ap.add_argument("--out", default=None, help="output path (default vendor/results/final_request.json)")
args = ap.parse_args()
Q8_BAND_TM, Q8_BAND_ACT = args.q8_band_tm, args.q8_band_act
B = args.root; V = os.path.join(B, "vendor", "results")
QSET, IBM_CAP, LADDER_CAP, MCM_FLOOR, ACT_SHOTS = args.qset, args.ibm_cap, args.ladder_cap, args.mcm_floor, args.act_shots
Q12_TARGET, SHOT_STEP, FLOOR_MULT = args.q12_target, args.shot_step, args.floor_mult
IBM_MAX_EXECUTIONS_PER_JOB, IBM_MAX_JOB_SECONDS, OLCF_IBM_MINUTES = 10_000_000, 3 * 3600, 400     # IBM job limits; OLCF ibm_quantum.html
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
       "parameters": {"quantinuum_figure_set": QSET, "ibm_cap_cz": IBM_CAP, "ladder_cap_cz": LADDER_CAP, "mcm_e_minus_b_floor": MCM_FLOOR, "actinide_shots": ACT_SHOTS,
                      "ibm_qaoa_target_expected_successes": Q12_TARGET, "ibm_qaoa_shot_step": SHOT_STEP, "ibm_qaoa_floor_multiple": FLOOR_MULT,
                      "q8_band_transition_metal": Q8_BAND_TM, "q8_band_actinide": Q8_BAND_ACT},
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

# ---- Q8 with range predictions (decisions 45, 49 and 50; package v1.0.2) ----
# A shot with an error can still keep the right electron numbers. On Selene under Quantinuum's 2025 emulator defaults
# (vendor/selene-2025/results/selene_results.json) the fraction that did, k = (share - error-free) / (1 - error-free), is
# read per chemistry circuit on each of the six settings (H2-1E, H2-2E, Helios-1E; dephasing left out, and at the assumed
# 71 ms per two-qubit layer). Each prediction is then a range over the circuit's k_min to k_max, the same for both:
# published [F + (1 - F) k_min, F + (1 - F) k_max] with F the figure set's e^-b, generic [g + (1 - g) k_min, ...] with g
# the generic law's modelled fidelity. Rule, per group (the 8 transition-metal circuits, the 4 actinide circuits):
#   verdict    per circuit the log distance from the measured share to each range (0 inside it); the published figures
#              win if the median over the group's circuits of (distance to the generic range - distance to the published
#              range) is positive, the generic law otherwise;
#   no verdict the group's gap, the median over its circuits of (generic range's lower end / published range's upper end),
#              must be at least G; below it the two are reported as indistinguishable and only the band test applies;
#   band       both are rejected if the median over the group's circuits of the distance to the winning range exceeds
#              log(band).
# G per group and shot count: the published F is moved from the admitted figures toward the generic law,
# F(t) = F_adm + t (g - F_adm) (t < 0 moves it away; F kept at 0 or above), and the worst wrong-verdict rate W(t) over k at
# k_min, k_median and k_max and both truths (the published figures F(t), and the generic law, each with that k) is found
# by bisection on t to 1/1024; G is the group's gap at the last t with W <= Q8R_CEILING. Shots: 200 for the
# transition-metal circuits; for the actinides the smallest of 100, 150 and 200 at which the admitted figures' gap is at
# least G (this sets ACT_SHOTS unless --act-shots is given). Band: the smallest listed value whose rejection rate, over
# the eight published sets as the truth (each with k at k_min, k_median and k_max, and the generic law likewise), is at
# most Q8R_CEILING. Draws: Bernoulli shots, seed 20261115 reset per case, Q8R_DRAWS draws. H2 keeps its chance term.
SR2025 = load(B, "vendor", "selene-2025", "results", "selene_results.json")["circuits"]
Q8R_SETTINGS = [(s, v) for s in ("H2-1E_2025-07-16", "H2-2E_2025-07-16", "Helios-1E_2025-11-18") for v in ("docs", "docs_dephasing")]
Q8R_GROUPS = {"transition_metal": TGT["IonQ"], "actinide": TGT["Quantinuum"]}
Q8R_SHOT_OPTIONS = {"transition_metal": (200,), "actinide": (100, 150, 200)}
Q8R_BANDS = {"transition_metal": (1.25, 1.3, 1.35, 1.5), "actinide": (1.5, 1.6, 1.75, 2.0)}
Q8R_CEILING, Q8R_DRAWS, Q8R_LEVELS = 0.01, 2000, ("k_min", "k_median", "k_max")
def chem_id(case): return "qcup-f-tgt-" + case.lower().replace("_", "-")
def k_keep(x): return (x["score"] - x["no_fault_fraction"]) / (1 - x["no_fault_fraction"])
KR = {}
for _src in Q8R_GROUPS.values():
    for r in _src:
        c = chem_id(r["case"]); ks = {f"{s}|{v}": k_keep(SR2025[c][s][v]) for s, v in Q8R_SETTINGS}
        KR[c] = {"case": r["case"], "k_by_setting": ks, "k_min": min(ks.values()), "k_median": st.median(ks.values()), "k_max": max(ks.values())}
def q8r_rows(src, Fs):
    out_ = []
    for r, F in zip(src, Fs):
        c = chem_id(r["case"]); g = r["modelled_fidelity"]; a, b = KR[c]["k_min"], KR[c]["k_max"]
        out_.append({"case": r["case"], "id": c, "F": F, "g": g, "pub": (F + (1 - F) * a, F + (1 - F) * b), "gen": (g + (1 - g) * a, g + (1 - g) * b)})
    return out_
def q8r_F(src, k): return [qfid(chem_id(r["case"]), k) for r in src]
# G is derived once, along a path that starts at the figures admitted on when it was frozen (H2-1, 20 October 2026), so a
# new --qset recomputes F and the ranges but moves neither G nor the derivation; the rule uses the frozen G (check 4, N4).
Q8R_DERIVATION_SET = "docs 2026-10-20 H2-1"
Q8R_G_FROZEN = {"transition_metal": args.q8_g_tm, "actinide": args.q8_g_act}
def q8r_Ft(src, t): return [max(0.0, F + t * (r["modelled_fidelity"] - F)) for F, r in zip(q8r_F(src, Q8R_DERIVATION_SET), src)]
def q8r_gap(rs): return st.median(r["gen"][0] / r["pub"][1] for r in rs)
def q8r_dist(o, lo, hi):            # log distance from a share to a range, 0 inside it
    if lo <= o <= hi: return 0.0
    if o <= 0: return math.inf
    return math.log(lo / o) if o < lo else math.log(o / hi)
def q8r_verdict(obs, rs):           # (published wins, median distance to the winning range); a share of 0 sits below both ranges
    diffs = [math.log(r["gen"][0] / r["pub"][0]) if o <= 0 else q8r_dist(o, *r["gen"]) - q8r_dist(o, *r["pub"]) for o, r in zip(obs, rs)]
    pub_wins = st.median(diffs) > 0
    return pub_wins, st.median(q8r_dist(o, *(r["pub"] if pub_wins else r["gen"])) for o, r in zip(obs, rs))
def q8r_sim(true, rs, shots, bands):
    random.seed(20261115); pw = 0; rej = {b: 0 for b in bands}
    for _ in range(Q8R_DRAWS):
        obs = [sum(random.random() < p for _ in range(shots)) / shots for p in true]
        w, d = q8r_verdict(obs, rs); pw += w
        for b in bands: rej[b] += d > math.log(b)
    return {"published_wins": pw / Q8R_DRAWS, "published_wins_count": pw, "rejected_both": {str(b): rej[b] / Q8R_DRAWS for b in bands}}
def q8r_truth(rs, which, level): return [(r["F"] if which == "published" else r["g"]) + (1 - (r["F"] if which == "published" else r["g"])) * KR[r["id"]][level] for r in rs]
def q8r_worst(rs, shots, bands=()):
    w, at, rej = 0.0, None, {str(b): 0.0 for b in bands}
    for level in Q8R_LEVELS:
        for which in ("published", "generic"):
            x = q8r_sim(q8r_truth(rs, which, level), rs, shots, bands)
            wv = ((Q8R_DRAWS - x["published_wins_count"]) if which == "published" else x["published_wins_count"]) / Q8R_DRAWS   # from counts: 20 of 2,000 is 1%
            if at is None or wv > w: w, at = wv, f"{level}|{which}"
            for b in bands: rej[str(b)] = max(rej[str(b)], x["rejected_both"][str(b)])
    return w, at, rej
def q8r_find_G(src, shots):
    W0 = q8r_worst(q8r_rows(src, q8r_Ft(src, 0.0)), shots)[0]
    lo, hi = (0.0, 1.0) if W0 <= Q8R_CEILING else (-1.0, 0.0)
    Wlo = q8r_worst(q8r_rows(src, q8r_Ft(src, lo)), shots)[0]
    assert Wlo <= Q8R_CEILING, ("Q8: no published figures with a wrong-verdict rate within the ceiling", Wlo)
    for _ in range(10):
        mid = (lo + hi) / 2; W = q8r_worst(q8r_rows(src, q8r_Ft(src, mid)), shots)[0]
        if W <= Q8R_CEILING: lo, Wlo = mid, W
        else: hi = mid
    return {"G": q8r_gap(q8r_rows(src, q8r_Ft(src, lo))), "t_last_within": lo, "worst_wrong_at_t": Wlo, "t_first_beyond": hi,
            "gap_first_beyond": q8r_gap(q8r_rows(src, q8r_Ft(src, hi))), "worst_wrong_first_beyond": q8r_worst(q8r_rows(src, q8r_Ft(src, hi)), shots)[0],
            "worst_wrong_on_admitted_figures": W0}
# Check 4 (N1, N5, N6): the residual sensitivity, the rejection reach and 40,000-draw precision estimates.
#   sensitivity_k_above_selene   truth F_adm + (1 - F_adm)(k_max + d), d = 0.03, 0.05, 0.10: how often the published figures
#                                still win (and both are rejected), at the group's shots and band, Q8R_DRAWS draws, seed reset;
#   sensitivity_k_below_selene   truth g + (1 - g)(k_min - d) (the generic law right): how often the generic law still wins;
#   no_noise_flip_k_above_selene the d at which the no-noise verdict first goes to the generic law (bisection to 1e-4);
#   rejection_reach              no noise, the device's F scaled to s x F_adm with k at Selene's lowest, median and highest:
#                                the largest s at which both predictions are rejected (None: never, even at s = 0);
#   precise                      the worst wrong-verdict rate on the admitted figures and G at each listed shot count with
#                                Q8R_PRECISE draws, binomial counts by inverse CDF (random.Random(20261115)), same truths.
Q8R_SENS_D = (0.03, 0.05, 0.10); Q8R_PRECISE = args.q8_precise_draws
def q8r_noise_free(true, rs, band):
    w, d = q8r_verdict(true, rs); return w, d > math.log(band)
def q8r_binom_cdf(p, n):
    cdf, c = [], 0.0
    for x in range(n + 1):
        c += math.comb(n, x) * p ** x * (1 - p) ** (n - x); cdf.append(c)
    cdf[-1] = 1.0
    return cdf
def q8r_worst_precise(rs, shots, draws):
    worst = 0.0
    for level in Q8R_LEVELS:
        for which in ("published", "generic"):
            rng = random.Random(20261115); tabs = [q8r_binom_cdf(p, shots) for p in q8r_truth(rs, which, level)]; pw = 0
            for _ in range(draws):
                pw += q8r_verdict([bisect.bisect_left(tb, rng.random()) / shots for tb in tabs], rs)[0]
            worst = max(worst, ((draws - pw) if which == "published" else pw) / draws)
    return worst
def q8r_extra(gname, src, adm, shots, band, Gs):
    ex = {"sensitivity_k_above_selene": {}, "sensitivity_k_below_selene_generic_true": {}}
    for d in Q8R_SENS_D:
        x = q8r_sim([r["F"] + (1 - r["F"]) * min(1.0, KR[r["id"]]["k_max"] + d) for r in adm], adm, shots, (band,))
        ex["sensitivity_k_above_selene"][str(d)] = {"published_wins": x["published_wins"], "rejected_both": x["rejected_both"][str(band)]}
        y = q8r_sim([r["g"] + (1 - r["g"]) * max(0.0, KR[r["id"]]["k_min"] - d) for r in adm], adm, shots, (band,))
        ex["sensitivity_k_below_selene_generic_true"][str(d)] = {"generic_wins": 1 - y["published_wins"], "rejected_both": y["rejected_both"][str(band)]}
    lo, hi = 0.0, 0.5
    for _ in range(14):
        mid = (lo + hi) / 2
        if q8r_noise_free([r["F"] + (1 - r["F"]) * min(1.0, KR[r["id"]]["k_max"] + mid) for r in adm], adm, band)[0]: lo = mid
        else: hi = mid
    ex["no_noise_flip_k_above_selene"] = round(hi, 4)
    reach = {}
    for level in Q8R_LEVELS:
        def rej(s): return q8r_noise_free([s * r["F"] + (1 - s * r["F"]) * KR[r["id"]][level] for r in adm], adm, band)[1]
        if not rej(0.0): reach[level] = None; continue
        lo, hi = 0.0, 1.0
        for _ in range(14):
            mid = (lo + hi) / 2
            if rej(mid): lo = mid
            else: hi = mid
        reach[level] = round(lo, 4)
    ex["rejection_reach"] = reach
    if Q8R_PRECISE:
        pr = {"draws": Q8R_PRECISE, "seed": 20261115, "sampler": "binomial counts by inverse CDF", "by_shots": {}}
        for n in Q8R_SHOT_OPTIONS[gname]:
            W0 = q8r_worst_precise(q8r_rows(src, q8r_Ft(src, 0.0)), n, Q8R_PRECISE)
            lo, hi = (0.0, 1.0) if W0 <= Q8R_CEILING else (-1.0, 0.0)
            for _ in range(10):
                mid = (lo + hi) / 2
                if q8r_worst_precise(q8r_rows(src, q8r_Ft(src, mid)), n, Q8R_PRECISE) <= Q8R_CEILING: lo = mid
                else: hi = mid
            pr["by_shots"][str(n)] = {"worst_wrong_on_derivation_figures": W0, "G": q8r_gap(q8r_rows(src, q8r_Ft(src, lo))), "G_2000_draws": Gs[str(n)]["G"]}
        ex["precise"] = pr
    return ex
Q8R = {"rule": "per circuit the log distance from the measured share to each prediction's range (0 inside it); published wins if the median over the group's circuits of (distance to generic - distance to published) > 0, generic otherwise; a verdict only if the group's median gap (generic lower end / published upper end) >= G, else indistinguishable; both rejected if the median distance to the winning range > log(band)",
       "ceiling": Q8R_CEILING, "draws": Q8R_DRAWS, "seed": 20261115,
       "k": {c: {"case": d["case"], "k_min": round(d["k_min"], 6), "k_median": round(d["k_median"], 6), "k_max": round(d["k_max"], 6),
                 "k_by_setting": {s: round(x, 6) for s, x in d["k_by_setting"].items()}} for c, d in KR.items()},
       "groups": {}}
for gname, src in Q8R_GROUPS.items():
    adm = q8r_rows(src, q8r_F(src, QSET)); gap_adm = q8r_gap(adm)
    gap_der = q8r_gap(q8r_rows(src, q8r_F(src, Q8R_DERIVATION_SET)))
    Gs = {str(n): q8r_find_G(src, n) for n in Q8R_SHOT_OPTIONS[gname]}
    ok = [n for n in Q8R_SHOT_OPTIONS[gname] if gap_der >= Gs[str(n)]["G"]]
    assert ok, f"Q8: the derivation figures get no verdict for the {gname} circuits at any listed shot count"
    shots = ok[0]; Gd = Gs[str(shots)]["G"]; Gv = Q8R_G_FROZEN[gname]
    per_set, rejmax = {}, {str(b): 0.0 for b in Q8R_BANDS[gname]}
    for k in PUBLISHED:
        rk = q8r_rows(src, q8r_F(src, k)); w, at, rj = q8r_worst(rk, shots, Q8R_BANDS[gname]); gk = q8r_gap(rk)
        per_set[k] = {"gap": round(gk, 4), "outcome": "verdict" if gk >= Gv else "indistinguishable", "worst_wrong_verdict": w, "worst_at": at, "rejected_both_max": rj}
        for b in rj: rejmax[b] = max(rejmax[b], rj[b])
    band = next(b for b in Q8R_BANDS[gname] if rejmax[str(b)] <= Q8R_CEILING)
    assert all(v["worst_wrong_verdict"] <= Q8R_CEILING for v in per_set.values() if v["outcome"] == "verdict"), per_set
    sens, scen = {}, {}
    for s, v in Q8R_SETTINGS:
        key = f"{s}|{v}"
        x = q8r_sim([r["F"] + (1 - r["F"]) * KR[r["id"]]["k_by_setting"][key] for r in adm], adm, shots, (band,))
        sens[key] = {"published_wins": x["published_wins"], "rejected_both": x["rejected_both"][str(band)]}
        sel = [SR2025[r["id"]][s][v]["score"] for r in adm]; w0, d0 = q8r_verdict(sel, adm); y = q8r_sim(sel, adm, shots, (band,))
        scen[key] = {"no_noise_winner": "published" if w0 else "generic", "factor_from_winning_range": round(math.exp(d0), 4),
                     "published_wins": y["published_wins"], "rejected_both": y["rejected_both"][str(band)]}
    Q8R["groups"][gname] = {
        "circuits": {r["case"]: {"F": round(r["F"], 4), "g": round(r["g"], 4), "published_range": [round(x, 4) for x in r["pub"]], "generic_range": [round(x, 4) for x in r["gen"]],
                                 "gap": round(r["gen"][0] / r["pub"][1], 4)} for r in adm},
        "published_range": [round(min(r["pub"][0] for r in adm), 4), round(max(r["pub"][1] for r in adm), 4)],
        "generic_range": [round(min(r["gen"][0] for r in adm), 4), round(max(r["gen"][1] for r in adm), 4)],
        "ranges_overlap_on_admitted_figures": [r["case"] for r in adm if r["pub"][1] >= r["gen"][0]],
        "gap_admitted": gap_adm, "G_by_shots": Gs, "shots": shots, "G": Gd, "gap_margin": gap_adm / Gd,
        "band": band, "rejected_both_max_over_published_sets": rejmax, "per_published_set": per_set,
        "sensitivity_own_k_admitted_figures": sens, "selene_scenarios": scen,
        "rejection_from_above_impossible": all(math.log(1 / r["gen"][1]) < math.log(band) for r in adm),
        "G_frozen": Gv, "G_derivation_set": Q8R_DERIVATION_SET, "gap_margin_frozen": gap_adm / Gv,
        "outcome_on_qset_figures": "verdict" if gap_adm >= Gv else "indistinguishable"}
    Q8R["groups"][gname].update(q8r_extra(gname, src, adm, shots, band, Gs))
Q8R["rule_band_test_range"] = "the range chosen in step (1), with or without a verdict (check 4, N4)"
Q8R["G_frozen_note"] = "the rule uses G_frozen (--q8-g-tm, --q8-g-act), set from the derivation on 17 November 2026 and fixed with k for the first run; G holds the derivation's own value at the chosen shots"
Q8R["objective_max"] = max(max(g_["G_by_shots"][str(g_["shots"])]["worst_wrong_on_admitted_figures"] for g_ in Q8R["groups"].values()),
                           max(v["worst_wrong_verdict"] for g_ in Q8R["groups"].values() for v in g_["per_published_set"].values() if v["outcome"] == "verdict"),
                           max(max(g_["rejected_both_max_over_published_sets"].values()) for g_ in Q8R["groups"].values()))
assert Q8R["objective_max"] <= Q8R_CEILING
out["steps"]["q8_ranges"] = Q8R
if ACT_SHOTS is None: ACT_SHOTS = Q8R["groups"]["actinide"]["shots"]
out["parameters"]["actinide_shots"] = ACT_SHOTS

# ---- step 2: actinide test on Quantinuum, across the line ----
def pN(case, q):
    m = MODEL[case]; na, nb = m["electrons"]; return math.comb(m["orbitals"], na) * math.comb(m["orbitals"], nb) / 2 ** q
def chem_rows(src, k):
    rows = []
    for r in src:
        cid = "qcup-f-tgt-" + r["case"].lower().replace("_", "-"); q = C[cid]["qubits"]; F = qfid(cid, k); p = pN(r["case"], q); g = r["modelled_fidelity"]
        rows.append({"case": r["case"], "id": cid, "fidelity": F, "share": F + (1 - F) * p, "generic_share": g + (1 - g) * p})
    return rows
def q8_power_v101(rows, shots, N=2000):          # q8_power as in v1.0.1, kept as the control for the extended one below
    random.seed(20261115)
    def verdict(true, pub, gen):
        return st.median(sum(random.random() < p for _ in range(shots)) / shots / math.sqrt(a * b) for p, a, b in zip(true, pub, gen)) > 1.0
    pub = [r["share"] for r in rows]; gen = [r["generic_share"] for r in rows]
    return {"false_alarm_if_published_true": sum(verdict(pub, pub, gen) for _ in range(N)) / N,
            "power_if_generic_true": sum(verdict(gen, pub, gen) for _ in range(N)) / N}
def q8_power(rows, shots, N=2000, band=None):
    """Same draws as q8_power_v101 (seed reset, N draws with the published shares as the truth, then N with the generic
    shares). Verdict: generic if the median over circuits of measured / sqrt(published x generic) exceeds 1. With a band,
    both predictions are rejected when the median over circuits of measured / nearer prediction lies outside [1/band, band]."""
    random.seed(20261115)
    pub = [r["share"] for r in rows]; gen = [r["generic_share"] for r in rows]
    def draw(true):
        obs = [sum(random.random() < p for _ in range(shots)) / shots for p in true]
        gen_wins = st.median(o / math.sqrt(a * b) for o, a, b in zip(obs, pub, gen)) > 1.0
        m = st.median(o / x for o, x in zip(obs, gen if gen_wins else pub))
        return gen_wins, band is not None and not (1 / band <= m <= band)
    dp = [draw(pub) for _ in range(N)]; dg = [draw(gen) for _ in range(N)]
    res = {"false_alarm_if_published_true": sum(g for g, _ in dp) / N, "power_if_generic_true": sum(g for g, _ in dg) / N}
    assert res == q8_power_v101(rows, shots, N), "q8_power's verdict rates must repeat v1.0.1's"
    if band is not None:
        res |= {"band": band, "wrong_verdict_if_generic_true": sum(not g for g, _ in dg) / N,
                "rejected_both_if_published_true": sum(r for _, r in dp) / N, "rejected_both_if_generic_true": sum(r for _, r in dg) / N}
    return res
act_hqc = {s: round(sum(hqc(r["n1q"], r["rzz"], 2 * r["qubits"], s) for r in TGT["Quantinuum"]), 1) for s in sorted({50, 100, 150, 200, ACT_SHOTS})}
act_by_set = {}
for k in PUBLISHED:
    rows = chem_rows(TGT["Quantinuum"], k)
    act_by_set[k] = {"fidelity": [round(min(r["fidelity"] for r in rows), 4), round(max(r["fidelity"] for r in rows), 4)],
                     "share": [round(min(r["share"] for r in rows), 4), round(max(r["share"] for r in rows), 4)],
                     "above_30pct": sum(r["fidelity"] >= 0.30 for r in rows),
                     "q8_rule": {f"{s}_shots": q8_power(rows, s, band=Q8_BAND_ACT) for s in (50, 100, 200)}}
gen_act = chem_rows(TGT["Quantinuum"], QSET)
out["steps"]["2_actinide_test"] = {"shots": ACT_SHOTS, "hqc_total": act_hqc[ACT_SHOTS], "hqc_by_shots": act_hqc,
    "circuits": [{"case": r["case"], "fidelity": round(r["fidelity"], 4), "share": round(r["share"], 4), "generic_share": round(r["generic_share"], 4)} for r in gen_act],
    "generic_share": [round(min(r["generic_share"] for r in gen_act), 4), round(max(r["generic_share"] for r in gen_act), 4)],
    "by_figure_set": act_by_set,
    "max_false_alarm_over_published_sets": {f"{s}_shots": max(act_by_set[k]["q8_rule"][f"{s}_shots"]["false_alarm_if_published_true"] for k in PUBLISHED) for s in (50, 100, 200)},
    "max_over_published_sets_at_band": {f"{s}_shots": {key: max(act_by_set[k]["q8_rule"][f"{s}_shots"][key] for k in PUBLISHED)
        for key in ("wrong_verdict_if_generic_true", "rejected_both_if_published_true", "rejected_both_if_generic_true")} | {"band": Q8_BAND_ACT} for s in (50, 100, 200)}}

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
                    "above_30pct": sum(r["fidelity"] >= 0.30 for r in rows),
                    "q8_rule_200_shots": q8_power(rows, 200, band=Q8_BAND_TM)}
tm_rows = chem_rows(TGT["IonQ"], QSET)
out["steps"]["3_transition_metal_on_quantinuum"] = {"hqc_total": tm_hqc, "by_figure_set": tm_by_set,
    "generic_share": [round(min(r["generic_share"] for r in tm_rows), 4), round(max(r["generic_share"] for r in tm_rows), 4)],
    "q8_rule_200_shots": q8_power(tm_rows, 200, band=Q8_BAND_TM)}
# Q8's shot-noise rates at each group's band and request shots, maximised over the eight published sets as the published
# truth (and the generic law as the other truth): the wrong verdict and the rejection of both predictions. This is the
# point-prediction design of the Selene 2025 round, kept as recorded at its 100 actinide shots (LEGACY_ACT_SHOTS); Q8 now
# uses the range design in steps.q8_ranges, and the request's actinide shots (ACT_SHOTS) follow that rule.
LEGACY_ACT_SHOTS = 100
_q8g = {"transition_metal": ({k: tm_by_set[k]["q8_rule_200_shots"] for k in PUBLISHED}, 200, Q8_BAND_TM, 8),
        "actinide": ({k: act_by_set[k]["q8_rule"][f"{LEGACY_ACT_SHOTS}_shots"] for k in PUBLISHED}, LEGACY_ACT_SHOTS, Q8_BAND_ACT, len(TGT["Quantinuum"]))}
_q8keys = ("false_alarm_if_published_true", "wrong_verdict_if_generic_true", "rejected_both_if_published_true", "rejected_both_if_generic_true")
out["steps"]["q8_bands"] = {g: {"circuits": n, "shots": s, "band": b, "draws": 2000, "seed": 20261115,
                                "max_over_published_sets": {key: max(v[key] for v in d.values()) for key in _q8keys},
                                "argmax_set": {key: max(d, key=lambda k: d[k][key]) for key in _q8keys}}
                            for g, (d, s, b, n) in _q8g.items()}
out["steps"]["q8_bands"]["max_wrong_verdict_or_rejection"] = max(v for g in _q8g for v in out["steps"]["q8_bands"][g]["max_over_published_sets"].values())
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

# ---- IBM QAOA shots raised to Q12_TARGET expected successes at the device check's measured retention (17 Nov 2026) ----
CHK_PRED = {c["id"]: c for c in load(B, "vendor", "ibm-check", "predictions.json")["circuits"]}
CHK_RES = {r["id"]: r for r in load(B, "vendor", "ibm-check", "rescore", "out", "rescore_device.json")["dd_off"]}
RET_ID = "a1-b12-p1-warm"                                  # the check's QAOA circuit nearest the 117-CZ cap (130 CZ)
RETENTION = CHK_RES[RET_ID]["measured"] / CHK_PRED[RET_ID]["ideal_p_gs"]
assert abs(RETENTION - next(a["retained"] for a in load(B, "vendor", "ibm-check", "rescore", "out", "fits_device.json")["dd_off"]["aim1"] if a["id"] == RET_ID)) < 1e-12
def ideal_p(f, n, s, p, kind):
    assert n <= 20, "ideal success is stored for instances to 20 variables only"
    if kind == "cold": return next(z["p_gs"] for z in load(B, "results", f"aim1_{f}_{n}_{s}.json")["qaoa"] if z["p"] == p)
    return next(z["p_gs"] for z in load(B, "results", f"post_{f}_{n}_{s}.json")["ws"] if z["p"] == p)
def seed_optimal(f, n, s): return load(B, "results", f"post_{f}_{n}_{s}.json")["gw16_is_optimal"]
def guess_p(f, n, s):                 # a uniformly random bitstring's chance of an optimum: n_ground / 2^n
    return load(B, "results", f"aim1_{f}_{n}_{s}.json")["n_ground"] / 2 ** n
def raise_shots(pi, gp, target):      # shots that reach `target` expected optima at the check's retention, or None
    if not target or pi * RETENTION * 4000 >= target: return 4000
    if pi < FLOOR_MULT * gp: return None                                  # at the guessing floor: not raised (item 20)
    return max(4000, SHOT_STEP * math.ceil(target / (pi * RETENTION) / SHOT_STEP))
q12 = []
for f, n, s, p, cz in sel:
    gp = guess_p(f, n, s)
    for kind in ("cold", "warm"):
        pi = ideal_p(f, n, s, p, kind)
        need = raise_shots(pi, gp, Q12_TARGET)
        # what the rule of 17 November without the floor would have given (recorded for the change note only)
        need_nofloor = 4000 if not Q12_TARGET or pi * RETENTION * 4000 >= Q12_TARGET else max(4000, SHOT_STEP * math.ceil(Q12_TARGET / (pi * RETENTION) / SHOT_STEP))
        q12.append({"id": f"{f}{n}-s{s}-p{p}-{kind}", "family": f, "n": n, "seed": s, "p": p, "kind": kind, "cz": cz, "seed_optimal": seed_optimal(f, n, s),
                    "ideal_p_gs": pi, "random_guess_p": gp, "ideal_over_guess": round(pi / gp, 4),
                    "expected_at_4000_error_free": round(pi * 4000, 3), "expected_at_4000_check_retention": round(pi * RETENTION * 4000, 3),
                    "expected_at_2000_check_retention": round(pi * RETENTION * 2000, 3), "shots": need if need else 4000, "raised": bool(need and need > 4000),
                    "at_guessing_floor": pi < FLOOR_MULT * gp, "shots_without_floor_rule": need_nofloor})
short_ef = [r for r in q12 if r["expected_at_4000_error_free"] < Q12_TARGET]
short_ret = [r for r in q12 if r["expected_at_4000_check_retention"] < Q12_TARGET]
raised = [r for r in q12 if r["raised"]]
floor_short = [r for r in short_ret if r["at_guessing_floor"]]
qa_shots = sum(r["shots"] for r in q12)
g = ibm_a1["groups"]["qaoa"]; assert g["circuits"] == len(q12)
g["shots_per_circuit"] = [min(r["shots"] for r in q12), max(r["shots"] for r in q12)]; g["shots"] = qa_shots
ibm_a1["shots"] = sum(x["shots"] for x in ibm_a1["groups"].values())
iqm_short = [r for r in q12 if r["expected_at_2000_check_retention"] < Q12_TARGET]
def q2_eligible(key):             # Q2 (item 22): cold and warm both expect >= 20 successes and both have ideal success >= twice a random guess's
    by = collections.defaultdict(dict)
    for r in q12: by[(r["family"], r["n"], r["seed"], r["p"], r["seed_optimal"])][r["kind"]] = r
    el = [k for k, v in by.items() if all(key(v[c]) >= Q12_TARGET and not v[c]["at_guessing_floor"] for c in ("cold", "warm"))]
    return {"seed_optimal": sum(1 for k in el if k[4]), "seed_not_optimal": sum(1 for k in el if not k[4]),
            "of_seed_optimal": sum(1 for k in by if k[4]), "of_seed_not_optimal": sum(1 for k in by if not k[4])}
def q1_scored(key): return sum(1 for r in q12 if key(r) >= Q12_TARGET and not r["at_guessing_floor"])
out["steps"]["ibm_qaoa_shots_q1_q2"] = {
    "target_expected_successes": Q12_TARGET, "shot_step": SHOT_STEP, "retention_circuit": RET_ID, "retention_cz": CHK_PRED[RET_ID]["cz"], "retention": RETENTION,
    "floor_rule": f"raised only if ideal success >= {FLOOR_MULT} x a uniformly random guess's (n_ground / 2^n)",
    "circuits": len(q12), "short_at_4000_error_free": len(short_ef), "short_at_4000_check_retention": len(short_ret),
    "short_by_group": dict(collections.Counter(f"{r['family']} {r['kind']}" for r in short_ef)),
    "short_below_guess": sum(1 for r in short_ret if r["ideal_p_gs"] < r["random_guess_p"]), "short_below_twice_guess": len(floor_short),
    "short_at_or_above_twice_guess": len(short_ret) - len(floor_short),
    "random_guess_p_values": sorted({r["random_guess_p"] for r in q12}),
    "raised": len(raised), "raised_by_group": dict(collections.Counter(f"{r['family']} {r['kind']}" for r in raised)),
    "raised_shots_range": [min(r["shots"] for r in raised), max(r["shots"] for r in raised)] if raised else None,
    "raised_shots_total": sum(r["shots"] for r in raised), "added_shots": sum(r["shots"] - 4000 for r in raised),
    "qaoa_shots_total": qa_shots, "qaoa_shots_at_4000": 4000 * len(q12),
    "without_floor_rule": {"raised": sum(1 for r in q12 if r["shots_without_floor_rule"] > 4000), "added_shots": sum(r["shots_without_floor_rule"] - 4000 for r in q12),
                           "added_shots_on_floor_circuits": sum(r["shots_without_floor_rule"] - 4000 for r in floor_short)},
    "iqm_2000_shots_short_at_retention": len(iqm_short), "iqm_2000_shots_short_error_free": sum(1 for r in q12 if r["ideal_p_gs"] * 2000 < Q12_TARGET),
    "q1_scored_circuits": {"IBM": q1_scored(lambda r: r["shots"] * r["ideal_p_gs"] * RETENTION), "IQM_2000_at_retention": q1_scored(lambda r: r["expected_at_2000_check_retention"]), "of": len(q12)},
    "q2_eligible_instances": {"IBM_raised": q2_eligible(lambda r: r["shots"] * r["ideal_p_gs"] * RETENTION),
                              "IQM_2000_at_retention": q2_eligible(lambda r: r["expected_at_2000_check_retention"])},
    "ibm_limits": {"max_executions_per_sampler_job": IBM_MAX_EXECUTIONS_PER_JOB, "per": "job, not PUB", "max_qpu_seconds_per_job": IBM_MAX_JOB_SECONDS,
                   "sampler_jobs_needed_for_qaoa_at_least": math.ceil(qa_shots / IBM_MAX_EXECUTIONS_PER_JOB),
                   "largest_circuit_shots_within_one_job": max(r["shots"] for r in q12) <= IBM_MAX_EXECUTIONS_PER_JOB},
    "rows": q12}
# ---- Q2's chance of a false verdict from shot noise alone (item 32), the way q8_power does Q8's: the law exact ----
# Each eligible IBM instance (cold and warm circuits both >= 20 expected successes and both >= twice a random guess's
# ideal success) at its requested shots; counts Poisson with mean shots x (F' x ideal + (1 - F') x guess), F' = the
# check's retention for every circuit, so the true floor-subtracted warm/cold ratio equals the ideal circuits' ratio.
# Statistic as Q2 states it: per instance |ln(measured ratio / ideal ratio)|, each success less the guess (a non-positive
# excess counts as an infinite miss); falsified if the median over the arm's instances exceeds ln 1.25.
# Q2_DRAWS runs, seed 20261115 reset per arm. Poisson draws by Knuth's product below a mean of 30 and by Hormann's PTRS
# (transformed rejection, as numpy implements it) above; positive control: sample mean and variance against the mean.
Q2_DRAWS = 2000
def poisson(rng, lam):
    if lam < 30:
        L, k, p_ = math.exp(-lam), 0, 1.0
        while True:
            p_ *= rng.random()
            if p_ <= L: return k
            k += 1
    slam, loglam = math.sqrt(lam), math.log(lam)
    b = 0.931 + 2.53 * slam; a = -0.059 + 0.02483 * b; invalpha = 1.1239 + 1.1328 / (b - 3.4); vr = 0.9277 - 3.6224 / (b - 2)
    while True:
        U = rng.random() - 0.5; Vv = rng.random(); us = 0.5 - abs(U)
        k = math.floor((2 * a / us + b) * U + lam + 0.43)
        if us >= 0.07 and Vv <= vr: return k
        if k < 0 or (us < 0.013 and Vv > us): continue
        if math.log(Vv) + math.log(invalpha) - math.log(a / (us * us) + b) <= -lam + k * loglam - math.lgamma(k + 1): return k
_pc = random.Random(7)
POISSON_CONTROL = {}
for lam in (4.0, 25.0, 60.0, 900.0):
    xs = [poisson(_pc, lam) for _ in range(20000)]; m_ = st.mean(xs); v_ = st.pvariance(xs)
    POISSON_CONTROL[str(lam)] = [round(m_, 3), round(v_, 3)]
    assert abs(m_ - lam) < 4 * math.sqrt(lam / 20000) + 1e-9 and abs(v_ / lam - 1) < 0.05, (lam, m_, v_)
def q2_instances():
    by = collections.defaultdict(dict)
    for r in q12: by[(r["family"], r["n"], r["seed"], r["p"], r["seed_optimal"])][r["kind"]] = r
    return {k: v for k, v in by.items() if all(v[c]["shots"] * v[c]["ideal_p_gs"] * RETENTION >= Q12_TARGET and not v[c]["at_guessing_floor"] for c in ("cold", "warm"))}
def q2_power(inst, draws=Q2_DRAWS, seed=20261115):
    rng = random.Random(seed); fals = 0; meds = []
    for _ in range(draws):
        misses = []
        for v in inst:
            c, w = v["cold"], v["warm"]; g_ = c["random_guess_p"]
            ex = []
            for r in (w, c):
                lam = r["shots"] * (RETENTION * r["ideal_p_gs"] + (1 - RETENTION) * g_)
                ex.append(poisson(rng, lam) / r["shots"] - g_)
            ideal_ratio = (w["ideal_p_gs"] - g_) / (c["ideal_p_gs"] - g_)
            misses.append(abs(math.log((ex[0] / ex[1]) / ideal_ratio)) if ex[0] > 0 and ex[1] > 0 else math.inf)
        med = st.median(misses); meds.append(med); fals += med > math.log(1.25)
    return {"instances": len(inst), "draws": draws, "seed": seed, "false_verdict_rate": fals / draws,
            "median_log_miss_median_over_runs": round(st.median(meds), 4)}
Q2I = q2_instances()
arms = {"seed_optimal": [v for k, v in Q2I.items() if k[4]], "seed_not_optimal": [v for k, v in Q2I.items() if not k[4]]}
exc = lambda r: r["shots"] * RETENTION * (r["ideal_p_gs"] - r["random_guess_p"])
out["steps"]["q2_shot_noise_power"] = {"law": "counts Poisson, mean shots x (F' ideal + (1 - F') guess), F' = the check's retention", "retention": RETENTION,
    "poisson_positive_control_mean_variance": POISSON_CONTROL,
    "arms": {a: q2_power(v) for a, v in arms.items()},
    "expected_successes_above_floor": {a: [round(min(exc(v[c]) for v in vs for c in ("cold", "warm")), 2), round(max(exc(v[c]) for v in vs for c in ("cold", "warm")), 2)] for a, vs in arms.items()}}

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
# the shot raise of 17 November 2026: what it adds, the request as it stood with 4,000 shots, and the limits it must fit
a1_at_4000 = ibm_a1["shots"] - qa_shots + 4000 * len(q12)
ibm["minutes_cost_py_formula_qaoa_at_4000"] = ibm_minutes(a1_at_4000, ibm_a2_shots, ibm_a2["mean_sc_depth_all_streams"])
ibm["minutes_at_check_charge_rate_qaoa_at_4000"] = round((a1_at_4000 + ibm_a2_shots) * check_rate / 60, 1)
ibm["minutes_cost_py_formula_added_by_raise"] = round(ibm["minutes_cost_py_formula"] - ibm["minutes_cost_py_formula_qaoa_at_4000"], 1)
ibm["minutes_at_check_charge_rate_added_by_raise"] = round(ibm["minutes_at_check_charge_rate"] - ibm["minutes_at_check_charge_rate_qaoa_at_4000"], 1)
ibm["inside_default_minutes_at_check_rate"] = ibm["minutes_at_check_charge_rate"] < OLCF_IBM_MINUTES
ibm["inside_default_minutes_by_formula"] = ibm["minutes_cost_py_formula"] < OLCF_IBM_MINUTES
ibm["largest_sampler_job_qpu_seconds_at_check_rate"] = round(IBM_MAX_EXECUTIONS_PER_JOB * check_rate, 1)
ibm["largest_sampler_job_inside_3_hours"] = IBM_MAX_EXECUTIONS_PER_JOB * check_rate < IBM_MAX_JOB_SECONDS

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
    {"aim": 1, "vendor": "IBM", "qubits": ibm_a1["qubits"], "circuits": ibm_a1["circuits"], "total_shots": ibm_a1["shots"],
     "shots_per_circuit": (f"4,000 to {max(r['shots'] for r in q12):,} (12,000 for H2)" if raised else "4,000 (12,000 for H2)")},
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

# ---- figures the revised text quotes (17 November 2026) ----
SC = load(V, "ionq", "scores.json"); AN = load(V, "analysis.json")
scored = {r["id"] for r in SC}
ion_ids = sorted({x["id"] for x in ion_core})                      # the 3 H2 rows share one circuit id
NER = {r["id"]: r["reason"] for r in load(V, "ionq", "not_emulated_rows.json")}
def seed_state_stored(f, n, s_):     # a Goemans-Williamson seed state is stored only where results/aim1_* holds gw1_state or results/post_* holds ws
    pa = os.path.join(B, "results", f"aim1_{f}_{n}_{s_}.json"); pp = os.path.join(B, "results", f"post_{f}_{n}_{s_}.json")
    return (os.path.exists(pa) and "gw1_state" in json.load(open(pa))) or (os.path.exists(pp) and "ws" in json.load(open(pp)))
def rounding_energy_stored(f, n, s_):
    ps = os.path.join(B, "results", "scale", f"scale_{f}_{n}_{s_}.json")
    return os.path.exists(ps) and json.load(open(ps)).get("gw16_energy") is not None
not_emulated = []
for i in ion_ids:
    if i in scored: continue
    x = next(x for x in ion_core if x["id"] == i); f, n, s_, p_, kind = x["circuit"].split("_")
    not_emulated.append({"id": i, "qubits": x["count_qubits"], "reason_recorded": NER[i], "warm": kind == "warm",
                         "seed_state_stored": seed_state_stored(f, int(n), int(s_)), "rounding_energy_stored": rounding_energy_stored(f, int(n), int(s_))})
assert all(x["qubits"] > 29 or (x["warm"] and not x["seed_state_stored"]) for x in not_emulated), not_emulated
out["steps"]["ionq_emulator_coverage_of_request"] = {"circuits": len(ion_ids), "emulated": sum(1 for i in ion_ids if i in scored), "not_emulated": not_emulated,
    "ionq_estimate_for_every_circuit": all((x["id"], x["shots"]) in CC for x in ion_core)}
# Q1 on IonQ: QAOA rows kept in the core whose ideal success reaches 20 expected successes at the requested shots
def ion_ideal(x):
    f, n, s, p, kind = x["circuit"].split("_"); n, s, p = int(n), int(s), int(p[1:])
    if n > 20: return None
    return ideal_p(f, n, s, p, kind)
iq_rows = []
for x in ion_core:
    if x["group"] != "aim1_qaoa": continue
    pi = ion_ideal(x)
    f_, n_, s__ = x["circuit"].split("_")[:3]
    gq = guess_p(f_, int(n_), int(s__)) if int(n_) <= 20 else None
    iq_rows.append({"id": x["id"], "qubits": x["count_qubits"], "shots": x["shots"], "ideal_p_gs": pi, "random_guess_p": gq,
                    "at_guessing_floor": None if pi is None else pi < FLOOR_MULT * gq,
                    "expected_error_free": None if pi is None else round(pi * x["shots"], 3),
                    "expected_device_model": None if pi is None else round(pi * x["fidelity_device"] * x["shots"], 3)})
ok_ef = [r for r in iq_rows if r["expected_error_free"] is not None and r["expected_error_free"] >= Q12_TARGET]
ok_floor = [r for r in ok_ef if not r["at_guessing_floor"]]
ok_dm = [r for r in iq_rows if r["expected_device_model"] is not None and r["expected_device_model"] >= Q12_TARGET]
out["steps"]["q1_ionq_qaoa_reaching_20"] = {"qaoa_rows": len(iq_rows), "no_ideal_success_stored": sum(1 for r in iq_rows if r["ideal_p_gs"] is None),
    "reach_20_error_free": len(ok_ef), "qubits_error_free": [min(r["qubits"] for r in ok_ef), max(r["qubits"] for r in ok_ef)],
    "reach_20_error_free_and_above_twice_guess": len(ok_floor), "qubits_error_free_and_above_twice_guess": [min(r["qubits"] for r in ok_floor), max(r["qubits"] for r in ok_floor)],
    "reach_20_under_device_model": len(ok_dm), "qubits_device_model": [min(r["qubits"] for r in ok_dm), max(r["qubits"] for r in ok_dm)], "rows": iq_rows}
pairs = collections.defaultdict(dict)
for r, x in zip(iq_rows, [x for x in ion_core if x["group"] == "aim1_qaoa"]):
    f, n, s, p, kind = x["circuit"].split("_")
    if int(n) <= 20: pairs[(f, int(n), int(s), p)][kind] = r
q2i = [k for k, v in pairs.items() if len(v) == 2 and all(v[c]["expected_error_free"] >= Q12_TARGET and not v[c]["at_guessing_floor"] for c in ("cold", "warm"))]
out["steps"]["q1_ionq_qaoa_reaching_20"]["q2_eligible_instances_error_free"] = {
    "seed_optimal": sum(1 for k in q2i if seed_optimal(k[0], k[1], k[2])), "seed_not_optimal": sum(1 for k in q2i if not seed_optimal(k[0], k[1], k[2]))}
# period 2: what it holds
ext = {v: kept[(v, "extension")] for v in ("IonQ", "Quantinuum")}
def depth(x): return int(x["circuit"].split("_")[3][1:])
qx_q = [x for x in ext["Quantinuum"] if x["group"] == "aim1_qaoa"]; qx_2 = [x for x in ext["Quantinuum"] if x["aim"] == 2]; ix_q = [x for x in ext["IonQ"] if x["group"] == "aim1_qaoa"]
r1q = out["steps"]["1_readmission"]["Quantinuum|extension"]["by_figure_set"]
out["steps"]["period_2_contents"] = {
    "Quantinuum": {"qaoa_circuits": len(qx_q), "qaoa_variables": [min(x["count_qubits"] for x in qx_q), max(x["count_qubits"] for x in qx_q)],
                   "qaoa_depths": sorted({depth(x) for x in qx_q}), "family_C_60": sorted(x["circuit"] for x in qx_q if x["circuit"].startswith("C_60")),
                   "aim2_programs": len(qx_2), "aim2_two_qubit_gates": [min(x["count_n2q"] for x in qx_2), max(x["count_n2q"] for x in qx_2)],
                   "other": len(ext["Quantinuum"]) - len(qx_q) - len(qx_2),
                   "hqc_over_published_sets": [min(v["hqc_kept"] for v in r1q.values()), max(v["hqc_kept"] for v in r1q.values())]},
    "IonQ": {"qaoa_circuits": len(ix_q), "qaoa_depths": sorted({depth(x) for x in ix_q}), "other": len(ext["IonQ"]) - len(ix_q)}}
c60 = [x for x in A if x["group"] == "aim1_qaoa" and x["circuit"].startswith("C_60")]
out["steps"]["family_C_60_admission"] = [{"vendor": x["vendor"], "tier": x["tier_application"], "circuit": x["circuit"], "admitted": admit(x)} for x in c60]
# the ladder's mid-circuit programs under the device check's excess over the budget script (F = (e^-b)^k)
DSUM = load(B, "vendor", "ibm-check", "derived", "derived.json")["summary"]["five_step_over_budget_script"]
kept_mcm = [LAD[k]["e_minus_b_script"] for k, v in lad_e.items() if LAD[k]["e_minus_b_script"] >= MCM_FLOOR]
out["steps"]["ibm_ladder_mcm_under_check_excess"] = {"programs": len(kept_mcm), "e_minus_b": [min(kept_mcm), max(kept_mcm)], "excess_k": DSUM[:2],
    "below_030": [sum(1 for e in kept_mcm if e ** k < 0.30) for k in DSUM[:2]],
    "below_030_at_rounded_k_1_4_and_3_1": [sum(1 for e in kept_mcm if e ** k < 0.30) for k in (1.4, 3.1)],
    "circuits_above_ibm_cap": ibm_a2["circuits_above_ibm_cap"]}
# Q5: on IBM the ladder's multi-step garbage-retaining programs measure nothing mid-circuit, so step count, gate count and
# mid-circuit measurement vary separately there; on IQM (R and P styles) every multi-step program measures mid-circuit
def pearson(xs, ys):
    mx, my = st.mean(xs), st.mean(ys); sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)
placed = {c["id"]: c for c in LADD["circuits"]}
def lmcm(c): return c["mid_circuit_measurements"] > 0 or c["resets"] > 0
ibm_rows = [placed[lid(r)] for r in s0 if r["style"] in "GRP" and r["sc_like"]["two_qubit_gates"] <= LADDER_CAP and lid(r) in placed]
ms_nomcm = [c for c in ibm_rows if c["T"] >= 2 and not lmcm(c)]
iqm_ms = [c for c in ibm_rows if c["style"] in "RP" and c["T"] >= 2]
out["steps"]["q5_step_gate_mcm_separation"] = {
    "ibm_placed_programs": len(ibm_rows), "ibm_multi_step_without_mid_circuit_measurement": len(ms_nomcm),
    "their_styles": sorted({c["style"] for c in ms_nomcm}), "their_steps": sorted({c["T"] for c in ms_nomcm}), "their_cz": [min(c["cz"] for c in ms_nomcm), max(c["cz"] for c in ms_nomcm)],
    "ibm_corr_steps_cz": round(pearson([c["T"] for c in ibm_rows], [c["cz"] for c in ibm_rows]), 3),
    "ibm_corr_steps_mcm": round(pearson([c["T"] for c in ibm_rows], [1.0 if lmcm(c) else 0.0 for c in ibm_rows]), 3),
    "iqm_multi_step_programs": len(iqm_ms), "iqm_multi_step_with_mid_circuit_measurement": sum(1 for c in iqm_ms if lmcm(c)),
    "ionq_steps": sorted({C.get(x["id"], {}).get("T") for x in ion_core if x["aim"] == 2})}
# the same counts over the requested programs (item 34): IBM requests the ladder's kept rows, the 6 garbage-retaining
# programs not placed on the patch included; IQM requests the R and P styles. A program measures mid-circuit if it is
# R or P at two or more steps (the ladder's rule); every placed one is checked against its placed circuit.
def kept_rows(styles):
    rows = [r for r in s0 if r["style"] in styles and r["sc_like"]["two_qubit_gates"] <= LADDER_CAP]
    return [r for r in rows if not (r["T"] >= 2 and r["style"] in "RP") or LAD[lid(r)]["e_minus_b_script"] >= MCM_FLOOR]
def rule_mcm(r): return r["T"] >= 2 and r["style"] in "RP"
req_ibm, req_iqm = kept_rows("GRP"), kept_rows("RP")
assert len(req_ibm) == ibm_a2["rows"] and len(req_iqm) == iqm_a2["rows"]
assert all(rule_mcm(r) == lmcm(placed[lid(r)]) for r in req_ibm if lid(r) in placed)
assert all(r["resets"] == 0 for r in req_ibm if not rule_mcm(r))
rq0 = [r for r in req_ibm if r["T"] >= 2 and not rule_mcm(r)]
sep = out["steps"]["q5_step_gate_mcm_separation"]
sep["ibm_requested_programs"] = len(req_ibm)
sep["ibm_requested_multi_step_without_mid_circuit_measurement"] = len(rq0)
sep["of_which_not_placed_on_the_patch"] = sum(1 for r in rq0 if lid(r) not in placed)
sep["their_steps_requested"] = sorted({r["T"] for r in rq0})
sep["ibm_corr_steps_cz_requested"] = round(pearson([r["T"] for r in req_ibm], [r["sc_like"]["two_qubit_gates"] for r in req_ibm]), 3)
sep["iqm_requested_multi_step_programs"] = sum(1 for r in req_iqm if r["T"] >= 2)
sep["iqm_requested_multi_step_with_mid_circuit_measurement"] = sum(1 for r in req_iqm if r["T"] >= 2 and rule_mcm(r) and lmcm(placed[lid(r)]))
# kept IonQ QAOA rows with an emulator figure that fall below 0.30 on the emulator (analysis.json aim1_emulator_vs_model)
em1 = {r["id"]: r for r in AN["aim1_emulator_vs_model"]["rows"]}
kq = [x for x in ion_core if x["group"] == "aim1_qaoa" and x["id"] in em1]
out["steps"]["ionq_kept_qaoa_below_030_on_emulator"] = {"kept_with_emulator_figure": len(kq),
    "below_030": sorted(x["id"] for x in kq if em1[x["id"]]["effective_fidelity_emulator"] < 0.30)}
json.dump(out, open(args.out or os.path.join(V, "final_request.json"), "w"), indent=1)
print(json.dumps({"table": table, "totals": out["totals"], "costs": out["costs"], "controls": CTRL}, indent=1))

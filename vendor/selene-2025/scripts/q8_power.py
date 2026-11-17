"""Q8's chance of each verdict from shot noise, with the Selene shares of this rerun as the true shares, the way
final_request.py's q8_power() does it (vendor/scripts/final_request.py: Bernoulli shots, seed 20261115 reset per case,
N = 2,000 draws), with the band added and the transition-metal and actinide groups scored separately.

    python3 -I q8_power.py BASE PKG          (writes BASE/results/q8_power.json)

Q8 as the application states it: "Decided by which prediction the measured share lies nearer on a log scale, as a median
over circuits; the nearer prediction must lie within a factor of 1.5 of the measured share, or both are rejected."
Here, per group (the 8 transition-metal circuits at 200 shots; the 4 actinide circuits at 100 shots), per draw:
  verdict   generic if median_i(observed_i / sqrt(published_i x generic_i)) > 1, else published (final_request.py's rule);
  band      the nearer prediction is within a factor b if the median over circuits of observed_i / nearer_i lies in
            [1/b, b] (our reading of "within a factor of b ... as a median over circuits"); b = 1.5 (the application's) and 1.25.
Predictions:
  published  the model's share F + (1 - F) pN, F = e^-b under a figure set: the one the application admits on
             ("docs 2026-10-20 H2-1", the shares it quotes, 0.56 to 0.73 and 0.27 to 0.34), and, as a second reading,
             the model's closest 2025 set to each emulator (analyze.py's SETMAP), since the preregistered predictions are
             recomputed under the figures current at the first run;
  generic    final_request.py's generic_share, g + (1 - g) pN with g the circuit's modelled_fidelity under our generic law.
True shares: each circuit's Selene share (right electron numbers) on each set and variant, as measured (itself a sample of
200 or 100 shots). Positive control: with the published and generic shares as truth, the false-alarm and power figures
must equal final_request.json's for the admission set."""
import json, math, os, random, statistics as st, sys
B, PKG = sys.argv[1:3]
V = os.path.join(PKG, "vendor", "results")
R = json.load(open(os.path.join(B, "results", "selene_results.json")))["circuits"]
QS = json.load(open(os.path.join(V, "models", "quantinuum_sets.json")))["sets"]
FR = json.load(open(os.path.join(V, "final_request.json")))
TGT = json.load(open(os.path.join(PKG, "results", "targets", "request.json")))
MODEL = {r["case"]: r for r in json.load(open(os.path.join(PKG, "results", "targets", "model.json")))}
IDX = json.load(open(os.path.join(B, "builder", "index.json")))["circuits"]
ADMIT = "docs 2026-10-20 H2-1"
SETMAP = {"H2-1E_2025-07-16": "docs 2025-04-30 H2-1", "H2-2E_2025-07-16": "docs 2025-05-29 H2-2", "Helios-1E_2025-11-18": "docs 2025-08-28 H2-2"}
GROUPS = {"transition_metal": (TGT["IonQ"], 200), "actinide": (TGT["Quantinuum"], 100)}
BANDS = (1.5, 1.25)


def pN(case, q):
    m = MODEL[case]; na, nb = m["electrons"]; return math.comb(m["orbitals"], na) * math.comb(m["orbitals"], nb) / 2 ** q


def rows(src, k):
    out = []
    for r in src:
        cid = "qcup-f-tgt-" + r["case"].lower().replace("_", "-"); q = IDX[cid]["qubits"]; F = QS[k]["circuits"][cid][1]; p = pN(r["case"], q); g = r["modelled_fidelity"]
        out.append({"case": r["case"], "id": cid, "share": F + (1 - F) * p, "generic_share": g + (1 - g) * p})
    return out


def sim(true, pub, gen, shots, N=2000):
    random.seed(20261115)
    n = {"draws": N, "verdict_generic": 0} | {f"published_within_{b}": 0 for b in BANDS} | {f"generic_within_{b}": 0 for b in BANDS} | {f"rejected_both_at_{b}": 0 for b in BANDS}
    for _ in range(N):
        obs = [sum(random.random() < p for _ in range(shots)) / shots for p in true]
        gen_wins = st.median(o / math.sqrt(a * b) for o, a, b in zip(obs, pub, gen)) > 1.0
        near = gen if gen_wins else pub
        m = st.median(o / x for o, x in zip(obs, near))
        n["verdict_generic"] += gen_wins
        for b in BANDS:
            ok = (1 / b) <= m <= b
            if not ok: n[f"rejected_both_at_{b}"] += 1
            elif gen_wins: n[f"generic_within_{b}"] += 1
            else: n[f"published_within_{b}"] += 1
    return {k: (v / N if k != "draws" else v) for k, v in n.items()}


def noise_free(true, pub, gen):
    r = st.median(t / math.sqrt(a * b) for t, a, b in zip(true, pub, gen)); near = gen if r > 1 else pub
    m = st.median(t / x for t, x in zip(true, near))
    return {"median_ratio_to_geometric_midpoint": r, "nearer": "generic" if r > 1 else "published", "median_ratio_to_nearer": m,
            **{f"within_{b}": (1 / b) <= m <= b for b in BANDS}}


out = {"note": __doc__, "controls": {}, "groups": {}}
# positive control against final_request.json (admission set; actinides at 100 shots, transition-metal at 200)
for g, key in (("actinide", ("2_actinide_test", "by_figure_set", ADMIT, "q8_rule", "100_shots")), ("transition_metal", ("3_transition_metal_on_quantinuum", "q8_rule_200_shots"))):
    src, shots = GROUPS[g]; rs = rows(src, ADMIT); pub = [r["share"] for r in rs]; gen = [r["generic_share"] for r in rs]
    a, b = sim(pub, pub, gen, shots), sim(gen, pub, gen, shots)
    want = FR["steps"]
    for k in key: want = want[k]
    out["controls"][g] = {"false_alarm_if_published_true": a["verdict_generic"], "power_if_generic_true": b["verdict_generic"], "final_request_json": want,
                          "equal": abs(a["verdict_generic"] - want["false_alarm_if_published_true"]) < 1e-12 and abs(b["verdict_generic"] - want["power_if_generic_true"]) < 1e-12}
for g, (src, shots) in GROUPS.items():
    G = {"shots": shots, "circuits": len(src), "cases": {}}
    for s, near_set in SETMAP.items():
        for v in ("docs", "docs_dephasing"):
            ids = ["qcup-f-tgt-" + r["case"].lower().replace("_", "-") for r in src]
            if not all(v in R[c][s] for c in ids): continue
            true = [R[c][s][v]["score"] for c in ids]
            for lab, k in (("admission_set", ADMIT), ("closest_2025_set", near_set)):
                rs = rows(src, k); pub = [r["share"] for r in rs]; gen = [r["generic_share"] for r in rs]
                G["cases"][f"{s}|{v}|{lab}"] = {"published_set": k, "true_share": [min(true), max(true)], "published_share": [min(pub), max(pub)],
                                                 "generic_share": [min(gen), max(gen)], "noise_free": noise_free(true, pub, gen), "shot_noise": sim(true, pub, gen, shots)}
    out["groups"][g] = G
json.dump(out, open(os.path.join(B, "results", "q8_power.json"), "w"), indent=1)
print(json.dumps(out["controls"], indent=1))
for g, G in out["groups"].items():
    for k, c in G["cases"].items():
        nf, sn = c["noise_free"], c["shot_noise"]
        print(g, k, "true %.2f-%.2f pub %.2f-%.2f gen %.2f-%.2f" % (*c["true_share"], *c["published_share"], *c["generic_share"]),
              "| nearer", nf["nearer"], "ratio %.2f" % nf["median_ratio_to_nearer"], "| P(generic) %.3f P(pub,1.5) %.3f P(pub,1.25) %.3f P(gen,1.5) %.3f P(gen,1.25) %.3f P(rej,1.5) %.3f P(rej,1.25) %.3f" % (
                  sn["verdict_generic"], sn["published_within_1.5"], sn["published_within_1.25"], sn["generic_within_1.5"], sn["generic_within_1.25"], sn["rejected_both_at_1.5"], sn["rejected_both_at_1.25"]))

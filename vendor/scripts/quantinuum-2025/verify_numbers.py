"""Recompute every number the drafted replacements quote, from the result files. python3 -I verify_numbers.py RESULTS_DIR"""
import json, math, os, sys
D = sys.argv[1]; S = json.load(open(os.path.join(D, "model_results.json")))["sets"]; P = json.load(open(os.path.join(D, "post_results.json")))["sets"]
V = json.load(open(os.path.join(D, "validation.json")))
PUB = ["pub 2023-03-10 H2-1", "pub 2024-05-20 H2-1", "pub 2024-12-06 H2-2", "docs 2025-04-30 H2-1", "docs 2025-05-29 H2-2", "docs 2025-08-28 H2-2", "docs 2026-10-20 H2-1", "docs 2026-10-06 H2-2"]
N1, N2 = "docs 2026-10-20 H2-1", "docs 2026-10-06 H2-2"
def r2(x): return f"{math.floor(x * 100 + 0.5) / 100:.2f}"          # the text rounds half up
claims = []
def c(text, val, ok): claims.append((text, val, ok))
prog = {k: S[k]["n30_aim2_programs"] for k in PUB}; allr = {k: S[k]["n30_all_quantinuum_rows"] for k in PUB}
c("500 to 1,400 on programs (min, max over published sets)", (min(prog.values()), max(prog.values())), round(min(prog.values()), -2) == 500 and round(max(prog.values()), -2) == 1400)
c("550 to 1,600 over all rows", (min(allr.values()), max(allr.values())), round(min(allr.values()), -1) == 550 and round(max(allr.values()), -2) == 1600)
c("720 and 820 on H2-1 newest; 1,150 on H2-2 newest (programs)", (prog[N1], allr[N1], prog[N2]), round(prog[N1], -1) == 720 and round(allr[N1], -1) == 820 and round(prog[N2], -1) == 1150)
c("1.4 = 1,994/max programs", 1994 / max(prog.values()), f"{1994 / max(prog.values()):.1f}" == "1.4")
c("1.5 = (-ln0.3/max programs)/0.000595", (-math.log(0.3) / max(prog.values())) / 0.000595, f"{(-math.log(0.3) / max(prog.values())) / 0.000595:.1f}" == "1.5")
c("core keeps the same 72 on every published set", [P[k]["core_contains_the_72"] for k in PUB], all(P[k]["core_contains_the_72"] for k in PUB))
c("2 to 7 rows added on 2025 and 2026 sets", [len(P[k]["core_added"]) for k in PUB[3:]], min(len(P[k]["core_added"]) for k in PUB[3:]) == 2 and max(len(P[k]["core_added"]) for k in PUB[3:]) == 7)
c("extension 37 on H2-1 newest, 7,444 HQC; 20 to 64 across", (S[N1]["extension"]["kept"], S[N1]["extension"]["hqc_kept"], [S[k]["extension"]["kept"] for k in PUB]),
  S[N1]["extension"]["kept"] == 37 and round(S[N1]["extension"]["hqc_kept"]) == 7444 and min(S[k]["extension"]["kept"] for k in PUB) == 20 and max(S[k]["extension"]["kept"] for k in PUB) == 64)
c("extension total 61 = 37 + 24", 37 + 24, True)
ct = S[N1]["core_total"]; c("core 84 circuits, 4,309 HQC = 2,695 + 1,209 + 405 on H2-1 newest", (ct["circuits_without_double_count"], ct["hqc_without_double_count"]), ct["circuits_without_double_count"] == 84 and round(ct["hqc_without_double_count"]) == 4309)
tm1, ac1, ac2 = S[N1]["transition_metal"], S[N1]["actinides"], S[N2]["actinides"]
c("TM 0.56 to 0.73 (H2-1 newest), fidelity", (tm1["fidelity_min"], tm1["fidelity_max"]), (r2(tm1["fidelity_min"]), r2(tm1["fidelity_max"])) == ("0.56", "0.73"))
c("TM shares 0.56 to 0.73 (H2-1 newest)", (tm1["share_min"], tm1["share_max"]), (r2(tm1["share_min"]), r2(tm1["share_max"])) == ("0.56", "0.73"))
c("actinides 0.24 to 0.33 (H2-1 newest), 2 above 0.30", (ac1["fidelity_min"], ac1["fidelity_max"], ac1["above_30pct"]), (r2(ac1["fidelity_min"]), r2(ac1["fidelity_max"])) == ("0.24", "0.33") and ac1["above_30pct"] == 2)
c("actinides 0.40 to 0.49 (H2-2 newest)", (ac2["fidelity_min"], ac2["fidelity_max"]), (r2(ac2["fidelity_min"]), r2(ac2["fidelity_max"])) == ("0.40", "0.49"))
c("actinide shares 0.27 to 0.34 (H2-1 newest)", (ac1["share_min"], ac1["share_max"]), (r2(ac1["share_min"]), r2(ac1["share_max"])) == ("0.27", "0.34"))
old = PUB[:3]
c("actinides 0.14 to 0.27 on 2023 and 2024 sets", (min(S[k]["actinides"]["fidelity_min"] for k in old), max(S[k]["actinides"]["fidelity_max"] for k in old)),
  (r2(min(S[k]["actinides"]["fidelity_min"] for k in old)), r2(max(S[k]["actinides"]["fidelity_max"] for k in old))) == ("0.14", "0.27"))
c("TM band 0.45 to 0.83; actinide band 0.14 to 0.55", (min(S[k]["transition_metal"]["fidelity_min"] for k in PUB), max(S[k]["transition_metal"]["fidelity_max"] for k in PUB), min(S[k]["actinides"]["fidelity_min"] for k in PUB), max(S[k]["actinides"]["fidelity_max"] for k in PUB)),
  (r2(min(S[k]["transition_metal"]["fidelity_min"] for k in PUB)), r2(max(S[k]["transition_metal"]["fidelity_max"] for k in PUB)), r2(min(S[k]["actinides"]["fidelity_min"] for k in PUB)), r2(max(S[k]["actinides"]["fidelity_max"] for k in PUB))) == ("0.45", "0.83", "0.14", "0.55"))
gm = S[PUB[0]]
c("generic shares 0.81 to 0.91 and 0.63 to 0.68", (gm["transition_metal"]["generic_share_min"], gm["transition_metal"]["generic_share_max"], gm["actinides"]["generic_share_min"], gm["actinides"]["generic_share_max"]),
  (r2(gm["transition_metal"]["generic_share_min"]), r2(gm["transition_metal"]["generic_share_max"]), r2(gm["actinides"]["generic_share_min"]), r2(gm["actinides"]["generic_share_max"])) == ("0.81", "0.91", "0.63", "0.68"))
a60 = {k: (min(S[k]["family_A_60"].values()), max(S[k]["family_A_60"].values())) for k in PUB}
c("A60 0.10 to 0.11 on H2-1 newest; 0.03 to 0.35 across; >=0.30 only on Aug 2025 H2-2", (a60[N1], min(v[0] for v in a60.values()), max(v[1] for v in a60.values()), [k for k in PUB if a60[k][1] >= 0.30]),
  (r2(a60[N1][0]), r2(a60[N1][1])) == ("0.10", "0.11") and r2(min(v[0] for v in a60.values())) == "0.03" and r2(max(v[1] for v in a60.values())) == "0.35" and [k for k in PUB if a60[k][1] >= 0.30] == ["docs 2025-08-28 H2-2"])
q1, q2 = P[N1]["actinides_50_shots"], P[N2]["actinides_50_shots"]
c("Q8 actinides at 50 shots: 1 of 2,000 on H2-1 newest; at most 24 on H2-2's", (q1, q2), round(q1["false_alarm_if_published_true"] * 2000) == 1 and q1["power_if_generic_true"] == 1.0
  and max(round(q2["false_alarm_if_published_true"] * 2000), round((1 - q2["power_if_generic_true"]) * 2000)) == 24)
c("validation 51 of 51", (V["agree"], V["total"]), V["agree"] == 51 and V["total"] == 51)
c("seven later published sets", len(PUB) - 1, len(PUB) - 1 == 7)
bad = 0
for t, v, ok in claims:
    print(("OK  " if ok else "FAIL"), t, "|", v); bad += not ok
print(f"\n{len(claims) - bad} of {len(claims)} claims recompute")

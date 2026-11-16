"""Tabulate model_results.json and post_results.json. python3 -I summarize.py MODEL_RESULTS POST_RESULTS"""
import json, sys
R = json.load(open(sys.argv[1])); S = R["sets"]; P = json.load(open(sys.argv[2]))["sets"]
print("controls:", json.dumps(R["controls"]))
h = f"{'figure set':24s} {'2Q':>8s} {'1Q':>8s} {'mem':>8s} {'readout':>8s} | {'N30 prog':>8s} {'N30 all':>8s} | {'core':>6s} {'core HQC*':>9s} | {'ext':>5s} {'ext HQC':>8s} | {'TM F':>11s} {'TM share':>11s} | {'act F':>11s} {'act share':>11s} {'act>=.3':>7s} | {'A60':>11s} | Q8 act false alarm 50/100/200"
print(h); print("-" * len(h))
for k, v in S.items():
    t = v["terms"]; ct = v["core_total"]; p = P[k]; a60 = list(v["family_A_60"].values())
    print(f"{k:24s} {t['two_qubit_error']:8.2e} {t['one_qubit_error']:8.1e} {t['memory']:8.2e} {t['readout_and_reset']:8.2e} | {v['n30_aim2_programs']:8.1f} {v['n30_all_quantinuum_rows']:8.1f} | "
          f"{ct['circuits_without_double_count']:3d}/93 {ct['hqc_without_double_count']:9.1f} | {v['extension']['kept']:2d}/82 {v['extension']['hqc_kept']:8.1f} | "
          f"{v['transition_metal']['fidelity_min']:.3f}-{v['transition_metal']['fidelity_max']:.3f} {v['transition_metal']['share_min']:.3f}-{v['transition_metal']['share_max']:.3f} | "
          f"{v['actinides']['fidelity_min']:.3f}-{v['actinides']['fidelity_max']:.3f} {v['actinides']['share_min']:.3f}-{v['actinides']['share_max']:.3f} {v['actinides']['above_30pct']:7d} | "
          f"{min(a60):.3f}-{max(a60):.3f} | {p['actinides_50_shots']['false_alarm_if_published_true']:.4f}/{p['actinides_100_shots']['false_alarm_if_published_true']:.4f}/{p['actinides_200_shots']['false_alarm_if_published_true']:.4f}"
          f" (power {p['actinides_50_shots']['power_if_generic_true']:.3f}/{p['actinides_100_shots']['power_if_generic_true']:.3f}/{p['actinides_200_shots']['power_if_generic_true']:.3f})")
print("\n* core circuits and HQC: the kept core rows, plus the 4 actinide circuits at 50 shots (405.0 HQC) and the 8 transition-metal circuits at 200 (1,208.9 HQC),"
      " counting an actinide circuit once when the rule also admits it (final_request.py would count it twice: see core_total.hqc_as_final_request).")
print("generic-law shares (unchanged): transition metals", f"{S['pub 2023-03-10 H2-1']['transition_metal']['generic_share_min']:.3f}-{S['pub 2023-03-10 H2-1']['transition_metal']['generic_share_max']:.3f},",
      "actinides", f"{S['pub 2023-03-10 H2-1']['actinides']['generic_share_min']:.3f}-{S['pub 2023-03-10 H2-1']['actinides']['generic_share_max']:.3f}")
for k in P: print(f"rows added to the 72-row core on {k}: {P[k]['core_added']}")

"""Selene settings from Quantinuum's published emulator parameter table (Emulator_parameters.csv, repository
quantinuum-hardware-specifications at 59e68bb, read as plain data), for H2-1 of 2024-05-20 and H2-2 of 2024-12-06.

    python3 -I make_params.py CSV OUT_DIR

Column meanings (the repository's qtm_spec/combined_analysis.py emulator_parameters(), read as text, and Quantinuum's
emulator documentation, Emulator Noise Model page):
  p1, p2               1- and 2-qubit fault probability (randomized benchmarking, leakage included)
  p1_emission_ratio    fraction of p1 that is spontaneous emission (2 x 1Q leakage / p1)
  p2_emission_ratio    fraction of p2 that is spontaneous emission (2Q leakage / p2 / 0.543)
  dephasing_error      memory (transport) randomized-benchmarking error per memory step, a one-qubit gate included
  p_crosstalk_meas     crosstalk fault probability per mid-circuit measurement
  p_crosstalk_init     crosstalk fault probability per initialisation (blank for every H2 row)
  p_meas_0, p_meas_1   readout flip probability of a 0 and of a 1
The plugin's memory term per clock unit (one layer of two-qubit gates, the application's placement): a Z with
probability 1.5 x (dephasing_error - p1), the dephasing channel whose randomized-benchmarking error is
dephasing_error - p1 (the step's one-qubit gate taken out). The table publishes no per-unit-time rate or durations."""
import csv, json, os, sys
CSV, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
WANT = {("2024_05_20", "H2-1"): "H2-1_2024-05-20", ("2024_12_06", "H2-2"): "H2-2_2024-12-06"}
f = lambda s: float(s) if s.strip() else None
for r in csv.DictReader(open(CSV)):
    k = (r["Date"], r["Machine"])
    if k not in WANT: continue
    t = {c: f(r[c]) for c in ("p1", "p1_emission_ratio", "p2", "p2_emission_ratio", "dephasing_error", "p_crosstalk_meas", "p_crosstalk_init", "p_meas_0", "p_meas_1")}
    mem = t["dephasing_error"] - t["p1"]
    out = {"name": WANT[k], "source": "Emulator_parameters.csv row %s %s (repository 59e68bb)" % k, "table": t,
           "selene": {
               "p1": t["p1"], "p1_emission_ratio": t["p1_emission_ratio"], "p2": t["p2"], "p2_emission_ratio": t["p2_emission_ratio"],
               "p_meas_0": t["p_meas_0"], "p_meas_1": t["p_meas_1"], "p_init": 0.0,
               "p_crosstalk_meas": t["p_crosstalk_meas"], "p_crosstalk_init": t["p_crosstalk_init"] or 0.0,
               "memory_step_error": mem, "memory_pz": 1.5 * mem},
           "selene_depolarizing": {"p_1q": t["p1"], "p_2q": t["p2"], "p_meas": (t["p_meas_0"] + t["p_meas_1"]) / 2, "p_init": 0.0}}
    json.dump(out, open(os.path.join(OUT, WANT[k] + ".json"), "w"), indent=1)
    print(json.dumps(out))

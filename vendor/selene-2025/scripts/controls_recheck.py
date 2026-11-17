"""Re-run of control C3 (the emission split) with fresh seeds and more shots: in controls.json both C3 runs used seed 11
on the same program, so they share one draw of the emission branch (leaked fraction 0.4914 at 20,000 shots, z = -2.43).
    python -I controls_recheck.py WORK_DIR PLUGIN_LIB OUT_JSON"""
import json, math, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
WORK, LIB, OUT = sys.argv[1:4]
os.makedirs(WORK, exist_ok=True)
PI = math.pi
Z0 = {"p1": 0.0, "p1_emission_ratio": 0.0, "p2": 0.0, "p2_emission_ratio": 0.0, "przz_a": 0.0, "przz_b": 1.0, "przz_c": 0.0, "przz_d": 1.0, "przz_power": 1.0,
      "p_meas_0": 0.0, "p_meas_1": 0.0, "p_init": 0.0, "p_crosstalk_meas": 0.0, "p_crosstalk_init": 0.0, "leakage_model": False, "leak2depolar": False,
      "p_prep_leak_ratio": 0.0, "p1_seepage_prob": 0.0, "p2_seepage_prob": 0.0, "memory_pz": 0.0}
res = {}
for leak in (True, False):
    for seed in (12, 13):
        name = f"c3_recheck_{'leak' if leak else 'noleak'}_s{seed}"
        gp = os.path.join(WORK, name + ".gates.json"); json.dump({"id": name, "qubits": 1, "clbits": 1, "gates": [["rx", [0], [PI], []], ["measure", [0], [], [0]]]}, open(gp, "w"))
        jp = os.path.join(WORK, name + ".job.json"); op = os.path.join(WORK, name + ".out.json")
        json.dump({"id": name, "gates": gp, "set": "control", "variant": "control", "shots": 40000, "seed": seed, "out": op,
                   "params": dict(Z0, p1=1.0, p1_emission_ratio=1.0, leakage_model=leak), "plugin_lib": LIB, "work_dir": WORK, "min_angles": True}, open(jp, "w"))
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "run_job.py"), jp], check=True, capture_output=True)
        o = json.load(open(op)); n = len(o["metrics"])
        k = "leak_1q" if leak else "leak_as_depolar_1q"
        f = sum(m.get("e:" + k, 0) for m in o["metrics"]) / n; xy = sum(m.get("e:emission_xy_1q", 0) for m in o["metrics"]) / n
        p0 = sum(1 for b in o["bits"] if b == "0") / n; e0 = 0.5 if leak else 5 / 6
        res[name] = {"leakage_branch_fraction": f, "z": (f - 0.5) / math.sqrt(0.25 / n), "x_or_y_fraction": xy, "p_read_0": p0, "expect_read_0": e0,
                     "z_read_0": (p0 - e0) / math.sqrt(e0 * (1 - e0) / n), "shots": n}
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps(res, indent=1))

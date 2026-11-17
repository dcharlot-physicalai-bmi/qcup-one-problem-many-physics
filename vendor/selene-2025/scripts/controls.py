"""Positive controls for the docs-noise plugin and the Selene setup, each against a closed form.

    python -I controls.py WORK_DIR PLUGIN_LIB OUT_JSON PROGRAM_GATES_JSON PARAMS_DIR [N_PARALLEL]

Carried over from the 2024 run (same programs, same closed forms):
C1 readout      |0> and |1> read 40,000 times, p_meas_0 = 0.01, p_meas_1 = 0.05: flip rates.
C2 memory       a qubit in |+> waits 22 two-qubit layers (memory_pz = 0.01): P(1) = (1 - (1 - 2p)^22) / 2; in |0>: P(1) = 0.
C4 meas. xtalk  p_crosstalk_meas = 0.2 on a waiting qubit in |+>: P(1) = 0.2 x 1/2 = 0.1.
C5 depolarizing the plugin with neutral angle scaling (przz 0, 1, 0, 1, 1) against Selene's DepolarizingErrorModel on a
                request program: mean faults per shot and trace fidelity equal within shot noise.
C6 ideal        the same program with no noise gives its reference trace on every shot.
New terms:
C3 emission     one rx(pi) then a read, p1 = 1, emission ratio 1. Leakage model (Helios): half the shots leak (read
                as 1), P(read 0) = 1/2. No leakage model (H2): the leakage half is X, Y or Z evenly, nothing leaks,
                P(read 0) = 1/4 + 1/4 + 1/2 x 2/3 = 5/6.
C7 angle        six qubit pairs in |00>, one rzz each at theta = pi/2, pi/4, pi/8, 0.05, -pi/4, -pi/2; emission ratio 0,
                p2 = 0.5. A depolarizing fault (15 Paulis evenly) changes the pair's reading with probability 12/15, so
                P(pair not 00) = 0.5 x s(theta) x 0.8. Run (a) with the documented fit (1.518, 0.241, 1.518, 0.241, 1),
                and (b) with an unequal fit (2.0, 0.1, 1.0, 0.3, power 2), which tells the theta < 0 branch (a, b) from
                the theta > 0 branch (c, d) and checks the power. Also the per-shot sum of s(theta) the plugin reports,
                against the closed form to 1e-12.
C7c emission    the same six rzz with p2 = 0.5 and emission ratio 0.5 (documented fit, no leakage model): emissions per
                shot 6 x 0.25 = 1.5 at every angle (the emission channel is not scaled), depolarizing faults per shot
                0.25 x sum of s(theta).
C8 init leak    Helios leakage model, p_init = 1, p_prep_leak_ratio = 0.75: leakage at 0.75 of initialisations.
C8b seepage 1q  every allocation leaks (p_init = 1, ratio 1); three rx(pi) on the leaked qubit, p1_seepage_prob = 1/3:
                seepage events per shot 1 - (2/3)^3 = 0.7037; P(read 1) = (2/3)^3 + (1 - (2/3)^3)/2 = 0.6481.
C8c seepage 2q  both qubits leak at allocation; three rzz(pi/2) on the pair, p2_seepage_prob = 1/3: seepage events per
                shot 2 (1 - (2/3)^3) = 1.4074; leaked-partner events sum over k < 3 of 2 (2/3)^k (1 - (2/3)^k) = 76/81.
C9 init xtalk   p_crosstalk_init = 0.2 on a waiting qubit in |+> while another qubit is reset: P(1) = 0.1.
C10 init error  no leakage model, p_init = 0.1: an X at allocation, P(1) = 0.1.
C11 dephasing   each set's memory_pz recomputed here from the table and the stated duration, against params/."""
import json, math, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
WORK, LIB, OUT, PROG, PARAMS = sys.argv[1:6]
NPAR = int(sys.argv[6]) if len(sys.argv) > 6 else 6
os.makedirs(WORK, exist_ok=True)
PY = sys.executable
PI = math.pi
Z0 = {"p1": 0.0, "p1_emission_ratio": 0.0, "p2": 0.0, "p2_emission_ratio": 0.0, "przz_a": 0.0, "przz_b": 1.0, "przz_c": 0.0, "przz_d": 1.0, "przz_power": 1.0,
      "p_meas_0": 0.0, "p_meas_1": 0.0, "p_init": 0.0, "p_crosstalk_meas": 0.0, "p_crosstalk_init": 0.0, "leakage_model": False, "leak2depolar": False,
      "p_prep_leak_ratio": 0.0, "p1_seepage_prob": 0.0, "p2_seepage_prob": 0.0, "memory_pz": 0.0}
DOC_FIT = {"przz_a": 1.518, "przz_b": 0.241, "przz_c": 1.518, "przz_d": 0.241, "przz_power": 1.0}
ODD_FIT = {"przz_a": 2.0, "przz_b": 0.1, "przz_c": 1.0, "przz_d": 0.3, "przz_power": 2.0}
ANGLES = [PI / 2, PI / 4, PI / 8, 0.05, -PI / 4, -PI / 2]


def s_of(fit, t):
    x = (abs(t) / PI) ** fit["przz_power"]
    return fit["przz_a"] * x + fit["przz_b"] if t < 0 else (fit["przz_c"] * x + fit["przz_d"] if t > 0 else (fit["przz_b"] + fit["przz_d"]) / 2)


def job(name, gates, nq, nc, variant, params, shots, seed=11):
    gp = os.path.join(WORK, name + ".gates.json"); json.dump({"id": name, "qubits": nq, "clbits": nc, "gates": gates}, open(gp, "w"))
    jp = os.path.join(WORK, name + ".job.json"); op = os.path.join(WORK, name + ".out.json")
    json.dump({"id": name, "gates": gp, "set": "control", "variant": variant, "shots": shots, "seed": seed, "out": op, "params": params,
               "plugin_lib": LIB, "work_dir": WORK, "min_angles": True}, open(jp, "w"))
    return name, jp, op


def frac(rows, pos, val="1"):
    return sum(1 for b in rows if b[pos] == val) / len(rows)


def sig(p, n): return math.sqrt(max(p * (1 - p), 1e-12) / n)


def mean(o, k): return sum(m.get("e:" + k, 0) for m in o["metrics"]) / len(o["metrics"])


g = json.load(open(PROG))
pairs = [["rzz", [2 * j, 2 * j + 1], [t], []] for j, t in enumerate(ANGLES)]
meas12 = [["measure", [q], [], [q]] for q in range(12)]
lay = [["rzz", [1, 2], [PI / 2], []] for _ in range(20)]
wait = [["rzz", [0, 1], [PI / 2], []], ["rzz", [0, 1], [-PI / 2], []]]
JOBS = [
    job("c1_readout", [["rx", [1], [PI], []], ["measure", [0], [], [0]], ["measure", [1], [], [1]]], 2, 2, "control", dict(Z0, p_meas_0=0.01, p_meas_1=0.05), 40000),
    job("c2_memory", [["ry", [0], [PI / 2], []]] + lay + wait + [["ry", [0], [-PI / 2], []], ["measure", [0], [], [0]]], 3, 1, "control", dict(Z0, memory_pz=0.01), 20000),
    job("c2_memory_basis", [["rx", [0], [PI], []]] + lay + wait + [["measure", [0], [], [0]]], 3, 1, "control", dict(Z0, memory_pz=0.01), 4000),
    job("c3_emission_leak", [["rx", [0], [PI], []], ["measure", [0], [], [0]]], 1, 1, "control", dict(Z0, p1=1.0, p1_emission_ratio=1.0, leakage_model=True), 20000),
    job("c3_emission_noleak", [["rx", [0], [PI], []], ["measure", [0], [], [0]]], 1, 1, "control", dict(Z0, p1=1.0, p1_emission_ratio=1.0), 20000),
    job("c4_crosstalk", [["ry", [0], [PI / 2], []], ["ry", [1], [PI / 2], []], ["measure", [1], [], [1]], ["rzz", [0, 1], [PI / 2], []], ["rzz", [0, 1], [-PI / 2], []],
                         ["ry", [0], [-PI / 2], []], ["measure", [0], [], [0]]], 2, 2, "control", dict(Z0, p_crosstalk_meas=0.2), 40000),
    job("c7_angle_documented", pairs + meas12, 12, 12, "control", dict(Z0, p2=0.5, **DOC_FIT), 20000),
    job("c7_angle_unequal_fit", pairs + meas12, 12, 12, "control", dict(Z0, p2=0.5, **ODD_FIT), 20000),
    job("c7c_emission_unscaled", pairs + meas12, 12, 12, "control", dict(Z0, p2=0.5, p2_emission_ratio=0.5, **DOC_FIT), 20000),
    job("c8_init_leak", [["measure", [0], [], [0]]], 1, 1, "control", dict(Z0, p_init=1.0, leakage_model=True, p_prep_leak_ratio=0.75), 20000),
    job("c8b_seepage_1q", [["rx", [0], [PI], []]] * 3 + [["measure", [0], [], [0]]], 1, 1, "control",
        dict(Z0, p_init=1.0, leakage_model=True, p_prep_leak_ratio=1.0, p1_seepage_prob=1 / 3), 20000),
    job("c8c_seepage_2q", [["rzz", [0, 1], [PI / 2], []]] * 3 + [["measure", [0], [], [0]], ["measure", [1], [], [1]]], 2, 2, "control",
        dict(Z0, p_init=1.0, leakage_model=True, p_prep_leak_ratio=1.0, p2_seepage_prob=1 / 3), 20000),
    job("c9_init_crosstalk", [["ry", [0], [PI / 2], []]] + wait + [["reset", [1], [], []]] + wait + [["ry", [0], [-PI / 2], []], ["measure", [0], [], [0]]], 2, 1,
        "control", dict(Z0, p_crosstalk_init=0.2), 40000),
    job("c10_init_error", [["measure", [0], [], [0]]], 1, 1, "control", dict(Z0, p_init=0.1), 40000),
    job("c5_depolarizing", g["gates"], g["qubits"], g["clbits"], "depolarizing", dict(Z0, p1=2e-3, p2=2e-2, p_meas_0=1e-2, p_meas_1=1e-2), 4000),
    job("c5_plugin", g["gates"], g["qubits"], g["clbits"], "control", dict(Z0, p1=2e-3, p2=2e-2, p_meas_0=1e-2, p_meas_1=1e-2), 4000),
    job("c6_ideal", g["gates"], g["qubits"], g["clbits"], "ideal", {}, 500),
]


def run(j):
    name, jp, op = j
    if not os.path.exists(op):
        r = subprocess.run([PY, "-I", os.path.join(HERE, "run_job.py"), jp], capture_output=True, text=True)
        if r.returncode: raise SystemExit(f"{name} failed: {r.stdout[-2000:]} {r.stderr[-2000:]}")
    return name, json.load(open(op))


with ThreadPoolExecutor(NPAR) as ex:
    R = dict(ex.map(run, JOBS))

res = {}
o = R["c1_readout"]; b = o["bits"]; f0 = frac(b, 1, "1"); f1 = frac(b, 0, "0")       # bits are printed clbit 1 first
res["C1_readout"] = {"flip_0": f0, "expect_0": 0.01, "z_0": (f0 - 0.01) / sig(0.01, len(b)), "flip_1": f1, "expect_1": 0.05, "z_1": (f1 - 0.05) / sig(0.05, len(b))}
o = R["c2_memory"]; p = frac(o["bits"], 0); e = (1 - (1 - 0.02) ** 22) / 2
res["C2_memory"] = {"p1": p, "expect": e, "z": (p - e) / sig(e, len(o["bits"])), "memory_units_values": sorted({m.get("e:memory_units") for m in o["metrics"]})}
o = R["c2_memory_basis"]; res["C2_memory_basis_state"] = {"p_wrong": 1 - frac(o["bits"], 0), "expect": 0.0, "memory_z_total": sum(m.get("e:memory_z", 0) for m in o["metrics"])}
o = R["c3_emission_leak"]; n = len(o["bits"]); p0 = frac(o["bits"], 0, "0"); lk = mean(o, "leak_1q")
res["C3_emission_leakage_model"] = {"leaked_fraction": lk, "expect": 0.5, "z": (lk - 0.5) / sig(0.5, n), "p_read_0": p0, "expect_read_0": 0.5, "z_read_0": (p0 - 0.5) / sig(0.5, n),
                                    "leaked_read_as_1": all(bb == "1" for bb, m in zip(o["bits"], o["metrics"]) if m.get("e:leaked_reads"))}
o = R["c3_emission_noleak"]; n = len(o["bits"]); p0 = frac(o["bits"], 0, "0"); ld = mean(o, "leak_as_depolar_1q")
res["C3_emission_no_leakage_model"] = {"leaks": sum(m.get("e:leak_1q", 0) for m in o["metrics"]), "leak_as_depolar_fraction": ld, "expect": 0.5, "z": (ld - 0.5) / sig(0.5, n),
                                       "p_read_0": p0, "expect_read_0": 5 / 6, "z_read_0": (p0 - 5 / 6) / sig(5 / 6, n)}
o = R["c4_crosstalk"]; p = frac(o["bits"], 1)
res["C4_crosstalk"] = {"p1": p, "expect": 0.1, "z": (p - 0.1) / sig(0.1, len(o["bits"]))}
for key, fit in (("c7_angle_documented", DOC_FIT), ("c7_angle_unequal_fit", ODD_FIT)):
    o = R[key]; n = len(o["bits"]); rows = []
    for j, t in enumerate(ANGLES):
        # bits are printed clbit 11 first: qubit q is position 11 - q
        a, c = 11 - 2 * j, 11 - (2 * j + 1)
        got = sum(1 for bb in o["bits"] if bb[a] == "1" or bb[c] == "1") / n
        s = s_of(fit, t); want = 0.5 * s * 0.8
        rows.append({"theta": t, "s": s, "p_pair_changed": got, "expect": want, "z": (got - want) / sig(want, n)})
    ssum = [m.get("e:rzz_scale_sum") for m in o["metrics"]]
    res["C7_" + key[3:]] = {"fit": fit, "per_angle": rows, "max_abs_z": max(abs(r["z"]) for r in rows),
                            "scale_sum_closed_form": sum(r["s"] for r in rows), "scale_sum_plugin_max_abs_difference": max(abs(x - sum(r["s"] for r in rows)) for x in ssum)}
o = R["c7c_emission_unscaled"]; n = len(o["metrics"]); S = sum(s_of(DOC_FIT, t) for t in ANGLES)
em = mean(o, "emission_xy_2q") + mean(o, "leak_as_depolar_2q") + mean(o, "leak_2q"); dp = mean(o, "pauli_2q")
# emissions per shot: a sum of 6 Bernoulli(0.25) draws less the cases where a depolarizing draw took the same rzz; the draw is one
# uniform per rzz: emission if u < 0.25, depolarizing if 0.25 <= u < 0.25 + 0.25 s, so the counts are independent sums of Bernoulli trials
ve = 6 * 0.25 * 0.75; vd = sum(0.25 * s_of(DOC_FIT, t) * (1 - 0.25 * s_of(DOC_FIT, t)) for t in ANGLES)
res["C7c_emission_not_scaled"] = {"emissions_per_shot": em, "expect": 1.5, "z": (em - 1.5) / math.sqrt(ve / n), "depolarizing_per_shot": dp, "expect_depolarizing": 0.25 * S,
                                  "z_depolarizing": (dp - 0.25 * S) / math.sqrt(vd / n),
                                  "emission_prob_sum_plugin": sorted({round(m.get("e:rzz_emis_prob_sum"), 12) for m in o["metrics"]}),
                                  "depolarizing_prob_sum_plugin": sorted({round(m.get("e:rzz_dep_prob_sum"), 12) for m in o["metrics"]}), "depolarizing_prob_sum_closed_form": round(0.25 * S, 12)}
o = R["c8_init_leak"]; n = len(o["metrics"]); li = mean(o, "leak_init"); ie = mean(o, "init_errors")
res["C8_init_leakage"] = {"leak_fraction": li, "expect": 0.75, "z": (li - 0.75) / sig(0.75, n), "x_fraction": ie, "expect_x": 0.25, "inits_per_shot": mean(o, "inits")}
o = R["c8b_seepage_1q"]; n = len(o["metrics"]); sp = mean(o, "seep_1q"); e = 1 - (2 / 3) ** 3; p1 = frac(o["bits"], 0); ep = (2 / 3) ** 3 + e / 2
res["C8b_seepage_1q"] = {"seepage_per_shot": sp, "expect": e, "z": (sp - e) / sig(e, n), "p_read_1": p1, "expect_read_1": ep, "z_read_1": (p1 - ep) / sig(ep, n)}
o = R["c8c_seepage_2q"]; n = len(o["metrics"]); sp = mean(o, "seep_2q"); e = 2 * (1 - (2 / 3) ** 3); lp = mean(o, "leaked_partner"); el = 76 / 81
vs = 2 * (1 - (2 / 3) ** 3) * (2 / 3) ** 3
res["C8c_seepage_2q"] = {"seepage_per_shot": sp, "expect": e, "z": (sp - e) / math.sqrt(vs / n), "leaked_partner_per_shot": lp, "expect_leaked_partner": el}
o = R["c9_init_crosstalk"]; p = frac(o["bits"], 0)
res["C9_init_crosstalk"] = {"p1": p, "expect": 0.1, "z": (p - 0.1) / sig(0.1, len(o["bits"]))}
o = R["c10_init_error"]; p = frac(o["bits"], 0)
res["C10_init_error"] = {"p1": p, "expect": 0.1, "z": (p - 0.1) / sig(0.1, len(o["bits"]))}
a = R["c5_depolarizing"]; c = R["c5_plugin"]; ref = g["reference_bits"]
st = a["program_stats"]; nm = st["measure_mid"] + st["measure_final"]
expect = st["rxy_native"] * 2e-3 + st["rzz_native"] * 2e-2 + nm * 1e-2
fa = [sum(v for k, v in m.items() if k.startswith("e:errors_") or k in ("e:measurement_errors", "e:init_errors")) for m in a["metrics"]]
fc = [m.get("e:faults_total", 0) for m in c["metrics"]]
ta = sum(bb == ref for bb in a["bits"]) / len(a["bits"]); tc = sum(bb == ref for bb in c["bits"]) / len(c["bits"])
res["C5_depolarizing_vs_plugin"] = {"program": g["id"], "program_stats": st, "expected_faults_per_shot": expect, "depolarizing_mean_faults": sum(fa) / len(fa),
                                    "plugin_mean_faults": sum(fc) / len(fc), "depolarizing_trace_fidelity": ta, "plugin_trace_fidelity": tc,
                                    "trace_difference_z": (ta - tc) / math.sqrt(sig(ta, len(a["bits"])) ** 2 + sig(tc, len(c["bits"])) ** 2)}
i = R["c6_ideal"]; res["C6_ideal"] = {"program": g["id"], "trace_fidelity": sum(bb == ref for bb in i["bits"]) / len(i["bits"])}
res["C11_dephasing_arithmetic"] = {}
for f in sorted(os.listdir(PARAMS)):
    if not f.endswith(".json") or "_20" not in f: continue
    P = json.load(open(os.path.join(PARAMS, f))); T = P["table"]; d = P["dephasing_assumption"]["seconds_per_two_qubit_layer"]
    pl = T["linear_dephasing_rate"] * d; ang = 2 * PI * T["quadratic_dephasing_rate"] * T["coherent_to_incoherent_factor"] * d; pq = math.sin(ang / 2) ** 2
    m = pl * (1 - pq) + pq * (1 - pl)
    res["C11_dephasing_arithmetic"][P["name"]] = {"memory_pz_here": m, "memory_pz_params": P["plugin_docs_dephasing"]["memory_pz"], "equal": abs(m - P["plugin_docs_dephasing"]["memory_pz"]) < 1e-15}
zs = []
def walk(x):
    if isinstance(x, dict):
        for k, v in x.items():
            if (k.startswith("z") or k.endswith("_z")) and k != "max_abs_z" and isinstance(v, (int, float)): zs.append(abs(v))
            else: walk(v)
    elif isinstance(x, list):
        for v in x: walk(v)
walk(res)
res["summary"] = {"z_values": len(zs), "max_abs_z": max(zs), "within_2_sigma": sum(z < 2 for z in zs), "within_3_sigma": sum(z < 3 for z in zs)}
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps(res, indent=1))

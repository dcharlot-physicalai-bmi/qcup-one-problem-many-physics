"""Positive controls for the published-noise plugin and the Selene setup, each against a closed form.

    python controls.py WORK_DIR PLUGIN_LIB OUT_JSON

C1 readout      |0> and |1> read 40,000 times, p_meas_0 = 0.01, p_meas_1 = 0.05: flip rates.
C2 memory       a qubit in |+> waits while 20 two-qubit layers run on two other qubits, then takes two rzz with one of
                them (in |0>, so the pair is rz(pi/2) rz(-pi/2) on it: the identity, but it must wait for the layers), is
                rotated back and read; memory_pz = 0.01 over 22 units: P(1) = (1 - (1 - 2p)^22) / 2 = 0.1794. (Selene's
                runtime schedules each operation as soon as its qubits are free, so a qubit with nothing to wait for is
                rotated back at once and idles in |0>.) With the qubit in |0> instead (a state a Z cannot change), P(1) = 0.
C3 emission     one rx(pi/2) with p1 = 1: with emission ratio 1, half the shots leak (read as 1, leaked_reads), a quarter
                get X, a quarter Y; with ratio 0, none leaks.
C4 crosstalk    two qubits in |+>; one is measured, then takes rzz(pi/2) and rzz(-pi/2) with the other (the identity,
                but after the measurement), which is then rotated back and read; p_crosstalk_meas = 0.2: P(1) = 0.2 x 1/2 = 0.1.
C5 depolarizing the same small program under Selene's DepolarizingErrorModel and under the plugin with the same p1, p2
                and a symmetric readout and nothing else: mean faults per shot equal to n_rxy p1 + n_rzz p2 + n_meas p_meas
                for both, and trace fidelities equal within shot noise.
C6 ideal        the same program with no noise: every shot gives the reference trace."""
import json, math, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
WORK, LIB, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(WORK, exist_ok=True)
PY = sys.executable
PI = math.pi
Z0 = {k: 0.0 for k in ("p1", "p1_emission_ratio", "p2", "p2_emission_ratio", "p_meas_0", "p_meas_1", "p_init", "p_crosstalk_meas", "p_crosstalk_init", "memory_pz")}


def run(name, gates, nq, nc, variant, params, shots, seed=11):
    gp = os.path.join(WORK, name + ".gates.json"); json.dump({"id": name, "qubits": nq, "clbits": nc, "gates": gates}, open(gp, "w"))
    jp = os.path.join(WORK, name + ".job.json"); op = os.path.join(WORK, name + ".out.json")
    json.dump({"id": name, "gates": gp, "set": "control", "variant": variant, "shots": shots, "seed": seed, "out": op, "params": params, "plugin_lib": LIB, "work_dir": WORK}, open(jp, "w"))
    subprocess.run([PY, os.path.join(HERE, "run_job.py"), jp], check=True)
    return json.load(open(op))


def frac(rows, pos, val="1"):
    return sum(1 for b in rows if b[pos] == val) / len(rows)


def sig(p, n): return math.sqrt(max(p * (1 - p), 1e-12) / n)


res = {}
# C1
o = run("c1_readout", [["rx", [1], [PI], []], ["measure", [0], [], [0]], ["measure", [1], [], [1]]], 2, 2, "published", dict(Z0, p_meas_0=0.01, p_meas_1=0.05), 40000)
b = o["bits"]; f0 = frac(b, 1, "1"); f1 = frac(b, 0, "0")       # bits are printed clbit 1 first
res["C1_readout"] = {"flip_0": f0, "expect_0": 0.01, "z_0": (f0 - 0.01) / sig(0.01, len(b)), "flip_1": f1, "expect_1": 0.05, "z_1": (f1 - 0.05) / sig(0.05, len(b))}
# C2
lay = [["rzz", [1, 2], [PI / 2], []] for _ in range(20)]
wait = [["rzz", [0, 1], [PI / 2], []], ["rzz", [0, 1], [-PI / 2], []]]
o = run("c2_memory", [["ry", [0], [PI / 2], []]] + lay + wait + [["ry", [0], [-PI / 2], []], ["measure", [0], [], [0]]], 3, 1, "published", dict(Z0, memory_pz=0.01), 20000)
p = frac(o["bits"], 0); e = (1 - (1 - 0.02) ** 22) / 2
res["C2_memory"] = {"p1": p, "expect": e, "units_expected": 22, "z": (p - e) / sig(e, 20000), "clock_first_shot": o["metrics"][0].get("e:clock_max"), "memory_units_values": sorted({m.get("e:memory_units") for m in o["metrics"]})}
o = run("c2_memory_basis", [["rx", [0], [PI], []]] + lay + wait + [["measure", [0], [], [0]]], 3, 1, "published", dict(Z0, memory_pz=0.01), 4000)
res["C2_memory_basis_state"] = {"p_wrong": 1 - frac(o["bits"], 0), "expect": 0.0, "memory_z_total": sum(m.get("e:memory_z", 0) for m in o["metrics"])}
# C3
o = run("c3_emission", [["rx", [0], [PI / 2], []], ["measure", [0], [], [0]]], 1, 1, "published", dict(Z0, p1=1.0, p1_emission_ratio=1.0), 20000)
lk = sum(m.get("e:leaked_reads", 0) for m in o["metrics"]) / len(o["metrics"]); xy = sum(m.get("e:emission_xy_1q", 0) for m in o["metrics"]) / len(o["metrics"])
res["C3_emission"] = {"leaked_fraction": lk, "expect": 0.5, "z": (lk - 0.5) / sig(0.5, 20000), "xy_fraction": xy, "leaked_read_as_1": all(b == "1" for b, m in zip(o["bits"], o["metrics"]) if m.get("e:leaked_reads"))}
o = run("c3_emission_off", [["rx", [0], [PI / 2], []], ["measure", [0], [], [0]]], 1, 1, "published", dict(Z0, p1=1.0, p1_emission_ratio=0.0), 4000)
res["C3_emission_ratio_0"] = {"leaks": sum(m.get("e:leak_1q", 0) for m in o["metrics"]), "pauli_1q_per_shot": sum(m.get("e:pauli_1q", 0) for m in o["metrics"]) / 4000}
# C4
o = run("c4_crosstalk", [["ry", [0], [PI / 2], []], ["ry", [1], [PI / 2], []], ["measure", [1], [], [1]], ["rzz", [0, 1], [PI / 2], []], ["rzz", [0, 1], [-PI / 2], []],
         ["ry", [0], [-PI / 2], []], ["measure", [0], [], [0]]], 2, 2,
        "published", dict(Z0, p_crosstalk_meas=0.2), 40000)
p = frac(o["bits"], 1)                       # clbit 0 is printed last
res["C4_crosstalk"] = {"p1": p, "expect": 0.1, "z": (p - 0.1) / sig(0.1, 40000)}
# C5 and C6 on a request program
g = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else None
if g:
    ref = g["reference_bits"]; P = dict(Z0, p1=2e-3, p2=2e-2, p_meas_0=1e-2, p_meas_1=1e-2)
    a = run("c5_depolarizing", g["gates"], g["qubits"], g["clbits"], "depolarizing", P, 4000)
    c = run("c5_plugin", g["gates"], g["qubits"], g["clbits"], "published", P, 4000)
    st = a["program_stats"]; nm = st["measure_mid"] + st["measure_final"]
    expect = st["rxy_native"] * 2e-3 + st["rzz_native"] * 2e-2 + nm * 1e-2
    fa = [sum(v for k, v in m.items() if k.startswith("e:errors_") or k in ("e:measurement_errors", "e:init_errors")) for m in a["metrics"]]
    fc = [m.get("e:faults_total", 0) for m in c["metrics"]]
    ta = sum(b == ref for b in a["bits"]) / 4000; tc = sum(b == ref for b in c["bits"]) / 4000
    native = {k: sorted({m.get("u:" + k) for m in a["metrics"]}) for k in ("rxy_count", "rz_count", "rzz_count")}
    # project_z adds a conditional x after a read of 1 (an extra rxy); expected faults are counted on the program's own operations
    res["C5_depolarizing_vs_plugin"] = {"program": g["id"], "program_stats": st, "selene_native_counts": native, "expected_faults_per_shot": expect,
        "depolarizing_mean_faults": sum(fa) / len(fa), "plugin_mean_faults": sum(fc) / len(fc), "depolarizing_trace_fidelity": ta, "plugin_trace_fidelity": tc,
        "trace_difference_z": (ta - tc) / math.sqrt(sig(ta, 4000) ** 2 + sig(tc, 4000) ** 2)}
    i = run("c6_ideal", g["gates"], g["qubits"], g["clbits"], "ideal", {}, 500)
    res["C6_ideal"] = {"program": g["id"], "trace_fidelity": sum(b == ref for b in i["bits"]) / 500}
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps(res, indent=1))

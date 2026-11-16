#!/usr/bin/env python3
"""QCUP hardware check, design stage: build the circuits exactly as the package does, embed them on IBM devices, export.

Runs on the build host in a venv with the package's pinned versions (numpy 2.5.3, scipy 1.18.1, qiskit 2.6.2,
qiskit-aer 0.18.2, qiskit-ibm-runtime 0.52.0). Reads the package's own builders (aim2.py, aim2b.py, aim1_post.py) and
result files; never writes to the package.

Each circuit is transpiled the way the application does it (aim2_run.py / aim1_post.py): to the n-qubit heavy-hex patch,
CZ basis, optimisation level 3, seed 7. The two-qubit gate count is checked against the package's own result file. The
patch circuit is then placed on the device unchanged: a noise-aware subgraph embedding (VF2Layout over the device's
design-time calibration) maps every patch qubit to a device qubit, so the device runs exactly the application's circuit
and its CZ count is the admission count. No routing and no further optimisation.

Arms: dd_off = the ISA circuit as placed (no delays; the device times it). dd_on = the same circuit scheduled ALAP with the
device's durations and padded with the XX sequence (tau/2 X tau X tau/2, IBM's default) by qiskit's PadDynamicalDecoupling.

Usage: design.py OUT_DIR CAL_DIR"""
import glob, io, json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); PKG = os.path.abspath(os.path.join(HERE, "..", "pkg")); sys.path.insert(0, PKG)
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile, qasm3, qpy
from qiskit.circuit.library import XGate
from qiskit.quantum_info import Statevector
from qiskit.transpiler import PassManager, Target, InstructionProperties
from qiskit.transpiler.passes import VF2Layout, ALAPScheduleAnalysis, PadDynamicalDecoupling, PadDelay
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.models import BackendConfiguration, BackendProperties
from qiskit_ibm_runtime.utils.backend_converter import convert_to_target
from aim2 import build, reference, trace_prob
from aim2b import build_inplace
from aim1_post import heavy_hex_patch, qaoa_circuit, diag_energy, EPS

OUT, CAL = map(os.path.abspath, sys.argv[1:3]); os.makedirs(OUT, exist_ok=True)
R = f"{PKG}/results"
BACKENDS = ("ibm_marrakesh", "ibm_kingston", "ibm_fez")
SC_BASIS = ["cz", "rz", "sx", "x"]

# ---- the selection: distinct programs spanning the heavy-hex CZ range (stream 0, the stream the package records)
# A mix of one-step (no mid-circuit measurement or reset) and five-step programs, with two- and three-step ones at the top
# of the range. One-step programs carry a guessing floor of 1/8 (3 trace bits), so they are kept to 422 CZ and below.
AIM2 = [("17_traffic_light_accept", "P", 5), ("ch07_form_injective_f64", "R", 5), ("counter_flag", "R", 1),
        ("t59_distinguish_mod3_mod4", "R", 5), ("t59_distinguish_mod5_mod4", "R", 1), ("hc_21_kept_step_is_input", "R", 1),
        ("t60_dim_redundant_k5", "R", 5), ("queue_sim", "R", 1), ("counter", "R", 1), ("hc_11_fabric_caps_logged", "R", 5),
        ("washer", "R", 5), ("door", "R", 3), ("03_distributed_accept", "G", 2), ("s1_guard_trap_keeps", "R", 3),
        ("t62_dependent_differ", "R", 2), ("session", "R", 2)]
CONTROL_ZERO = ("thermostat", "R", 5)              # 0 CZ, mid-circuit measurement and reset, 5 trace bits
# (family, n, depth, start, placement). "embed": the patch circuit placed unchanged. "route": the patch circuit contains the
# patch's 10-cycle, which no Heron lattice has, so it is transpiled to the device as aim1_ibm.py does (level 3, best of 8 seeds).
AIM1 = [("B", 12, 1, "warm", "embed"), ("R", 12, 2, "cold", "route"), ("B", 20, 1, "warm", "embed"), ("B", 16, 2, "warm", "embed"),
        ("D", 12, 2, "warm", "embed"), ("B", 16, 3, "warm", "embed")]
SHOTS = {"aim2": 1000, "control": 1000, "aim1": 4000}


def rows_for(form):
    return json.load(open(f"{R}/aim2/{form}.json"))


def aim2_circuit(form, style, T):
    forms = json.load(open(f"{PKG}/forms/selected.json")); i = next(k for k, F in enumerate(forms) if F["name"] == form); F = forms[i]
    table, S, E = F["table"], F["states"], len(F["events"])
    sb = max(1, math.ceil(math.log2(S))); eb = math.ceil(math.log2(E)) if E > 1 else 0
    delta = lambda s, e: table[s][e] if s < S and e < E else s
    rng = np.random.default_rng([20261111, i])                      # aim2_run.run_form, same streams
    streams = [[int(x) for x in rng.integers(0, E, 5)] for _ in range(5)] if E > 1 else [[0] * 5]
    ev = streams[0][:T]; ref = reference(delta, 0, ev)
    qc = build_inplace(delta, sb, 0, T) if style == "P" else build(style, delta, sb, eb, 0, ev)[0]
    row = next(r for r in rows_for(form) if r["stream"] == 0 and r["style"] == style and r["T"] == T)
    assert row["reference_trace"] == ref and row["event_stream"] == ev, f"{form}: stream or trace differs from the package"
    w = qc.num_qubits
    tq = transpile(qc, coupling_map=heavy_hex_patch(w) if w > 1 else None, basis_gates=SC_BASIS + ["reset", "measure"], optimization_level=3, seed_transpiler=7)
    cz = int(tq.count_ops().get("cz", 0))
    assert cz == row["sc_like"]["two_qubit_gates"], f"{form} {style} T{T}: CZ {cz} != package {row['sc_like']['two_qubit_gates']}"
    ideal = AerSimulator(method="statevector").run(tq, shots=200, seed_simulator=3).result().get_counts()
    assert trace_prob(ideal, ref, sb) == 1.0
    return tq, {"kind": "aim2", "form": form, "source": F["source"], "style": style, "T": T, "state_bits": sb, "event_bits": eb, "event_stream": ev,
                "reference_trace": ref, "trace_bits": sb * T, "uniform_floor": 2.0 ** -(sb * T), "qubits": w, "resets": int(tq.count_ops().get("reset", 0)),
                "mid_circuit_measurements": int(tq.count_ops().get("measure", 0)) - (sb if style != "G" else sb * T), "cz": cz,
                "want": "".join(format(s, f"0{sb}b") for s in reversed(ref)), "creg": "trace",
                "package_generic_trace_fidelity_2000_shots": row["sc_like"].get("trace_fidelity"),
                "package_snapshot": {k: row[k] for k in ("ibm_torino_snapshot", "ibm_fez_snapshot") if k in row}}


def mirror_circuit():
    """Positive control: U then U^-1 on a 6-qubit patch, then X on a fixed pattern, so the ideal output is one known string."""
    n = 6; cm = heavy_hex_patch(n); edges = sorted({tuple(sorted(e)) for e in cm.get_edges()})
    rng = np.random.default_rng(20261115)
    u = QuantumCircuit(n)
    for layer in range(3):
        for q in range(n):
            u.rz(float(rng.integers(1, 8)) * math.pi / 4, q); u.sx(q)
        used = set()
        for a, b in (edges if layer % 2 == 0 else edges[::-1]):
            if a not in used and b not in used: u.cz(a, b); used |= {a, b}
    want_bits = [1, 0, 1, 1, 0, 1]                                    # qubit q -> bit q
    qc = QuantumCircuit(QuantumRegister(n, "q"), ClassicalRegister(n, "c"))
    qc.compose(u, inplace=True); qc.barrier(); qc.compose(u.inverse(), inplace=True); qc.barrier()
    for q, b in enumerate(want_bits):
        if b: qc.x(q)
    qc.measure(range(n), range(n))
    tq = transpile(qc, coupling_map=cm, basis_gates=SC_BASIS + ["measure"], optimization_level=0, initial_layout=list(range(n)), seed_transpiler=7)
    tq = transpile(tq, basis_gates=SC_BASIS + ["measure"], optimization_level=0)  # keep as written
    noll = QuantumCircuit(*tq.qregs, *tq.cregs)
    for ins in tq.data:
        if ins.operation.name != "barrier": noll.append(ins)
    want = "".join(str(b) for b in reversed(want_bits))
    ideal = AerSimulator(method="statevector").run(noll, shots=200, seed_simulator=3).result().get_counts()
    assert ideal.get(want, 0) == 200, ideal
    return noll, {"kind": "control_mirror", "qubits": n, "cz": int(noll.count_ops().get("cz", 0)), "want": want, "creg": "c", "uniform_floor": 2.0 ** -n,
                  "description": "3 layers of rz(k pi/4) sx and a CZ matching on the 6-qubit heavy-hex patch, then the exact inverse, then X on bits 0,2,3,5"}


def aim1_circuit(fam, n, p, kind, place="embed"):
    d = json.load(open(f"{R}/aim1_{fam}_{n}_0.json")); post = json.load(open(f"{R}/post_{fam}_{n}_0.json")); gw = json.load(open(f"{R}/gw_{fam}_{n}_0.json"))
    h, edges = d["h"], d["edges"]; e = diag_energy(n, h, edges); e_min, e_max = float(e.min()), float(e.max())
    ground = [int(g) for g in np.flatnonzero(e <= e_min + 1e-9 * (1 + abs(e_min)))]
    x = np.array([(s + 1) // 2 for s in gw["gw16_state"]]); thetas = 2 * np.arcsin(np.sqrt(np.where(x == 1, 1 - EPS, EPS)))
    q = (d["qaoa"] if kind == "cold" else post["ws"])[p - 1]
    qc = qaoa_circuit(n, h, edges, q["gamma"], q["beta"], thetas if kind == "warm" else None)
    pr = np.abs(Statevector(qc).data) ** 2; p_gs = float(pr[ground].sum())
    assert abs(p_gs - q["p_gs"]) < 1e-6, f"{fam}{n} p{p} {kind}: ideal p_gs {p_gs} != package {q['p_gs']}"
    package_cz = next(t["heavy_hex_cz"] for t in post["transpile"] if t["p"] == p)
    qm = qc.copy(); qm.measure_all()
    tq = transpile(qm, coupling_map=heavy_hex_patch(n), basis_gates=SC_BASIS, optimization_level=3, seed_transpiler=7)   # aim1_post's sampling call
    return tq, {"kind": "aim1", "family": fam, "n": n, "p": p, "start": kind, "placement": place, "qubits": n, "cz": int(tq.count_ops().get("cz", 0)), "package_heavy_hex_cz": package_cz,
                "ideal_p_gs": p_gs, "ground_states": ground, "e_min": e_min, "e_max": e_max, "creg": "meas", "uniform_floor": len(ground) / 2 ** n,
                "gw16_is_optimal": post["gw16_is_optimal"], "_logical": qm}


def load_target(b):
    conf = BackendConfiguration.from_dict(json.load(open(glob.glob(f"{CAL}/{b}-configuration-*.json")[0])))
    props_d = json.load(open(glob.glob(f"{CAL}/{b}-properties-*.json")[0])); props = BackendProperties.from_dict(props_d)
    full = convert_to_target(conf, props)
    # layout target: only usable qubits (T1, T2 and readout stated, readout error < 0.1) and CZ pairs with error < 0.05
    ok = set()
    for i, qq in enumerate(props_d["qubits"]):
        d = {x["name"]: x["value"] for x in qq}
        if d.get("T1") and d.get("T2") and d.get("readout_error") is not None and d["readout_error"] < 0.1: ok.add(i)
    lt = Target(num_qubits=full.num_qubits, dt=full.dt)
    for name in ("cz", "rz", "sx", "x", "measure", "reset", "delay"):
        pr = {}
        for qargs, ip in full[name].items():
            if not all(qa in ok for qa in qargs): continue
            if name == "cz" and (ip is None or ip.error is None or ip.error >= 0.05): continue
            pr[qargs] = ip
        lt.add_instruction(full.operation_from_name(name), pr)
    return full, lt, props_d["last_update_date"], sorted(set(range(full.num_qubits)) - ok)


def strip(tq):
    plain = QuantumCircuit(QuantumRegister(tq.num_qubits, "q"), *tq.cregs)
    for ins in tq.data:
        if ins.operation.name == "barrier": continue
        plain.append(ins.operation, [plain.qubits[tq.find_bit(q).index] for q in ins.qubits], [plain.clbits[tq.find_bit(c).index] for c in ins.clbits])
    return plain


def route(plain, full, lt):
    """aim1_ibm.py's device transpilation: optimisation level 3, keep the best of 8 layout seeds by two-qubit gate count."""
    best = None
    for seed in range(8):
        t = transpile(plain, target=lt, optimization_level=3, seed_transpiler=seed); two = int(t.count_ops().get("cz", 0))
        if best is None or two < best[0]: best = (two, seed, t)
    isa = best[2]
    for ins in isa.data:
        qs = tuple(isa.find_bit(q).index for q in ins.qubits)
        assert ins.operation.name == "barrier" or full.instruction_supported(ins.operation.name, qs), (ins.operation.name, qs)
    phys = sorted({isa.find_bit(q).index for ins in isa.data for q in ins.qubits if ins.operation.name not in ("barrier", "delay")})
    return isa, phys, best[1]


def embed(plain, full, lt):
    pm = PassManager([VF2Layout(target=lt, seed=7, call_limit=int(3e7), max_trials=250000, strict_direction=False)])
    pm.run(plain)
    lay = pm.property_set["layout"]
    if lay is None: raise RuntimeError(f"no embedding: {pm.property_set.get('VF2Layout_stop_reason')}")
    phys = [lay[q] for q in plain.qubits]
    isa = transpile(plain, target=full, initial_layout=phys, routing_method="none", optimization_level=0, seed_transpiler=7)
    assert int(isa.count_ops().get("cz", 0)) == int(plain.count_ops().get("cz", 0))
    for ins in isa.data:
        qs = tuple(isa.find_bit(q).index for q in ins.qubits)
        assert full.instruction_supported(ins.operation.name, qs), (ins.operation.name, qs)
    return isa, phys


def active_only(circ, active):
    """Drop instructions on device qubits the program does not use (delays or DD that padding may put there)."""
    out = circ.copy_empty_like()
    for ins in circ.data:
        if all(circ.find_bit(q).index in active for q in ins.qubits): out.append(ins)
    return out


def scheduled(isa, full, dd):
    passes = [ALAPScheduleAnalysis(target=full)]
    passes.append(PadDynamicalDecoupling(target=full, dd_sequence=[XGate(), XGate()], skip_reset_qubits=True) if dd else PadDelay(target=full))
    return PassManager(passes).run(isa)


def main():
    circs = []
    for form, style, T in AIM2:
        tq, meta = aim2_circuit(form, style, T); meta["id"] = f"a2-{form}-{style}{T}".lower().replace("_", "-"); meta["shots"] = SHOTS["aim2"]; circs.append((tq, meta))
    tq, meta = aim2_circuit(*CONTROL_ZERO); meta.update(kind="control_zero_cz", id="ctl-zero-cz-thermostat-r5", shots=SHOTS["control"]); circs.append((tq, meta))
    tq, meta = mirror_circuit(); meta.update(id="ctl-mirror-6q", shots=SHOTS["control"]); circs.append((tq, meta))
    for fam, n, p, kind, place in AIM1:
        tq, meta = aim1_circuit(fam, n, p, kind, place); meta["id"] = f"a1-{fam}{n}-p{p}-{kind}".lower(); meta["shots"] = SHOTS["aim1"]; circs.append((tq, meta))
    for tq, m in circs: print(m["id"], "qubits", m["qubits"], "cz", m["cz"], flush=True)
    with open(f"{OUT}/patch_circuits.qpy", "wb") as f: qpy.dump([strip(tq) for tq, _ in circs], f)
    design = {"circuits": [m for _, m in circs], "backends": {}}
    for b in BACKENDS:
        full, lt, cal_date, excluded = load_target(b)
        bd = {"calibration_last_update_date": cal_date, "excluded_qubits": excluded, "layouts": {}, "durations_us": {}, "device_cz": {}, "route_seed": {}}
        isas, isas_dd = [], []
        os.makedirs(f"{OUT}/{b}/qasm_dd_off", exist_ok=True); os.makedirs(f"{OUT}/{b}/qasm_dd_on", exist_ok=True)
        for tq, m in circs:
            plain = strip(tq)
            if m.get("placement") == "route": isa, phys, bd["route_seed"][m["id"]] = route(m["_logical"], full, lt)
            else: isa, phys = embed(plain, full, lt)
            act = set(phys); bd["device_cz"][m["id"]] = int(isa.count_ops().get("cz", 0))
            dd = active_only(scheduled(isa, full, True), act); pad = active_only(scheduled(isa, full, False), act)
            dd._layout = isa._layout; pad._layout = isa._layout       # keep physical-qubit naming ($n) in the export
            bd["layouts"][m["id"]] = phys
            bd["durations_us"][m["id"]] = {"alap_us": round(pad.estimate_duration(full, unit="s") * 1e6, 3), "dd_x_pulses": int(dd.count_ops().get("x", 0) - isa.count_ops().get("x", 0)),
                                         "idle_delay_us_total": round(sum(float(i.operation.duration) for i in pad.data if i.operation.name == "delay") * full.dt * 1e6, 3)}
            open(f"{OUT}/{b}/qasm_dd_off/{m['id']}.qasm", "w").write(qasm3.dumps(isa)); open(f"{OUT}/{b}/qasm_dd_on/{m['id']}.qasm", "w").write(qasm3.dumps(dd))
            isas.append(isa); isas_dd.append(dd)
            print(b, m["id"], "layout", phys, bd["durations_us"][m["id"]], flush=True)
        with open(f"{OUT}/{b}/isa_dd_off.qpy", "wb") as f: qpy.dump(isas, f)
        with open(f"{OUT}/{b}/isa_dd_on.qpy", "wb") as f: qpy.dump(isas_dd, f)
        design["backends"][b] = bd
    design["circuits"] = [{k: v for k, v in m.items() if not k.startswith("_")} for m in design["circuits"]]
    json.dump(design, open(f"{OUT}/design.json", "w"), indent=1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Budget-script e^-b on ibm_marrakesh for every IBM Aim 2 circuit up to CAP2 CZ (stream 0, the stream the package counts).

Each circuit is built by the package's own code and placed on the device exactly as the sealed IBM check placed its
circuits: rows_for, aim2_circuit, load_target, strip and embed are copied verbatim from the check's scripts/design.py
(heavy-hex patch, CZ basis, level 3, seed 7; the patch circuit embedded unchanged by VF2Layout over the design-time
calibration). The placed circuit is exported as OpenQASM 3 with a design.json that the check's budget.py (unchanged)
reads, so e^-b here is that script's per-circuit figure. Circuits whose patch uses the 10-cycle no Heron lattice has
cannot be embedded and are listed, not costed.
Positive control: the check's own circuits in this range must reproduce the sealed design/pred/budget_script.json.
Usage: ladder_budget.py PKG CAL OUT CAP2"""
import glob, io, json, math, os, sys
import numpy as np
PKG, CAL, OUT = map(os.path.abspath, sys.argv[1:4]); CAP2 = int(sys.argv[4]); sys.path.insert(0, PKG)
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile, qasm3
from qiskit.transpiler import PassManager, Target
from qiskit.transpiler.passes import VF2Layout
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.models import BackendConfiguration, BackendProperties
from qiskit_ibm_runtime.utils.backend_converter import convert_to_target
from aim2 import build, reference, trace_prob
from aim2b import build_inplace
from aim1_post import heavy_hex_patch
R = f"{PKG}/results"
SC_BASIS = ["cz", "rz", "sx", "x"]
B = "ibm_marrakesh"


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

def main():
    a2 = [r for p in sorted(glob.glob(f"{R}/aim2/*.json")) for r in json.load(open(p))]
    rows = [r for r in a2 if r["stream"] == 0 and r["sc_like"]["two_qubit_gates"] <= CAP2]
    full, lt, cal_date, excluded = load_target(B)
    os.makedirs(f"{OUT}/{B}/qasm_dd_off", exist_ok=True)
    metas, device_cz, layouts, failed = [], {}, {}, []
    for r in sorted(rows, key=lambda r: (r["sc_like"]["two_qubit_gates"], r["form"], r["style"], r["T"])):
        form, style, T = r["form"], r["style"], r["T"]
        mid = f"a2-{form}-{style}{T}".lower().replace("_", "-")
        tq, meta = aim2_circuit(form, style, T); meta["id"] = mid
        try:
            isa, phys = embed(strip(tq), full, lt)
        except Exception as e:
            failed.append({"id": mid, "form": form, "style": style, "T": T, "qubits": meta["qubits"], "cz": meta["cz"], "why": str(e)[:200]}); print(mid, "NO EMBEDDING", flush=True); continue
        device_cz[mid] = int(isa.count_ops().get("cz", 0)); layouts[mid] = phys
        open(f"{OUT}/{B}/qasm_dd_off/{mid}.qasm", "w").write(qasm3.dumps(isa))
        metas.append(meta); print(mid, "qubits", meta["qubits"], "cz", meta["cz"], "resets", meta["resets"], "mcm", meta["mid_circuit_measurements"], flush=True)
    design = {"circuits": metas, "backends": {B: {"calibration_last_update_date": cal_date, "excluded_qubits": excluded, "device_cz": device_cz, "layouts": layouts}},
              "not_embedded": failed, "cap2": CAP2, "rows_in_range": len(rows)}
    json.dump(design, open(f"{OUT}/design.json", "w"), indent=1)


if __name__ == "__main__":
    main()

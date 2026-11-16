#!/usr/bin/env python3
"""RELAX/1 quantum lowering (draft, for QCUP): `relax.sample` and `relax.anneal` on Ising energies -> QAOA.

RELAX/1 v0.1 (EFA-RFC-002) lowers one relaxation program to GPU simulation, settling fabrics, p-bit
samplers, Ising annealers and neuromorphic chips, and names gate-model quantum hardware as out of scope.
This module is the missing column. It follows the RFC's op signatures and design rules:
  - energy-typed execution: every executing op takes a budget and either satisfies it or REFUSES,
    and a refusal is a receipted outcome with a typed reason
  - receipts native: every executing op emits an OER/1 (EFA-RFC-001) receipt
  - provenance is stated on both axes; a simulated run is `simulated x emulation`
The RFC does not fix JSON field names for the exchange form, so the names used here are PROVISIONAL.
Two deviations from OER/1 v1.0 are flagged in the receipt itself: `execution.substrate.family` uses the
proposed value `quantum_gate` (v1.0 offers only `other`), and `energy.joules_total` is null with
`extensions.unpriced = true`, because no metered gate-model energy figure exists yet.
"""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.abspath(__file__))
import os
import hashlib, json, math, sys, time, uuid
import numpy as np

DEFAULT_GATE_BUDGET = {"heavy_hex": 660, "all_to_all": 2000}   # two-qubit gates at 30% modelled trace fidelity (generic models, fitted on the 40 Aim 2 programs)


class Refusal(Exception):
    def __init__(self, reason, detail):
        super().__init__(f"{reason}: {detail}"); self.reason, self.detail = reason, detail


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def ising_from_node(node):
    if node.get("form") != "ising":
        raise Refusal("unsupported_energy_form", f"{node.get('form')!r}: the quantum lowering accepts form 'ising' only")
    n = int(node["n"]); h = [0.0] * n
    for i, v in node.get("biases", []): h[int(i)] = float(v)
    edges = [(int(i), int(j), float(w)) for i, j, w in node.get("couplings", [])]
    return n, h, edges


def qaoa_circuit(n, h, edges, gamma, beta, warm_state=None, eps=0.25):
    """E(s) = -sum J s_i s_j - sum h s_i, bit 1 <-> s = +1. Cold start, or Egger-style warm start from a +-1 state."""
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(n)
    thetas = None
    if warm_state is not None:
        c = [1 - eps if s > 0 else eps for s in warm_state]
        thetas = [2 * math.asin(math.sqrt(ci)) for ci in c]
    for q in range(n):
        qc.h(q) if thetas is None else qc.ry(thetas[q], q)
    for g, b in zip(gamma, beta):
        for i, j, w in edges: qc.rzz(-2 * g * w, i, j)
        for i in range(n):
            if h[i]: qc.rz(2 * g * h[i], i)
        for q in range(n):
            if thetas is None: qc.rx(2 * b, q)
            else: qc.ry(-thetas[q], q); qc.rz(-2 * b, q); qc.ry(thetas[q], q)
    qc.measure_all()
    return qc


def energy_of(bits, h, edges):
    s = [1 if b == "1" else -1 for b in reversed(bits)]
    return -sum(w * s[i] * s[j] for i, j, w in edges) - sum(hi * si for hi, si in zip(h, s))


def lower_and_run(program, shots_default=1000):
    """Execute a RELAX/1 program on the reference emulator. Returns (result, receipt). Never raises on refusal."""
    t0 = time.time()
    nodes = {nd["id"]: nd for nd in program["nodes"]}
    op = next(nd for nd in program["nodes"] if nd["op"] in ("relax.sample", "relax.anneal"))
    ver = next((nd for nd in program["nodes"] if nd["op"] == "relax.verify"), None)
    receipt = {"oer_version": "1.0", "receipt_id": str(uuid.uuid4()), "issued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "issuer": {"org": "Institute for Physical AI @ JBI", "contact": "mailto:david@physicalai-bmi.org"},
               "workload": {"name": program.get("name", "relax-program"), "spec_uri": "https://physicalai-bmi.org/assets/papers/relax-1-dialect", "input_hash": sha(program), "output_hash": None, "quality": None},
               "execution": {"substrate": {"family": "quantum_gate", "device_model": "qiskit-aer statevector (reference emulation)", "device_count": 1, "firmware": None},
                             "stack": [{"layer": "compiler", "name": "relax_quantum (draft lowering)", "version": "0.1"}], "site": None},
               "energy": {"joules_total": None, "breakdown": {"compute_j": None, "movement_j": None, "idle_alloc_j": None}, "method": "model_estimated", "meter": None, "sampling_hz": None},
               "provenance": {"how": "simulated", "device": "emulation", "note": "ideal state-vector emulation; no device noise, no device energy"},
               "latency": {"wall_s": None, "time_to_first_valid_s": None, "p99_decision_s": None},
               "certificate": {"type": "none", "coverage": None, "evidence_uri": None},
               "extensions": {"unpriced": True, "proposed_substrate_family": "quantum_gate", "refused": None}}
    try:
        from qiskit import transpile, qasm3
        from qiskit_aer import AerSimulator
        n, h, edges = ising_from_node(nodes[op["energy"]])
        budget = op.get("budget", {})
        if "qubits" in budget and n > budget["qubits"]:
            raise Refusal("qubit_budget", f"program needs {n} qubits, budget allows {budget['qubits']}")
        lw = op.get("lowering", {})
        if "gamma" not in lw or "beta" not in lw:
            raise Refusal("angles_missing", "QAOA angles must be supplied (pre-optimised in simulation or transferred); the lowering runs no in-loop optimisation")
        qc = qaoa_circuit(n, h, edges, lw["gamma"], lw["beta"], lw.get("warm_state"))
        topo = lw.get("topology", "all_to_all")
        tq = transpile(qc, basis_gates=["rzz", "rz", "rx", "ry"], optimization_level=3, seed_transpiler=7)
        two = int(tq.count_ops().get("rzz", 0))
        if topo == "heavy_hex":
            sys.path.insert(0, ROOT); from aim1_post import heavy_hex_patch
            tq = transpile(qc, coupling_map=heavy_hex_patch(n), basis_gates=["cz", "rz", "sx", "x"], optimization_level=3, seed_transpiler=7)
            two = int(tq.count_ops().get("cz", 0))
        cap = budget.get("two_qubit_gates", DEFAULT_GATE_BUDGET[topo])
        if two > cap:
            raise Refusal("gate_budget", f"{two} two-qubit gates on {topo} exceeds the admission budget of {cap}")
        shots = int(op.get("n", shots_default))
        counts = AerSimulator(method="statevector").run(tq, shots=shots, seed_simulator=int(op.get("seed", 0))).result().get_counts()
        scored = sorted(((energy_of(b.replace(" ", ""), h, edges), b.replace(" ", ""), c) for b, c in counts.items()))
        best_e, best_bits, _ = scored[0]
        result = {"best_state": [1 if b == "1" else -1 for b in reversed(best_bits)], "best_energy": best_e, "shots": shots,
                  "two_qubit_gates": two, "topology": topo, "mean_energy": sum(e * c for e, _, c in scored) / shots, "openqasm3": qasm3.dumps(tq)}
        bound = lw.get("certified_lower_bound")
        if bound is not None:
            gap = (best_e - bound) / abs(bound) if bound else None
            result["certified_gap"] = gap; result["proof"] = bool(gap is not None and gap <= 1e-9)
            receipt["workload"]["quality"] = {"metric": "certified_relative_gap", "value": gap, "higher_is_better": False}
        if ver is not None:
            result["verified"] = bool(best_e <= ver["threshold"]); result["margin"] = ver["threshold"] - best_e
        receipt["workload"]["output_hash"] = sha({k: v for k, v in result.items() if k != "openqasm3"})
    except Refusal as r:
        result = {"refused": r.reason, "detail": r.detail}
        receipt["extensions"]["refused"] = {"reason": r.reason, "detail": r.detail}
    receipt["latency"]["wall_s"] = round(time.time() - t0, 4)
    receipt["attestation"] = {"receipt_hash": sha({k: v for k, v in receipt.items() if k != "receipt_id"}), "signature": None, "pubkey": None, "witness": None}
    return result, receipt


def program_from_instance(path, post_path, p=1, warm=False, topology="all_to_all", shots=1000):
    """Build a RELAX/1 program from an Aim 1 instance file, with angles taken from its simulation record."""
    d = json.load(open(path)); post = json.load(open(post_path))
    src = (post["ws"] if warm else d["qaoa"])[p - 1]
    gw = json.load(open(path.replace("aim1_", "gw_")))
    return {"relax": "1", "name": f"aim1-{d['family']}-{d['n']}-{d['seed']}-p{p}-{'warm' if warm else 'cold'}",
            "nodes": [{"id": "E", "op": "relax.define_energy", "form": "ising", "n": d["n"], "couplings": d["edges"], "biases": [[i, v] for i, v in enumerate(d["h"]) if v]},
                      {"id": "S", "op": "relax.sample", "energy": "E", "n": shots, "seed": 17, "budget": {"qubits": 60},
                       "lowering": {"target": "qaoa", "gamma": src["gamma"], "beta": src["beta"], "warm_state": gw["gw16_state"] if warm else None,
                                    "topology": topology, "certified_lower_bound": d["sdp_bound"]}},
                      {"id": "V", "op": "relax.verify", "energy": "E", "threshold": d["gw16_energy"] if "gw16_energy" in d else gw["gw16_energy"]}]}


if __name__ == "__main__":
    R = os.path.join(ROOT, "results")
    demos = []
    for tag, p, warm, topo in (("B_12_0", 2, True, "all_to_all"), ("C_12_0", 3, False, "heavy_hex"), ("A_16_0", 3, False, "heavy_hex")):
        prog = program_from_instance(f"{R}/aim1_{tag}.json", f"{R}/post_{tag}.json", p, warm, topo)
        res, rec = lower_and_run(prog)
        qasm = res.pop("openqasm3", None)
        if qasm: open(f"{R}/relax_demo_{tag}.qasm", "w").write(qasm)
        demos.append({"program": prog["name"], "result": res, "receipt": rec})
        print(prog["name"], {k: res[k] for k in res if k not in ("best_state",)})
    json.dump(demos, open(f"{R}/relax_quantum_demo.json", "w"), indent=1)

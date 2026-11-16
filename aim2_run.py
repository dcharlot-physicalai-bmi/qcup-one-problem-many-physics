#!/usr/bin/env python3
"""QCUP pre-submission, Aim 2 on the harvested Form set: one Form per call, every style and target.

Input: forms/selected.json (written by select_forms.py from the reference-derived tables of harvest.py).
For Form i: state bits = ceil(log2(states)), event bits = ceil(log2(events)); codes outside the table are fixed points.
Styles: G garbage-retaining (stream 0 only), R reset, and P in place when the Form has one event and its
transition is a permutation.
Per circuit: transpile to a heavy-hex patch (CZ) and all-to-all (RZZ); if width <= 14, check the noiseless circuit
against the reference trace (20 shots) and, if width <= 12 and it has at most GATE_CAP two-qubit gates, sample it
under the generic noise model (2,000 shots).
For R and P on stream 0: OpenQASM 3 and Guppy emission, and, at T = 5, Selene replay and the IBM calibration snapshots.
Usage: aim2_run.py <index> [<index> ...]
"""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.abspath(__file__))
import os
import json, math, os, subprocess, sys, time
import numpy as np
from qiskit import transpile, qasm3
from qiskit_aer import AerSimulator
sys.path.insert(0, ROOT)
from aim2 import anf, build, reference, logical_erasure, noise, trace_prob
from aim2b import is_permutation, build_inplace, to_guppy
from aim1_post import heavy_hex_patch
OUT = f"{ROOT}/results/aim2"
GATE_CAP = 3000      # above this a 2,000-shot fidelity estimate is indistinguishable from zero
for d in ("", "/qasm3", "/guppy"): os.makedirs(OUT + d, exist_ok=True)


def complexity(delta, sb, eb):
    """Size of the positive-polarity Reed-Muller form of the transition: monomials and literals over all output bits."""
    nin, terms, lits = sb + eb, 0, 0
    for b in range(sb):
        for mono in anf([(delta(x & ((1 << sb) - 1), x >> sb) >> b) & 1 for x in range(1 << nin)], nin):
            terms += 1; lits += bin(mono).count("1")
    return terms, lits


def run_form(i, fakes):
    F = json.load(open(f"{ROOT}/forms/selected.json"))[i]
    name, table, S, E = F["name"], F["table"], F["states"], len(F["events"])
    sb = max(1, math.ceil(math.log2(S))); eb = math.ceil(math.log2(E)) if E > 1 else 0
    delta = lambda s, e: table[s][e] if s < S and e < E else s
    rng = np.random.default_rng([20261111, i])
    streams = [[int(x) for x in rng.integers(0, E, 5)] for _ in range(5)] if E > 1 else [[0] * 5]
    perm = is_permutation(delta, sb, eb) and eb == 0
    terms, lits = complexity(delta, sb, eb)
    rows = []
    for si, stream in enumerate(streams):
        for T in ([1, 2, 3, 4, 5] if si == 0 else [5]):
            ev = stream[:T]; ref = reference(delta, 0, ev)
            for style in (["G"] if si == 0 else []) + ["R"] + (["P"] if perm and si == 0 else []):
                qc = build_inplace(delta, sb, 0, T) if style == "P" else build(style, delta, sb, eb, 0, ev)[0]
                w = qc.num_qubits; tag = f"{name}_{style}_T{T}"
                row = {"form": name, "source": F["source"], "kind": F["kind"], "states": S, "events": E, "state_bits": sb, "event_bits": eb, "anf_terms": terms, "anf_literals": lits,
                       "is_permutation": perm, "stream": si, "event_stream": ev, "T": T, "style": style, "qubits": w, "resets": int(qc.count_ops().get("reset", 0)),
                       "overwritten_bits": sb * T, "logical_erasure_bits": round(logical_erasure(delta, sb, 0, ev), 4), "reference_trace": ref}
                for target in ("sc_like", "ion_like"):
                    nm, basis = noise(target)
                    tq = transpile(qc, coupling_map=heavy_hex_patch(w) if target == "sc_like" and w > 1 else None, basis_gates=basis + ["reset", "measure"], optimization_level=3, seed_transpiler=7)
                    two = int(tq.count_ops().get(basis[0], 0))
                    r = {"two_qubit_gates": two, "two_qubit_depth": int(tq.depth(lambda g: g.operation.num_qubits == 2)), "depth": int(tq.depth())}
                    if w <= 14:
                        ideal = AerSimulator(method="statevector").run(tq, shots=20, seed_simulator=3).result().get_counts()
                        assert trace_prob(ideal, ref, sb) == 1.0, f"{tag}: compiled circuit does not replay the reference trace"
                        r["noiseless_trace_ok"] = True
                        if two <= GATE_CAP and w <= 12:
                            c = AerSimulator(noise_model=nm, method="statevector").run(tq, shots=2000, seed_simulator=11).result().get_counts()
                            r["trace_fidelity"] = trace_prob(c, ref, sb); r["shots"] = 2000
                    row[target] = r
                if style in ("R", "P") and si == 0:
                    open(f"{OUT}/qasm3/{tag}.qasm", "w").write(qasm3.dumps(transpile(qc, basis_gates=["x", "h", "cx", "ccx", "rz", "reset", "measure"], optimization_level=0)))
                    gsrc, ngates = to_guppy(qc, tag); path = f"{OUT}/guppy/{tag}.py"; open(path, "w").write(gsrc); row["guppy_gates"] = ngates
                    if T == 5:
                        try:
                            got = json.loads(subprocess.run([sys.executable, path, "20"], capture_output=True, text=True, timeout=900, check=True).stdout.strip().splitlines()[-1])
                            want = "".join(format(s, f"0{sb}b") for s in reversed(ref))
                            row["selene_replays_reference"] = all(g == want for g in got); row["selene_shots"] = len(got)
                        except subprocess.TimeoutExpired: row["selene_replays_reference"] = "timeout"
                        except subprocess.CalledProcessError as e: row["selene_replays_reference"] = "error: " + e.stderr.strip().splitlines()[-1][:120]
                    for fname, fb in (fakes.items() if T == 5 else []):
                        tq = transpile(qc, backend=fb, optimization_level=3, seed_transpiler=7)
                        two = sum(v for k, v in tq.count_ops().items() if k in ("cz", "ecr", "cx", "rzz"))
                        active = len({q for inst in tq.data for q in inst.qubits})
                        r = {"two_qubit_gates": int(two), "active_qubits": active, "depth": int(tq.depth())}
                        if active <= 14 and two <= GATE_CAP:
                            c = AerSimulator.from_backend(fb).run(tq, shots=2000, seed_simulator=11).result().get_counts()
                            r["trace_fidelity"] = trace_prob(c, ref, sb); r["shots"] = 2000
                        row[fname] = r
                rows.append(row)
                print(" ", tag, si, time.strftime("%H:%M:%S"), flush=True)
    json.dump(rows, open(f"{OUT}/{name}.json", "w"), indent=1)
    t5 = [r for r in rows if r["T"] == 5 and r["style"] == "R" and r["stream"] == 0][0]
    print(i, name, "S", S, "E", E, "R T5 qubits", t5["qubits"], "CZ", t5["sc_like"]["two_qubit_gates"], "fid", t5["sc_like"].get("trace_fidelity"), "selene", t5.get("selene_replays_reference"), flush=True)


if __name__ == "__main__":
    from qiskit_ibm_runtime.fake_provider import FakeTorino, FakeFez
    fakes = {"ibm_torino_snapshot": FakeTorino(), "ibm_fez_snapshot": FakeFez()}
    for i in map(int, sys.argv[1:]):
        if not os.path.exists(f"{OUT}/{json.load(open(f'{ROOT}/forms/selected.json'))[i]['name']}.json"): run_form(i, fakes)

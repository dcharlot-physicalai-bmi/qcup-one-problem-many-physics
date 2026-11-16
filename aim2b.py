#!/usr/bin/env python3
"""QCUP pre-submission, Aim 2 extensions.

Adds to aim2.py:
  P  in-place style for Forms whose transition is a permutation: no ancilla, no reset, no erasure
     (transformation-based reversible synthesis, Miller-Maslov-Dueck)
  OpenQASM 3 emission for every circuit, Guppy emission for every R and P circuit
  replay of the Guppy programs on the open-source Selene emulator against the reference trace
  transpilation to IBM device topologies and sampling under IBM calibration snapshots
     (qiskit-ibm-runtime fake backends FakeTorino and FakeFez; snapshots, not live devices)
"""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.abspath(__file__))
import os
import importlib.util, json, os, subprocess, sys, textwrap
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile, qasm3
from qiskit_aer import AerSimulator
sys.path.insert(0, ROOT)
import aim2
from aim2 import FORMS, build, reference, logical_erasure, noise, trace_prob
from aim1_post import heavy_hex_patch

OUT = os.path.join(ROOT, "results")
os.makedirs(f"{OUT}/qasm3", exist_ok=True); os.makedirs(f"{OUT}/guppy", exist_ok=True)


def is_permutation(delta, sb, eb):
    return all(sorted(delta(s, e) for s in range(1 << sb)) == list(range(1 << sb)) for e in range(1 << eb))


def mmd(perm, n):
    """Transformation-based synthesis. Returns gates [(controls, target)] whose in-order application maps x -> perm[x]."""
    f, gates = list(perm), []
    def apply(ctr, tgt):
        mask = sum(1 << c for c in ctr)
        for x in range(1 << n):
            if f[x] & mask == mask: f[x] ^= 1 << tgt
        gates.append((tuple(ctr), tgt))
    for b in range(n):
        if f[0] >> b & 1: apply((), b)
    for i in range(1, 1 << n):
        y = f[i]
        if y == i: continue
        for j in range(n):
            if (i >> j & 1) and not (f[i] >> j & 1): apply([c for c in range(n) if f[i] >> c & 1], j)
        for j in range(n):
            if (f[i] >> j & 1) and not (i >> j & 1): apply([c for c in range(n) if i >> c & 1], j)
    assert f == list(range(1 << n))
    return gates[::-1]


def build_inplace(delta, sb, s0, T):
    perm = [delta(s, 0) for s in range(1 << sb)]
    gates = mmd(perm, sb)
    S = QuantumRegister(sb, "s"); C = ClassicalRegister(sb * T, "trace")
    qc = QuantumCircuit(S, C)
    for b in range(sb):
        if s0 >> b & 1: qc.x(S[b])
    for t in range(T):
        for ctr, tgt in gates:
            if not ctr: qc.x(S[tgt])
            elif len(ctr) == 1: qc.cx(S[ctr[0]], S[tgt])
            else: qc.mcx([S[c] for c in ctr], S[tgt])
        for b in range(sb): qc.measure(S[b], C[t * sb + b])   # non-destructive read of the trace
    return qc


def to_guppy(qc, name):
    """Emit a Guppy program for a circuit over {x, h, cx, rz, reset, measure}. Mid-circuit reads use project_z."""
    low = transpile(qc, basis_gates=["x", "h", "cx", "rz", "reset", "measure"], optimization_level=1, seed_transpiler=7)
    nq, lines = low.num_qubits, []
    idx = {q: i for i, q in enumerate(low.qubits)}; cidx = {c: i for i, c in enumerate(low.clbits)}
    for inst in low.data:
        g = inst.operation.name; qs = [idx[q] for q in inst.qubits]
        if g == "x": lines.append(f"x(q{qs[0]})")
        elif g == "h": lines.append(f"h(q{qs[0]})")
        elif g == "cx": lines.append(f"cx(q{qs[0]}, q{qs[1]})")
        elif g == "rz": lines.append(f"rz(q{qs[0]}, angle({float(inst.operation.params[0]) / np.pi!r}))")
        elif g == "reset": lines.append(f"reset(q{qs[0]})")
        elif g == "measure": lines.append(f'result("c{cidx[inst.clbits[0]]:03d}", project_z(q{qs[0]}).read())')
        elif g == "barrier": pass
        else: raise ValueError(g)
    body = "\n".join(f"    q{i} = qubit()" for i in range(nq)) + "\n" + "\n".join("    " + l for l in lines) + "\n" + "\n".join(f"    discard(q{i})" for i in range(nq))
    src = f'''# Generated from RCE Form circuit {name}. Reversible logic lowered to {{x, h, cx, rz}}; project_z is a non-destructive read.
from guppylang import guppy
from guppylang.std.builtins import result
from guppylang.std.angles import angle
from guppylang.std.quantum import qubit, x, h, cx, rz, reset, project_z, discard

N_QUBITS = {nq}

@guppy
def main() -> None:
{body}

if __name__ == "__main__":
    import json, sys
    shots = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    res = main.emulator(n_qubits=N_QUBITS).with_shots(shots).with_seed(5).run()
    out = []
    for shot in res.results:
        d = dict(shot.entries)
        out.append("".join(str(int(d[k])) for k in sorted(d, reverse=True)))
    print(json.dumps(out))
'''
    return src, len(lines)


def main():
    from qiskit_ibm_runtime.fake_provider import FakeTorino, FakeFez
    fakes = {"ibm_torino_snapshot": FakeTorino(), "ibm_fez_snapshot": FakeFez()}
    rng = np.random.default_rng(20261111)   # same streams as aim2.py
    rows = []
    for name, src, sb, eb, delta, s0 in FORMS:
        streams = [[int(x) for x in rng.integers(0, 1 << eb, 5)] for _ in range(5)] if eb else [[0] * 5]
        perm = is_permutation(delta, sb, eb)
        ev5 = streams[0]
        for T in (1, 2, 3, 4, 5):
            ev = ev5[:T]; ref = reference(delta, s0, ev)
            styles = ["G", "R"] + (["P"] if perm and eb == 0 else [])
            for style in styles:
                qc = build_inplace(delta, sb, s0, T) if style == "P" else build(style, delta, sb, eb, s0, ev)[0]
                tag = f"{name}_{style}_T{T}"
                open(f"{OUT}/qasm3/{tag}.qasm", "w").write(qasm3.dumps(transpile(qc, basis_gates=["x", "h", "cx", "ccx", "rz", "reset", "measure"], optimization_level=0)))
                row = {"form": name, "style": style, "T": T, "qubits": qc.num_qubits, "is_permutation": perm, "reference_trace": ref,
                       "resets": int(qc.count_ops().get("reset", 0)), "logical_erasure_bits": round(logical_erasure(delta, sb, s0, ev), 4)}
                if style == "P":   # generic-noise numbers for the new style, same models as aim2.py
                    for target in ("sc_like", "ion_like"):
                        nm, basis = noise(target)
                        tq = transpile(qc, coupling_map=heavy_hex_patch(qc.num_qubits) if target == "sc_like" else None, basis_gates=basis + ["reset", "measure"], optimization_level=3, seed_transpiler=7)
                        ideal = AerSimulator(method="statevector").run(tq, shots=200, seed_simulator=3).result().get_counts()
                        assert trace_prob(ideal, ref, sb) == 1.0
                        c = AerSimulator(noise_model=nm, method="statevector").run(tq, shots=2000, seed_simulator=11).result().get_counts()
                        row[target] = {"two_qubit_gates": int(tq.count_ops().get(basis[0], 0)), "trace_fidelity": trace_prob(c, ref, sb), "shots": 2000}
                if style in ("R", "P"):
                    gsrc, ngates = to_guppy(qc, tag)
                    path = f"{OUT}/guppy/{tag}.py"; open(path, "w").write(gsrc)
                    row["guppy_gates"] = ngates
                    if T == 5 or style == "P":
                        got = json.loads(subprocess.run([sys.executable, path, "20"], capture_output=True, text=True, timeout=900, check=True).stdout.strip().splitlines()[-1])
                        want = "".join(format(s, f"0{sb}b") for s in reversed(ref))
                        row["selene_replays_reference"] = all(g == want for g in got); row["selene_shots"] = len(got)
                        assert row["selene_replays_reference"], f"{tag}: Guppy program does not replay the reference trace: {got[:2]} vs {want}"
                    for fname, fb in fakes.items():
                        tq = transpile(qc, backend=fb, optimization_level=3, seed_transpiler=7)
                        two = sum(v for k, v in tq.count_ops().items() if k in ("cz", "ecr", "cx", "rzz"))
                        active = len({q for inst in tq.data for q in inst.qubits})
                        r = {"two_qubit_gates": int(two), "active_qubits": active, "depth": int(tq.depth())}
                        if active <= 14:
                            sim = AerSimulator.from_backend(fb)
                            c = sim.run(tq, shots=2000, seed_simulator=11).result().get_counts()
                            r["trace_fidelity"] = trace_prob(c, ref, sb); r["shots"] = 2000
                        row[fname] = r
                rows.append(row)
                print(tag, {k: (row[k]["two_qubit_gates"], row[k].get("trace_fidelity")) for k in row if isinstance(row[k], dict)}, row.get("selene_replays_reference"), flush=True)
    json.dump(rows, open(f"{OUT}/aim2b.json", "w"), indent=1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""QCUP pre-submission, Aim 2: reversible projection of real RCE Forms.

Each Form's transition function delta (transcribed from the .rce source named below) is lowered to an
out-of-place reversible oracle |s>|e>|0> -> |s>|e>|delta(s,e)> by exact Reed-Muller (ANF) synthesis,
then run for T event steps in two styles:
  G  garbage-retaining: a fresh state register per step, nothing erased (width grows with T)
  R  reset: two state registers used in turn; the stale register is reset each step (constant width)
Circuits are transpiled to an n-qubit heavy-hex patch (CZ basis) and to an all-to-all RZZ basis,
checked noiselessly against the reference trace, and sampled under a generic depolarizing noise model
(NOT a device calibration). Nothing is hardcoded: every count is read off the transpiled circuit.
"""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.abspath(__file__))
import os
import itertools, json, math, sys
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError
sys.path.insert(0, ROOT)
from aim1_post import heavy_hex_patch

# ---- Forms: (name, source file in openIE-dev/rce, state bits, event bits, delta, initial state) ----
def traffic(s, e):   # spec/examples/17_traffic_light.rce : Red=0 -> Green=1 -> Yellow=2 -> Red ; code 3 unused, fixed
    return {0: 1, 1: 2, 2: 0, 3: 3}[s]

def mod6(s, e):      # spec/examples/60_dim_hidden_period.rce : n = (n + 1) % 6 ; codes 6,7 unused, fixed
    return (s + 1) % 6 if s < 6 else s

def door(s, e):      # book/listings/ch05/door.rce : bit0 = open, bit1 = locked ; events Open=0 Close=1 Lock=2 Unlock=3
    op, lk = s & 1, (s >> 1) & 1
    if e == 0: op = op if lk else 1          # Open if locked -> fail Locked (state kept)
    elif e == 1: op = 0
    elif e == 2: lk = lk if op else 1        # Lock if open -> fail DoorOpen (state kept)
    else: lk = 0
    return op | (lk << 1)

def counter(k):      # examples/surface/counter.rce with n narrowed from u64 to k bits ; events Inc=0 Dec=1
    def f(s, e):
        if e == 0: return s + 1 if s < (1 << k) - 1 else s   # checked overflow -> state kept
        return s - 1 if s > 0 else s                          # Underflow -> state kept
    return f

FORMS = [
    ("traffic_light", "spec/examples/17_traffic_light.rce", 2, 0, traffic, 0),
    ("mod6_counter", "spec/examples/60_dim_hidden_period.rce", 3, 0, mod6, 0),
    ("door", "book/listings/ch05/door.rce", 2, 2, door, 0),
    ("counter_2bit", "examples/surface/counter.rce (n narrowed to 2 bits)", 2, 1, counter(2), 0),
    ("counter_3bit", "examples/surface/counter.rce (n narrowed to 3 bits)", 3, 1, counter(3), 0),
]


def anf(table, nin):
    """Positive-polarity Reed-Muller coefficients of a Boolean function given as a truth table."""
    a = list(table)
    for i in range(nin):
        for x in range(1 << nin):
            if x >> i & 1:
                a[x] ^= a[x ^ (1 << i)]
    return [m for m in range(1 << nin) if a[m]]


def oracle(qc, sreg, ereg, oreg, delta, sb, eb):
    nin = sb + eb
    ins = list(sreg) + list(ereg)
    for b in range(sb):
        table = [(delta(x & ((1 << sb) - 1), x >> sb) >> b) & 1 for x in range(1 << nin)]
        for mono in anf(table, nin):
            ctr = [ins[i] for i in range(nin) if mono >> i & 1]
            if not ctr: qc.x(oreg[b])
            elif len(ctr) == 1: qc.cx(ctr[0], oreg[b])
            else: qc.mcx(ctr, oreg[b])


def build(style, delta, sb, eb, s0, events):
    T = len(events)
    if style == "G":
        S = [QuantumRegister(sb, f"s{t}") for t in range(T + 1)]
        E = [QuantumRegister(eb, f"e{t}") for t in range(T)] if eb else []
        C = ClassicalRegister(sb * T, "trace")
        qc = QuantumCircuit(*S, *E, C)
        for b in range(sb):
            if s0 >> b & 1: qc.x(S[0][b])
        for t, ev in enumerate(events):
            er = E[t] if eb else []
            for b in range(eb):
                if ev >> b & 1: qc.x(er[b])
            oracle(qc, S[t], er, S[t + 1], delta, sb, eb)
        for t in range(T):
            for b in range(sb): qc.measure(S[t + 1][b], C[t * sb + b])
        return qc, 0
    A, B = QuantumRegister(sb, "a"), QuantumRegister(sb, "b")
    E = QuantumRegister(eb, "e") if eb else None
    C = ClassicalRegister(sb * T, "trace")
    qc = QuantumCircuit(A, B, *( [E] if eb else [] ), C)
    for b in range(sb):
        if s0 >> b & 1: qc.x(A[b])
    cur, nxt, resets = A, B, 0
    for t, ev in enumerate(events):
        for b in range(eb):
            if ev >> b & 1: qc.x(E[b])
        oracle(qc, cur, E if eb else [], nxt, delta, sb, eb)
        for b in range(eb):                       # the event is classical and known: un-prepare, no erasure
            if ev >> b & 1: qc.x(E[b])
        for b in range(sb):
            qc.measure(nxt[b], C[t * sb + b])     # record the trace
            if t < T - 1:
                qc.reset(cur[b]); resets += 1     # the stale state is erased
        cur, nxt = nxt, cur
    return qc, resets


def reference(delta, s0, events):
    tr, s = [], s0
    for ev in events:
        s = delta(s, ev); tr.append(s)
    return tr


def logical_erasure(delta, sb, s0, events):
    """Bits of information about the previous state that the step itself destroys, along the trace:
    sum_t log2 |{s : delta(s, e_t) = s_t}|. Zero for a permutation."""
    tot, s = 0.0, s0
    for ev in events:
        s2 = delta(s, ev)
        tot += math.log2(sum(1 for x in range(1 << sb) if delta(x, ev) == s2))
        s = s2
    return tot


def noise(kind):
    p2, p1, pm, basis = (3e-3, 3e-4, 1e-2, ["cz", "rz", "sx", "x"]) if kind == "sc_like" else (1e-3, 3e-5, 2e-3, ["rzz", "rz", "rx", "ry"])
    nm = NoiseModel(basis_gates=basis + ["reset", "measure"])
    nm.add_all_qubit_quantum_error(depolarizing_error(p2, 2), [basis[0]])
    nm.add_all_qubit_quantum_error(depolarizing_error(p1, 1), [b for b in basis[1:] if b != "rz"])
    nm.add_all_qubit_quantum_error(depolarizing_error(pm, 1), ["reset"])
    nm.add_all_qubit_readout_error(ReadoutError([[1 - pm, pm], [pm, 1 - pm]]))
    return nm, basis


def trace_prob(counts, ref, sb):
    want = "".join(format(s, f"0{sb}b") for s in reversed(ref))
    tot = sum(counts.values())
    return counts.get(want, 0) / tot


def main():
    rng = np.random.default_rng(20261111)
    rows = []
    for name, src, sb, eb, delta, s0 in FORMS:
        streams = [[int(x) for x in rng.integers(0, 1 << eb, 5)] for _ in range(5)] if eb else [[0] * 5]
        for si, stream in enumerate(streams):
            for T in ([1, 2, 3, 4, 5] if si == 0 else [5]):
                ev = stream[:T]
                ref = reference(delta, s0, ev)
                for style in ("G", "R"):
                    qc, resets = build(style, delta, sb, eb, s0, ev)
                    w = qc.num_qubits
                    row = {"form": name, "source": src, "state_bits": sb, "event_bits": eb, "stream": si, "events": ev, "T": T,
                           "style": style, "qubits": w, "resets": resets, "overwritten_bits": sb * T,
                           "logical_erasure_bits": round(logical_erasure(delta, sb, s0, ev), 4), "reference_trace": ref}
                    for target in ("sc_like", "ion_like"):
                        nm, basis = noise(target)
                        cmap = heavy_hex_patch(w) if target == "sc_like" else None
                        tq = transpile(qc, coupling_map=cmap, basis_gates=basis + ["reset", "measure"], optimization_level=3, seed_transpiler=7)
                        two = int(tq.count_ops().get(basis[0], 0))
                        d2 = int(tq.depth(lambda g: g.operation.num_qubits == 2))
                        r = {"two_qubit_gates": two, "two_qubit_depth": d2, "depth": int(tq.depth())}
                        if w <= 14:
                            ideal = AerSimulator(method="statevector").run(tq, shots=200, seed_simulator=3).result().get_counts()
                            assert trace_prob(ideal, ref, sb) == 1.0, f"{name} {style} T={T}: compiled circuit does not replay the reference trace"
                            r["noiseless_trace_ok"] = True
                            shots = 2000
                            c = AerSimulator(noise_model=nm, method="statevector").run(tq, shots=shots, seed_simulator=11).result().get_counts()
                            r["trace_fidelity"] = trace_prob(c, ref, sb); r["shots"] = shots
                        row[target] = r
                    rows.append(row)
                    print(name, style, "T", T, "w", w, {k: (row[k]["two_qubit_gates"], row[k].get("trace_fidelity")) for k in ("sc_like", "ion_like")}, flush=True)
    json.dump(rows, open(os.path.join(ROOT, "results/aim2.json"), "w"), indent=1)


if __name__ == "__main__":
    main()

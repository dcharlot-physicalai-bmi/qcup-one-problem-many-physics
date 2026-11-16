#!/usr/bin/env python3
"""Positive control for the scorers: noiseless simulation of the exact submitted OpenQASM 3 files, written out in the same
Sampler V2 JSON layout as run/raw/results-<arm>.json, so the scorers can be fed it unchanged.

For each arm: load every submitted QASM file (order = predictions.json), keep only the device qubits it uses (relabelled
in increasing physical index; a relabelling cannot change measured bits), sample it noiselessly with Aer's SamplerV2 at the
device shot count, and encode each shot's register value as a hex integer whose bit i is classical bit i. The encoding is
checked by decoding it again with qiskit's own BitArray.from_samples and comparing bit for bit.

Also decodes the device's raw results with BitArray.from_samples and writes counts, so the stdlib decoder can be compared.
Usage: sim_control.py QASM_ROOT PREDICTIONS RAW_DIR OUT_DIR"""
import json, sys, hashlib
import numpy as np
from qiskit import qasm3, QuantumCircuit
from qiskit.primitives.containers import BitArray
from qiskit_aer.primitives import SamplerV2
QROOT, PRED, RAW, OUT = sys.argv[1:5]
pred = json.load(open(PRED)); C = pred["circuits"]


def compact(qc):
    used = sorted({qc.find_bit(q).index for ins in qc.data for q in ins.qubits})
    pos = {p: i for i, p in enumerate(used)}
    out = QuantumCircuit(len(used))
    for cr in qc.cregs: out.add_register(cr)
    for ins in qc.data:
        out.append(ins.operation, [out.qubits[pos[qc.find_bit(q).index]] for q in ins.qubits], [out.clbits[qc.find_bit(c).index] for c in ins.clbits])
    return out, used


def to_hex(ba):
    """BitArray -> list of hex strings, one per shot; bit i of the integer is classical bit i (array is big-endian bytes)."""
    arr = ba.array.reshape(-1, ba.array.shape[-1])
    return [hex(int.from_bytes(bytes(row), "big")) for row in arr]


sampler = SamplerV2(seed=20261116)
for arm in ("dd_off", "dd_on"):
    pubs_out, summary = [], []
    for meta in C:
        path = f"{QROOT}/qasm_{arm}/{meta['id']}.qasm"; src = open(path).read()
        qc = qasm3.loads(src); cq, used = compact(qc)
        assert len(cq.cregs) == 1, (meta["id"], cq.cregs)
        reg = cq.cregs[0].name
        res = sampler.run([cq], shots=meta["shots"]).result()[0]
        ba = getattr(res.data, reg); hx = to_hex(ba)
        back = BitArray.from_samples(hx, num_bits=ba.num_bits)
        assert np.array_equal(back.array.reshape(-1, back.array.shape[-1]), ba.array.reshape(-1, ba.array.shape[-1])), meta["id"]
        assert back.get_counts() == ba.get_counts()
        pubs_out.append({"data": {reg: {"samples": hx, "num_bits": ba.num_bits}}, "metadata": {"simulated": "aer noiseless", "qasm_sha256": hashlib.sha256(src.encode()).hexdigest()}})
        ops = cq.count_ops()
        summary.append({"id": meta["id"], "qubits_used": len(used), "cz": int(ops.get("cz", 0)), "reset": int(ops.get("reset", 0)), "measure": int(ops.get("measure", 0)), "delay": int(ops.get("delay", 0)), "distinct_outcomes": len(ba.get_counts())})
        print(arm, summary[-1], flush=True)
    json.dump({"results": pubs_out, "metadata": {"simulated": True}}, open(f"{OUT}/results-sim-{arm}.json", "w"))
    json.dump(summary, open(f"{OUT}/sim-summary-{arm}.json", "w"), indent=1)
    # device raw decoded by qiskit's BitArray
    raw = json.load(open(f"{RAW}/results-{arm}.json"))["results"]
    dev = {}
    for meta, pub in zip(C, raw):
        (reg, d), = pub["data"].items()
        dev[meta["id"]] = BitArray.from_samples(d["samples"], num_bits=d["num_bits"]).get_counts()
    json.dump(dev, open(f"{OUT}/device-counts-bitarray-{arm}.json", "w"))
print("done")

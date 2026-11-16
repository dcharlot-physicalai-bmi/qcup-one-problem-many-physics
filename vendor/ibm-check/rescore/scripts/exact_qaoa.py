"""Exact (no sampling) ground-set probability of each submitted QAOA circuit, read through the clbit map of its own
measurements, with the ground sets passed in. Usage: exact_qaoa.py QASM_ROOT GROUND_JSON"""
import json, sys
from qiskit import qasm3, QuantumCircuit
from qiskit.quantum_info import Statevector
root, gpath = sys.argv[1:3]; G = json.load(open(gpath))
for arm in ("dd_off", "dd_on"):
    for cid, g in G.items():
        qc = qasm3.loads(open(f"{root}/qasm_{arm}/{cid}.qasm").read())
        used = sorted({qc.find_bit(q).index for ins in qc.data for q in ins.qubits}); pos = {p: i for i, p in enumerate(used)}
        body = QuantumCircuit(len(used)); cl2q = {}
        for ins in qc.data:
            qs = [pos[qc.find_bit(q).index] for q in ins.qubits]
            if ins.operation.name == "measure": cl2q[qc.find_bit(ins.clbits[0]).index] = qs[0]; continue
            if ins.operation.name in ("delay", "barrier"): continue
            body.append(ins.operation, [body.qubits[i] for i in qs])
        nb = len(cl2q); order = [cl2q[i] for i in range(nb)]
        p = Statevector(body).probabilities(qargs=order)      # index bit i = clbit i
        print(arm, cid, "exact P(ground set) = %.5f" % float(sum(p[z] for z in g)), "clbits", nb, flush=True)

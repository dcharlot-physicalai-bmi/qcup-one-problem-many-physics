# Generated from RCE Form circuit t60_dim_redundant_k4_P_T3. Reversible logic lowered to {x, h, cx, rz}; project_z is a non-destructive read.
from guppylang import guppy
from guppylang.std.builtins import result
from guppylang.std.angles import angle
from guppylang.std.quantum import qubit, x, h, cx, rz, reset, project_z, discard

N_QUBITS = 2

@guppy
def main() -> None:
    q0 = qubit()
    q1 = qubit()
    cx(q0, q1)
    x(q0)
    result("c000", project_z(q0).read())
    result("c001", project_z(q1).read())
    cx(q0, q1)
    x(q0)
    result("c002", project_z(q0).read())
    result("c003", project_z(q1).read())
    cx(q0, q1)
    x(q0)
    result("c004", project_z(q0).read())
    result("c005", project_z(q1).read())
    discard(q0)
    discard(q1)

if __name__ == "__main__":
    import json, sys
    shots = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    res = main.emulator(n_qubits=N_QUBITS).with_shots(shots).with_seed(5).run()
    out = []
    for shot in res.results:
        d = dict(shot.entries)
        out.append("".join(str(int(d[k])) for k in sorted(d, reverse=True)))
    print(json.dumps(out))

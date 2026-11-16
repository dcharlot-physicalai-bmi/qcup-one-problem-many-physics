# Generated from RCE Form circuit 17_traffic_light_accept_R_T4. Reversible logic lowered to {x, h, cx, rz}; project_z is a non-destructive read.
from guppylang import guppy
from guppylang.std.builtins import result
from guppylang.std.angles import angle
from guppylang.std.quantum import qubit, x, h, cx, rz, reset, project_z, discard

N_QUBITS = 4

@guppy
def main() -> None:
    q0 = qubit()
    q1 = qubit()
    q2 = qubit()
    q3 = qubit()
    x(q2)
    cx(q0, q2)
    cx(q1, q2)
    reset(q1)
    cx(q0, q3)
    reset(q0)
    x(q0)
    result("c000", project_z(q2).read())
    cx(q2, q0)
    cx(q2, q1)
    reset(q2)
    x(q2)
    result("c001", project_z(q3).read())
    cx(q3, q0)
    reset(q3)
    result("c002", project_z(q0).read())
    cx(q0, q2)
    cx(q0, q3)
    reset(q0)
    x(q0)
    result("c003", project_z(q1).read())
    cx(q1, q2)
    reset(q1)
    result("c004", project_z(q2).read())
    cx(q2, q0)
    cx(q2, q1)
    result("c005", project_z(q3).read())
    cx(q3, q0)
    result("c006", project_z(q0).read())
    result("c007", project_z(q1).read())
    discard(q0)
    discard(q1)
    discard(q2)
    discard(q3)

if __name__ == "__main__":
    import json, sys
    shots = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    res = main.emulator(n_qubits=N_QUBITS).with_shots(shots).with_seed(5).run()
    out = []
    for shot in res.results:
        d = dict(shot.entries)
        out.append("".join(str(int(d[k])) for k in sorted(d, reverse=True)))
    print(json.dumps(out))

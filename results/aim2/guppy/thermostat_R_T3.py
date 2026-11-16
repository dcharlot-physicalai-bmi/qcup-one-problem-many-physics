# Generated from RCE Form circuit thermostat_R_T3. Reversible logic lowered to {x, h, cx, rz}; project_z is a non-destructive read.
from guppylang import guppy
from guppylang.std.builtins import result
from guppylang.std.angles import angle
from guppylang.std.quantum import qubit, x, h, cx, rz, reset, project_z, discard

N_QUBITS = 3

@guppy
def main() -> None:
    q0 = qubit()
    q1 = qubit()
    q2 = qubit()
    reset(q0)
    x(q0)
    x(q1)
    result("c000", project_z(q1).read())
    reset(q1)
    x(q1)
    result("c001", project_z(q0).read())
    result("c002", project_z(q1).read())
    discard(q0)
    discard(q1)
    discard(q2)

if __name__ == "__main__":
    import json, sys
    shots = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    res = main.emulator(n_qubits=N_QUBITS).with_shots(shots).with_seed(5).run()
    out = []
    for shot in res.results:
        d = dict(shot.entries)
        out.append("".join(str(int(d[k])) for k in sorted(d, reverse=True)))
    print(json.dumps(out))

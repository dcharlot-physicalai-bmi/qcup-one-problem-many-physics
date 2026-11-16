"""Write a WAI Quantum forecast suite from the exported gate lists. WAI Quantum's native toolchain takes angles that are
dyadic multiples of 2pi (2pi m / 2^k, k <= 32), so each angle is rounded to the nearest pi m / 2^31 (at most 1.5e-9 rad
off) and written as that expression. Only circuits whose every measurement is terminal are written.
Usage: wai_suite.py BASE NAME OUT id1 id2 ..."""
import json, math, sys
BASE, NAME, OUT = sys.argv[1:4]; ids = sys.argv[4:]
def dy(x):
    k = round(x * 2 ** 31 / math.pi)
    return f"pi*{k}/2147483648" if k else "0"
suite = {"forecast_suite": 1, "name": NAME, "shots": 500, "circuits": []}
for i in ids:
    g = json.load(open(f"{BASE}/circuits/gates/{i}.json")); n = g["qubits"]
    L = ["OPENQASM 3.0;", 'include "stdgates.inc";', "gate rzz(p0) a, b { cx a, b; rz(p0) b; cx a, b; }", f"qubit[{n}] q;", f"bit[{n}] c;"]
    for name, qs, ps, cs in g["gates"]:
        if name == "measure": continue
        if name == "reset": raise SystemExit(f"{i}: reset")
        L.append(f"{name}({dy(ps[0])}) " + ", ".join(f"q[{x}]" for x in qs) + ";")
    L.append("c = measure q;")
    suite["circuits"].append({"id": i.lower(), "qasm": "\n".join(L) + "\n", "layout": list(range(n)), "figure": {"outcomes": ["0" * n]}})
json.dump(suite, open(OUT, "w"))
print(len(suite["circuits"]), "circuits")

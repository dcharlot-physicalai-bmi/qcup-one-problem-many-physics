"""Tiny trajectory simulator for the exported OpenQASM 3 subset (rx, ry, rz, rzz as defined, x, reset, measure into a
named bit register) to check that a five-step reset-style circuit replays its reference trace. Light: 4 to 6 qubits."""
import json, math, re, sys
import numpy as np
path = sys.argv[1]; shots = int(sys.argv[2]) if len(sys.argv) > 2 else 200
src = open(path).read()
src = re.sub(r"gate rzz\(p0\)[^}]*\}", "", src, flags=re.S)
regs = {}; nq = 0
for name, size in re.findall(r"qubit\[(\d+)\]\s+(\w+);", src):
    pass
for size, name in re.findall(r"qubit\[(\d+)\]\s+(\w+);", src): regs[name] = (nq, int(size)); nq += int(size)
bits = {name: int(size) for size, name in re.findall(r"bit\[(\d+)\]\s+(\w+);", src)}
def q(tok):
    m = re.match(r"(\w+)\[(\d+)\]", tok.strip()); return regs[m.group(1)][0] + int(m.group(2))
def ang(s): return float(eval(s, {"pi": math.pi}))
def u1(name, t):
    c, s = math.cos(t / 2), math.sin(t / 2)
    return {"rx": np.array([[c, -1j * s], [-1j * s, c]]), "ry": np.array([[c, -s], [s, c]]), "rz": np.diag([np.exp(-1j * t / 2), np.exp(1j * t / 2)]), "x": np.array([[0, 1], [1, 0]])}[name]
ops = []
for line in src.split(";"):
    line = line.strip()
    if not line or line.startswith(("OPENQASM", "include", "qubit", "bit")): continue
    m = re.match(r"(\w+)\[(\d+)\]\s*=\s*measure\s+(.+)", line)
    if m: ops.append(("measure", q(m.group(3)), (m.group(1), int(m.group(2))))); continue
    m = re.match(r"reset\s+(.+)", line)
    if m: ops.append(("reset", q(m.group(1)), None)); continue
    m = re.match(r"(rx|ry|rz|rzz)\((.+?)\)\s+(.+)", line)
    if m:
        qs = [q(t) for t in m.group(3).split(",")]; ops.append((m.group(1), qs, ang(m.group(2)))); continue
    m = re.match(r"(x)\s+(.+)", line)
    if m: ops.append(("x", [q(m.group(2))], 0.0)); continue
    raise ValueError(line)
idx = np.arange(1 << nq); rng = np.random.default_rng(1); hist = {}
for _ in range(shots):
    psi = np.zeros(1 << nq, complex); psi[0] = 1; cl = {k: [0] * v for k, v in bits.items()}
    for op in ops:
        if op[0] in ("rx", "ry", "rz", "x"):
            qq = op[1][0]; psi = psi.reshape([2] * nq); ax = nq - 1 - qq
            psi = np.moveaxis(np.tensordot(u1(op[0], op[2]), psi, axes=([1], [ax])), 0, ax).reshape(-1)
        elif op[0] == "rzz":
            a, b = op[1]; z = (1 - 2 * ((idx >> a) & 1)) * (1 - 2 * ((idx >> b) & 1)); psi = psi * np.exp(-1j * op[2] / 2 * z)
        else:
            qq = op[1]; one = ((idx >> qq) & 1) == 1; p1 = float(np.sum(np.abs(psi[one]) ** 2)); r = int(rng.random() < p1)
            psi = np.where(one == bool(r), psi, 0); psi /= np.linalg.norm(psi)
            if op[0] == "measure": cl[op[2][0]][op[2][1]] = r
            elif r: psi = psi[idx ^ (1 << qq)]
    key = "|".join("".join(str(b) for b in reversed(v)) for v in cl.values()); hist[key] = hist.get(key, 0) + 1
print(json.dumps(dict(sorted(hist.items(), key=lambda kv: -kv[1]))))

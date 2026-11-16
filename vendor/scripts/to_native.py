"""Lower a QIS circuit over rx, ry, rz, zz (radians) to IonQ's native gates gpi, gpi2, zz (turns), so the service runs
the gates as written instead of re-optimising them.

  rz(l)        a frame change on the qubit (no pulse): later gpi/gpi2 phases are shifted by -l/2pi; zz commutes.
  rx(t)        gpi2(0.75), rz(t), gpi2(0.25) in time order (rx(+-pi/2) one gpi2, rx(pi) one gpi);
  ry(t)        gpi2(0), rz(t), gpi2(0.5) (ry(+-pi/2) one gpi2, ry(pi) one gpi).
  zz(t)        zz(t/2pi turns), folded into [-1/4, 1/4] turn with a Z on both qubits (a frame change) where needed.
Each identity was checked numerically (see the positive control in native_control)."""
import json, math, os, sys

TWO_PI = 2 * math.pi
EPS = 1e-12


def wrap(x):           # turns into [0, 1)
    x = x % 1.0
    return 0.0 if abs(x - 1.0) < 1e-15 else x


def near(a, b): return abs(math.remainder(a - b, TWO_PI)) < 1e-9


def lower(qis):
    nq = qis["qubits"]; frame = [0.0] * nq; out = []
    def g1(kind, q, phase): out.append({"gate": kind, "target": q, "phase": wrap(phase - frame[q] / TWO_PI)})
    for g in qis["circuit"]:
        n = g["gate"]
        if n == "rz": frame[g["target"]] += g["rotation"]
        elif n in ("rx", "ry"):
            q, t = g["target"], g["rotation"]; base = 0.0 if n == "rx" else 0.25
            if near(t, 0): continue
            if near(t, math.pi / 2): g1("gpi2", q, base)
            elif near(t, -math.pi / 2): g1("gpi2", q, base + 0.5)
            elif near(t, math.pi) or near(t, -math.pi): g1("gpi", q, base)
            else:
                first, last = (0.75, 0.25) if n == "rx" else (0.0, 0.5)
                g1("gpi2", q, first); frame[q] += t; g1("gpi2", q, last)
        elif n == "zz":
            a, b = g["targets"]; th = math.remainder(g["rotation"], TWO_PI) / TWO_PI     # turns in [-1/2, 1/2]
            if th > 0.25: th -= 0.5; frame[a] += math.pi; frame[b] += math.pi
            elif th < -0.25: th += 0.5; frame[a] += math.pi; frame[b] += math.pi
            if abs(th) < EPS: continue
            out.append({"gate": "zz", "targets": [a, b], "angle": th})
        else: raise ValueError(n)
    return {"qubits": nq, "gateset": "native", "circuit": out}


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]; os.makedirs(dst, exist_ok=True); n = 0
    for f in sorted(os.listdir(src)):
        if not f.endswith(".json"): continue
        d = json.load(open(os.path.join(src, f))); nat = lower(d["input"])
        json.dump({"id": d["id"], "input": nat, "clbit_to_qubit": d["clbit_to_qubit"], "clbits": d["clbits"]}, open(os.path.join(dst, f), "w")); n += 1
    print("lowered", n)

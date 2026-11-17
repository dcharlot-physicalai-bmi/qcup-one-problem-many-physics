"""Write one request circuit as a Guppy program, from the gate list the package's builder exported for it
(build_circuits.py: circuits/gates/<id>.json, the transpiled circuit in rzz, rz, rx, ry, measure and reset; the same list
the device models cost, so every count here is the request's count).

Rules (each the identity, up to a global phase, or the device's own handling):
  rx, ry   -> Guppy's rx, ry (Selene runs each as one rxy native operation); an angle of 0 mod 2pi is dropped.
  rz       -> Guppy's rz (under Selene's soft-RZ runtime a frame change: no native operation, no error, as on the device).
  rzz(t)   -> Guppy's qsystem zz_phase(t) (ZZPhase(t) = exp(-i t/2 Z(x)Z), OpenQASM 3's rzz), one rzz native operation;
              t = 0 mod 2pi is dropped and t = pi mod 2pi becomes rz(pi) on both qubits (Z(x)Z, a frame change), the two
              cases the device models also treat as free ("frame_only_rzz").
  measure  -> project_z (keeps the qubit) if the qubit is used again, else measure; each classical bit is a result
              "c<k>" (the last write of bit k wins, as in OpenQASM).
  reset    -> reset.
A qubit never measured is discarded at the end.

min_angles=True (the 2025 runs) adds the device's documented rounding (Quantinuum's H2 and Helios pages: "The minimum
gate angles for the Rzz gate angle is 1e-4 and the minimum Rxy gate angle is 3e-4. Gates angles smaller are
automatically rounded to zero"): an rzz with 0 < |t| < 1e-4 and an rx or ry with 0 < |t| < 3e-4 (t modulo 2pi) are
dropped. With min_angles=False the program is the 2024 run's, gate for gate.
"""
import json, math

PI = math.pi


def _ht(theta):
    """An angle in half turns, as Guppy's angle() takes it."""
    return float(theta) / PI


def _mod2pi(theta):
    return abs(math.remainder(float(theta), 2 * PI))       # in [0, pi]


def guppy_text(gates, n_qubits, n_clbits, min_angles=False):
    MIN_RZZ, MIN_RXY = (1e-4, 3e-4) if min_angles else (1e-12, 1e-12)
    last_use = {}
    for k, (name, qs, ps, cs) in enumerate(gates):
        for q in qs: last_use[q] = k
    L = ["from guppylang import guppy",
         "from guppylang.std.quantum import qubit, discard, measure, project_z, reset, rx, ry, rz",
         "from guppylang.std.qsystem.helios import zz_phase",
         "from guppylang.std.angles import angle",
         "from guppylang.std.builtins import result",
         "", "", "@guppy", "def main() -> None:"]
    L += ["    q%d = qubit()" % i for i in range(n_qubits)]
    gone = set(); stats = {"rzz_native": 0, "rzz_dropped_zero": 0, "rzz_dropped_min_angle": 0, "rzz_as_frame_pi": 0, "rxy_native": 0, "rxy_dropped_zero": 0,
                           "rxy_dropped_min_angle": 0, "rz": 0,
                           "measure_mid": 0, "measure_final": 0, "reset": 0}
    written = {}
    for k, (name, qs, ps, cs) in enumerate(gates):
        if name == "barrier": continue
        if name in ("rx", "ry"):
            if _mod2pi(ps[0]) < 1e-12: stats["rxy_dropped_zero"] += 1; continue
            if _mod2pi(ps[0]) < MIN_RXY: stats["rxy_dropped_min_angle"] += 1; continue
            L.append("    %s(q%d, angle(%r))" % (name, qs[0], _ht(ps[0]))); stats["rxy_native"] += 1
        elif name == "rz":
            if _mod2pi(ps[0]) < 1e-12: continue
            L.append("    rz(q%d, angle(%r))" % (qs[0], _ht(ps[0]))); stats["rz"] += 1
        elif name == "rzz":
            t = _mod2pi(ps[0])
            if t < 1e-12: stats["rzz_dropped_zero"] += 1; continue
            if t < MIN_RZZ: stats["rzz_dropped_min_angle"] += 1; continue
            if abs(t - PI) < 1e-12:
                L.append("    rz(q%d, angle(1.0))" % qs[0]); L.append("    rz(q%d, angle(1.0))" % qs[1]); stats["rzz_as_frame_pi"] += 1; continue
            L.append("    zz_phase(q%d, q%d, angle(%r))" % (qs[0], qs[1], _ht(ps[0]))); stats["rzz_native"] += 1
        elif name == "measure":
            q, c = qs[0], cs[0]
            if last_use[q] == k:
                L.append("    result(\"c%03d\", measure(q%d).read())" % (c, q)); gone.add(q); stats["measure_final"] += 1
            else:
                L.append("    result(\"c%03d\", project_z(q%d).read())" % (c, q)); stats["measure_mid"] += 1
            written[c] = written.get(c, 0) + 1
        elif name == "reset":
            L.append("    reset(q%d)" % qs[0]); stats["reset"] += 1
        else:
            raise ValueError("gate the builder does not emit: %r" % name)
    L += ["    discard(q%d)" % i for i in range(n_qubits) if i not in gone]
    stats["clbits_written_twice"] = sum(1 for v in written.values() if v > 1)
    return "\n".join(L) + "\n", stats


def bits_of_shot(entries, n_clbits):
    """Classical bits of one shot as OpenQASM/Qiskit prints them (bit n-1 first), from the shot's result entries."""
    v = {}
    for tag, val in entries:
        if tag.startswith("c") and tag[1:].isdigit(): v[int(tag[1:])] = int(val)
    return "".join(str(v.get(b, 0)) for b in range(n_clbits - 1, -1, -1)), v


if __name__ == "__main__":
    import sys
    g = json.load(open(sys.argv[1]))
    txt, st = guppy_text(g["gates"], g["qubits"], g["clbits"])
    print(txt[:2000]); print(st)

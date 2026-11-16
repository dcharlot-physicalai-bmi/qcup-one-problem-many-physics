#!/usr/bin/env python3
"""Error budgets of every requested trapped-ion circuit under the application's generic model and under device models
built from the makers' published figures, and the application's admission rule re-applied.

    python3 models.py BASE_DIR          (BASE_DIR holds circuits/index.json and circuits/gates/)

Budget: b = sum of -ln(1 - x) over every error event x, as WAI Quantum's noise budget (engine::targets::noise::Budget)
counts it; F = exp(-b) is the chance the whole circuit runs with no error event.

  generic   aim2.py noise("ion_like"): depolarising 1e-3 on every rzz at any angle, 3e-5 on rx and ry (rz noiseless),
            2e-3 readout and 2e-3 on each reset; no memory or idle error. Fitted on circuits of 12 qubits or fewer.
  quantinuum-h2-1-2023  WAI Quantum's target from the maker's published 2023-03-10 H2-1 figures (spec sheet and emulator
            parameters, Moses et al. 2023): each rzz is one zz at its folded angle, costed on the line
            (2.9 theta/pi + 0.46)e-3; one-qubit gates 2.7e-5 each (one per rx or ry: the machine's own rotation runs
            at any angle); memory 1.95e-4 per qubit per two-qubit layer, applied by WAI Quantum's rule (layers counted
            as soon as qubits are free, a run on one pair counting once; charged after a qubit's last two-qubit gate and
            only once it holds a state a Z can change); readout (9e-4 + 2.2e-3)/2; a reset charged as a readout
            (no published figure; an assumption).
  quantinuum-h2-2-2024  sensitivity: the newest machine-date of the same sheet (H2-2, 2024-12-06), angle line scaled
            to its 2Q error 1.4e-3, memory 5.3e-4 - 7e-5 = 4.6e-4, one-qubit 8e-5, readout (9e-4 + 1.8e-3)/2.
  ionq-forte-1          IonQ's characterization of qpu.forte-1 of 2026-11-14 (read from its API): 2Q 1 - 0.9936 on
            every zz at any angle (no angle dependence is published), 1Q 1 - 0.9999 per native gpi/gpi2 (an rx or ry is
            two gpi2, one at +-pi/2 or pi), readout 1 - 0.9966; T1 100 s, T2 1 s, gate times 130 us and 970 us:
            relaxation inside each gate taken out of its stated error and idling relaxed on an as-soon-as-possible
            schedule, as WAI Quantum applies a target's T1, T2 and durations. No memory figure is published.
The application's admission figure is its fitted law F_rule = (1 - loss)^N_RZZ (loss 0.060% per RZZ, from trace
fidelity of Aim 2 circuits under the generic model). Under a device model it is carried over as
F_rule^(b_device / b_generic): the same law, its exponent scaled by the circuit's own budget ratio."""
import json, math, os, sys, collections
BASE = os.path.abspath(sys.argv[1]); PKG = sys.argv[2] if len(sys.argv) > 2 else None
IDX = json.load(open(f"{BASE}/circuits/index.json")); C, ROWS = IDX["circuits"], IDX["rows"]
LOSS = 0.0006
if PKG:
    s = json.load(open(f"{PKG}/results/summary.json")); LOSS = s["aim2"]["fidelity_fits"]["ion_like"]["loss_per_two_qubit_gate_pct"] / 100
PI = math.pi


def nl(x): return -math.log1p(-x) if x < 1 else 745.0


def fold(theta):
    t = abs(math.remainder(theta, 2 * PI))          # [0, pi]
    return min(t, PI - t)                            # [0, pi/2]; 0 and pi are local


def line(points):
    def f(t):
        (a0, e0), (a1, e1) = points
        return e0 + (e1 - e0) * (t - a0) / (a1 - a0)
    return f


MODELS = {
    "generic": {"two": lambda t: (1e-3, "lambda"), "one": 3e-5, "one_lambda": True, "readout": 2e-3, "reset": 2e-3, "memory": 0.0, "count_1q": "transpiled", "drop_local_rzz": False},
    "quantinuum-h2-1-2023": {"two": (lambda f: (lambda t: (f(t), "r")))(line([(0.0, 0.46e-3), (PI / 2, 1.91e-3)])), "one": 2.7e-5, "readout": (9e-4 + 2.2e-3) / 2, "reset": (9e-4 + 2.2e-3) / 2,
                              "memory": 1.95e-4, "count_1q": "transpiled", "drop_local_rzz": True},
    "quantinuum-h2-2-2024": {"two": (lambda f: (lambda t: (f(t), "r")))(line([(0.0, 0.46e-3 * 1.4 / 1.93), (PI / 2, 1.91e-3 * 1.4 / 1.93)])), "one": 8e-5, "readout": (9e-4 + 1.8e-3) / 2,
                              "reset": (9e-4 + 1.8e-3) / 2, "memory": 4.6e-4, "count_1q": "transpiled", "drop_local_rzz": True},
    "ionq-forte-1": {"two": lambda t: (1 - 0.9936, "r"), "one": 1 - 0.9999, "readout": 1 - 0.9966, "reset": None, "memory": 0.0, "count_1q": "native", "drop_local_rzz": True,
                     "t1_s": 100.0, "t2_s": 1.0, "t1q_s": 130e-6, "t2q_s": 970e-6},
}
MODELS["ionq-forte-1-best-of-5-days"] = dict(MODELS["ionq-forte-1"], two=lambda t: (1 - 0.9959, "r"))
MODELS["ionq-forte-1-best-of-5-days-no-idle"] = dict(MODELS["ionq-forte-1-best-of-5-days"], no_idle=True)
MODELS["quantinuum-h2-1-2023-no-memory"] = dict(MODELS["quantinuum-h2-1-2023"], memory=0.0)
# for the cross-check against WAI Quantum only: its trapped-ion targets name gpi and gpi2 as the one-qubit gates, so an rx or ry is costed as two
MODELS["quantinuum-h2-1-2023-gpi-one-qubit"] = dict(MODELS["quantinuum-h2-1-2023"], count_1q="native")


def native_1q(name, theta):
    """IonQ native one-qubit gates for an rx or ry (to_native.py's lowering)."""
    t = abs(math.remainder(theta, 2 * PI))
    if t < 1e-9: return 0
    if abs(t - PI / 2) < 1e-9 or abs(t - PI) < 1e-9: return 1
    return 2


def relax(t1, t2, dt):
    g = 1 - math.exp(-dt / t1); rate = 1 / t2 - 1 / (2 * t1); z = (1 - math.exp(-dt * rate)) / 2
    s = math.sqrt(1 - g); fpro = ((1 - z) * (1 + s) ** 2 + z * (1 - s) ** 2) / 4
    return fpro


def budget(gates, M):
    b = collections.Counter(); n2 = n1 = 0
    nq = 1 + max((q for g in gates for q in g[1]), default=0)
    # memory layering (WAI Quantum's rule)
    at = [0] * nq; partner = [-1] * nq; memory_at = [0] * nq; moved = [False] * nq; moved_at = [False] * nq; layers = 0; mem_layers = 0
    r_mem = M["memory"]; one = 1.5 * r_mem
    def charge(k):
        nonlocal mem_layers
        if r_mem <= 0 or k <= 0: return
        pz = (1 - (1 - 2 * one) ** k) / 2; b["memory"] += nl(pz); mem_layers += k
    timed = "t1_s" in M; clock = [0.0] * nq
    def relax_q(q, dt, key):
        if dt > 0 and not (key == "idle" and M.get("no_idle")): b[key] += -math.log(relax(M["t1_s"], M["t2_s"], dt))
    def gate_error(r, qs, dur):
        d = 2 ** len(qs)
        if timed:
            fe = 1.0
            for q in qs: fe *= relax(M["t1_s"], M["t2_s"], dur)
            rR = 1 - (d * fe + 1) / (d + 1)
            pd = max(0.0, d * (r - rR) / (d * (1 - rR) - 1))
            for q in qs: relax_q(q, dur, "relaxation")
        else: pd = d * r / (d - 1)
        b["gate"] += nl(pd)
    two_layers_events = []
    for name, qs, ps, cs in gates:
        if name == "rzz":
            t = fold(ps[0])
            if M["drop_local_rzz"] and t < 1e-12:
                b["frame_only_rzz"] += 0; continue
            a_, c_ = qs
            # layer
            if not (partner[a_] == c_ and partner[c_] == a_):
                l = max(at[a_], at[c_]) + 1; at[a_] = at[c_] = l; partner[a_], partner[c_] = c_, a_; layers = max(layers, l)
                for q in qs:
                    if moved_at[q]: charge(l - memory_at[q])
                    memory_at[q] = l
            for q in qs: moved_at[q] = moved[q]
            val, kind = M["two"](t)
            n2 += 1
            if timed:
                start = max(clock[a_], clock[c_])
                for q in qs: relax_q(q, start - clock[q], "idle"); clock[q] = start + M["t2q_s"]
                gate_error(val, qs, M["t2q_s"])
            elif kind == "lambda": b["gate"] += nl(val)
            else: gate_error(val, qs, 0)
        elif name in ("rx", "ry"):
            q = qs[0]; moved[q] = True
            k = native_1q(name, ps[0]) if M["count_1q"] == "native" else (0 if M["drop_local_rzz"] and abs(math.remainder(ps[0], 2 * PI)) < 1e-12 else 1)
            for _ in range(k):
                n1 += 1
                if timed:
                    relax_q(q, 0, "idle"); gate_error(M["one"], [q], M["t1q_s"]); clock[q] += M["t1q_s"]
                elif M.get("one_lambda"): b["gate"] += nl(M["one"])
                else: gate_error(M["one"], [q], 0)
        elif name == "rz": continue
        elif name == "measure":
            b["readout"] += nl(M["readout"]); q = qs[0]; moved[q] = moved_at[q] = False
        elif name == "reset":
            if M["reset"] is None: b["unsupported_reset"] += 1
            else: b["reset"] += nl(M["reset"])
            q = qs[0]; moved[q] = moved_at[q] = False
        else: raise ValueError(name)
    for q in range(nq):
        if moved_at[q]: charge(layers - memory_at[q])
    if timed:
        end = max(clock)
        for name, qs, ps, cs in gates:
            if name == "measure": relax_q(qs[0], end - clock[qs[0]], "idle"); clock[qs[0]] = end
    tot = sum(v for k, v in b.items() if k not in ("unsupported_reset", "frame_only_rzz"))
    return {"terms": {k: round(v, 6) for k, v in b.items()}, "total": tot, "fidelity": math.exp(-tot), "two_qubit_gates_costed": n2, "one_qubit_native_gates": n1, "two_qubit_layers": layers, "memory_qubit_layers": mem_layers}


def main():
    pred = {}
    for cid, c in C.items():
        p = f"{BASE}/circuits/gates/{cid}.json"
        if not os.path.exists(p): continue
        g = json.load(open(p))["gates"]
        pred[cid] = {m: budget(g, M) for m, M in MODELS.items()}
        pred[cid]["rzz_built"] = c.get("n2q")
    json.dump(pred, open(f"{BASE}/models/predictions.json", "w"), indent=1)
    # the admission re-check, row by row
    out = []
    for r in ROWS:
        p = pred.get(r["id"])
        if p is None: out.append({**r, "modelled": False}); continue
        dev = "ionq-forte-1" if r["vendor"] == "IonQ" else "quantinuum-h2-1-2023"
        alt = "ionq-forte-1-best-of-5-days" if r["vendor"] == "IonQ" else "quantinuum-h2-2-2024"
        low = "ionq-forte-1-best-of-5-days-no-idle" if r["vendor"] == "IonQ" else "quantinuum-h2-1-2023-no-memory"
        f_rule = (1 - LOSS) ** r["count_n2q"]; ratio = p[dev]["total"] / p["generic"]["total"]; ratio_alt = p[alt]["total"] / p["generic"]["total"]; ratio_low = p[low]["total"] / p["generic"]["total"]
        mid = C[r["id"]].get("mid_circuit_measure_or_reset", False)
        out.append({**{k: r[k] for k in ("aim", "group", "vendor", "tier_application", "circuit", "id", "shots", "count_n1q", "count_n2q", "count_qubits", "spam")},
                    "rule_fidelity_generic": f_rule, "budget_generic": p["generic"]["total"], "fidelity_generic": p["generic"]["fidelity"],
                    "device_model": dev, "budget_device": p[dev]["total"], "fidelity_device": p[dev]["fidelity"], "budget_ratio": ratio,
                    "rule_fidelity_device": f_rule ** ratio, "admitted_device": f_rule ** ratio >= 0.30,
                    "device_alt": alt, "rule_fidelity_device_alt": f_rule ** ratio_alt, "admitted_device_alt": f_rule ** ratio_alt >= 0.30,
                    "device_low": low, "rule_fidelity_device_low": f_rule ** ratio_low, "admitted_device_low": f_rule ** ratio_low >= 0.30,
                    "ionq_mid_circuit_unsupported": bool(r["vendor"] == "IonQ" and mid), "terms_device": p[dev]["terms"], "memory_qubit_layers": p[dev]["memory_qubit_layers"], "two_qubit_layers": p[dev]["two_qubit_layers"]})
    json.dump(out, open(f"{BASE}/models/admission.json", "w"), indent=1)
    print("loss per RZZ used for the rule:", LOSS)
    for v in ("IonQ", "Quantinuum"):
        for t in ("core", "extension"):
            rs = [x for x in out if x["vendor"] == v and x["tier_application"] == t and "rule_fidelity_device" in x]
            print(v, t, len(rs), "admitted under the device model:", sum(x["admitted_device"] for x in rs), "| alt:", sum(x["admitted_device_alt"] for x in rs), "| most favourable:", sum(x["admitted_device_low"] for x in rs),
                  "| median budget ratio %.2f" % sorted(x["budget_ratio"] for x in rs)[len(rs) // 2])


if __name__ == "__main__":
    os.makedirs(f"{BASE}/models", exist_ok=True); main()

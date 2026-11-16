#!/usr/bin/env python3
"""Budget-script variant of the calibration model, on the exact circuits that will be submitted (dd_off arm).

A port of ~/wai-ci-tools/qcup-emulators/scripts/ibm_budget.py to IBM's properties file and to circuits with mid-circuit
measurement and reset. Same terms as that script: each gate's stated error as depolarising beside the relaxation its
duration gives (T1, T2), idle relaxation on an as-soon-as-possible schedule, each read's assignment error ((p01+p10)/2).
No static ZZ, no leakage, no coherent term (those are in WAI Quantum's forecast, which this does not reproduce).
Additions needed for these circuits, not in the original: a mid-circuit measure occupies its qubit for the readout length
and costs one assignment error; a reset occupies its qubit for the reset length and costs the qubit's init_error.
Terminal measurements happen together at the end of the circuit, as in the original.
Idle conventions, both reported: "script" charges idle from t = 0 (before a qubit's first operation, as the original does);
"no_leading" does not charge idle before a qubit's first operation.
Outputs per circuit: the budget, e^-budget, the generic budget of the same circuit (ibm_sample.py's generic_sc), their
ratio, and the application's trace law carried over by that ratio, (1 - 0.001595)^(CZ x ratio), as ibm_analyze.py does.
Pure arithmetic over the exported OpenQASM 3. Usage: budget.py OUT CAL RESULT_JSON"""
import glob, json, math, re, sys
OUT, CAL, RES = sys.argv[1:4]
LOSS = 0.001595                                  # the package's generic fit, sc_like (results/summary.json)
def nl(x): return -math.log1p(-x)


def relax_f(t1, t2, dt):                          # verbatim from ibm_budget.py
    if dt <= 0 or not t1: return 1.0
    t2 = min(t2 or 2 * t1, 2 * t1); g = 1 - math.exp(-dt / t1); rate = 1 / t2 - 1 / (2 * t1); z = (1 - math.exp(-dt * rate)) / 2; s = math.sqrt(1 - g)
    return ((1 - z) * (1 + s) ** 2 + z * (1 - s) ** 2) / 4


design = json.load(open(f"{OUT}/design.json"))
out = {}
for b in design["backends"]:
    P = json.load(open(glob.glob(f"{CAL}/{b}-properties-*.json")[0]))
    Q = {}
    for i, qq in enumerate(P["qubits"]):
        d = {x["name"]: x["value"] for x in qq}
        Q[i] = {"t1": (d.get("T1") or 0) * 1e3, "t2": (d.get("T2") or 0) * 1e3, "p01": d.get("prob_meas1_prep0"), "p10": d.get("prob_meas0_prep1"), "ro_len": d.get("readout_length"), "init": d.get("init_error") or 0.0}
    G = {}
    for g in P["gates"]:
        d = {x["name"]: x["value"] for x in g["parameters"]}; G[(g["gate"], tuple(g["qubits"]))] = (d.get("gate_length") or 0.0, d.get("gate_error") or 0.0)
    res = {}
    for meta in design["circuits"]:
        lines = open(f"{OUT}/{b}/qasm_dd_off/{meta['id']}.qasm").read().splitlines()
        ops = []
        for line in lines:
            m = re.match(r"\s*(\w+)(\[\d+\])?\s*=\s*measure\s+\$(\d+);", line)
            if m: ops.append(("measure", [int(m.group(3))])); continue
            m = re.match(r"\s*(\w+)(\([^)]*\))?\s+(\$\d+(\s*,\s*\$\d+)*);", line)
            if m and m.group(1) not in ("barrier", "bit", "qubit", "include"):
                ops.append((m.group(1), [int(x) for x in re.findall(r"\$(\d+)", m.group(3))]))
        lastop = {}
        for k, (n, qs) in enumerate(ops):
            for p in qs: lastop[p] = k
        terminal = {k for k, (n, qs) in enumerate(ops) if n == "measure" and lastop[qs[0]] == k}
        used = sorted(lastop)
        bud = {"gate": 0.0, "relaxation": 0.0, "idle": 0.0, "idle_leading": 0.0, "readout": 0.0, "reset": 0.0}
        clock = {p: 0.0 for p in used}; started = {p: False for p in used}
        counts = {"cz": 0, "one_qubit": 0, "measure": 0, "reset": 0}
        T = lambda p: (Q[p]["t1"], Q[p]["t2"])
        def wait(p, until):
            w = until - clock[p]
            if w > 0:
                c = -math.log(relax_f(*T(p), w)); bud["idle"] += c
                if not started[p]: bud["idle_leading"] += c
        for k, (n, qs) in enumerate(ops):
            if k in terminal: continue
            if n == "measure":
                p = qs[0]; wait(p, clock[p]); clock[p] += Q[p]["ro_len"]; started[p] = True
                bud["readout"] += nl((Q[p]["p01"] + Q[p]["p10"]) / 2); counts["measure"] += 1; continue
            if n == "reset":
                p = qs[0]; d = G[("reset", (p,))][0]; clock[p] += d; started[p] = True; bud["reset"] += nl(Q[p]["init"]); counts["reset"] += 1; continue
            key = (n, tuple(qs)) if (n, tuple(qs)) in G else (n, tuple(reversed(qs)))
            d, r = G[key]
            start = max(clock[p] for p in qs)
            for p in qs: wait(p, start); clock[p] = start + d; started[p] = True
            if n == "cz": counts["cz"] += 1
            elif n in ("sx", "x"): counts["one_qubit"] += 1
            if r > 0:
                dd = 2 ** len(qs); fe = 1.0
                for p in qs: fe *= relax_f(*T(p), d)
                rR = 1 - (dd * fe + 1) / (dd + 1); pd = max(0.0, dd * (r - rR) / (dd * (1 - rR) - 1))
                bud["gate"] += nl(pd)
                for p in qs: bud["relaxation"] += -math.log(relax_f(*T(p), d))
        end = max(clock.values()) if clock else 0.0
        for k in terminal:
            p = ops[k][1][0]; wait(p, end); bud["readout"] += nl((Q[p]["p01"] + Q[p]["p10"]) / 2); counts["measure"] += 1
        tot = sum(v for kk, v in bud.items() if kk != "idle_leading")
        gen = counts["cz"] * nl(3e-3) + counts["one_qubit"] * nl(3e-4) + counts["measure"] * nl(1e-2) + counts["reset"] * nl(1e-2)
        ratio = tot / gen if gen else None; ratio_nl = (tot - bud["idle_leading"]) / gen if gen else None
        res[meta["id"]] = {"counts": counts, "budget": bud, "total_script": tot, "total_no_leading": tot - bud["idle_leading"], "e_minus_b_script": math.exp(-tot),
                           "e_minus_b_no_leading": math.exp(-(tot - bud["idle_leading"])), "generic_budget": gen, "ratio_script": ratio, "ratio_no_leading": ratio_nl,
                           "law_carried_over_script": (1 - LOSS) ** (counts["cz"] * ratio) if ratio else 1.0,
                           "law_carried_over_no_leading": (1 - LOSS) ** (counts["cz"] * ratio_nl) if ratio_nl else 1.0,
                           "duration_ns_asap": end}
        assert counts["cz"] == design["backends"][b]["device_cz"][meta["id"]]
        print(b, meta["id"], "cz", counts["cz"], "budget %.3f lead %.3f ratio %.2f e^-b %.3f carried %.3f" % (tot, bud["idle_leading"], ratio or 0, math.exp(-tot), res[meta["id"]]["law_carried_over_script"]))
    out[b] = res
json.dump(out, open(RES, "w"), indent=1)

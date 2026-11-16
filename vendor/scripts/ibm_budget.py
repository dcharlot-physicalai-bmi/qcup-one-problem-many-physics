"""Budget of the routed IBM sample circuits from a device target (WAI Quantum's import of the calibration), with the
terms WAI Quantum applies: each gate's stated error as depolarising beside the relaxation its duration gives (T1, T2),
idling relaxed on an as-soon-as-possible schedule, each read qubit's assignment error. Static ZZ is left out.
Used for the circuits wider than WAI's forecast takes (30 qubits); checked against WAI on the narrower ones.
Usage: ibm_budget.py BASE"""
import json, math, re, sys
B = sys.argv[1]
def nl(x): return -math.log1p(-x)
def relax_f(t1, t2, dt):
    if dt <= 0 or not t1: return 1.0
    t2 = min(t2 or 2 * t1, 2 * t1); g = 1 - math.exp(-dt / t1); rate = 1 / t2 - 1 / (2 * t1); z = (1 - math.exp(-dt * rate)) / 2; s = math.sqrt(1 - g)
    return ((1 - z) * (1 + s) ** 2 + z * (1 - s) ** 2) / 4
out = {}
for b in ("ibm_kingston", "ibm_fez", "ibm_marrakesh"):
    t = json.load(open(f"{B}/models/targets/{b}.target.json")); Q = {q["qubit"]: q for q in t["qubits"]}
    G = {}
    for g in t["gates"]: G[(g["gate"], tuple(g["qubits"]))] = g
    res = {}
    for part in ("small", "big"):
        s = json.load(open(f"{B}/ibm/out/suite-{b}-{part}.json"))
        for c in s["circuits"]:
            lay = c["layout"]; clock = {}; bud = {"gate": 0.0, "relaxation": 0.0, "idle": 0.0, "readout": 0.0}
            def T(p): q = Q[p]; return (q.get("t1_us") or 0) * 1e3, (q.get("t2_us") or 0) * 1e3
            for line in c["qasm"].splitlines():
                m = re.match(r"(\w+)(\([^)]*\))? (q\[\d+\](, q\[\d+\])*);", line)
                if not m or m.group(1) in ("qubit", "bit"): continue
                name = m.group(1); qs = [lay[int(x)] for x in re.findall(r"q\[(\d+)\]", m.group(3))]
                g = G.get((name, tuple(qs))) or G.get((name, tuple(reversed(qs))))
                if g is None: raise SystemExit(f"{b} {c['id']}: no entry for {name} {qs}")
                d = g.get("duration_ns") or 0.0; r = g.get("error") or 0.0
                start = max(clock.get(p, 0.0) for p in qs)
                for p in qs:
                    w = start - clock.get(p, 0.0)
                    if w > 0: bud["idle"] += -math.log(relax_f(*T(p), w))
                    clock[p] = start + d
                if r > 0:
                    dd = 2 ** len(qs); fe = 1.0
                    for p in qs: fe *= relax_f(*T(p), d)
                    rR = 1 - (dd * fe + 1) / (dd + 1); pd = max(0.0, dd * (r - rR) / (dd * (1 - rR) - 1))
                    bud["gate"] += nl(pd)
                    for p in qs: bud["relaxation"] += -math.log(relax_f(*T(p), d))
            end = max(clock.values()) if clock else 0.0
            for p in lay:
                w = end - clock.get(p, 0.0)
                if w > 0: bud["idle"] += -math.log(relax_f(*T(p), w))
                ro = Q[p].get("readout")
                if ro: bud["readout"] += nl((ro["p01"] + ro["p10"]) / 2)
            res[c["id"]] = {"budget": bud, "total": sum(bud.values()), "qubits": len(lay)}
    out[b] = res
json.dump(out, open(f"{B}/ibm/ibm_budget_script.json", "w"), indent=1)
print({b: len(v) for b, v in out.items()})

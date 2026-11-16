#!/usr/bin/env python3
"""IBM sample: the largest IBM-requested circuit per family and size, transpiled (a) to the package's heavy-hex patch in
CZ, as the admission rule counts it, and (b) to each device's current calibration (Heron, CZ basis, noise-aware layout,
optimisation level 3, seed 7). Writes the routed circuits as WAI Quantum forecast suites (physical qubits named, angles
rounded to dyadic multiples of 2pi) and the generic superconducting-like budget of each.

    python ibm_sample.py PKG_DIR IBM_DIR OUT_DIR"""
import glob, json, math, os, sys
import numpy as np
PKG, IBM, OUT = map(os.path.abspath, sys.argv[1:4]); sys.path.insert(0, PKG); R = f"{PKG}/results"; os.makedirs(OUT, exist_ok=True)
from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import Target, CouplingMap
from qiskit_ibm_runtime.models import BackendConfiguration, BackendProperties
from qiskit_ibm_runtime.utils.backend_converter import convert_to_target
from aim1_post import qaoa_circuit, heavy_hex_patch
def scale_patch(n):
    """scale_post.py's patch (copied: importing that script would rerun it)."""
    full = CouplingMap.from_heavy_hex(5 if n <= 57 else 7); adj = {}
    for a, b in full.get_edges(): adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
    order, seen, queue = [], {0}, [0]
    while queue and len(order) < n:
        v = queue.pop(0); order.append(v)
        for w in sorted(adj[v]):
            if w not in seen: seen.add(w); queue.append(w)
    idx = {v: k for k, v in enumerate(order)}
    return CouplingMap(sorted({(idx[a], idx[b]) for a in order for b in adj[a] if b in idx}))

SUM = json.load(open(f"{R}/summary.json")); LOSS_SC = SUM["aim2"]["fidelity_fits"]["sc_like"]["loss_per_two_qubit_gate_pct"] / 100
nl = lambda x: -math.log1p(-x)


def generic_sc(t):
    c = t.count_ops(); n_cz = c.get("cz", 0); n1 = c.get("sx", 0) + c.get("x", 0); nm = c.get("measure", 0); nr = c.get("reset", 0)
    return {"cz": int(n_cz), "one_qubit": int(n1), "measure": int(nm), "reset": int(nr), "budget": n_cz * nl(3e-3) + n1 * nl(3e-4) + nm * nl(1e-2) + nr * nl(1e-2)}


samples = []
# Aim 1 QAOA: per family and size, the admitted circuit with the most heavy-hex CZ (cold; warm adds one-qubit gates only)
a1 = json.load(open(f"{R}/aim1_request.json"))[0]["sizes_by_family"]
cand = {}
for p in glob.glob(f"{R}/post_*.json"):
    d = json.load(open(p))
    for t in d["transpile"]:
        if t["heavy_hex_cz"] <= 660 and not (d["family"] == "B" and d["n"] > 20 and t["p"] > 1): cand.setdefault((d["family"], d["n"]), []).append((t["heavy_hex_cz"], d["seed"], t["p"], "small"))
for d in json.load(open(f"{R}/scale_post.json")):
    for t in d["transpile"]:
        if d["n"] <= 156 and t["heavy_hex_cz"] <= 660 and not (d["family"] == "B" and d["n"] > 20 and t["p"] > 1): cand.setdefault((d["family"], d["n"]), []).append((t["heavy_hex_cz"], d["seed"], t["p"], "scale"))
for (f, n), L in sorted(cand.items()):
    cz, seed, p, where = max(L)
    inst = json.load(open(f"{R}/aim1_{f}_{n}_{seed}.json" if where == "small" else f"{R}/scale/scale_{f}_{n}_{seed}.json"))
    if where == "small": q = inst["qaoa"][p - 1]; gam, bet = q["gamma"], q["beta"]
    else: gam, bet = [0.3] * p, [0.2] * p
    qc = qaoa_circuit(n, inst["h"], inst["edges"], gam, bet); qc.measure_all()
    samples.append({"id": f"ibm-a1-{f}{n}-s{seed}-p{p}".lower(), "family": f"A1-{f}", "n": n, "p": p, "package_cz": cz, "qc": qc, "patch": heavy_hex_patch(n) if n <= 57 else scale_patch(n)})
# Aim 2: per style, the largest admitted circuit whose measurements are all terminal (garbage-retaining at any T; reset and in place at T = 1)
from aim2 import build, reference
from aim2b import is_permutation, build_inplace
rows = [r for p in glob.glob(f"{R}/aim2/*.json") for r in json.load(open(p)) if r["stream"] == 0 and r["sc_like"]["two_qubit_gates"] <= 660]
forms = {F["name"]: (i, F) for i, F in enumerate(json.load(open(f"{PKG}/forms/selected.json")))}
for style, Ts in (("G", (1, 2, 3, 4, 5)), ("R", (1,)), ("P", (1,))):
    L = [r for r in rows if r["style"] == style and r["T"] in Ts and r["form"] in forms]
    if not L: continue
    r = max(L, key=lambda r: r["sc_like"]["two_qubit_gates"]); i, F = forms[r["form"]]
    table, S, E = F["table"], F["states"], len(F["events"]); sb = max(1, math.ceil(math.log2(S))); eb = math.ceil(math.log2(E)) if E > 1 else 0
    delta = lambda s, e, table=table, S=S, E=E: table[s][e] if s < S and e < E else s
    qc = build_inplace(delta, sb, 0, r["T"]) if style == "P" else build(style, delta, sb, eb, 0, r["event_stream"])[0]
    samples.append({"id": f"ibm-a2-{r['form']}-{style}-t{r['T']}".lower().replace("_", "-"), "family": f"A2-{style}", "n": qc.num_qubits, "T": r["T"], "package_cz": r["sc_like"]["two_qubit_gates"], "qc": qc, "patch": heavy_hex_patch(qc.num_qubits)})
# Hubbard (IBM: product start), the largest admitted depth per lattice
import hubbard as H
from qiskit.circuit.library import PauliEvolutionGate
from qiskit.quantum_info import SparsePauliOp
hreq = json.load(open(f"{R}/hubbard/request.json"))["IBM"]
for lat in sorted({x["lattice"] for x in hreq}):
    x = max((y for y in hreq if y["lattice"] == lat), key=lambda y: y["cz"]); Lx, Ly = map(int, lat.split("x")); L_ = Lx * Ly; n = 2 * L_
    hb, vb = H.bonds(Lx, Ly); qq = lambda i, s: i + s * L_; qc = QuantumCircuit(n)
    for xx in range(Lx):
        for yy in range(Ly):
            i = xx * Ly + yy; qc.x(i if (xx + yy) % 2 == 0 else i + L_)
    for _ in range(x["p"]):
        for i in range(L_): qc.rzz(0.1, qq(i, 0), qq(i, 1))
        for a, b in hb + vb:
            for s_ in (0, 1):
                lo, hi = sorted((qq(a, s_), qq(b, s_))); lab = lambda P: "".join("I" if k < lo or k > hi else (P if k in (lo, hi) else "Z") for k in reversed(range(n)))
                qc.append(PauliEvolutionGate(SparsePauliOp([lab("X"), lab("Y")], [0.5, 0.5]), time=0.1), range(n))
    qc.measure_all(); samples.append({"id": f"ibm-f-hub-{lat}-p{x['p']}", "family": "F-hubbard", "n": n, "p": x["p"], "package_cz": x["cz"], "qc": qc, "patch": heavy_hex_patch(n)})
# family E at 8 bits, depth 2; sampling B16 depth 2
import labs as LB
T_ = LB.spin_terms(8); qa = json.load(open(f"{R}/labs/qaoa_8.json"))["depths"][1]; qc = QuantumCircuit(8); [qc.h(q) for q in range(8)]
for g, b in zip(qa["gamma"], qa["beta"]):
    for k, c in T_.items():
        q = sorted(k)
        if len(q) == 2: qc.rzz(2 * g * c, q[0], q[1])
        elif len(q) == 4: qc.cx(q[0], q[1]); qc.cx(q[1], q[2]); qc.cx(q[2], q[3]); qc.rz(2 * g * c, q[3]); qc.cx(q[2], q[3]); qc.cx(q[1], q[2]); qc.cx(q[0], q[1])
    [qc.rx(2 * b, q) for q in range(8)]
qc.measure_all(); samples.append({"id": "ibm-e-labs8-p2", "family": "E", "n": 8, "p": 2, "package_cz": 594, "qc": qc, "patch": heavy_hex_patch(8)})
dB = json.load(open(f"{R}/aim1_B_16_0.json")); qs = {(r["family"], r["n"], r["temperature"]): r for r in json.load(open(f"{R}/sampling/qaoa.json"))}[("B", 16, "warm")]["depths"][1]
qc = qaoa_circuit(16, dB["h"], dB["edges"], qs["gamma"], qs["beta"]); qc.measure_all(); samples.append({"id": "ibm-q7-b16-p2", "family": "Q7", "n": 16, "p": 2, "package_cz": None, "qc": qc, "patch": heavy_hex_patch(16)})

# devices
targets = {}
for b in ("ibm_kingston", "ibm_fez", "ibm_marrakesh"):
    conf = BackendConfiguration.from_dict(json.load(open(f"{IBM}/raw/{b}-configuration.json"))); props = BackendProperties.from_dict(json.load(open(f"{IBM}/raw/{b}-properties.json")))
    full = convert_to_target(conf, props); t = Target(num_qubits=full.num_qubits, dt=full.dt)
    for name in ("cz", "rz", "sx", "x", "measure", "reset", "delay"):
        if name in full.operation_names: t.add_instruction(full.operation_from_name(name), dict(full[name]))
    targets[b] = t

def dy(x):
    k = round(float(x) * 2 ** 31 / math.pi); return f"pi*{k}/2147483648" if k else "0"

out = []; suites = {b: {"forecast_suite": 1, "name": f"qcup-ibm-{b}", "shots": 1000, "circuits": []} for b in targets}
for s in samples:
    tp = transpile(s["qc"], coupling_map=s["patch"], basis_gates=["cz", "rz", "sx", "x", "reset", "measure"], optimization_level=3, seed_transpiler=7)
    g = generic_sc(tp); rec = {k: v for k, v in s.items() if k not in ("qc", "patch")}; rec.update(patch=g, rule_fidelity_generic=(1 - LOSS_SC) ** g["cz"], fidelity_generic=math.exp(-g["budget"]), devices={})
    for b, tg in targets.items():
        td = transpile(s["qc"], target=tg, optimization_level=3, seed_transpiler=7)
        idx = {q: i for i, q in enumerate(td.qubits)}; used = sorted({idx[q] for ins in td.data for q in ins.qubits if ins.operation.name not in ("barrier", "delay")})
        pos = {p: k for k, p in enumerate(used)}; c = td.count_ops()
        L = ["OPENQASM 3.0;", 'include "stdgates.inc";', f"qubit[{len(used)}] q;", f"bit[{len(used)}] c;"]; mid = False; last = {}
        for k, ins in enumerate(td.data):
            n_ = ins.operation.name
            if n_ in ("barrier", "delay", "measure"): continue
            if n_ == "reset": mid = True; break
            qs_ = [pos[idx[q]] for q in ins.qubits]; ps = ins.operation.params
            L.append(f"{n_}({dy(ps[0])}) " + ", ".join(f"q[{x}]" for x in qs_) + ";" if ps else f"{n_} " + ", ".join(f"q[{x}]" for x in qs_) + ";")
        L.append("c = measure q;")
        rec["devices"][b] = {"cz": int(c.get("cz", 0)), "one_qubit": int(c.get("sx", 0) + c.get("x", 0)), "physical_qubits": used, "mid_circuit": mid}
        if not mid:
            suites[b]["circuits"].append({"id": s["id"], "qasm": "\n".join(L) + "\n", "layout": used, "figure": {"outcomes": ["0" * len(used)]}})
    out.append(rec); print(rec["id"], rec["package_cz"], rec["patch"]["cz"], {b: v["cz"] for b, v in rec["devices"].items()}, flush=True)
json.dump(out, open(f"{OUT}/ibm_sample.json", "w"), indent=1)
for b, s in suites.items(): json.dump(s, open(f"{OUT}/suite-{b}.json", "w"))
print("sc loss per CZ", LOSS_SC, "samples", len(out))

#!/usr/bin/env python3
"""The package's Selene replay of the Aim 2 Guppy programs at T = 5 (results/aim2/guppy/*_T5.py), run again under
Selene's depolarizing error model with its parameters set to the maker's published 2023-03-10 H2-1 figures:
p_1q 2.7e-5, p_2q 1.93e-3 (the fully entangling gate's error; Selene does not scale it with the angle), p_meas 1.55e-3
(the mean of 9e-4 and 2.2e-3), p_init 0. Selene places this noise on each native operation of its own compile, not per
gate of our circuit, and has no memory term. 200 shots each (the request's Quantinuum shots), seed 5.

    python selene_noisy.py PKG OUT.json"""
import glob, importlib.util, json, math, os, sys, time
PKG, OUT = sys.argv[1], sys.argv[2]
from selene_sim import DepolarizingErrorModel
R = f"{PKG}/results/aim2"
rows = {(r["form"], r["style"], r["T"], r["stream"]): r for p in glob.glob(f"{R}/*.json") for r in json.load(open(p))}
out = json.load(open(OUT)) if os.path.exists(OUT) else []; done = {r["program"] for r in out}
for path in sorted(glob.glob(f"{R}/guppy/*_T5.py")):
    tag = os.path.basename(path)[:-3]
    if tag in done: continue
    form, style = tag[:-5], tag[-4]
    r = rows.get((form, style, 5, 0))
    if r is None or r["ion_like"]["two_qubit_gates"] > 2000: continue      # only programs the Quantinuum request admits
    sb = r["state_bits"]; want = "".join(format(s, f"0{sb}b") for s in reversed(r["reference_trace"]))
    spec = importlib.util.spec_from_file_location("g_" + tag, path); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    t0 = time.time()
    try:
        em = DepolarizingErrorModel(random_seed=5, p_1q=2.7e-5, p_2q=1.93e-3, p_meas=1.55e-3, p_init=0.0)
        res = mod.main.emulator(n_qubits=mod.N_QUBITS).with_error_model(em).with_shots(200).with_seed(5).run()
        got = []
        for shot in res.results:
            d = dict(shot.entries); got.append("".join(str(int(d[k])) for k in sorted(d, reverse=True)))
        f = sum(1 for g in got if g == want) / len(got)
        rec = {"program": tag, "form": form, "style": style, "T": 5, "shots": len(got), "trace_fidelity_selene_depolarizing": f, "ion_like_rzz": r["ion_like"]["two_qubit_gates"],
               "package_generic_trace_fidelity": r["ion_like"].get("trace_fidelity"), "qubits": r["qubits"], "seconds": round(time.time() - t0, 1)}
    except Exception as ex:
        rec = {"program": tag, "error": repr(ex)[:300]}
    out.append(rec); json.dump(out, open(OUT, "w"), indent=1); print(rec, flush=True)

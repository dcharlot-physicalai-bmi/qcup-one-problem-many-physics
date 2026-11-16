"""Modelled fidelity of the 48- and 72-qubit Hubbard circuits under each published Quantinuum figure set (same model
construction as model_drive.py). python3 -I large_circuits.py MODELS_PY EMU_BASE"""
import importlib.util, json, math, os, sys
MODELS_PY, EMU = sys.argv[1:3]; sys.argv = [MODELS_PY, EMU]
spec = importlib.util.spec_from_file_location("qcup_models", MODELS_PY); qm = importlib.util.module_from_spec(spec); spec.loader.exec_module(qm)
def make_model(e2q, e1q, e1q_legacy, transport, p0, p1):
    s = e2q / 1.93e-3; f = qm.line([(0.0, 0.46e-3 * s), (math.pi / 2, 1.91e-3 * s)]); ro = (p0 + p1) / 2
    return {"two": (lambda t, f=f: (f(t), "r")), "one": e1q, "readout": ro, "reset": ro, "memory": transport - e1q_legacy, "count_1q": "transpiled", "drop_local_rzz": True}
def docs(e1, l1, e2, mem, s0, s1): return make_model(e2, e1, e1 - l1 / 2, mem, s0, s1)
SETS = {"pub 2023-03-10 H2-1": make_model(1.93e-3, 2.7e-5, 2.5e-5, 2.2e-4, 9e-4, 2.2e-3), "pub 2024-05-20 H2-1": make_model(1.36e-3, 3.4e-5, 2.9e-5, 5.0e-4, 5e-4, 2.5e-3),
        "pub 2024-12-06 H2-2": make_model(1.4e-3, 8e-5, 7e-5, 5.3e-4, 9e-4, 1.8e-3), "docs 2025-04-30 H2-1": docs(1.9e-5, 4.8e-6, 1.1e-3, 2.0e-4, 6.0e-4, 1.4e-3),
        "docs 2025-05-29 H2-2": docs(3.5e-5, 9.6e-6, 1.1e-3, 2.3e-4, 6.0e-4, 1.8e-3), "docs 2025-08-28 H2-2": docs(2.8e-5, 6.1e-6, 8.3e-4, 1.2e-4, 6.7e-4, 1.2e-3),
        "docs 2026-10-20 H2-1": docs(4.7e-5, 8.8e-6, 1.2e-3, 3.1e-4, 6.5e-4, 3.2e-3), "docs 2026-10-06 H2-2": docs(3.9e-5, 1.2e-5, 8.3e-4, 1.8e-4, 6.7e-4, 1.9e-3)}
ids = ["qcup-f-hub-4x6-p1-free", "qcup-f-hub-4x6-p2-free", "qcup-f-hub-6x6-p1-neel", "qcup-f-hub-6x6-p2-neel"]
out = {}
for cid in ids:
    g = json.load(open(os.path.join(EMU, "circuits", "gates", f"{cid}.json")))["gates"]
    out[cid] = {k: qm.budget(g, M)["fidelity"] for k, M in SETS.items()}
    print(cid, {k: round(v, 4) for k, v in out[cid].items()})
print("max over the four, per set:", {k: round(max(out[c][k] for c in ids), 4) for k in SETS})

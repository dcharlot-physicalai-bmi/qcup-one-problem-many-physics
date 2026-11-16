"""Per-circuit error budgets under every published Quantinuum H2 figure set (writes vendor/results/models/quantinuum_sets.json).

The application admits Quantinuum circuits on a device model built from Quantinuum's published figures. models.py holds
two such models (H2-1 of 10 March 2023, H2-2 of 6 December 2024). Quantinuum has since published five more sets on its
documentation page (Performance Validation): H2-1 of 30 April 2025 and 20 October 2026, H2-2 of 29 May 2025, 28 August
2025 and 6 October 2026; and the repository table also holds H2-1 of 20 May 2024. Every set is turned into a models.py
device model by the rules models.py states for its two Quantinuum models (copied from the 2025 figure check,
qcup-quantinuum-2025/analysis/model_drive.py, make_model and docs):
  each rzz costed on the 2023 angle line (2.9 theta/pi + 0.46)e-3 scaled by (2Q error / 1.93e-3);
  one-qubit gate error = the 1Q error (leakage included); memory = transport 1Q error - 1Q error (legacy), where for the
  documentation-page sets the legacy 1Q error is the 1Q error less half the 1Q leakage;
  readout = (p_meas_0 + p_meas_1) / 2; a reset charged as a readout.
models.py itself is unchanged and imported; its main() is not called.

Positive control: the 2023 and 2024 sets built here must reproduce models.py's own totals in predictions.json exactly.

Usage (needs the gate lists models.py reads, BASE/circuits/index.json and BASE/circuits/gates/, from the vendor checks):
    python3 -I quantinuum_sets.py MODELS_PY BASE PACKAGE_ROOT
"""
import importlib.util, json, math, os, sys

MODELS_PY, BASE, PKG = sys.argv[1:4]
sys.argv = [MODELS_PY, BASE]                                  # models.py reads its BASE from argv at import
spec = importlib.util.spec_from_file_location("qcup_models", MODELS_PY); qm = importlib.util.module_from_spec(spec); spec.loader.exec_module(qm)
PI = math.pi
V = os.path.join(PKG, "vendor", "results")
P = json.load(open(os.path.join(V, "models", "predictions.json")))
C = json.load(open(os.path.join(V, "circuits", "index.json")))["circuits"]


def make_model(e2q, e1q, e1q_legacy, transport, p0, p1):
    s = e2q / 1.93e-3
    f = qm.line([(0.0, 0.46e-3 * s), (PI / 2, 1.91e-3 * s)])
    ro = (p0 + p1) / 2
    return {"two": (lambda t, f=f: (f(t), "r")), "one": e1q, "readout": ro, "reset": ro, "memory": transport - e1q_legacy,
            "count_1q": "transpiled", "drop_local_rzz": True,
            "_terms": {"two_qubit_error": e2q, "angle_line_scale": s, "one_qubit_error": e1q, "one_qubit_error_legacy": e1q_legacy,
                       "transport_1q_error": transport, "memory": transport - e1q_legacy, "p_meas_0": p0, "p_meas_1": p1, "readout_and_reset": ro}}


def docs(e1, l1, e2, mem, s0, s1): return make_model(e2, e1, e1 - l1 / 2, mem, s0, s1)


SETS = {
    # repository spec-sheet and emulator-parameter tables (github.com/Quantinuum/quantinuum-hardware-specifications at 59e68bb)
    "pub 2023-03-10 H2-1": make_model(1.93e-3, 2.7e-5, 2.5e-5, 2.2e-4, 9e-4, 2.2e-3),
    "pub 2024-05-20 H2-1": make_model(1.36e-3, 3.4e-5, 2.9e-5, 5.0e-4, 5e-4, 2.5e-3),
    "pub 2024-12-06 H2-2": make_model(1.4e-3, 8e-5, 7e-5, 5.3e-4, 9e-4, 1.8e-3),
    # Quantinuum documentation, Performance Validation page (dates are the page's plot captions)
    "docs 2025-04-30 H2-1": docs(1.9e-5, 4.8e-6, 1.1e-3, 2.0e-4, 6.0e-4, 1.4e-3),
    "docs 2025-05-29 H2-2": docs(3.5e-5, 9.6e-6, 1.1e-3, 2.3e-4, 6.0e-4, 1.8e-3),
    "docs 2025-08-28 H2-2": docs(2.8e-5, 6.1e-6, 8.3e-4, 1.2e-4, 6.7e-4, 1.2e-3),
    "docs 2026-10-20 H2-1": docs(4.7e-5, 8.8e-6, 1.2e-3, 3.1e-4, 6.5e-4, 3.2e-3),
    "docs 2026-10-06 H2-2": docs(3.9e-5, 1.2e-5, 8.3e-4, 1.8e-4, 6.7e-4, 1.9e-3),
}

out = {"note": "Per circuit: [budget total in nats, e^-budget] under each published Quantinuum figure set, by models.py's budget().",
       "sets": {k: {"terms": M["_terms"], "circuits": {}} for k, M in SETS.items()}, "controls": {}}
for cid in C:
    p = os.path.join(BASE, "circuits", "gates", f"{cid}.json")
    if not os.path.exists(p): continue
    g = json.load(open(p))["gates"]
    for k, M in SETS.items():
        b = qm.budget(g, M)
        out["sets"][k]["circuits"][cid] = [b["total"], b["fidelity"]]
for mine, theirs in (("pub 2023-03-10 H2-1", "quantinuum-h2-1-2023"), ("pub 2024-12-06 H2-2", "quantinuum-h2-2-2024")):
    d = [abs(out["sets"][mine]["circuits"][c][0] - P[c][theirs]["total"]) / max(P[c][theirs]["total"], 1e-300) for c in out["sets"][mine]["circuits"] if c in P]
    out["controls"][mine] = {"vs": theirs, "circuits": len(d), "max_relative_difference": max(d)}
json.dump(out, open(os.path.join(V, "models", "quantinuum_sets.json"), "w"), indent=0)
print(json.dumps(out["controls"]), {k: len(v["circuits"]) for k, v in out["sets"].items()})

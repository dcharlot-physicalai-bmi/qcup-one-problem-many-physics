#!/usr/bin/env python3
"""Aim 2 hardware request, derived from the simulated circuits by the admission rule (results/aim2_request.json).
A circuit is requested when its transpiled two-qubit gate count is within the budget at which modelled trace fidelity is 30%:
660 CZ (superconducting-like) or 2,000 RZZ (trapped-ion-like). Gate counts are taken from the first event stream; other
streams of the same Form, style and step count differ only in input preparation. Trapped-ion time is asked for in two
tiers: a core tier of circuits up to 300 two-qubit gates and an extension tier for the rest of the admitted set."""
import glob, json, os
ROOT = os.path.dirname(os.path.abspath(__file__))
a2 = [r for p in sorted(glob.glob(f"{ROOT}/results/aim2/*.json")) for r in json.load(open(p))]
streams = {}
for r in a2: streams.setdefault(r["form"], set()).add(r["stream"])
s0 = [r for r in a2 if r["stream"] == 0]
CORE_ION = 300   # trapped-ion core tier: circuits up to 300 two-qubit gates (modelled trace fidelity about 0.8 and above)
PLAN = [("IBM", "core", "sc_like", 0, 660, "GRP", [1, 2, 3, 4, 5], True, 1000), ("IQM", "core", "sc_like", 0, 660, "RP", [1, 2, 3, 4, 5], True, 1000),
        ("IonQ", "core", "ion_like", 0, CORE_ION, "RP", [1, 5], False, 500), ("IonQ", "extension", "ion_like", CORE_ION, 2000, "RP", [1, 5], False, 500),
        ("Quantinuum", "core", "ion_like", 0, CORE_ION, "RP", [1, 3, 5], False, 200), ("Quantinuum", "extension", "ion_like", CORE_ION, 2000, "RP", [1, 3, 5], False, 200)]
out = []
for vendor, tier, model, lo, cap, styles, steps, all_streams, shots in PLAN:
    q = [r for r in s0 if r["style"] in styles and r["T"] in steps and (lo < r[model]["two_qubit_gates"] <= cap or (lo == 0 and r[model]["two_qubit_gates"] == 0))]
    n = sum(len(streams[r["form"]]) if all_streams else 1 for r in q)
    out.append({"vendor": vendor, "tier": tier, "noise_model": model, "two_qubit_gate_budget": cap, "styles": styles, "steps": steps, "all_event_streams": all_streams,
                "forms": len({r["form"] for r in q}), "circuits": n, "qubits": [min(r["qubits"] for r in q), max(r["qubits"] for r in q)], "shots_per_circuit": shots, "total_shots": n * shots})
    print(out[-1])
json.dump(out, open(f"{ROOT}/results/aim2_request.json", "w"), indent=1)

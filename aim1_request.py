#!/usr/bin/env python3
"""Aim 1 hardware request, derived from transpiled gate counts by the admission rule (results/aim1_request.json).

Circuit set: every instance (120 at 12 to 20 variables, 60 at 24 to 60) x {cold, warm start} x depth 1 to 3. The warm-start
circuit has the same two-qubit gates as the cold one. A circuit is requested on a vendor when it fits the device
(IBM 156 qubits, IQM 54, IonQ 36, Quantinuum 98; QCUP figures) and its two-qubit gate count is within the budget at which
modelled trace fidelity is 30%: 660 CZ on heavy-hex for the superconducting devices, 2,000 RZZ all-to-all for trapped ions.
The trapped-ion rows are then re-admitted circuit by circuit under device models from the makers' figures and IonQ's
emulator (vendor/scripts/final_request.py; vendor/results/models/admission.json lists each row's figure).
Superconducting devices get every admitted circuit. Trapped-ion devices get seed 0 of each family and size only, split by
width (IonQ up to 32 variables, Quantinuum from 40 up) and into a core and an extension tier (see PLAN). Family B runs at depth 1 only above 20 variables, because angle
transfer fails for it at depths 2 and 3 (results/transfer.json) and angles cannot be optimised in simulation at that size."""
import glob, json, os
ROOT = os.path.dirname(os.path.abspath(__file__)); R = f"{ROOT}/results"
C = []   # (family, n, seed, p, cz, rzz)
for p in sorted(glob.glob(f"{R}/post_*.json")):
    d = json.load(open(p))
    for t in d["transpile"]: C.append((d["family"], d["n"], d["seed"], t["p"], t["heavy_hex_cz"], t["all_to_all_rzz"]))
for d in json.load(open(f"{R}/scale_post.json")):
    for t in d["transpile"]: C.append((d["family"], d["n"], d["seed"], t["p"], t["heavy_hex_cz"], t["all_to_all_rzz"]))
# Superconducting devices get every admitted circuit. Trapped-ion time is the scarce resource, so it is asked for in two tiers.
# Core: on IonQ, seed 0 of each family and size up to 32 variables at depth 1; on Quantinuum, the two targets the simulations
# single out at 40 to 60 variables: family A at 60 (the first edge answers that fail certification) at depth 1, and program
# repair (the sparsest family, and the one where ideal QAOA needs the fewest shots times gates at 12 to 20 variables) at every admitted depth.
# Extension, requested only if the core runs confirm the fidelity model: the remaining admitted seed-0 circuits.
ion = lambda f, n, s, p: s == 0 and n <= 32
qtm = lambda f, n, s, p: s == 0 and n >= 40
PLAN = [("IBM", "core", 156, 4, 660, lambda f, n, s, p: True, 4000), ("IQM", "core", 54, 4, 660, lambda f, n, s, p: True, 2000),
        ("IonQ", "core", 36, 5, 2000, lambda f, n, s, p: ion(f, n, s, p) and p == 1, 500), ("IonQ", "extension", 36, 5, 2000, lambda f, n, s, p: ion(f, n, s, p) and p > 1, 500),
        ("Quantinuum", "core", 98, 5, 2000, lambda f, n, s, p: qtm(f, n, s, p) and ((f == "A" and n == 60 and p == 1) or f == "R"), 200),
        ("Quantinuum", "extension", 98, 5, 2000, lambda f, n, s, p: qtm(f, n, s, p) and not ((f == "A" and n == 60 and p == 1) or f == "R"), 200)]
out = []
for vendor, tier, width, col, cap, keep, shots in PLAN:
    q = [c for c in C if c[1] <= width and c[col] <= cap and keep(c[0], c[1], c[2], c[3]) and not (c[0] == "B" and c[1] > 20 and c[3] > 1)]
    by = {}
    for c in q: by.setdefault(c[0], set()).add(c[1])
    rec = {"vendor": vendor, "tier": tier, "device_qubits": width, "two_qubit_gate_budget": cap, "instances": len({c[:3] for c in q}), "circuits": 2 * len(q), "qubits": [min(c[1] for c in q), max(c[1] for c in q)],
           "sizes_by_family": {f: sorted(v) for f, v in sorted(by.items())}, "by_depth": {p: 2 * sum(1 for c in q if c[3] == p) for p in (1, 2, 3)}, "shots_per_circuit": shots, "total_shots": 2 * len(q) * shots}
    out.append(rec); print(rec)
json.dump(out, open(f"{R}/aim1_request.json", "w"), indent=1)

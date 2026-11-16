#!/usr/bin/env python3
"""Per classical bit: which physical qubit was measured, how many CZ preceded the measurement (in the whole circuit and in
its causal past), and the device probability that the bit is right. Stdlib only. Usage: bitmap.py HW_BASE ARM"""
import json, re, sys
HW, ARM = sys.argv[1], sys.argv[2]
pred = json.load(open(f"{HW}/predictions.json")); res = json.load(open(f"{HW}/run/raw/results-{ARM}.json"))["results"]
out = {}
for meta, pub in zip(pred["circuits"], res):
    if meta["kind"] not in ("aim2", "control_zero_cz"): continue
    src = open(f"{HW}/design/ibm_marrakesh/qasm_{ARM}/{meta['id']}.qasm").read().splitlines()
    want = meta["want"]; nb = len(want)
    # causal past: track, per qubit, the set of CZ indices that can influence it
    past = {}; czi = 0; rows = []
    for line in src:
        line = line.strip()
        m = re.match(r"^trace\[(\d+)\] = measure \$(\d+);", line)
        if m:
            b, q = int(m.group(1)), int(m.group(2)); rows.append((b, q, czi, len(past.get(q, set())))); continue
        m = re.match(r"^cz \$(\d+), \$(\d+);", line)
        if m:
            a, c = int(m.group(1)), int(m.group(2)); s = past.get(a, set()) | past.get(c, set()) | {czi}; past[a] = set(s); past[c] = set(s); czi += 1; continue
        m = re.match(r"^reset \$(\d+);", line)
        if m: past[int(m.group(1))] = set(); continue     # a reset cuts the causal past (ideally)
    reg = list(pub["data"].values())[0]; vals = [int(h, 16) for h in reg["samples"]]; n = len(vals)
    info = []
    for b, q, before, cone in sorted(rows):
        wb = int(want[nb - 1 - b]); ok = sum(1 for v in vals if ((v >> b) & 1) == wb) / n
        info.append({"clbit": b, "qubit": q, "cz_before": before, "cz_in_past": cone, "want": wb, "p_right": round(ok, 3)})
    out[meta["id"]] = info
    print(meta["id"], "total cz", czi)
    for x in info: print("   bit %2d q%3d want %d  cz_before %4d cz_in_causal_past %4d  P(right) %.3f" % (x["clbit"], x["qubit"], x["want"], x["cz_before"], x["cz_in_past"], x["p_right"]))
json.dump(out, open(f"bitmap-{ARM}.json", "w"), indent=1)

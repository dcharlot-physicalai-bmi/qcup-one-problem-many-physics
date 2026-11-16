"""Compare our fits (qrb_fit.py output) with every published figure for the same dataset.

    python3 -I validate.py FITS_JSON OUT_JSON

Published figures:
  pub CSV  github.com/Quantinuum/quantinuum-hardware-specifications @59e68bb, notebooks/"Spec sheet parameters.csv"
           (value with its one-sigma digit) and notebooks/"Emulator parameters.csv" (p_meas_0, p_meas_1; no uncertainty)
  docs     docs.quantinuum.com .../performance_validation.html, archived by the Internet Archive; the plot captions on the
           same page say "Data collected on 2025/04/30" (H2-1), "2025/05/29" and "2025/08/28" (H2-2)
A fit agrees when it lies within the published one-sigma uncertainty of the published value (for values printed
without one, within half a unit of the last printed digit)."""
import json, sys
F = json.load(open(sys.argv[1]))["dates"]
def u(v, s): return (v, s)
PUB = {
 "H2-1/2023_03_10": {"src": "pub CSV 2023_03_10 H2-1", "e1": u(2.7e-5, 0.3e-5), "e1_legacy": u(2.5e-5, 0.3e-5), "l1": u(4e-6, 2e-6), "e2": u(1.93e-3, 0.05e-3),
                     "e2_legacy": u(1.83e-3, 0.05e-3), "l2": u(3.9e-4, 0.2e-4), "transport": u(2.2e-4, 0.3e-4), "spam": u(1.6e-3, 0.1e-3), "p0": u(0.0009, 0.00005), "p1": u(0.0022, 0.00005)},
 "H2-1/2024_05_20": {"src": "pub CSV 2024_05_20 H2-1", "e1": u(3.4e-5, 0.4e-5), "e1_legacy": u(2.9e-5, 0.4e-5), "l1": u(1.0e-5, 0.2e-5), "e2": u(1.36e-3, 0.08e-3),
                     "e2_legacy": u(1.28e-3, 0.08e-3), "l2": u(3.3e-4, 0.4e-4), "transport": u(5.0e-4, 0.3e-4), "spam": u(1.5e-3, 0.1e-3), "p0": u(0.0005, 0.00005), "p1": u(0.0025, 0.00005)},
 "H2-2/2024_12_06": {"src": "pub CSV 2024_12_06 H2-2", "e1": u(8e-5, 2e-5), "e1_legacy": u(7e-5, 2e-5), "l1": u(1.2e-5, 0.3e-5), "e2": u(1.4e-3, 0.1e-3),
                     "e2_legacy": u(1.3e-3, 0.1e-3), "l2": u(4.3e-4, 0.6e-4), "transport": u(5.3e-4, 0.4e-4), "spam": u(1.33e-3, 0.09e-3), "p0": u(0.0009, 0.00005), "p1": u(0.0018, 0.00005)},
 "H2-1/2025_04_30": {"src": "docs, archived 2025-06-18 to 2026-09-09", "e1": u(1.9e-5, 4.2e-6), "l1": u(4.8e-6, 1.5e-6), "e2": u(1.1e-3, 8.1e-5), "l2": u(1.4e-4, 2.1e-5),
                     "transport": u(2.0e-4, 2.3e-5), "p0": u(6.0e-4, 8.2e-5), "p1": u(1.4e-3, 1.2e-4)},
 "H2-2/2025_05_29": {"src": "docs, archived 2025-06-18 and 2025-07-17", "e1": u(3.5e-5, 3.9e-6), "l1": u(9.6e-6, 2.2e-6), "e2": u(1.1e-3, 1.7e-4), "l2": u(2.4e-4, 3.4e-5),
                     "transport": u(2.3e-4, 2.9e-5), "p0": u(6.0e-4, 8.2e-5), "p1": u(1.8e-3, 1.4e-4)},
 "H2-2/2025_08_28": {"src": "docs, archived 2025-10-16 to 2026-09-09 (also arXiv:2608.04290 Table I)", "e1": u(2.8e-5, 3.6e-6), "l1": u(6.1e-6, 1.3e-6), "e2": u(8.3e-4, 4.8e-5),
                     "l2": u(1.9e-4, 1.7e-5), "transport": u(1.2e-4, 2.0e-5), "p0": u(6.7e-4, 8.7e-5), "p1": u(1.2e-3, 1.1e-4)},
}
def mine(r, k):
    sq, tq, mm, sp = r["SQ_RB"], r["TQ_RB"], r["Memory_RB"], r["SPAM"]
    return {"e1": (sq["e_with_leakage"], sq["e_with_leakage_sd"]), "e1_legacy": (sq["e_legacy"], sq["e_legacy_sd"]), "l1": (sq["leak_rate"], sq["leak_rate_sd"]),
            "e2": (tq["e_with_leakage"], tq["e_with_leakage_sd"]), "e2_legacy": (tq["e_legacy"], tq["e_legacy_sd"]), "l2": (tq["leak_rate"], tq["leak_rate_sd"]),
            "transport": (mm["e_legacy"], mm["e_legacy_sd"]), "spam": (sp["spam_avg"], sp["spam_avg_sd"]), "p0": (sp["p_meas_0"], sp["p_meas_0_sd"]), "p1": (sp["p_meas_1"], sp["p_meas_1_sd"])}[k]
NAMES = {"e1": "1Q error (with leakage)", "e1_legacy": "1Q error (legacy)", "l1": "1Q leakage", "e2": "2Q error (with leakage)", "e2_legacy": "2Q error (legacy)",
         "l2": "2Q leakage", "transport": "transport 1Q / memory per depth-1", "spam": "SPAM (average)", "p0": "SPAM |0> (p_meas_0)", "p1": "SPAM |1> (p_meas_1)"}
out = {}; n = agree = 0; lines = []
for dt, pub in PUB.items():
    lines.append(f"\n{dt}  [{pub['src']}]")
    for k, (pv, ps) in pub.items() if False else [(k, v) for k, v in pub.items() if k != "src"]:
        v, s = mine(F[dt], k); dev = (v - pv) / ps; ok = abs(v - pv) <= ps + 1e-15
        n += 1; agree += ok
        out.setdefault(dt, {})[k] = {"published": pv, "published_sd": ps, "fit": v, "fit_sd": s, "deviation_in_published_sd": dev, "agrees": ok}
        lines.append(f"  {NAMES[k]:36s} published {pv:.3g} +- {ps:.2g} | fit {v:.4g} +- {s:.2g} | (fit - pub)/sd_pub {dev:+.2f} | {'agrees' if ok else 'OUTSIDE'}")
lines.append(f"\n{agree} of {n} fitted figures lie within the published one-sigma of the published value.")
print("\n".join(lines)); json.dump({"comparisons": out, "agree": agree, "total": n}, open(sys.argv[2], "w"), indent=1)

"""Component-benchmark fits of Quantinuum's published raw H2 data, written from the published method descriptions only.

    python3 -I qrb_fit.py RAW_DIR OUT_JSON [N_BOOT] [SEED]

RAW_DIR holds <machine>/<date>/{SQ_RB,TQ_RB,Memory_RB,SPAM}.json as published in
github.com/Quantinuum/quantinuum-hardware-specifications (commit 59e68bb). Only the count tables are read
("shots", "survival", "leakage_postselect"); the circuit text and per-shot records in the files are not used.

Methods, each from a published description (no code from that repository was read or run):
  RB decay (1Q, 2Q, transport): Moses et al., PRX 13, 041052 (2023), App. A1, Eqs. (A1)-(A2):
      p(l) = A r^l + 1/2^N (asymptote fixed by the random final Pauli), average infidelity e = (2^N - 1)/2^N (1 - r).
      The combined estimate fits the survival averaged over every qubit's (or pair's) random sequences at each length.
  2Q per gate: the 2Q Clifford infidelity divided by 1.5, the mean number of UZZ(pi/2) per Clifford (Moses Sec. III;
      Quantinuum documentation, Performance Validation, "2-qubit gate fidelity").
  Leakage: the fraction of shots with no leakage flagged by the gadget, fitted to p(l) = A (1 - r_L)^l
      (Moses Eq. (A8)); for 2Q, r_L per Clifford divided by 1.5 for the rate per 2Q gate (documentation, as above).
  Error including leakage (the repository's "1Q error"/"2Q error" columns since May 2025): average infidelity
      1 - F = (d - 1)/d * lambda + tau  (Chen and Baldwin, arXiv:2502.00154, Eq. (10)), i.e. the legacy estimate
      (d - 1)/d (1 - r) plus tau/d, d = 2 (1Q) or 4 (2Q).
  Transport 1Q RB (memory): 1Q RB interleaved with transport to random pairings on all qubits; the same 1Q fit,
      averaged across all qubits (Moses Sec. III; documentation, "Memory error per qubit at depth-1 circuit time").
  SPAM: prepare |0> (|1>) and count wrong outcomes; the reported SPAM error is the average of the two
      (Moses Sec. III; documentation, "State preparation and measurement (SPAM) error"); counts summed over qubits.
  Uncertainty: semi-parametric bootstrap (Meier 2006, cited by Moses as [44]): at each length resample the
      sequences with replacement, redraw each sequence's shots binomially at its observed rate, refit; report the
      standard deviation over resamples. SPAM: each qubit's counts redrawn binomially.
"""
import json, math, os, sys
import numpy as np
from scipy.optimize import curve_fit

RAW, OUT = sys.argv[1], sys.argv[2]
NBOOT = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
SEED = int(sys.argv[4]) if len(sys.argv) > 4 else 20261116
DATES = ["H2-1/2023_03_10", "H2-1/2024_05_20", "H2-1/2025_04_30", "H2-2/2024_12_06", "H2-2/2025_05_29", "H2-2/2025_08_28"]


def table(t):
    """{unit: {length: {seq: count}}} -> {length: np.array of counts over every (unit, seq)}"""
    out = {}
    for unit, by_len in t.items():
        for L, seqs in by_len.items():
            out.setdefault(int(L), []).extend(float(c) for c in seqs.values())
    return {L: np.array(v) for L, v in sorted(out.items())}


def fit_rb(Ls, means, d):
    f = lambda l, A, r: A * r ** l + 1.0 / d
    p, _ = curve_fit(f, Ls, means, p0=[1 - 1.0 / d, 0.999], bounds=([0, 0.5], [1.5, 1.0]), maxfev=20000)
    return p  # A, r


def fit_rb_free(Ls, means):
    f = lambda l, A, r, B: A * r ** l + B
    p, _ = curve_fit(f, Ls, means, p0=[0.7, 0.999, 0.3], bounds=([0, 0.5, 0], [1.5, 1.0, 1.0]), maxfev=20000)
    return p


def fit_leak(Ls, means):
    f = lambda l, A, rL: A * (1 - rL) ** l
    p, _ = curve_fit(f, Ls, means, p0=[1.0, 1e-4], bounds=([0, -0.01], [1.5, 0.5]), maxfev=20000)
    return p  # A, rL


def analyse_rb(d, nq, per_gate, surv, leak, shots, rng):
    """Combined fit and semi-parametric bootstrap. per_gate scales Clifford quantities to per-gate (1.5 for 2Q)."""
    Ls = np.array(sorted(surv)); dim = 2 ** nq

    def est(S, Lk):
        A, r = fit_rb(Ls, np.array([S[L].mean() for L in Ls]) / shots, dim)
        e_cliff = (dim - 1) / dim * (1 - r); e_leg = e_cliff / per_gate
        res = {"A": A, "r": r, "e_clifford_legacy": e_cliff, "e_legacy": e_leg}
        if Lk is not None:
            Al, rL = fit_leak(Ls, np.array([Lk[L].mean() for L in Ls]) / shots)
            tau = rL / per_gate
            res.update({"A_leak": Al, "leak_rate_clifford": rL, "leak_rate": tau, "e_with_leakage": e_leg + tau / dim})
        return res

    point = est(surv, leak)
    # sensitivity: asymptote left free (not the published method; reported only to show the fixed asymptote is not decisive)
    Af, rf, Bf = fit_rb_free(Ls, np.array([surv[L].mean() for L in Ls]) / shots)
    point["e_legacy_free_asymptote"] = (dim - 1) / dim * (1 - rf) / per_gate; point["free_asymptote_B"] = Bf
    boots = []
    for _ in range(NBOOT):
        S, Lk = {}, ({} if leak is not None else None)
        for L in Ls:
            n = len(surv[L]); idx = rng.integers(0, n, n)
            S[L] = rng.binomial(shots, np.clip(surv[L][idx] / shots, 0, 1)).astype(float)
            if leak is not None:
                Lk[L] = rng.binomial(shots, np.clip(leak[L][idx] / shots, 0, 1)).astype(float)
        try:
            boots.append(est(S, Lk))
        except RuntimeError:
            continue
    sd = {k + "_sd": float(np.std([b[k] for b in boots], ddof=1)) for k in boots[0]}
    point = {k: float(v) for k, v in point.items()}
    point.update(sd); point["n_boot_ok"] = len(boots)
    point["lengths"] = [int(L) for L in Ls]; point["sequences_per_length"] = {int(L): int(len(surv[L])) for L in Ls}; point["shots"] = shots
    point["mean_survival"] = {int(L): float(surv[L].mean() / shots) for L in Ls}
    if leak is not None: point["mean_unleaked"] = {int(L): float(leak[L].mean() / shots) for L in Ls}
    return point


def analyse_spam(js, rng):
    n = js["shots"]; sv = js["survival"]
    e = {s: np.array([(n - float(sv[q][s])) / n for q in sorted(sv, key=int)]) for s in ("0", "1")}
    res = {"shots_per_qubit": n, "qubits": len(sv), "p_meas_0": float(e["0"].mean()), "p_meas_1": float(e["1"].mean()),
           "spam_avg": float((e["0"].mean() + e["1"].mean()) / 2),
           "per_qubit_e0": [float(x) for x in e["0"]], "per_qubit_e1": [float(x) for x in e["1"]]}
    b = []
    for _ in range(NBOOT):
        b0 = rng.binomial(n, e["0"]) / n; b1 = rng.binomial(n, e["1"]) / n
        b.append((b0.mean(), b1.mean(), (b0.mean() + b1.mean()) / 2))
    b = np.array(b); res.update({"p_meas_0_sd": float(b[:, 0].std(ddof=1)), "p_meas_1_sd": float(b[:, 1].std(ddof=1)), "spam_avg_sd": float(b[:, 2].std(ddof=1))})
    return res


def main():
    rng = np.random.default_rng(SEED); out = {"method": __doc__, "n_boot": NBOOT, "seed": SEED, "dates": {}}
    for dt in DATES:
        p = os.path.join(RAW, dt); r = {}
        sq = json.load(open(os.path.join(p, "SQ_RB.json")))
        r["SQ_RB"] = analyse_rb(2, 1, 1.0, table(sq["survival"]), table(sq["leakage_postselect"]), sq["shots"], rng)
        tq = json.load(open(os.path.join(p, "TQ_RB.json")))
        r["TQ_RB"] = analyse_rb(4, 2, 1.5, table(tq["survival"]), table(tq["leakage_postselect"]), tq["shots"], rng)
        mm = json.load(open(os.path.join(p, "Memory_RB.json")))
        r["Memory_RB"] = analyse_rb(2, 1, 1.0, table(mm["survival"]), None, mm["shots"], rng)
        r["Memory_RB"]["units"] = len(mm["survival"])
        r["SPAM"] = analyse_spam(json.load(open(os.path.join(p, "SPAM.json"))), rng)
        # the model's memory term, by the rule models.py applies to the published figures: transport minus 1Q (legacy)
        mem = r["Memory_RB"]["e_legacy"] - r["SQ_RB"]["e_legacy"]
        r["model_terms"] = {"two_qubit_error": r["TQ_RB"]["e_with_leakage"], "two_qubit_error_sd": r["TQ_RB"]["e_with_leakage_sd"],
                            "one_qubit_error": r["SQ_RB"]["e_with_leakage"], "one_qubit_error_sd": r["SQ_RB"]["e_with_leakage_sd"],
                            "one_qubit_error_legacy": r["SQ_RB"]["e_legacy"], "transport_1q_error": r["Memory_RB"]["e_legacy"],
                            "transport_1q_error_sd": r["Memory_RB"]["e_legacy_sd"],
                            "memory_error": mem, "memory_error_sd": math.hypot(r["Memory_RB"]["e_legacy_sd"], r["SQ_RB"]["e_legacy_sd"]),
                            "p_meas_0": r["SPAM"]["p_meas_0"], "p_meas_1": r["SPAM"]["p_meas_1"], "readout": r["SPAM"]["spam_avg"]}
        out["dates"][dt] = r
        mt = r["model_terms"]
        print(f"{dt}: 2Q {mt['two_qubit_error']:.3e}+-{mt['two_qubit_error_sd']:.1e} (legacy {r['TQ_RB']['e_legacy']:.3e}, leak {r['TQ_RB']['leak_rate']:.2e}) | "
              f"1Q {mt['one_qubit_error']:.2e} (legacy {mt['one_qubit_error_legacy']:.2e}, leak {r['SQ_RB']['leak_rate']:.1e}) | transport {mt['transport_1q_error']:.2e}+-{mt['transport_1q_error_sd']:.1e} | "
              f"SPAM {r['SPAM']['spam_avg']:.3e} (p0 {mt['p_meas_0']:.2e}, p1 {mt['p_meas_1']:.2e})", flush=True)
    json.dump(out, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()

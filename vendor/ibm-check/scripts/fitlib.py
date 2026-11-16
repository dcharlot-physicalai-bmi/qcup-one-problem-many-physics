"""Fit rules for the QCUP hardware check, pure Python so the same code scores predictions and device data.

package:          aggregate.py's rule. Least squares of ln F on two-qubit gate count with a free intercept, on circuits
                  with F >= 0.01 (at least 20 correct traces in 2,000). 30% point = (ln 0.3 - c) / k.
no_intercept:     ln F = k x CZ through F(0) = 1, same points. 30% point = ln 0.3 / k. The convention behind 754 CZ.
floor_corrected:  F' = (F - f) / (1 - f) with f = 2^-(trace bits), the probability of guessing the trace; points with
                  F' >= 0.01; then as package. Guards against one-step programs flattening the slope at their floor."""
import math, random


def ols(xs, ys, intercept=True):
    n = len(xs)
    if intercept:
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx == 0: return None
        k = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx; c = my - k * mx
    else:
        sxx = sum(x * x for x in xs)
        if sxx == 0: return None
        k = sum(x * y for x, y in zip(xs, ys)) / sxx; c = 0.0
    yh = [c + k * x for x in xs]; my = sum(ys) / n
    sst = sum((y - my) ** 2 for y in ys); r2 = 1 - sum((y - h) ** 2 for y, h in zip(ys, yh)) / sst if sst > 0 else None
    return k, c, r2


def fit(points, rule):
    """points: list of (cz, F, floor). Returns the fit summary or None."""
    if rule == "floor_corrected":
        pts = [(cz, (F - f) / (1 - f)) for cz, F, f in points]
    else:
        pts = [(cz, F) for cz, F, f in points]
    pts = [(cz, F) for cz, F in pts if F >= 0.01]
    if len(pts) < 3: return None
    r = ols([p[0] for p in pts], [math.log(p[1]) for p in pts], intercept=(rule != "no_intercept"))
    if r is None: return None
    k, c, r2 = r
    return {"circuits": len(pts), "loss_per_cz_pct": 100 * (1 - math.exp(k)), "fidelity_at_zero_cz": math.exp(c), "r2": r2,
            "cz_at_30pct": (math.log(0.3) - c) / k if k < 0 else None}


def bootstrap_30(points_counts, rule, reps=2000, seed=20261116):
    """points_counts: list of (cz, hits, shots, floor). Resample circuits with replacement and each circuit's hits from
    Binomial(shots, hits/shots). Returns percentiles of the 30% point (None draws, from non-negative slopes, count as +inf)."""
    rng = random.Random(seed); vals = []
    for _ in range(reps):
        draw = [points_counts[rng.randrange(len(points_counts))] for _ in points_counts]
        pts = []
        for cz, h, n, f in draw:
            p = h / n; hh = sum(1 for _ in range(n) if rng.random() < p) if n <= 4000 else round(rng.gauss(n * p, math.sqrt(max(n * p * (1 - p), 1e-12))))
            pts.append((cz, hh / n, f))
        r = fit(pts, rule); vals.append(r["cz_at_30pct"] if r and r["cz_at_30pct"] is not None else float("inf"))
    vals.sort(); q = lambda a: vals[min(len(vals) - 1, int(a * len(vals)))]
    return {"reps": reps, "p2.5": q(0.025), "p16": q(0.16), "median": q(0.5), "p84": q(0.84), "p97.5": q(0.975)}


def held_out(rows, order):
    """Q5 held-out test, as aggregate.py: fit (package rule, gates only) on programs at even positions of `order`, predict
    the odd ones, and the reverse. rows: list of (name, cz, F). Returns the median and 90th-percentile error factor."""
    errs = []
    for fold in (0, 1):
        tr = [(cz, F) for n, cz, F in rows if order.index(n) % 2 == fold and F >= 0.01]
        te = [(cz, F) for n, cz, F in rows if order.index(n) % 2 != fold and F >= 0.01]
        if len(tr) < 2 or not te: continue
        k, c, _ = ols([a for a, _ in tr], [math.log(b) for _, b in tr])
        errs += [abs(c + k * cz - math.log(F)) for cz, F in te]
    if not errs: return None
    errs.sort(); med = errs[len(errs) // 2] if len(errs) % 2 else 0.5 * (errs[len(errs) // 2 - 1] + errs[len(errs) // 2])
    return {"median_error_factor": math.exp(med), "p90_error_factor": math.exp(errs[min(len(errs) - 1, int(0.9 * len(errs)))]), "predictions": len(errs)}

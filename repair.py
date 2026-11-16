#!/usr/bin/env python3
"""Bounded program repair as a QUBO (Aim 1, second part of family D; instance tag R).

Source programs are Forms harvested from the RCE repository (forms/harvest.json): a table delta[state][event].
A fault is injected by overwriting 1 or 2 table entries. A suspect set of m entries (the faulty ones plus
others, as an imperfect fault localiser would return) is opened for repair; every other entry is trusted.
The test suite is every two-step run from every reachable state, observing only the final state, with the
expected final state taken from the unmodified Form (the reference trace).

Variables: x[a][v] = 1 when suspect entry a is set to next-state v (one-hot per entry, S values).
Energy:   - (number of tests passed)  +  MU * (suspect entries that differ from the faulty program)
          +  LAMBDA * sum_a (sum_v x[a][v] - 1)^2
A two-step test (s, e1, e2, f) passes when delta[delta[s][e1]][e2] = f, which is a product of at most two
variables, so the energy is exactly quadratic. The QUBO is rescaled by 1/LAMBDA and written as an Ising
instance in the runner's convention E(s) = -sum J s_i s_j - sum h s_i, bit set <-> s = +1.
Every instance is brute-forced here over all S^m one-hot assignments to check that the QUBO optimum is
one-hot, passes every test, and to record whether it restores the original table.
Usage: repair.py <harvest.json> <out dir>
"""
import collections, itertools, json, os, sys
import numpy as np
harvest, out = sys.argv[1:3]
MU = 0.25
# (variables, seed) -> (source Form, suspect entries m, injected faults); n = m * states
PLAN = {(12, 0): ("programs/multi/washer.rce", 3, 1), (12, 1): ("spec/checker/tests/mutants/equivalent.rce", 3, 1), (12, 2): ("book/listings/ch05/door.rce", 4, 1),
        (16, 0): ("programs/multi/washer.rce", 4, 2), (16, 1): ("conformance/tests/properties/ch07-form-injective-f64.rce", 4, 2),
        (20, 0): ("programs/multi/washer.rce", 5, 2), (20, 1): ("conformance/tests/properties/t59-distinguish-mod5-mod4.rce", 4, 2),
        # scale-up instances, past exhaustive enumeration (optimum checked over one-hot assignments here and by branch and bound in the runner)
        (24, 0): ("programs/multi/session.rce", 4, 2), (24, 1): ("programs/multi/lobby.rce", 3, 1), (24, 2): ("programs/multi/washer.rce", 6, 2),
        (30, 0): ("programs/multi/parking.rce", 3, 1), (30, 1): ("programs/multi/reservoir.rce", 3, 2), (30, 2): ("programs/multi/session.rce", 5, 2),
        (40, 0): ("programs/multi/lobby.rce", 5, 2), (40, 1): ("programs/multi/parking.rce", 4, 2), (40, 2): ("programs/multi/reservoir.rce", 4, 2),
        (60, 0): ("programs/multi/elevator.rce", 5, 2), (60, 1): ("programs/multi/printer.rce", 5, 2), (60, 2): ("programs/multi/parking.rce", 6, 3)}
forms = {f["source"]: f for f in json.load(open(harvest))}

def tests_passed(table, tests):
    return sum(1 for s, e1, e2, f in tests if table[table[s][e1]][e2] == f)

for (n, seed), (src, m, nfault) in sorted(PLAN.items()):
    F = forms[src]; ref = F["table"]; S, E = F["states"], len(F["events"])
    assert m * S == n and F["kind"] == "exact"
    rng = np.random.default_rng(770000 + 100 * n + seed)
    entries = [(s, e) for s in range(S) for e in range(E)]
    suspects = [entries[i] for i in sorted(rng.choice(len(entries), m, replace=False))]
    buggy = [row[:] for row in ref]
    for i in rng.choice(m, nfault, replace=False):
        s, e = suspects[i]; buggy[s][e] = int(rng.choice([v for v in range(S) if v != ref[s][e]]))
    tests = [(s, e1, e2, ref[ref[s][e1]][e2]) for s in range(S) for e1 in range(E) for e2 in range(E)]
    var = {(a, v): a * S + v for a in range(m) for v in range(S)}; sidx = {se: a for a, se in enumerate(suspects)}
    Q = collections.defaultdict(float); const = 0.0
    def add(vs, c):
        global const
        vs = sorted(set(vs))
        if not vs: const += c
        elif len(vs) == 1: Q[(vs[0], vs[0])] += c
        else: Q[(vs[0], vs[1])] += c
    for s, e1, e2, f in tests:
        firsts = [(var[(sidx[(s, e1)], v)], v) for v in range(S)] if (s, e1) in sidx else [(None, buggy[s][e1])]
        for xv, v in firsts:
            if (v, e2) in sidx: add([x for x in (xv, var[(sidx[(v, e2)], f)]) if x is not None], -1.0)
            elif buggy[v][e2] == f: add([xv] if xv is not None else [], -1.0)
    for a, (s, e) in enumerate(suspects):
        for v in range(S):
            if v != buggy[s][e]: add([var[(a, v)]], MU)
    lam = 1.0 + max(sum(abs(c) for k, c in Q.items() if i in k) for i in range(n))
    for a in range(m):
        vs = [var[(a, v)] for v in range(S)]; const += lam
        for x in vs: add([x], -lam)
        for x, y in itertools.combinations(vs, 2): add([x, y], 2 * lam)
    Q = {k: c / lam for k, c in Q.items() if c}; const /= lam
    # brute force over one-hot assignments and, as a check, over all 2^n states when n <= 20
    def qubo(x): return const + sum(c * x[i] * x[j] for (i, j), c in Q.items())
    best = None
    for assign in itertools.product(range(S), repeat=m):
        x = [0] * n
        for a, v in enumerate(assign): x[var[(a, v)]] = 1
        e = qubo(x)
        if best is None or e < best[0] - 1e-12: best = (e, [assign])
        elif abs(e - best[0]) <= 1e-12: best[1].append(assign)
    if n <= 20:
        z = np.arange(1 << n, dtype=np.uint32); bits = [((z >> i) & 1).astype(float) for i in range(n)]
        full = np.full(1 << n, const)
        for (i, j), c in Q.items(): full += c * bits[i] * bits[j]
        assert abs(full.min() - best[0]) < 1e-9, "the QUBO optimum is not one-hot"
    repaired = []
    for assign in best[1]:
        t = [row[:] for row in buggy]
        for a, v in enumerate(assign): t[suspects[a][0]][suspects[a][1]] = v
        repaired.append(t)
    assert all(tests_passed(t, tests) == max(tests_passed(t2, tests) for t2 in repaired) for t in repaired)
    # Ising: x = (s + 1) / 2
    h = [0.0] * n; J = {}
    for (i, j), c in Q.items():
        if i == j: h[i] -= c / 2
        else: J[(i, j)] = -c / 4; h[i] -= c / 4; h[j] -= c / 4
    meta = {"tag": f"R_{n}_{seed}", "source": src, "source_sha256": F["sha256"], "states": S, "events": F["events"], "suspect_entries": suspects, "faults_injected": nfault,
            "tests": len(tests), "tests_passed_by_faulty_program": tests_passed(buggy, tests), "tests_passed_by_optimum": tests_passed(repaired[0], tests),
            "optimal_repairs": len(repaired), "optimum_restores_original": any(t == ref for t in repaired), "edits_in_optimum": sum(1 for a, v in enumerate(best[1][0]) if v != buggy[suspects[a][0]][suspects[a][1]]),
            "lambda": lam, "mu": MU, "qubo_optimum": best[0], "ising_offset": const + sum(c / 2 for (i, j), c in Q.items() if i == j) + sum(c / 4 for (i, j), c in Q.items() if i != j)}
    with open(os.path.join(out, f"R_{n}_{seed}.txt"), "w") as f:
        f.write(f"{n}\n" + "".join(f"h {i} {v!r}\n" for i, v in enumerate(h) if v) + "".join(f"J {i} {j} {w!r}\n" for (i, j), w in sorted(J.items())))
    json.dump(meta, open(os.path.join(out, f"R_{n}_{seed}.json"), "w"), indent=1)
    print(meta["tag"], src.split("/")[-1], "tests", meta["tests_passed_by_faulty_program"], "->", meta["tests_passed_by_optimum"], "of", len(tests), "| optimal repairs", len(repaired), "| restores original", meta["optimum_restores_original"], "| couplings", len(J))

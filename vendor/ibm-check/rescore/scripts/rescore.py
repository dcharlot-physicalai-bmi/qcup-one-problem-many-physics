#!/usr/bin/env python3
"""Independent re-score of the QCUP hardware check from the raw Sampler V2 JSON. Stdlib only.

Decoding: each PUB's data holds one register {"samples": [hex...], "num_bits": nb}. A sample's integer has bit i equal to
classical bit i of that register (Sampler V2 / BitArray convention). The bitstring is printed with classical bit 0
rightmost (qiskit get_counts order), which is the order aim2.trace_prob's `want` uses.

Reference traces are recomputed from forms/selected.json (the package's transition tables) and the event stream recorded in
design.json, and checked against the package's result row; `want` is rebuilt exactly as aim2.trace_prob builds it.
QAOA ground sets are recomputed from results/aim1_<fam>_<n>_0.json with aim1_post.diag_energy's convention.
Usage: rescore.py HW_BASE PKG_DIR [RESULTS_FILE_PATTERN] OUT_JSON"""
import json, math, sys, os, glob
HW, PKG, OUT = sys.argv[1], sys.argv[2], sys.argv[-1]
PAT = sys.argv[3] if len(sys.argv) == 5 else HW + "/run/raw/results-{arm}.json"
pred = json.load(open(f"{HW}/predictions.json")); design = json.load(open(f"{HW}/design/design.json"))
C = pred["circuits"]; D = {c["id"]: c for c in design["circuits"]}
forms = json.load(open(f"{PKG}/forms/selected.json")); fidx = {F["name"]: i for i, F in enumerate(forms)}


def decode(reg):
    nb = reg["num_bits"]; out = {}
    for h in reg["samples"]:
        v = int(h, 16); assert v < (1 << nb)
        s = "".join("1" if (v >> i) & 1 else "0" for i in reversed(range(nb)))   # clbit 0 rightmost
        out[s] = out.get(s, 0) + 1
    return out, nb


def ref_trace(meta):
    F = forms[fidx[meta["form"]]]; S = F["states"]; E = len(F["events"])
    s, tr = 0, []
    for e in meta["event_stream"]:
        s = F["table"][s][e] if (s < S and e < E) else s; tr.append(s)
    row = next(r for r in json.load(open(f"{PKG}/results/aim2/{meta['form']}.json")) if r["stream"] == 0 and r["style"] == meta["style"] and r["T"] == meta["T"])
    assert row["reference_trace"] == tr == meta["reference_trace"] and row["event_stream"] == meta["event_stream"], meta["id"]
    sb = max(1, math.ceil(math.log2(S)))
    assert sb == meta["state_bits"]
    return tr, sb


_gs_cache = {}
def ground(meta):
    key = (meta["family"], meta["n"])
    if key in _gs_cache: return _gs_cache[key]
    d = json.load(open(f"{PKG}/results/aim1_{meta['family']}_{meta['n']}_0.json")); n, h, edges = meta["n"], d["h"], d["edges"]
    best, gs = None, []
    for z in range(1 << n):
        s = [1.0 if (z >> i) & 1 else -1.0 for i in range(n)]
        e = -sum(h[i] * s[i] for i in range(n) if h[i] != 0.0) - sum(w * s[i] * s[j] for i, j, w in edges)
        if best is None or e < best - 1e-9 * (1 + abs(best)): best, gs = e, [z]
        elif abs(e - best) <= 1e-9 * (1 + abs(best)): gs.append(z)
    gs = [z for z in gs]
    _gs_cache[key] = (set(gs), best); return _gs_cache[key]


def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den; w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - w), min(1.0, c + w)


out = {}
for arm in ("dd_off", "dd_on"):
    res = json.load(open(PAT.format(arm=arm)))["results"]; assert len(res) == len(C)
    rows = []
    for meta, pub in zip(C, res):
        regs = list(pub["data"].keys()); assert len(regs) == 1 and regs[0] == D[meta["id"]]["creg"], (meta["id"], regs)
        counts, nb = decode(pub["data"][regs[0]]); n = sum(counts.values())
        r = {"id": meta["id"], "kind": meta["kind"], "cz": meta["backends"]["ibm_marrakesh"]["executed_cz"], "shots": n, "num_bits": nb}
        if meta["kind"] in ("aim2", "control_zero_cz"):
            tr, sb = ref_trace(meta); T = len(tr); assert nb == sb * T
            want = "".join(format(s, f"0{sb}b") for s in reversed(tr)); assert want == meta["want"]
            hit = counts.get(want, 0)
            # per step: bits of step t are clbits t*sb .. t*sb+sb-1 -> string positions from the right
            def step_val(bs, t): return int(bs[nb - (t + 1) * sb: nb - t * sb], 2)
            marg = []; prefix_ok = []; cond = []
            for t in range(T):
                ok = sum(v for k, v in counts.items() if step_val(k, t) == tr[t]); marg.append(ok / n)
                pk = sum(v for k, v in counts.items() if all(step_val(k, u) == tr[u] for u in range(t + 1))); prefix_ok.append(pk / n)
                prev = prefix_ok[t - 1] if t else 1.0; cond.append(pk / n / prev if prev > 0 else None)
            dist = []
            for t in range(T):
                dd = {}
                for k, v in counts.items(): dd[step_val(k, t)] = dd.get(step_val(k, t), 0) + v
                dist.append({str(a): round(b / n, 3) for a, b in sorted(dd.items(), key=lambda x: -x[1])[:4]})
            rev = want[::-1]; steprev = "".join(format(s, f"0{sb}b") for s in tr)
            r.update(want=want, ref=tr, sb=sb, T=T, hits=hit, measured=hit / n, ci95=wilson(hit, n), floor=2.0 ** -nb,
                     step_marginal=marg, prefix=prefix_ok, cond_step=cond, step_dist=dist,
                     reversed_bits_score=counts.get(rev, 0) / n, reversed_steps_score=counts.get(steprev, 0) / n,
                     top=sorted(counts.items(), key=lambda x: -x[1])[:3])
        elif meta["kind"] == "control_mirror":
            want = meta["want"]; hit = counts.get(want, 0)
            r.update(want=want, hits=hit, measured=hit / n, ci95=wilson(hit, n), floor=2.0 ** -nb, top=sorted(counts.items(), key=lambda x: -x[1])[:3],
                     bit_marginals=[sum(v for k, v in counts.items() if k[nb - 1 - i] == want[nb - 1 - i]) / n for i in range(nb)])
        else:
            gs, emin = ground(meta); assert sorted(gs) == sorted(D[meta["id"]]["ground_states"]), meta["id"]
            hit = sum(v for k, v in counts.items() if int(k, 2) in gs)
            hit_rev = sum(v for k, v in counts.items() if int(k[::-1], 2) in gs)
            r.update(hits=hit, measured=hit / n, ci95=wilson(hit, n), ideal=meta["ideal_p_gs"], ground=len(gs), floor=len(gs) / 2 ** nb, reversed_bits_score=hit_rev / n)
        rows.append(r)
    out[arm] = rows
json.dump(out, open(OUT, "w"), indent=1)
for arm in out:
    print("==", arm)
    for r in out[arm]:
        extra = ""
        if "step_marginal" in r: extra = " steps " + " ".join(f"{m:.2f}" for m in r["step_marginal"]) + " | cond " + " ".join(f"{c:.2f}" if c is not None else "-" for c in r["cond_step"]) + f" | rev {r['reversed_bits_score']:.3f} steprev {r['reversed_steps_score']:.3f}"
        elif "reversed_bits_score" in r: extra = f" ideal {r['ideal']:.3f} rev {r['reversed_bits_score']:.4f}"
        print(f"{r['id']:36s} cz {r['cz']:4d} {r['hits']:4d}/{r['shots']} = {r['measured']:.4f}  [{r['ci95'][0]:.3f},{r['ci95'][1]:.3f}] floor {r['floor']:.4g}{extra}")

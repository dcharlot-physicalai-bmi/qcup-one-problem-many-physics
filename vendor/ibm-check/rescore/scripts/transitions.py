import json, math, sys
H, PKG, ARM = sys.argv[1:4]
pred = json.load(open(f"{H}/predictions.json")); res = json.load(open(f"{H}/run/raw/results-{ARM}.json"))["results"]
forms = json.load(open(f"{PKG}/forms/selected.json")); fi = {F["name"]: F for F in forms}
for meta, pub in zip(pred["circuits"], res):
    if meta["kind"] not in ("aim2","control_zero_cz") or meta["T"] < 2: continue
    F = fi[meta["form"]]; S = F["states"]; E = len(F["events"]); sb = meta["state_bits"]; ev = meta["event_stream"]
    delta = lambda s, e: F["table"][s][e] if (s < S and e < E) else s
    (reg, d), = pub["data"].items(); nb = d["num_bits"]; vals = [int(h, 16) for h in d["samples"]]
    step = lambda v, t: (v >> (t * sb)) & ((1 << sb) - 1)
    print(f"== {meta['id']}  ref {meta['reference_trace']} events {ev}")
    for t in range(meta["T"] - 1):
        # P(next == delta(measured this step, event t+1))  vs  P(next == delta(0-ish))
        n = len(vals); follow = sum(1 for v in vals if step(v, t + 1) == delta(step(v, t), ev[t + 1])) / n
        # conditional on this step being right
        right = [v for v in vals if step(v, t) == meta["reference_trace"][t]]
        if not right: continue
        nxt = {}
        for v in right: nxt[step(v, t + 1)] = nxt.get(step(v, t + 1), 0) + 1
        top = sorted(nxt.items(), key=lambda x: -x[1])[:4]
        # what delta gives from each single-bit-dropped version of the right state
        s = meta["reference_trace"][t]; drops = {}
        for b in range(sb):
            if s >> b & 1: drops[f"drop bit{b}"] = delta(s & ~(1 << b), ev[t + 1])
        drops["from 0"] = delta(0, ev[t + 1])
        print(f"  step {t+1}->{t+2}: P(next follows delta of measured) {follow:.3f} | given step {t+1} right (n={len(right)}): next want {delta(s, ev[t+1])}, got " +
              ", ".join(f"{k}:{c/len(right):.2f}" for k, c in top) + f" | if a 1-bit of {s} were lost: {drops}")

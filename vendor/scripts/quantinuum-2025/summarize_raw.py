"""Compact shape summary of every raw benchmark file: top-level keys, and for nested count tables the levels' key sets.
python3 -I summarize_raw.py RAW_DIR"""
import json, sys, os
def levels(x, maxd=5):
    out = []
    while isinstance(x, dict) and maxd > 0:
        ks = list(x.keys())
        out.append(f"{len(ks)}:{sorted(ks, key=lambda k: (len(k), k))[:8]}{'...' if len(ks) > 8 else ''}")
        x = x[ks[0]]; maxd -= 1
    out.append(type(x).__name__ + (f"={str(x)[:50]!r}" if not isinstance(x, (dict, list)) else f"[{len(x)}]"))
    return " > ".join(out)
root = sys.argv[1]
for dp, dn, fn in sorted(os.walk(root)):
    for f in sorted(fn):
        p = os.path.join(dp, f); d = json.load(open(p))
        print(f"## {os.path.relpath(p, root)}  top-level: {list(d.keys())}")
        for k, v in d.items():
            print(f"   {k}: {levels(v) if isinstance(v, dict) else (type(v).__name__ + '=' + repr(str(v)[:80]))}")

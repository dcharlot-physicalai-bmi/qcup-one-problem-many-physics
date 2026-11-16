import json, re, sys
HW, ARM, MAXC = sys.argv[1], sys.argv[2], int(sys.argv[3])
pred = json.load(open(f"{HW}/predictions.json")); res = json.load(open(f"{HW}/run/raw/results-{ARM}.json"))["results"]
rows=[]
for meta, pub in zip(pred["circuits"], res):
    if meta["kind"] not in ("aim2", "control_zero_cz", "control_mirror"): continue
    src = open(f"{HW}/design/ibm_marrakesh/qasm_{ARM}/{meta['id']}.qasm").read().splitlines()
    want = meta["want"]; nb = len(want)
    past = {}; czl = []
    reg = list(pub["data"].values())[0]; vals = [int(h, 16) for h in reg["samples"]]; n = len(vals)
    for line in src:
        line=line.strip()
        m = re.match(r"^(?:trace|c)\[(\d+)\] = measure \$(\d+);", line)
        if m:
            b,q=int(m.group(1)),int(m.group(2)); P=past.get(q,set())
            if len(P)<=MAXC:
                wb=int(want[nb-1-b]); ok=sum(1 for v in vals if ((v>>b)&1)==wb)/n
                pc={}
                for i in P: pc[czl[i]]=pc.get(czl[i],0)+1
                rows.append((meta['id'][:28],b,q,len(P),round(ok,3),dict(sorted(pc.items()))))
            continue
        m = re.match(r"^cz \$(\d+), \$(\d+);", line)
        if m:
            a,c=int(m.group(1)),int(m.group(2)); pr=tuple(sorted((a,c))); czl.append(pr); i=len(czl)-1
            s=past.get(a,set())|past.get(c,set())|{i}; past[a]=set(s); past[c]=set(s); continue
        m = re.match(r"^reset \$(\d+);", line)
        if m: past[int(m.group(1))]=set()
for r in rows: print(*r)

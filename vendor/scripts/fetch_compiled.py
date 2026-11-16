"""Fetch the native circuit IonQ compiled for a job (artifact ionq.native.v1) and count its gates."""
import json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ionq_api import call, save
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = json.load(open(os.path.join(BASE, "ionq", "ledger.json")))
ids = sys.argv[1:] or [e["id"] for e in L.values() if e.get("status") == "completed"]
out = {}
p_out = os.path.join(BASE, "ionq", "compiled_counts.json")
if os.path.exists(p_out): out = json.load(open(p_out))
for key, e in L.items():
    if e["id"] not in ids or e.get("status") != "completed" or key in out: continue
    sfx = f"-s{e['shots']}" + ("-native" if e.get("route") == "native" else "")
    j = json.load(open(os.path.join(BASE, "ionq", "raw", "jobs", f"job-{e['id']}{sfx}.json")))["answer"]
    art = j["output"]["compilation"]["compiled_circuits"]["ionq.native.v1"]["id"]
    s, a = call("GET", f"/jobs/{e['job_id']}/artifacts/{art}")
    save(f"compiled-{e['id']}{sfx}", s, a, "compiled")
    circ = None
    if isinstance(a, dict):
        circ = a.get("circuit") if isinstance(a.get("circuit"), list) else ((a.get("input") or {}).get("circuit") or (a.get("data") or {}).get("circuit"))
        if circ is None:
            for v in a.values():
                if isinstance(v, dict) and "circuit" in v: circ = v["circuit"]
    if circ is None: out[key] = {"status": s, "keys": list(a.keys()) if isinstance(a, dict) else str(type(a))}; continue
    c = collections.Counter(g.get("gate") for g in circ)
    out[key] = {"id": e["id"], "route": e.get("route", "qis"), "native_gates": dict(c), "native_2q": sum(v for k, v in c.items() if k in ("zz", "ms")), "native_1q": sum(v for k, v in c.items() if k in ("gpi", "gpi2")),
                "input_2q": (e.get("stats") or {}).get("gate_counts", {}).get("2q"), "input_1q": (e.get("stats") or {}).get("gate_counts", {}).get("1q")}
    json.dump(out, open(p_out, "w"), indent=1)
    print(e["id"], out[key].get("native_gates"), "input 2q", out[key].get("input_2q"), flush=True)

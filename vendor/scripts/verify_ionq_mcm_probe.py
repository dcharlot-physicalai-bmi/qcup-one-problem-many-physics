"""Checker's probe: does IonQ's OpenQASM 3 route (ionq.qasm3.v1) accept mid-circuit measurement and reset on the free
simulator? Simulator only (asserted). Generic job names; circuits only. At most 4 jobs."""
import json, os, sys, time
sys.path.insert(0, os.path.expanduser("~/wai-ci-tools/qcup-emulators/scripts"))
from ionq_api import call, save
B = os.path.expanduser("~/wai-ci-tools/qcup-emulators")

def post(body):
    assert body["backend"] == "simulator"
    return call("POST", "/jobs", body)

def wait(jid, limit=900):
    t0 = time.time()
    while True:
        s, j = call("GET", f"/jobs/{jid}")
        if s == 200 and j.get("status") in ("completed", "failed", "canceled", "cancelled"): return j
        if time.time() - t0 > limit: return j
        time.sleep(3)

MIN = """OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[3] c;
x q[0];
c[0] = measure q[0];
reset q[0];
x q[1];
c[1] = measure q[0];
c[2] = measure q[1];
"""
tl = open(f"{B}/circuits/qasm/qcup-a2-17-traffic-light-accept-r-t5.qasm").read()
door = open(f"{B}/circuits/qasm/qcup-a2-door-r-t5.qasm").read()
jobs = [("verify-probe-1", MIN, {"model": "ideal"}, 100),
        ("verify-probe-2", tl, {"model": "ideal"}, 100),
        ("verify-probe-3", tl, {"model": "forte-1", "seed": 7}, 500),
        ("verify-probe-4", door, {"model": "forte-1", "seed": 7}, 500)]
which = sys.argv[1:] or [j[0] for j in jobs]
for name, prog, noise, shots in jobs:
    if name not in which: continue
    body = {"type": "ionq.qasm3.v1", "backend": "simulator", "name": name, "shots": shots, "noise": noise, "input": {"data": prog}}
    s, a = post(body); save(f"{name}-submit", s, a)
    print(name, "submit", s, json.dumps(a)[:300], flush=True)
    if s not in (200, 201) or not isinstance(a, dict) or not a.get("id"): continue
    j = wait(a["id"]); save(f"{name}-job", 200, j)
    print(name, "status", j.get("status"), "failure", json.dumps(j.get("failure")), "stats", json.dumps(j.get("stats")), flush=True)
    res = {}
    for k, v in (j.get("results") or {}).items():
        u = v.get("url") if isinstance(v, dict) else None
        if u:
            s2, r = call("GET", u.replace("/v0.4", "")); res[k] = r if s2 == 200 else {"status": s2, "answer": r}
    save(f"{name}-results", 200, res)
    print(name, "results", json.dumps(res)[:1200], flush=True)
    s3, c = call("GET", f"/jobs/{a['id']}/cost"); save(f"{name}-cost", s3, c)
    print(name, "cost", s3, json.dumps(c)[:300], flush=True)

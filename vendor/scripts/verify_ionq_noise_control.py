"""Checker's controls (simulator only): under the forte-1 noise model, (7) the minimal mid-circuit measure + reset
program, (8) the same gates with every measurement terminal and no reset. Attributes probe-3/4/6 failures."""
import json, os, sys, time
sys.path.insert(0, os.path.expanduser("~/wai-ci-tools/qcup-emulators/scripts"))
from ionq_api import call, save
P7 = 'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[3] c;\nx q[0];\nc[0] = measure q[0];\nreset q[0];\nx q[1];\nc[1] = measure q[0];\nc[2] = measure q[1];\n'
P8 = 'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\nbit[3] c;\nx q[0];\nx q[2];\ncx q[0], q[1];\nc[0] = measure q[0];\nc[1] = measure q[1];\nc[2] = measure q[2];\n'
def wait(jid, limit=900):
    t0 = time.time()
    while True:
        s, j = call("GET", f"/jobs/{jid}")
        if s == 200 and j.get("status") in ("completed", "failed", "canceled", "cancelled"): return j
        if time.time() - t0 > limit: return j
        time.sleep(3)
for name, prog in (("verify-probe-7", P7), ("verify-probe-8", P8)):
    body = {"type": "ionq.qasm3.v1", "backend": "simulator", "name": name, "shots": 500, "noise": {"model": "forte-1", "seed": 7}, "input": {"data": prog}}
    assert body["backend"] == "simulator"
    s, a = call("POST", "/jobs", body); save(f"{name}-submit", s, a); print(name, "submit", s, flush=True)
    if not (isinstance(a, dict) and a.get("id")): print(json.dumps(a)[:400]); continue
    j = wait(a["id"]); save(f"{name}-job", 200, j); print(name, j.get("status"), json.dumps(j.get("failure")), json.dumps(j.get("stats")), flush=True)
    art = (j.get("results") or {}).get("ionq.result.histogram.json.v2")
    if art:
        s2, r = call("GET", f"/jobs/{a['id']}/artifacts/{art['id']}"); save(f"{name}-hist-v2", s2, r); print(name, json.dumps(r)[:600], flush=True)
    s4, cc = call("GET", f"/jobs/{a['id']}/cost"); save(f"{name}-cost", s4, cc); print(name, "cost", s4, json.dumps(cc), flush=True)

"""Checker's follow-up probe (simulator only): the same five-step traffic-light circuit with the custom rzz gate
definition inlined as cx; rz; cx, on the ideal simulator and under the forte-1 noise model. Generic names; circuits only."""
import json, os, re, sys, time
sys.path.insert(0, os.path.expanduser("~/wai-ci-tools/qcup-emulators/scripts"))
from ionq_api import call, save
B = os.path.expanduser("~/wai-ci-tools/qcup-emulators")
src = open(f"{B}/circuits/qasm/qcup-a2-17-traffic-light-accept-r-t5.qasm").read()
src = re.sub(r"gate rzz\(p0\)[^}]*\}\n", "", src, flags=re.S)
src = re.sub(r"rzz\((.+?)\) (\w+\[\d+\]), (\w+\[\d+\]);", lambda m: f"cx {m.group(2)}, {m.group(3)};\nrz({m.group(1)}) {m.group(3)};\ncx {m.group(2)}, {m.group(3)};", src)
assert "rzz" not in src
open(f"{B}/verify/traffic-light-r-t5-inlined.qasm", "w").write(src)
def wait(jid, limit=900):
    t0 = time.time()
    while True:
        s, j = call("GET", f"/jobs/{jid}")
        if s == 200 and j.get("status") in ("completed", "failed", "canceled", "cancelled"): return j
        if time.time() - t0 > limit: return j
        time.sleep(3)
for name, noise, shots in (("verify-probe-5", {"model": "ideal"}, 100), ("verify-probe-6", {"model": "forte-1", "seed": 7}, 500)):
    body = {"type": "ionq.qasm3.v1", "backend": "simulator", "name": name, "shots": shots, "noise": noise, "input": {"data": src}}
    assert body["backend"] == "simulator"
    s, a = call("POST", "/jobs", body); save(f"{name}-submit", s, a); print(name, "submit", s, flush=True)
    if not (isinstance(a, dict) and a.get("id")): print(json.dumps(a)[:400]); continue
    j = wait(a["id"]); save(f"{name}-job", 200, j); print(name, j.get("status"), json.dumps(j.get("failure")), json.dumps(j.get("stats")), flush=True)
    for fmt in ("ionq.result.histogram.json.v2",):
        art = (j.get("results") or {}).get(fmt)
        if art:
            s2, r = call("GET", f"/jobs/{a['id']}/artifacts/{art['id']}"); save(f"{name}-{fmt}", s2, r); print(name, json.dumps(r)[:1500], flush=True)
    for fmt, art in ((j.get("output") or {}).get("compilation") or {}).get("compiled_circuits", {}).items():
        s3, c = call("GET", f"/jobs/{a['id']}/artifacts/{art['id']}"); save(f"{name}-compiled-{fmt}", s3, c)
        txt = c.get("text") if isinstance(c, dict) else str(c); print(name, "compiled zz lines:", sorted(set(re.findall(r"zz\(([-0-9.e]+)\)", txt or "")))[:6], flush=True)
    s4, cc = call("GET", f"/jobs/{a['id']}/cost"); save(f"{name}-cost", s4, cc); print(name, "cost", s4, json.dumps(cc), flush=True)

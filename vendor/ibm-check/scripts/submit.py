#!/usr/bin/env python3
"""Submit the pre-registered QCUP hardware check to IBM Quantum Platform (open plan only), Sampler V2 over REST.

Runs on the dev Mac with python3 -I. The API key is read from the keychain item wai-ibm-api-key straight into the token
request and never printed or written; the instance CRN comes from the WAI provider registry and is never written outside
private/. Every saved response is redacted (CRNs, account and user ids).

Steps: check that predictions.json still matches prereg.txt; read usage and the three backends' queues; pick the backend
with the shortest queue among those online; read its calibration now; send the DD-off arm with a hard max execution time;
read IBM's own estimate for it; send the DD-on arm only if the remaining free time covers both estimates plus 30 s.
Options: no twirling, no server-side DD (the DD-on arm carries its DD in the circuits), default shots per PUB set
explicitly, init_qubits on. Nothing optional or paid is enabled.

Usage: python3 -I submit.py BASE [--plan-only]"""
import hashlib, json, os, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
BASE = os.path.abspath(sys.argv[1]); PLAN_ONLY = "--plan-only" in sys.argv
API = "https://quantum.cloud.ibm.com/api/v1"; UA = {"User-Agent": "qcup-hw-client/1"}
CAP_S = 45                                   # max execution time per job (seconds of QPU time); the service cancels past it
SPARE_S = 30
PLAN = "850b21a7-71de-4e53-9441-1abdd202f35d"  # the open plan id this instance reported at design time
reg = json.load(open(os.path.expanduser("~/.config/wai/quantum-providers.json")))
crn = next(p["settings"]["crn"] for p in reg["providers"] if p["name"] == "ibm-kingston")


def token():
    key = subprocess.run(["security", "find-generic-password", "-s", "wai-ibm-api-key", "-w"], capture_output=True, text=True, check=True).stdout.strip()
    body = urllib.parse.urlencode({"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": key}).encode(); del key
    r = urllib.request.urlopen(urllib.request.Request("https://iam.cloud.ibm.com/identity/token", data=body, headers={**UA, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}), timeout=30)
    return json.load(r)["access_token"]


H = {**UA, "Authorization": f"Bearer {token()}", "Service-CRN": crn, "IBM-API-Version": "2026-04-15", "Accept": "application/json"}


def redact(text):
    text = text.replace(crn, "<instance-crn>"); text = re.sub(r"crn:v1:[^\"\s]*", "<crn>", text); text = re.sub(r"a/[0-9a-f]{32}", "a/<account>", text)
    return re.sub(r"\"(account_id|accountId|user_id|userId|iam_id|email|instance|instance_id)\"\s*:\s*\"[^\"]*\"", r'"\1": "<redacted>"', text)


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    hd = {**H, **({"Content-Type": "application/json"} if data else {})}
    try:
        r = urllib.request.urlopen(urllib.request.Request(API + path, data=data, headers=hd, method=method), timeout=120); return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:4000].decode("utf-8", "replace")


stamp = lambda: time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
def save(sub, name, text):
    d = os.path.join(BASE, sub); os.makedirs(d, exist_ok=True); p = os.path.join(d, f"{name}-{stamp()}.json"); open(p, "w").write(redact(text)); return p


def log(*a):
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ ", time.gmtime()) + " ".join(str(x) for x in a); print(line, flush=True)
    open(os.path.join(BASE, "run", "submit.log"), "a").write(line + "\n")


os.makedirs(os.path.join(BASE, "run"), exist_ok=True)
# 1. pre-registration intact
pre = open(os.path.join(BASE, "prereg.txt")).read()
want = re.search(r"predictions\.json sha256 ([0-9a-f]{64})", pre).group(1)
have = hashlib.sha256(open(os.path.join(BASE, "predictions.json"), "rb").read()).hexdigest()
if want != have: sys.exit(f"predictions.json changed since pre-registration ({have} != {want})")
pred = json.load(open(os.path.join(BASE, "predictions.json")))
log("prereg ok", have)
# 2. usage and queues
st, t = call("GET", "/instances/usage"); save("run/reads", "usage-before", t); u = json.loads(t)
if u.get("plan_id") != PLAN: sys.exit(f"instance plan {u.get('plan_id')} is not the open plan seen at design time; stopping")
remaining = u["usage_limit_seconds"] - u["usage_consumed_seconds"]
log("usage", u["usage_consumed_seconds"], "of", u["usage_limit_seconds"], "s; remaining", remaining, "s; limit reached", u.get("usage_limit_reached"))


def pending_other():
    """Worst-case seconds of jobs already queued or running on this instance: each job's hard cost cap (max execution
    time), 300 s if a job states none. Another agent shares the instance."""
    st, t = call("GET", "/jobs?pending=true&limit=50&exclude_params=true"); save("run/reads", "pending-jobs", t)
    if st != 200: sys.exit(f"cannot list pending jobs (HTTP {st}); stopping")
    js = json.loads(t).get("jobs", [])
    return sum(float(j.get("cost") or 300) for j in js), [(j.get("id"), j.get("status"), j.get("estimated_running_time_seconds"), j.get("cost")) for j in js]


other_s, other = pending_other(); log("pending jobs on the instance", other, "-> reserve", round(other_s, 1), "s")
remaining -= other_s
queues = {}
for b in ("ibm_marrakesh", "ibm_fez"):        # kingston's free queue held another job for more than 8.7 h
    st, t = call("GET", f"/backends/{b}/status"); save("run/reads", f"{b}-status", t); s = json.loads(t)
    if s.get("state") and s.get("status") == "active": queues[b] = s.get("length_queue", 10 ** 9)
    log("status", b, s.get("status"), "queue", s.get("length_queue"))
B = pred["backend"]                          # fixed at sealing; fez is only read and recorded
if B not in queues: sys.exit(f"{B} is not online; nothing sent")
log("backend", B, "queue", queues[B])
# 3. calibration at submission
for what in ("properties", "configuration"):
    st, t = call("GET", f"/backends/{B}/{what}"); p = save("run/calibration_at_submission", f"{B}-{what}", t); log("calibration", what, "HTTP", st, os.path.basename(p))
# 4. circuits of the chosen backend, checked against the manifest
man = json.load(open(os.path.join(BASE, "design", "qasm_manifest_sha256.json")))
ids = [c["id"] for c in pred["circuits"]]; shots = {c["id"]: c["shots"] for c in pred["circuits"]}
pubs = {}
for arm in ("dd_off", "dd_on"):
    pubs[arm] = []
    for cid in ids:
        rel = f"{B}/qasm_{arm}/{cid}.qasm"; src = open(os.path.join(BASE, "design", rel)).read()
        assert hashlib.sha256(src.encode()).hexdigest() == man[rel], rel
        pubs[arm].append([src, None, shots[cid]])
    log("arm", arm, "pubs", len(pubs[arm]), "shots", sum(shots.values()), "executed CZ", sum(len(re.findall(r"^cz ", p[0], re.M)) for p in pubs[arm]))
est = pred["qpu_seconds_estimate"]["per_backend"][B]["estimate_per_arm_s"]
# remaining already has every pending job's cap reserved; a job is sent only if what is left covers its own cap
plan_both = remaining >= 2 * CAP_S + SPARE_S and 2 * est[1] <= 100; plan_off = remaining >= CAP_S + SPARE_S
log("estimate per arm", est, "s; cap per job", CAP_S, "s; both arms fit:", plan_both, "; DD-off fits:", plan_off)
if PLAN_ONLY or not plan_off: sys.exit(0 if PLAN_ONLY else "not enough free time for the DD-off arm; nothing sent")


def submit(arm):
    body = {"program_id": "sampler", "backend": B, "cost": CAP_S, "tags": ["qcup-hw-check", f"arm-{arm.replace('_', '-')}", f"qcup-prereg:{have}"],
            "params": {"pubs": pubs[arm], "version": 2, "support_qiskit": False,
                       "options": {"dynamical_decoupling": {"enable": False}, "twirling": {"enable_gates": False, "enable_measure": False},
                                   "execution": {"init_qubits": True}}}}
    st, t = call("POST", "/jobs", body); save("run/reads", f"submit-{arm}", t); log("submit", arm, "HTTP", st, redact(t)[:300])
    if st not in (200, 201, 202): sys.exit(f"submission of {arm} refused: HTTP {st}")
    jid = json.loads(t)["id"]; json.dump({"arm": arm, "backend": B, "job": jid, "sent_utc": stamp()}, open(os.path.join(BASE, "run", f"job-{arm}.json"), "w"))
    return jid


j_off = submit("dd_off")
time.sleep(10)
st, t = call("GET", f"/jobs/{j_off}?exclude_params=true"); save("run/reads", f"job-{j_off}", t); jd = json.loads(t)
ibm_est = jd.get("estimated_running_time_seconds"); log("IBM estimate for DD-off", ibm_est, "s; status", jd.get("status"))
need_on = max(est[1], ibm_est or 0)
both_est = (ibm_est or est[1]) + need_on
st, t = call("GET", "/instances/usage"); save("run/reads", "usage-after-dd-off-sent", t); u = json.loads(t)
other_s, other = pending_other()             # now includes the DD-off job itself
remaining = u["usage_limit_seconds"] - u["usage_consumed_seconds"] - other_s
log("remaining after reserving every pending job (DD-off included)", round(remaining, 1), "s")
if remaining >= CAP_S + SPARE_S and both_est <= 100:
    j_on = submit("dd_on"); log("both arms sent", j_off, j_on)
else:
    log("DD-on not sent: remaining", round(remaining, 1), "s, cap", CAP_S, "+", SPARE_S, "; both arms estimated", both_est, "s (limit 100)")

"""IonQ cloud simulator runs for the QCUP request circuits (free; no QPU job is ever created here).

Run through ionq.sh (the key comes from the environment variable IONQ_API_KEY, never printed):
  ionq.sh ionq_run.py control                     positive control on the ideal simulator: QIS rotation conventions and bit order
  ionq.sh ionq_run.py probe-mcm                   does the service accept a measurement mid-circuit? (simulator only)
  ionq.sh ionq_run.py submit BUILD_DIR PLAN.json  submit the planned circuits to the simulator under the forte-1 noise model
  ionq.sh ionq_run.py collect                     poll every submitted job, save the job, its results and its cost
  ionq.sh ionq_run.py estimate PLAN.json          IonQ's own estimate for each circuit on qpu.forte-1 (a free read)

Every backend named in a request body is checked to be "simulator" before anything is sent."""
import json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ionq_api import call, save

HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(HERE)
RAW = os.path.join(BASE, "ionq", "raw"); PRIV = os.path.join(BASE, "ionq", "raw-private"); LEDGER = os.path.join(BASE, "ionq", "ledger.json")
NOISE = "forte-1"


def ledger():
    return json.load(open(LEDGER)) if os.path.exists(LEDGER) else {}


def put_ledger(L):
    json.dump(L, open(LEDGER + ".tmp", "w"), indent=1); os.replace(LEDGER + ".tmp", LEDGER)


def post_job(body):
    assert body["backend"] == "simulator", "only the simulator is ever used"
    return call("POST", "/jobs", body)


def job_body(name, nq, circuit, shots, noise, seed, gateset="qis"):
    b = {"type": "ionq.circuit.v1", "backend": "simulator", "name": name, "shots": shots,
         "settings": {"error_mitigation": {"debiasing": False}}, "input": {"gateset": gateset, "qubits": nq, "circuit": circuit}}
    if noise != "ideal": b["noise"] = {"model": noise, "seed": seed}
    else: b["noise"] = {"model": "ideal"}
    return b


def wait(jid, limit=1800):
    t0 = time.time()
    while True:
        s, j = call("GET", f"/jobs/{jid}")
        if s == 200 and j.get("status") in ("completed", "failed", "canceled", "cancelled"): return j
        if time.time() - t0 > limit: return j
        time.sleep(3)


def results(j):
    out = {}
    for k in ("probabilities", "histogram"):
        u = (j.get("results") or {}).get(k, {}).get("url")
        if u:
            s, a = call("GET", u.replace("/v0.4", "")); out[k] = a if s == 200 else {"status": s, "answer": a}
    return out


# ---------------------------------------------------------------- positive control
def rx(t): return np.array([[np.cos(t / 2), -1j * np.sin(t / 2)], [-1j * np.sin(t / 2), np.cos(t / 2)]])
def ry(t): return np.array([[np.cos(t / 2), -np.sin(t / 2)], [np.sin(t / 2), np.cos(t / 2)]])
def rz(t): return np.diag([np.exp(-1j * t / 2), np.exp(1j * t / 2)])


def ideal(nq, circ):
    psi = np.zeros(1 << nq, complex); psi[0] = 1
    for g in circ:
        psi = psi.reshape([2] * nq)
        if g["gate"] in ("rx", "ry", "rz"):
            u = {"rx": rx, "ry": ry, "rz": rz}[g["gate"]](g["rotation"]); ax = nq - 1 - g["target"]
            psi = np.moveaxis(np.tensordot(u, psi, axes=([1], [ax])), 0, ax)
        elif g["gate"] == "zz":
            a, b = g["targets"]; idx = np.arange(1 << nq); za = 1 - 2 * ((idx >> a) & 1); zb = 1 - 2 * ((idx >> b) & 1)
            psi = psi.reshape(-1) * np.exp(-1j * g["rotation"] / 2 * za * zb)
        psi = psi.reshape(-1)
    return np.abs(psi) ** 2


def control():
    circ = [{"gate": "ry", "target": 0, "rotation": 0.7}, {"gate": "ry", "target": 1, "rotation": 1.1}, {"gate": "rx", "target": 2, "rotation": 2.3},
            {"gate": "zz", "targets": [0, 1], "rotation": 0.9}, {"gate": "zz", "targets": [1, 2], "rotation": 1.7},
            {"gate": "rx", "target": 0, "rotation": 0.5}, {"gate": "rx", "target": 1, "rotation": 0.3}, {"gate": "ry", "target": 2, "rotation": 0.4},
            {"gate": "rz", "target": 0, "rotation": 0.8}, {"gate": "ry", "target": 0, "rotation": 1.2}]
    want = ideal(3, circ)
    s, a = post_job(job_body("qcup-control-ideal", 3, circ, 1000, "ideal", None)); save("control-submit", s, a)
    jid = a.get("id"); j = wait(jid); save("control-job", 200, j); r = results(j); save("control-results", 200, r)
    got = np.zeros(8)
    for k, v in r["probabilities"].items(): got[int(k)] = v
    print("control status", j.get("status"), "max |ideal - service| =", float(np.abs(got - want).max()))
    print("want", np.round(want, 5).tolist()); print("got ", np.round(got, 5).tolist())
    s, c = call("GET", f"/jobs/{jid}/cost"); save("control-cost", s, c); print("cost of the control job:", s, c)
    # the same circuit under the forte-1 noise model: a second, noisy positive control
    s, a = post_job(job_body("qcup-control-forte1", 3, circ, 1000, NOISE, 7)); save("control-forte1-submit", s, a)
    j = wait(a.get("id")); save("control-forte1-job", 200, j); r = results(j); save("control-forte1-results", 200, r)
    got = np.zeros(8)
    for k, v in r["probabilities"].items(): got[int(k)] = v
    print("forte-1 control:", j.get("status"), "TVD to ideal", round(0.5 * float(np.abs(got - want).sum()), 4), "stats", j.get("stats"))
    s, c = call("GET", f"/jobs/{a.get('id')}/cost"); save("control-forte1-cost", s, c); print("cost of the noisy control job:", s, c)


def probe_mcm():
    circ = [{"gate": "rx", "target": 0, "rotation": 1.0}, {"gate": "measure", "target": 0}, {"gate": "rx", "target": 1, "rotation": 1.0}]
    s, a = post_job(job_body("qcup-probe-mcm", 2, circ, 10, "ideal", None)); save("probe-mcm-submit", s, a)
    print("mid-circuit measure probe:", s, json.dumps(a)[:400])
    if s in (200, 201) and a.get("id"):
        j = wait(a["id"], 300); save("probe-mcm-job", 200, j); print("job status", j.get("status"), json.dumps(j.get("failure"))[:300])
    circ = [{"gate": "rx", "target": 0, "rotation": 1.0}, {"gate": "reset", "target": 0}]
    s, a = post_job(job_body("qcup-probe-reset", 1, circ, 10, "ideal", None)); save("probe-reset-submit", s, a)
    print("reset probe:", s, json.dumps(a)[:400])
    if s in (200, 201) and a.get("id"):
        j = wait(a["id"], 300); save("probe-reset-job", 200, j); print("job status", j.get("status"), json.dumps(j.get("failure"))[:300])


def native_control():
    """Positive control of the native lowering: random circuits over rx, ry, rz, zz (special and generic angles), lowered
    to gpi, gpi2, zz, run on the ideal simulator, compared with the exact distribution of the QIS circuit."""
    from to_native import lower
    r = np.random.default_rng(5); special = [np.pi / 2, -np.pi / 2, np.pi, -np.pi, 2.4, -2.9, 0.3]
    worst = 0
    for trial in range(3):
        nq = 4; circ = []
        for _ in range(40):
            k = r.integers(4)
            ang = float(r.choice(special)) if r.random() < 0.4 else float(r.uniform(-np.pi, np.pi))
            if k == 3: a, b = r.choice(nq, 2, replace=False); circ.append({"gate": "zz", "targets": [int(a), int(b)], "rotation": ang})
            else: circ.append({"gate": ["rx", "ry", "rz"][k], "target": int(r.integers(nq)), "rotation": ang})
        want = ideal(nq, circ); nat = lower({"qubits": nq, "circuit": circ})
        s, a = post_job(job_body(f"qcup-control-native-{trial}", nq, nat["circuit"], 1000, "ideal", None, "native")); save(f"native-control-{trial}-submit", s, a)
        j = wait(a.get("id")); save(f"native-control-{trial}-job", 200, j); res = results(j); save(f"native-control-{trial}-results", 200, res)
        got = np.zeros(1 << nq)
        for k_, v in res["probabilities"].items(): got[int(k_)] = v
        d = float(np.abs(got - want).max()); worst = max(worst, d)
        print("native control", trial, j.get("status"), "max |ideal - service| =", round(d, 5), "native gates", len(nat["circuit"]), "service 2q/1q", (j.get("stats") or {}).get("gate_counts"))
    print("worst", worst)


# ---------------------------------------------------------------- submission
def submit(build, plan_path, native=False):
    plan = json.load(open(plan_path)); L = ledger(); n = 0
    for k, item in enumerate(plan):
        key = item["id"] + "|" + str(item["shots"]) + ("|native" if native else "")
        if key in L and L[key].get("job_id"): continue
        src = json.load(open(os.path.join(build, "ionq-native" if native else "ionq", item["id"] + ".json")))
        body = job_body(item["id"] + ("-nat" if native else ""), src["input"]["qubits"], src["input"]["circuit"], item["shots"], NOISE, 1000 + k, "native" if native else "qis")
        s, a = post_job(body); save("submit-" + item["id"] + f"-s{item['shots']}" + ("-native" if native else ""), s, {k_: v for k_, v in a.items()} if isinstance(a, dict) else a, "submit")
        L[key] = {"id": item["id"], "shots": item["shots"], "seed": 1000 + k, "route": "native" if native else "qis", "status_code": s, "job_id": a.get("id") if isinstance(a, dict) else None, "submitted": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        if s not in (200, 201): L[key]["error"] = a; print("refused", item["id"], s, json.dumps(a)[:300])
        put_ledger(L); n += 1
        time.sleep(0.3)
    print("submitted", n, "ledger", len(L))


def collect():
    L = ledger(); done = 0; pend = 0
    for key, e in L.items():
        if not e.get("job_id") or e.get("collected"): done += bool(e.get("collected")); continue
        s, j = call("GET", f"/jobs/{e['job_id']}")
        if s != 200: print("job read", key, s); continue
        if j.get("status") not in ("completed", "failed", "canceled", "cancelled"): pend += 1; e["status"] = j.get("status"); continue
        sfx = f"-s{e['shots']}" + ("-native" if e.get("route") == "native" else "")
        save("job-" + e["id"] + sfx, 200, j, "jobs")
        if j.get("status") == "completed":
            r = results(j); save("results-" + e["id"] + sfx, 200, r, "results")
        s, c = call("GET", f"/jobs/{e['job_id']}/cost"); save("cost-" + e["id"] + sfx, s, c, "cost")
        e.update(collected=True, status=j.get("status"), stats=j.get("stats"), cost_model=j.get("cost_model"), cost_answer=c, failure=j.get("failure"),
                 execution_duration_ms=j.get("execution_duration_ms"), compilation=(j.get("output") or {}).get("compilation", {}).get("gate_basis"))
        done += 1
    put_ledger(L); print("collected", done, "pending", pend, "of", len(L))


def estimate(plan_path):
    """IonQ's estimate on qpu.forte-1 for each planned circuit: with IonQ's own gate counts where the simulator job reports
    them, and with the package's counts (cost.py) beside. A free read: no job is created."""
    plan = json.load(open(plan_path)); L = ledger(); out = []
    os.makedirs(PRIV, exist_ok=True)
    for item in plan:
        e = L.get(item["id"] + "|" + str(item["shots"]), {})
        sets = []
        if e.get("stats") and e["stats"].get("gate_counts"): sets.append(("ionq_counts", e["stats"]["gate_counts"]["1q"], e["stats"]["gate_counts"]["2q"]))
        if item.get("count_n1q") is not None: sets.append(("package_counts", item["count_n1q"], item["count_n2q"]))
        for label, n1, n2 in sets:
            q = f"/jobs/estimate?backend=qpu.forte-1&type=ionq.circuit.v1&qubits={item['qubits']}&shots={item['shots']}&1q_gates={n1}&2q_gates={n2}&error_mitigation=false"
            s, a = call("GET", q)
            save(f"estimate-{item['id']}-s{item['shots']}-{label}", s, a, "../raw-private/estimates")
            rec = {"id": item["id"], "shots": item["shots"], "qubits": item["qubits"], "counts": label, "1q_gates": n1, "2q_gates": n2, "status": s}
            if s == 200:
                rec.update(estimated_total_cost=a.get("estimated_total_cost"), estimated_unit=a.get("estimated_unit"), estimated_execution_time_ms=a.get("estimated_execution_time"),
                           rates=[{k: v for k, v in r.items() if k != "id"} for r in (a.get("rate_card") or {}).get("rates", [])])
            else: rec["answer"] = a
            out.append(rec); time.sleep(0.2)
    json.dump(out, open(os.path.join(BASE, "ionq", "estimates.json"), "w"), indent=1)
    print("estimates", len(out), "ok", sum(1 for r in out if r["status"] == 200))


if __name__ == "__main__":
    os.makedirs(RAW, exist_ok=True)
    {"control": lambda: control(), "probe-mcm": lambda: probe_mcm(), "submit": lambda: submit(sys.argv[2], sys.argv[3]), "submit-native": lambda: submit(sys.argv[2], sys.argv[3], True), "native-control": lambda: native_control(), "collect": lambda: collect(),
     "estimate": lambda: estimate(sys.argv[2])}[sys.argv[1]]()

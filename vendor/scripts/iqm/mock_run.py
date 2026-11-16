"""Timing evidence for the IQM credit request from IQM Resonance's emerald:mock (a mock of IQM Emerald, Crystal 54).

The mock has no instruments: its counts are random bits. What it does return is IQM's own compilation of each job for
the Emerald architecture and calibration, and the job record, which carries the server's runtime estimate for the job
(compilation.execution_runtime_estimate_seconds) and its billing metrics (metrics.billed_seconds). Those, not the counts,
are what this script collects.

Safety: before anything is submitted the price of emerald:mock is read from the API and the script stops unless it is
exactly 0. At most MAX_JOBS jobs are sent. Only circuits are sent, under generic names (c0, c1, ...). The token is read
from the macOS keychain into memory and never printed or written.

Circuits are the request's own, from the package (vendor/results/circuits/qasm): seed-0 Aim 1 QAOA circuits in the IQM
set (results/iqm/exported.json), the H2 circuit, the 8-variable LABS circuit, a Q7 sampling circuit and Aim 2 programs in
the IQM set (results/aim2, stream 0, reset and in-place styles, within 660 CZ). Each is transpiled with IQM's client to
emerald:mock's architecture (optimization level 3, seed 7, as iqm_check.py).

Usage:  python -I mock_run.py plan <evidence dir>     transpile and list the jobs; nothing submitted
        python -I mock_run.py run  <evidence dir>     submit the jobs to emerald:mock and record the job records
"""
import datetime, glob, json, os, sys, time, urllib.request, urllib.error
from decimal import Decimal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from _tok import token, scrub

PKG = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))   # package root (package copy: vendor/scripts/iqm/)
QASM = f"{PKG}/vendor/results/circuits/qasm"
QC_ALIAS = "emerald:mock"; URL = "https://resonance.iqm.tech"; API = URL + "/api/v1"
MAX_JOBS = 30

def a1_name(row, kind): f, n, s, p = row["family"], row["n"], row["seed"], row["p"]; return f"qcup-a1-{f}{n}-p{p}-{kind}"

def iqm_sets():
    a1 = [r for r in json.load(open(f"{PKG}/results/iqm/exported.json")) if r["seed"] == 0]
    a2 = [r for p in sorted(glob.glob(f"{PKG}/results/aim2/*.json")) for r in json.load(open(p))]
    a2 = [r for r in a2 if r["stream"] == 0 and r["style"] in "RP" and r["sc_like"]["two_qubit_gates"] <= 660]
    a2n = {f"qcup-a2-{r['form'].replace('_', '-')}-{r['style'].lower()}-t{r['T']}": r for r in a2}
    return a1, {k: v for k, v in a2n.items() if os.path.exists(f"{QASM}/{k}.qasm")}

def plan_jobs(a1, a2n):
    q = lambda f, n, p, kind="cold": f"qcup-a1-{f}{n}-p{p}-{kind}"
    a1all = [a1_name(r, k) for r in a1 for k in ("cold", "warm")]
    a2all = sorted(a2n)
    jobs = [  # (label, circuit names, shots)
        ("single C12 p1, 100 shots", [q("C", 12, 1)], 100),
        ("single C12 p1, 1000 shots", [q("C", 12, 1)], 1000),
        ("single C12 p1, 2000 shots", [q("C", 12, 1)], 2000),
        ("single C12 p1, 6000 shots", [q("C", 12, 1)], 6000),
        ("single C42 p1 (widest), 2000 shots", [q("C", 42, 1)], 2000),
        ("single R30 p1 (624 heavy-hex CZ), 2000 shots", [q("R", 30, 1)], 2000),
        ("single C18 p3 (618 heavy-hex CZ), 2000 shots", [q("C", 18, 3)], 2000),
        ("single H2 (merged row), 6000 shots", ["qcup-f-chem-h2-n4"], 6000),
        ("single LABS N=8 p1, 2000 shots", ["qcup-e-labs8-p1"], 2000),
        ("single Q7 sampling B12 warm p1, 2000 shots", ["qcup-q7-B12-warmT-p1"], 2000),
        ("single Aim 2 phase in place T1, 1000 shots", ["qcup-a2-phase-p-t1"], 1000),
        ("single Aim 2 door reset T5 (mid-circuit reset; 1,028 superconducting-like CZ, outside the IQM set), 1000 shots", ["qcup-a2-door-r-t5"], 1000),
        ("batch 10 Aim 1 QAOA, 2000 shots", a1all[:10], 2000),
        (f"batch {len(a1all)} Aim 1 QAOA (all seed-0 IQM circuits, cold and warm), 2000 shots", a1all, 2000),
        ("batch 10 Aim 2, 1000 shots", a2all[:10], 1000),
        (f"batch {len(a2all)} Aim 2 (all stream-0 IQM programs at T 1, 3, 5 in the package), 1000 shots", a2all, 1000),
        ("repeat: single C12 p1, 2000 shots", [q("C", 12, 1)], 2000),
    ]
    assert len(jobs) <= MAX_JOBS
    return jobs

def api_get(path, T):
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + T, "Accept": "application/json", "User-Agent": "qcup-reader/1"})
    try:
        r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, {"error": scrub(e.read()[:600].decode("utf-8", "replace"), T)}

def main():
    mode, out = sys.argv[1], sys.argv[2]; priv = os.path.join(out, "private"); os.makedirs(priv, exist_ok=True); os.makedirs(f"{out}/mock", exist_ok=True)
    T = token()
    s, d = api_get("/quantum-computers/" + QC_ALIAS, T)
    price = Decimal(str(((d.get("pricing") or {}).get("payg_price_per_second", "nan")))) if s == 200 else None
    print(QC_ALIAS, "price per second:", price, "backend_type:", d.get("backend_type"))
    if price is None or price != 0 or d.get("backend_type") != "mock": sys.exit("STOP: emerald:mock is not priced at 0 (or not a mock); nothing submitted")
    from qiskit import transpile, qasm3
    from iqm.qiskit_iqm import IQMProvider
    backend = IQMProvider(URL, quantum_computer=QC_ALIAS, token=T).get_backend()
    a1, a2n = iqm_sets(); jobs = plan_jobs(a1, a2n)
    names = sorted({c for _, cs, _ in jobs for c in cs}); tc = {}; meta = {}
    for nm in names:
        qc = qasm3.load(f"{QASM}/{nm}.qasm")
        t = transpile(qc, backend=backend, optimization_level=3, seed_transpiler=7)
        ops = t.count_ops(); tc[nm] = t
        meta[nm] = {"qubits": qc.num_qubits, "cz": int(ops.get("cz", 0)), "prx_or_r": int(ops.get("r", 0) + ops.get("prx", 0)), "measure": int(ops.get("measure", 0)),
                    "reset": int(ops.get("reset", 0)), "depth": t.depth(), "ops": {k: int(v) for k, v in ops.items()}}
        print(nm, meta[nm]["qubits"], "CZ", meta[nm]["cz"], "depth", meta[nm]["depth"], flush=True)
    plan = [{"job": i, "label": lab, "circuits": len(cs), "shots": sh, "circuit_names": cs} for i, (lab, cs, sh) in enumerate(jobs)]
    json.dump({"backend": QC_ALIAS, "price_per_second_read": str(price), "transpile": "qiskit transpile, IQM client 36.0.0 target, optimization_level 3, seed 7",
               "circuits": meta, "jobs": plan}, open(f"{out}/mock/plan.json", "w"), indent=1)
    print(len(jobs), "jobs,", sum(p["circuits"] for p in plan), "circuit executions planned")
    if mode != "run": return
    rows = []
    for i, (lab, cs, sh) in enumerate(jobs):
        s, d = api_get("/quantum-computers/" + QC_ALIAS, T)      # price re-read before every job
        if s != 200 or Decimal(str(d["pricing"]["payg_price_per_second"])) != 0: sys.exit(f"STOP before job {i}: price is no longer 0")
        circs = []
        for k, nm in enumerate(cs):
            c = tc[nm].copy(); c.name = f"c{k}"; c.metadata = {}; circs.append(c)
        t0 = time.time(); job = backend.run(circs, shots=sh); jid = job.job_id()
        try: job.result(timeout=900)
        except Exception as e: print("job", i, "result error:", type(e).__name__, scrub(str(e)[:300], T))
        wall = time.time() - t0
        s, raw = api_get(f"/jobs/{jid}", T)
        sa, est = api_get(f"/jobs/{jid}/artifacts/runtime_estimates", T)
        json.dump({"job": i, "label": lab, "record": raw, "runtime_estimates_artifact": {"status": sa, "answer": est}}, open(f"{priv}/mock_job_{i:02d}.json", "w"), indent=1)
        comp = raw.get("compilation") or {}; met = raw.get("metrics") or {}
        row = {"job": i, "label": lab, "circuits": len(cs), "shots": sh, "status": raw.get("status"),
               "execution_runtime_estimate_seconds": comp.get("execution_runtime_estimate_seconds"),
               "metrics": met, "errors": [e.get("message") for e in raw.get("errors", [])], "messages": [m.get("message") for m in raw.get("messages", [])],
               "runtime_estimates_artifact_status": sa, "client_wall_seconds": round(wall, 2), "cz_total": sum(meta[n]["cz"] for n in cs), "qubits_max": max(meta[n]["qubits"] for n in cs)}
        rows.append(row); print(scrub(json.dumps(row), T), flush=True)
        json.dump({"read_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "backend": QC_ALIAS, "rows": rows}, open(f"{out}/mock/jobs.json", "w"), indent=1)

if __name__ == "__main__": main()

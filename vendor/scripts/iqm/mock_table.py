"""Copies IQM's runtime estimate for each emerald:mock job (runtime_estimates artifact and compilation record, kept with ids
in private/) into mock/runtime_estimates.json without job or calibration ids. Usage: python3 -I mock_table.py <evidence dir>"""
import json, os, sys
out = sys.argv[1]; jobs = json.load(open(f"{out}/mock/jobs.json")); plan = json.load(open(f"{out}/mock/plan.json"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock_run import iqm_sets, a1_name
a1, a2n = iqm_sets()
REQ = {a1_name(r, k) for r in a1 for k in ("cold", "warm")} | set(a2n) | {"qcup-f-chem-h2-n4", "qcup-e-labs8-p1", "qcup-q7-B12-warmT-p1"}   # H2, LABS N=8 p1 and Q7 B12 warm p1 are IQM rows
names = {j["job"]: j["circuit_names"] for j in plan["jobs"]}
rows = []
for r in jobs["rows"]:
    d = json.load(open(f"{out}/private/mock_job_{r['job']:02d}.json")); a = d["runtime_estimates_artifact"]["answer"]; rec = d["record"]
    q, s = a["qpu_execution"], a["sweep_execution"]
    rows.append({"job": r["job"], "label": r["label"], "circuits": r["circuits"], "shots": r["shots"], "status": rec["status"],
                 "qpu_execution_s": q, "sweep_execution_s": s, "execution_runtime_estimate_seconds": rec["compilation"]["execution_runtime_estimate_seconds"],
                 "overhead_s": round(s - q, 4), "qpu_us_per_circuit_shot": round(1e6 * q / (r["circuits"] * r["shots"]), 1), "playlist_repeats": a["playlist_repeats"],
                 "mock_billed_seconds": rec["metrics"].get("billed_seconds"), "mock_runtime_seconds": rec["metrics"].get("runtime_seconds"),
                 "cz_total_after_iqm_transpile": r["cz_total"], "in_iqm_request": all(n in REQ for n in names[r["job"]]), "qubits_max": r["qubits_max"], "errors": r["errors"]})
json.dump({"backend": "emerald:mock (IQM Resonance), priced 0.00 per second when read before each job", "read_at": jobs["read_at"],
           "fields": "qpu_execution_s and sweep_execution_s from GET /api/v1/jobs/{id}/artifacts/runtime_estimates; execution_runtime_estimate_seconds and mock metrics from GET /api/v1/jobs/{id}",
           "rows": rows}, open(f"{out}/mock/runtime_estimates.json", "w"), indent=1)
print(len(rows), "rows")

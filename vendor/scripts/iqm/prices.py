"""Free reads from IQM Resonance: the quantum computers this account sees, their limits and their pay-as-you-go price
per second. Nothing is submitted. Raw answers go to private/ (they carry device ids); a summary without ids goes to the
evidence folder. Usage: python -I prices.py <evidence dir>"""
import json, os, sys, datetime, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from _tok import token, scrub
out = sys.argv[1]; priv = os.path.join(out, "private"); os.makedirs(priv, exist_ok=True)
T = token(); H = {"Authorization": "Bearer " + T, "Accept": "application/json", "User-Agent": "qcup-reader/1"}
BASE = "https://resonance.iqm.tech/api/v1"
def get(p):
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + p, headers=H), timeout=60); return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, {"error": scrub(e.read()[:600].decode("utf-8", "replace"), T)}
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
s, lst = get("/quantum-computers"); raw = {"read_at": now, "list": {"status": s, "answer": lst}, "details": {}}
summary = {"read_at": now, "source": "GET https://resonance.iqm.tech/api/v1/quantum-computers/{alias}", "computers": []}
for qc in lst.get("quantum_computers", []):
    a = qc["alias"]; s2, d = get("/quantum-computers/" + a); raw["details"][a] = {"status": s2, "answer": d}
    if s2 == 200:
        summary["computers"].append({"alias": a, "display_name": d.get("display_name"), "backend_type": d.get("backend_type"), "number_of_qubits": d.get("number_of_qubits"),
            "operational_status": d.get("operational_status"), "pricing": d.get("pricing"), "limits": d.get("limits"), "mock_url": (d.get("additional_info") or {}).get("mock_url")})
open(os.path.join(priv, "prices_raw.json"), "w").write(scrub(json.dumps(raw, indent=1), T))
open(os.path.join(out, "prices.json"), "w").write(scrub(json.dumps(summary, indent=1), T))
for c in summary["computers"]: print(c["alias"], c["backend_type"], c["number_of_qubits"], c["pricing"], c["operational_status"])

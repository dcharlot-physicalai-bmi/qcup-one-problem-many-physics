"""Free calibration reads from IBM Quantum Platform: each backend's properties and configuration, now. Nothing is
submitted. The API key comes from the environment variable IBM_API_KEY and is never printed; the instance CRN from
IBM_INSTANCE_CRN. Usage: python3 -E ibm_reads.py OUT_DIR backend..."""
import json, os, subprocess, sys, urllib.parse, urllib.request, urllib.error
out = sys.argv[1]; names = sys.argv[2:]; os.makedirs(out, exist_ok=True)
crn = os.environ["IBM_INSTANCE_CRN"]
BASE = "https://quantum.cloud.ibm.com/api/v1"; UA = {"User-Agent": "qcup-calibration-reader/1"}
key = os.environ["IBM_API_KEY"].strip()
body = urllib.parse.urlencode({"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": key}).encode(); del key
req = urllib.request.Request("https://iam.cloud.ibm.com/identity/token", data=body, headers={**UA, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
token = json.load(urllib.request.urlopen(req, timeout=30))["access_token"]
H = {**UA, "Authorization": f"Bearer {token}", "Service-CRN": crn, "IBM-API-Version": "2026-04-15", "Accept": "application/json"}
def get(path):
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + path, headers=H), timeout=90); return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, {"error": e.read()[:500].decode("utf-8", "replace")}
for b in names:
    for what in ("properties", "configuration"):
        s, v = get(f"/backends/{b}/{what}"); json.dump(v, open(os.path.join(out, f"{b}-{what}.json"), "w"))
        print(b, what, s, v.get("last_update_date") if isinstance(v, dict) else None, len(json.dumps(v)))

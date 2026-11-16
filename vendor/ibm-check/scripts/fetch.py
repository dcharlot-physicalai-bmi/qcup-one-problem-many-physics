#!/usr/bin/env python3
"""Read the state, results and usage of the submitted jobs (free reads). Saves redacted copies under run/raw/.
Usage: python3 -I fetch.py BASE            (one pass; prints each job's status)"""
import json, os, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
BASE = os.path.abspath(sys.argv[1]); API = "https://quantum.cloud.ibm.com/api/v1"; UA = {"User-Agent": "qcup-hw-client/1"}
reg = json.load(open(os.path.expanduser("~/.config/wai/quantum-providers.json")))
crn = next(p["settings"]["crn"] for p in reg["providers"] if p["name"] == "ibm-kingston")
key = subprocess.run(["security", "find-generic-password", "-s", "wai-ibm-api-key", "-w"], capture_output=True, text=True, check=True).stdout.strip()
body = urllib.parse.urlencode({"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": key}).encode(); del key
tok = json.load(urllib.request.urlopen(urllib.request.Request("https://iam.cloud.ibm.com/identity/token", data=body, headers={**UA, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}), timeout=30))["access_token"]
H = {**UA, "Authorization": f"Bearer {tok}", "Service-CRN": crn, "IBM-API-Version": "2026-04-15", "Accept": "application/json"}


def redact(text):
    text = text.replace(crn, "<instance-crn>"); text = re.sub(r"crn:v1:[^\"\s]*", "<crn>", text); text = re.sub(r"a/[0-9a-f]{32}", "a/<account>", text)
    return re.sub(r"\"(account_id|accountId|user_id|userId|iam_id|email|instance|instance_id)\"\s*:\s*\"[^\"]*\"", r'"\1": "<redacted>"', text)


def get(path):
    try:
        r = urllib.request.urlopen(urllib.request.Request(API + path, headers=H), timeout=120); return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:4000].decode("utf-8", "replace")


raw = os.path.join(BASE, "run", "raw"); os.makedirs(raw, exist_ok=True)
stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
for arm in ("dd_off", "dd_on"):
    p = os.path.join(BASE, "run", f"job-{arm}.json")
    if not os.path.exists(p): continue
    jid = json.load(open(p))["job"]
    st, t = get(f"/jobs/{jid}?exclude_params=true"); open(os.path.join(raw, f"job-{arm}-{stamp}.json"), "w").write(redact(t))
    j = json.loads(t) if st == 200 else {}
    status = j.get("status") or j.get("state", {}).get("status")
    print(arm, jid, "HTTP", st, "status", status, "estimate", j.get("estimated_running_time_seconds"), "usage", j.get("usage"), flush=True)
    if status in ("Completed", "Done", "COMPLETED"):
        out = os.path.join(raw, f"results-{arm}.json")
        if not os.path.exists(out):
            st, t = get(f"/jobs/{jid}/results"); open(out, "w").write(redact(t)); print(arm, "results HTTP", st, len(t), "bytes")
        st, t = get(f"/jobs/{jid}/metrics"); open(os.path.join(raw, f"metrics-{arm}.json"), "w").write(redact(t)); print(arm, "metrics", redact(t)[:400])
st, t = get("/instances/usage"); open(os.path.join(raw, f"usage-{stamp}.json"), "w").write(redact(t)); print("usage", redact(t)[:300])

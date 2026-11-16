"""Free reads from IBM Quantum Platform for the QCUP hardware check. Nothing is submitted.
The API key comes from the keychain item wai-ibm-api-key and is never printed; the instance CRN comes from the
WAI provider registry. CRNs and account ids are redacted from every file written outside private/.
Usage: python3 -I ibm_read.py OUT_DIR usage | backends | status B... | calibration B... | job ID | metrics ID"""
import json, os, re, subprocess, sys, time, urllib.parse, urllib.request, urllib.error

out, what, args = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(out, exist_ok=True)
BASE = "https://quantum.cloud.ibm.com/api/v1"
UA = {"User-Agent": "qcup-hw-reader/1"}
reg = json.load(open(os.path.expanduser("~/.config/wai/quantum-providers.json")))
crn = next(p["settings"]["crn"] for p in reg["providers"] if p["name"] == "ibm-kingston")
key = subprocess.run(["security", "find-generic-password", "-s", "wai-ibm-api-key", "-w"], capture_output=True, text=True, check=True).stdout.strip()
body = urllib.parse.urlencode({"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": key}).encode()
del key
try:
    token = json.load(urllib.request.urlopen(urllib.request.Request("https://iam.cloud.ibm.com/identity/token", data=body,
        headers={**UA, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}), timeout=30))["access_token"]
except urllib.error.HTTPError as e:
    sys.exit(f"IAM token: HTTP {e.code}")
del body
H = {**UA, "Authorization": f"Bearer {token}", "Service-CRN": crn, "IBM-API-Version": "2026-04-15", "Accept": "application/json"}


def redact(text):
    text = text.replace(crn, "<instance-crn>")
    text = re.sub(r"crn:v1:[^\"\s]*", "<crn>", text)
    text = re.sub(r"a/[0-9a-f]{32}", "a/<account>", text)
    text = re.sub(r"\"(account_id|accountId|user_id|userId|iam_id|email|instance|instance_id)\"\s*:\s*\"[^\"]*\"", r'"\1": "<redacted>"', text)
    return text


def get(path):
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + path, headers=H), timeout=90)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:2000].decode("utf-8", "replace")


stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def save(name, st, text):
    p = os.path.join(out, f"{name}-{stamp}.json")
    open(p, "w").write(redact(text))
    print(f"{name}: HTTP {st}, {len(text)} bytes -> {p}")
    return p


if what == "usage":
    st, t = get("/instances/usage"); save("usage", st, t); print(redact(t))
elif what == "backends":
    st, t = get("/backends"); save("backends", st, t)
    try:
        d = json.loads(t)
        for b in d.get("devices", d if isinstance(d, list) else []):
            print(b if isinstance(b, str) else {k: b.get(k) for k in ("name", "status", "queue_length", "qubits", "processor_type")})
    except Exception as e:
        print(redact(t)[:3000])
elif what == "status":
    for b in args:
        st, t = get(f"/backends/{b}/status"); save(f"{b}-status", st, t); print(b, redact(t))
elif what == "calibration":
    for b in args:
        st, t = get(f"/backends/{b}/configuration"); save(f"{b}-configuration", st, t)
        st, t = get(f"/backends/{b}/properties"); save(f"{b}-properties", st, t)
        print(b, "last_update_date", json.loads(t).get("last_update_date"))
elif what == "job":
    st, t = get(f"/jobs/{args[0]}?exclude_params=true"); save(f"job-{args[0]}", st, t); print(redact(t)[:3000])
elif what == "metrics":
    st, t = get(f"/jobs/{args[0]}/metrics"); save(f"metrics-{args[0]}", st, t); print(redact(t)[:3000])
else:
    sys.exit("unknown read")

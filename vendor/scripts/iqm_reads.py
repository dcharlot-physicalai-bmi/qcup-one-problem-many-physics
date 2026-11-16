"""Free reads from IQM Resonance: does the API state that mock or emulator backends cost nothing on this account's plan?
The token comes from the environment variable IQM_TOKEN and is never printed. Nothing is submitted."""
import json, os, subprocess, sys, urllib.request, urllib.error
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
tok = os.environ.get("IQM_TOKEN", "").strip()
if len(tok) < 10: sys.exit("no IQM token")
H = {"Authorization": "Bearer " + tok, "Accept": "application/json", "User-Agent": "qcup-reader/1"}; del tok
BASE = "https://resonance.iqm.tech/api/v1"
def get(p):
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + p, headers=H), timeout=60); t = r.read()
        try: return r.status, json.loads(t)
        except ValueError: return r.status, {"text": t[:2000].decode("utf-8", "replace")}
    except urllib.error.HTTPError as e: return e.code, {"error": e.read()[:600].decode("utf-8", "replace")}
for name, p in (("quantum-computers", "/quantum-computers"), ("garnet-mock", "/quantum-computers/garnet:mock"), ("user", "/users/me"), ("account", "/account"), ("organizations", "/organizations"), ("pricing", "/pricing"), ("credits", "/credits")):
    s, v = get(p); json.dump({"status": s, "answer": v}, open(os.path.join(out, name + ".json"), "w"), indent=1)
    txt = json.dumps(v); print(name, s, len(txt), [w for w in ("price", "cost", "credit", "free", "charge", "billing", "mock", "emulat") if w in txt.lower()])

"""Fetch the v2 result artifacts (classical registers by name) of the checker's probe jobs. Reads only."""
import json, os, sys
sys.path.insert(0, os.path.expanduser("~/wai-ci-tools/qcup-emulators/scripts"))
from ionq_api import call, save
R = os.environ["RAW"]
for name in sys.argv[1:]:
    j = json.load(open(f"{R}/{name}-job.json"))["answer"]
    for fmt in ("ionq.result.histogram.json.v2", "ionq.result.probabilities.json.v2"):
        art = (j.get("results") or {}).get(fmt)
        if not art: continue
        s, a = call("GET", f"/jobs/{j['id']}/artifacts/{art['id']}")
        save(f"{name}-{fmt}", s, a)
        print(name, fmt, s, json.dumps(a)[:900])

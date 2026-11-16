"""Fetch the compiled-circuit artifacts IonQ produced for the checker's probe jobs (a read; no job is created)."""
import json, os, sys
sys.path.insert(0, os.path.expanduser("~/wai-ci-tools/qcup-emulators/scripts"))
from ionq_api import call, save
R = os.environ["RAW"]
for name in sys.argv[1:]:
    j = json.load(open(f"{R}/{name}-job.json"))["answer"]
    for fmt, art in ((j.get("output") or {}).get("compilation") or {}).get("compiled_circuits", {}).items():
        s, a = call("GET", f"/jobs/{j['id']}/artifacts/{art['id']}")
        save(f"{name}-compiled-{fmt}", s, a)
        print(name, fmt, s, (a.get("text") if isinstance(a, dict) and "text" in a else json.dumps(a))[:6000])

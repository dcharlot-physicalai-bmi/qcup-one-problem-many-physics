"""Run the Selene jobs of the 2025 rerun, at most N at a time, resumable (a job whose output exists is skipped).

    python -I run_queue.py ROOT N_PARALLEL      (ROOT holds builder/, params/, plugin-target/, scripts/)

The cap can be changed while the queue runs by writing a number to ROOT/NPAR; a file ROOT/STOP stops new jobs from
starting (running ones finish). QUEUE_PHASES (default 1,2,3,4) picks the phases to run.

Order (the actinide circuits last, as the plan says):
  1. every circuit up to 20 qubits (the 80 non-actinide core circuits) and the 44 Quantinuum Aim 2 programs of the
     extension tier, for the fit: the ideal control, then, on each of H2-1E 2025-07-16, H2-2E 2025-07-16 and Helios-1E
     2025-11-18, the docs variant and the docs_dephasing variant, 200 shots each;
  2. the 4 actinide circuits (26 qubits first, then 24) under the docs variant on the three sets, 100 shots in four
     25-shot chunks;
  3. the actinide ideal controls, 10 shots in two 5-shot chunks;
  4. the actinide circuits under the docs_dephasing variant on the three sets, 100 shots in four chunks.
Every program has the device's documented minimum gate angles applied (gen_guppy.py, min_angles)."""
import hashlib, json, os, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
ROOT, NPAR = sys.argv[1], int(sys.argv[2])
ids = json.load(open(f"{ROOT}/params/core84_ids.json"))
EXT = json.load(open(f"{ROOT}/params/ext_aim2_ids.json"))
IDX = json.load(open(f"{ROOT}/builder/index.json"))["circuits"]
SETS = ("H2-1E_2025-07-16", "H2-2E_2025-07-16", "Helios-1E_2025-11-18")
PJ = {s: json.load(open(f"{ROOT}/params/{s}.json")) for s in SETS}
VARIANT_PARAMS = {"docs": "plugin_docs", "docs_dephasing": "plugin_docs_dephasing"}
LIB = f"{ROOT}/plugin-target/release/libqcup_docs_noise_plugin.dylib"
OUT = f"{ROOT}/runs"
for d in (OUT, f"{ROOT}/work", f"{ROOT}/jobs"): os.makedirs(d, exist_ok=True)
ACT = sorted([c for c in ids if IDX[c]["qubits"] >= 24], key=lambda c: -IDX[c]["qubits"])
SMALL = [c for c in ids if c not in ACT]
PHASES = {int(x) for x in os.environ.get("QUEUE_PHASES", "1,2,3,4").split(",")}


def seed_of(*parts):
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


jobs = []
def add(phase, cid, s, variant, shots, chunk=None, chunks=1):
    if phase not in PHASES: return
    tag = f"{cid}__{s}__{variant}" + (f"__c{chunk}" if chunk is not None else "")
    per = shots // chunks
    params = PJ[s][VARIANT_PARAMS[variant]] if variant in VARIANT_PARAMS else {}
    jobs.append({"id": cid, "gates": f"{ROOT}/builder/gates/{cid}.json", "set": s, "variant": variant, "shots": per,
                 "shot_offset": (chunk or 0) * per, "seed": seed_of(cid, s, variant, chunk), "out": f"{OUT}/{tag}.json",
                 "params": params, "plugin_lib": LIB, "work_dir": f"{ROOT}/work", "tag": tag, "min_angles": True})


for cid in SMALL + EXT:
    add(1, cid, "none", "ideal", 200)
    for s in SETS:
        for v in ("docs", "docs_dephasing"):
            add(1, cid, s, v, 200)
for cid in ACT:
    for s in SETS:
        for k in range(4): add(2, cid, s, "docs", 100, k, 4)
for cid in ACT:
    for k in range(2): add(3, cid, "none", "ideal", 10, k, 2)
for cid in ACT:
    for s in SETS:
        for k in range(4): add(4, cid, s, "docs_dephasing", 100, k, 4)

GATE = threading.Lock()
EXCLUDE = set(open(os.environ["QUEUE_EXCLUDE"]).read().split()) if os.environ.get("QUEUE_EXCLUDE") else set()


def cap():
    try: return int(open(f"{ROOT}/NPAR").read().strip())
    except (OSError, ValueError): return NPAR


def running():
    """run_job.py processes of this ROOT now running, this driver's or an earlier one's: the cap holds across both."""
    r = subprocess.run(["pgrep", "-f", f"{ROOT}/scripts/run_job.py"], capture_output=True, text=True)
    return len(r.stdout.split())


def run(j):
    if os.path.exists(j["out"]) or j["tag"] in EXCLUDE: return j["tag"], "skip", 0
    jp = f"{ROOT}/jobs/{j['tag']}.json"; json.dump(j, open(jp, "w"))
    with GATE:
        while running() >= cap():
            time.sleep(15)
        if os.path.exists(f"{ROOT}/STOP"): return j["tag"], "stopped", 0
        t = time.time()
        p = subprocess.Popen([sys.executable, "-I", f"{ROOT}/scripts/run_job.py", jp], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(1)
    out, _ = p.communicate()
    with open(f"{ROOT}/jobs/{j['tag']}.log", "w") as f: f.write(out)
    return j["tag"], "ok" if p.returncode == 0 else "FAIL %d" % p.returncode, time.time() - t


print("jobs", len(jobs), "phases", sorted(PHASES), flush=True)
with ThreadPoolExecutor(32) as ex:
    for fu in as_completed([ex.submit(run, j) for j in jobs]):
        tag, st, dt = fu.result()
        print(time.strftime("%H:%M:%S"), st, tag, "%.0f s" % dt, flush=True)
print("QUEUE DONE", flush=True)

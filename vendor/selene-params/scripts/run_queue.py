"""Run the Selene jobs for the 84 Quantinuum core circuits, at most N at a time, resumable (a job whose output exists
is skipped). Order: every circuit up to 20 qubits, and the 44 Aim 2 programs of the extension tier for the fit (ideal control, Selene's depolarizing model and the published-noise
plugin, on both parameter sets), then the actinide circuits (26 qubits first, then 24) under the plugin on both sets in 25-shot chunks
(see the note at the actinide jobs for their shot counts).

    python queue.py ROOT N_PARALLEL            (ROOT holds builder-circuits/, params/, plugin-target/, scripts/)"""
import hashlib, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
ROOT, NPAR = sys.argv[1], int(sys.argv[2])
ids = json.load(open(f"{ROOT}/params/core84_ids.json"))
IDX = json.load(open(f"{ROOT}/builder-circuits/index.json"))["circuits"]
SETS = {s: json.load(open(f"{ROOT}/params/{s}.json"))["selene"] for s in ("H2-1_2024-05-20", "H2-2_2024-12-06")}
LIB = f"{ROOT}/plugin-target/release/libqcup_published_noise_plugin.dylib"
OUT = f"{ROOT}/runs"; os.makedirs(OUT, exist_ok=True); os.makedirs(f"{ROOT}/work", exist_ok=True); os.makedirs(f"{ROOT}/jobs", exist_ok=True)
ACT = [c for c in ids if IDX[c]["qubits"] >= 24]
SMALL = [c for c in ids if c not in ACT]
# the 44 Quantinuum Aim 2 programs of the extension tier (to 1,995 two-qubit gates), run for the 30% fit only: with them
# the programs span the line instead of stopping at 297 gates
EXT = json.load(open(f"{ROOT}/params/ext_aim2_ids.json"))


def seed_of(*parts):
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


jobs = []
def add(cid, s, variant, shots, chunk=None, chunks=1):
    tag = f"{cid}__{s}__{variant}" + (f"__c{chunk}" if chunk is not None else "")
    per = shots // chunks
    jobs.append({"id": cid, "gates": f"{ROOT}/builder-circuits/gates/{cid}.json", "set": s, "variant": variant, "shots": per,
                 "shot_offset": (chunk or 0) * per, "seed": seed_of(cid, s, variant, chunk), "out": f"{OUT}/{tag}.json",
                 "params": SETS.get(s, {}), "plugin_lib": LIB, "work_dir": f"{ROOT}/work", "tag": tag})

for cid in SMALL + EXT:
    add(cid, "none", "ideal", 200)
    for s in SETS:
        for v in ("published", "depolarizing"):
            add(cid, s, v, 200)
# Actinides under the plugin, in 25-shot chunks. A 26-qubit shot takes about 245 s with eight jobs at once, so the
# 26-qubit circuits run 200 shots on H2-1's parameters and 100 (the request's count) on H2-2's; the 24-qubit circuits
# run 100, except UO22p_stretched on H2-1, whose 200 were under way when the plan was cut (16:40, 16 November) to finish
# that evening. Selene's depolarizing model is not run on the actinides (time).
for cid in sorted(ACT, key=lambda c: -IDX[c]["qubits"]):
    for s in SETS:
        if IDX[cid]["qubits"] < 26: continue
        n = 8 if s == "H2-1_2024-05-20" else 4
        for k in range(n): add(cid, s, "published", 25 * n, k, n)
for cid in sorted(ACT, key=lambda c: -IDX[c]["qubits"]):
    for s in SETS:
        if IDX[cid]["qubits"] >= 26: continue
        n = 8 if (cid, s) == ("qcup-f-tgt-uo22p-stretched", "H2-1_2024-05-20") else 4
        for k in range(n): add(cid, s, "published", 25 * n, k, n)


import threading
GATE = threading.Lock()
EXCLUDE = set(open(os.environ["QUEUE_EXCLUDE"]).read().split()) if os.environ.get("QUEUE_EXCLUDE") else set()


def running():
    """run_job.py processes of this ROOT now running, this driver's or an earlier one's: the cap holds across both."""
    r = subprocess.run(["pgrep", "-f", f"{ROOT}/scripts/run_job.py"], capture_output=True, text=True)
    return len(r.stdout.split())


def run(j):
    if os.path.exists(j["out"]) or j["tag"] in EXCLUDE: return j["tag"], "skip", 0
    jp = f"{ROOT}/jobs/{j['tag']}.json"; json.dump(j, open(jp, "w"))
    with GATE:
        while running() >= NPAR: time.sleep(15)
        t = time.time()
        p = subprocess.Popen([sys.executable, f"{ROOT}/scripts/run_job.py", jp], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(1)
    out, _ = p.communicate()
    with open(f"{ROOT}/jobs/{j['tag']}.log", "w") as f: f.write(out)
    return j["tag"], "ok" if p.returncode == 0 else "FAIL %d" % p.returncode, time.time() - t


print("jobs", len(jobs), flush=True)
from concurrent.futures import as_completed
with ThreadPoolExecutor(NPAR) as ex:
    for fu in as_completed([ex.submit(run, j) for j in jobs]):
        tag, st, dt = fu.result()
        print(time.strftime("%H:%M:%S"), st, tag, "%.0f s" % dt, flush=True)
print("QUEUE DONE", flush=True)

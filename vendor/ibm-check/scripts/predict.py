#!/usr/bin/env python3
"""QCUP hardware check, predictions. Runs on the build host in the pinned venv, after design.py.

Models (each applied to the circuit that will be submitted, on the layout that will be submitted):
  generic     the application's generic superconducting-like model, aim2.noise("sc_like"): depolarising 3e-3 per CZ,
              3e-4 per sx/x, 1e-2 per reset, 1e-2 readout. Layout-blind. Not a device calibration.
  cal_idle    the device's design-time calibration (IBM properties read at design time), as qiskit-aer builds it from a
              backend: each gate's stated error as depolarising beside the thermal relaxation its duration gives, readout
              assignment error, and thermal relaxation (T1, T2) on idle time. Idle time comes from scheduling the circuit
              ALAP with the device's durations and padding the gaps with delays.
  cal_noidle  the same calibration with the circuit left unscheduled, so idle qubits do not relax. This is the
              idle-suppressed variant. Static ZZ, leakage, crosstalk and drift are in neither calibration model.
Scores: Aim 2 programs and the 0-CZ control, trace fidelity exactly as aim2.trace_prob; the mirror control, the probability
of its known string; Aim 1, the probability of an optimal assignment (the package's ground set).

Usage: predict.py OUT CAL BACKEND MODEL IDS_COMMA_SEPARATED RESULT_JSON
       predict.py verify OUT CAL BACKEND ARM   (noiseless replay of the exported OpenQASM 3 of one arm)"""
import glob, json, math, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = sys.argv[1] == "verify"
args = sys.argv[2:] if VERIFY else sys.argv[1:]
OUT, CAL, B = os.path.abspath(args[0]), os.path.abspath(args[1]), args[2]
sys.argv = [sys.argv[0], OUT, CAL]                      # design.py reads its paths from argv at import
sys.path.insert(0, HERE)
import design as D
from aim2 import noise as generic_noise, trace_prob
from qiskit import qpy, qasm3
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime.fake_provider.fake_backend import FakeBackendV2

design = json.load(open(f"{OUT}/design.json")); C = design["circuits"]; IDX = {c["id"]: i for i, c in enumerate(C)}
THREADS = int(os.environ.get("AER_THREADS", "4"))


def score(meta, counts):
    tot = sum(counts.values())
    if meta["kind"] in ("aim2", "control_zero_cz"):
        return trace_prob(counts, meta["reference_trace"], meta["state_bits"])
    if meta["kind"] == "control_mirror":
        return counts.get(meta["want"], 0) / tot
    g = set(meta["ground_states"])
    return sum(v for k, v in counts.items() if int(k.replace(" ", ""), 2) in g) / tot


def snapshot_backend(b):
    conf = os.path.basename(glob.glob(f"{CAL}/{b}-configuration-*.json")[0]); props = os.path.basename(glob.glob(f"{CAL}/{b}-properties-*.json")[0])
    class Snap(FakeBackendV2):
        dirname = CAL; conf_filename = conf; props_filename = props; backend_name = f"{b}_design_snapshot"
    return Snap()


def pred_shots(meta):
    if os.environ.get("PRED_SHOTS"): return int(os.environ["PRED_SHOTS"])
    if meta["kind"] != "aim1": return 20000
    return {12: 8000, 16: 4000, 20: 1500}[meta["qubits"]]


if VERIFY:
    arm = args[3]; full, lt, _, _ = D.load_target(B); bad = []
    for meta in C:
        qc = qasm3.loads(open(f"{OUT}/{B}/qasm_{arm}/{meta['id']}.qasm").read())
        shots = 4000 if meta["kind"] == "aim1" else 200
        counts = AerSimulator(method="statevector", max_parallel_threads=THREADS).run(qc, shots=shots, seed_simulator=3).result().get_counts()
        s = score(meta, counts)
        ok = abs(s - meta["ideal_p_gs"]) < 4 * math.sqrt(meta["ideal_p_gs"] * (1 - meta["ideal_p_gs"]) / shots) + 1e-9 if meta["kind"] == "aim1" else s == 1.0
        if not ok: bad.append(meta["id"])
        print(B, arm, meta["id"], "noiseless score", round(s, 4), "ideal", round(meta.get("ideal_p_gs", 1.0), 4), "OK" if ok else "MISMATCH", flush=True)
    print("VERIFY", B, arm, "all ok" if not bad else f"MISMATCH {bad}")
    sys.exit(1 if bad else 0)

MODEL, IDS, RES = args[3], args[4].split(","), args[5]
full, lt, _, _ = D.load_target(B)
with open(f"{OUT}/{B}/isa_dd_off.qpy", "rb") as f: isas = qpy.load(f)
if MODEL == "generic":
    nm, _ = generic_noise("sc_like")
elif MODEL in ("cal_idle", "cal_noidle"):
    nm = NoiseModel.from_backend(snapshot_backend(B), thermal_relaxation=True, gate_error=True, readout_error=True)
else:
    raise SystemExit("unknown model")
BRANCH = os.environ.get("AER_BRANCH", "0") == "1"         # shot branching: same distribution, fewer state copies
sim = AerSimulator(noise_model=nm, method="statevector", max_parallel_threads=THREADS, shot_branching_enable=BRANCH, shot_branching_sampling_enable=BRANCH)
out = {}
for cid in IDS:
    meta = C[IDX[cid]]; isa = isas[IDX[cid]]
    circ = isa
    if MODEL == "cal_idle":
        act = set(design["backends"][B]["layouts"][cid]); circ = D.active_only(D.scheduled(isa, full, False), act)
    shots = pred_shots(meta); t0 = time.time()
    counts = sim.run(circ, shots=shots, seed_simulator=11).result().get_counts()
    s = score(meta, counts)
    out[cid] = {"score": s, "shots": shots, "se": math.sqrt(max(s * (1 - s), 1.0 / shots) / shots), "seconds": round(time.time() - t0, 1)}
    print(B, MODEL, cid, out[cid], flush=True)
    json.dump({"backend": B, "model": MODEL, "results": out}, open(RES, "w"), indent=1)

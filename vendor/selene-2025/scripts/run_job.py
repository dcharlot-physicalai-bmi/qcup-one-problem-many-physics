"""One Selene job: a request circuit under one parameter set and one noise variant, a range of shots.

    python -I run_job.py JOB_JSON     (a dict: id, gates, set, variant, shots, shot_offset, seed, out, params, plugin_lib,
                                       min_angles, work_dir)

The circuit is the package builder's gate list (gen_guppy.py turns it into a Guppy program, with the device's documented
minimum gate angles when min_angles is true), compiled by Guppy at its Classical level (every gate as written: no merging
or cancelling), built by Selene, and run on Selene's QuEST state vector under Selene's soft-RZ runtime (rz is a frame
change, as on the device; only the rzz duration is set, to one clock unit, so the clock counts layers of two-qubit gates;
operations of a type are batched as soon as their qubits are free).

Variants:
  docs            the docs-noise plugin (plugin/rust/lib.rs) with every documented term it can hold; no memory term.
  docs_dephasing  the same plus the dephasing term at an assumed duration per layer (params: memory_pz).
  depolarizing    Selene's own DepolarizingErrorModel (controls only): p_1q = p1, p_2q = p2, p_meas = (p_meas_0 + p_meas_1) / 2.
  ideal           Selene's IdealErrorModel (positive control).
Writes OUT: every shot's classical bits (bit n-1 first) and the error model's per-shot metrics."""
import importlib.util, json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "plugin", "python"))
from gen_guppy import guppy_text, bits_of_shot

job = json.load(open(sys.argv[1]))
import selene_sim
from selene_sim import DepolarizingErrorModel, IdealErrorModel, Quest, SoftRZRuntime
from selene_sim.event_hooks import EventHook
from guppylang import OptimizationLevel


class Metrics(EventHook):
    """Every metric the error model and the user program report, per shot."""
    def __init__(self):
        self.shots = []; self.cur = None
    def get_selene_flags(self):
        return ["provide_metrics"]
    def try_invoke(self, tag, data):
        if not tag.startswith("METRICS:"): return False
        parts = tag.split(":")
        if len(parts) >= 4 and parts[-2] in ("error_model", "user_program"):
            if self.cur is None: self.cur = {}; self.shots.append(self.cur)
            self.cur[parts[-2][0] + ":" + parts[-1]] = data[0]
        return True
    def on_new_shot(self):
        self.cur = None


g = json.load(open(job["gates"]))
n, nc = g["qubits"], g["clbits"]
text, stats = guppy_text(g["gates"], n, nc, min_angles=bool(job.get("min_angles")))
work = tempfile.mkdtemp(prefix="sj-", dir=job.get("work_dir") or None)
src = os.path.join(work, "program.py"); open(src, "w").write(text)
t0 = time.time()
spec = importlib.util.spec_from_file_location("prog_" + job["id"].replace("-", "_"), src); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
pkg = mod.main.with_opt_level(OptimizationLevel.Classical).compile(); t1 = time.time()
inst = selene_sim.build(pkg, build_dir=os.path.join(work, "build")); t2 = time.time()

P = job.get("params") or {}
v = job["variant"]
if v == "ideal":
    em = IdealErrorModel()
elif v == "depolarizing":
    em = DepolarizingErrorModel(p_1q=P["p1"], p_2q=P["p2"], p_meas=(P["p_meas_0"] + P["p_meas_1"]) / 2, p_init=0.0)
elif v in ("docs", "docs_dephasing", "control"):
    from qcup_docs_noise import DocsNoise
    em = DocsNoise(library=job["plugin_lib"], **P)
else:
    raise SystemExit("unknown variant " + v)
rt = SoftRZRuntime(duration_ns_rzz=1, max_batch_size=1_000_000)
hook = Metrics()
rows = []
t3 = time.time()
for shot in inst.run_shots(Quest(), n_qubits=n, n_shots=job["shots"], random_seed=job["seed"], shot_offset=job.get("shot_offset", 0),
                           error_model=em, runtime=rt, event_hook=hook):
    bits, _ = bits_of_shot(list(shot), nc); rows.append(bits)
t4 = time.time()
out = {"id": job["id"], "set": job.get("set"), "variant": v, "shots": len(rows), "shot_offset": job.get("shot_offset", 0), "seed": job["seed"],
       "params": P, "min_angles": bool(job.get("min_angles")), "error_model": {"class": type(em).__name__, "init_args": em.get_init_args()},
       "runtime": {"class": "SoftRZRuntime", "init_args": rt.get_init_args()}, "simulator": "Quest (state vector)", "guppy_optimization": "Classical",
       "program_stats": stats, "qubits": n, "clbits": nc, "bits": rows, "metrics": hook.shots,
       "seconds": {"compile": round(t1 - t0, 2), "build": round(t2 - t1, 2), "run": round(t4 - t3, 2)}}
tmp = job["out"] + ".tmp"; json.dump(out, open(tmp, "w")); os.replace(tmp, job["out"])
import shutil; shutil.rmtree(work, ignore_errors=True)
print(job["id"], job.get("set"), v, "shots", len(rows), "run %.1f s" % (t4 - t3), flush=True)

"""Timing probe: one circuit, a few shots, ideal and Selene depolarizing, soft-RZ runtime. Prints seconds per shot.
    python timing_probe.py GATES_JSON SHOTS"""
import json, os, sys, time, tempfile, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_guppy import guppy_text
import selene_sim
from selene_sim import DepolarizingErrorModel, IdealErrorModel, Quest, SoftRZRuntime
from guppylang import OptimizationLevel

g = json.load(open(sys.argv[1])); shots = int(sys.argv[2])
txt, st = guppy_text(g["gates"], g["qubits"], g["clbits"]); print(st, flush=True)
work = tempfile.mkdtemp(prefix="probe-", dir=os.environ.get("PROBE_DIR", "."))
src = os.path.join(work, "program.py"); open(src, "w").write(txt)
t0 = time.time()
spec = importlib.util.spec_from_file_location("prog", src); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
pkg = mod.main.with_opt_level(OptimizationLevel.Classical).compile(); t1 = time.time()
inst = selene_sim.build(pkg, build_dir=os.path.join(work, "build")); t2 = time.time()
print("compile %.1f s, build %.1f s" % (t1 - t0, t2 - t1), flush=True)
for name, em in (("ideal", IdealErrorModel()), ("depolarizing", DepolarizingErrorModel(p_1q=3.4e-5, p_2q=1.36e-3, p_meas=1.5e-3, p_init=0.0))):
    t = time.time(); rows = [list(s) for s in inst.run_shots(Quest(), n_qubits=g["qubits"], n_shots=shots, random_seed=1, error_model=em, runtime=SoftRZRuntime())]
    dt = time.time() - t
    print(name, "%.2f s per shot" % (dt / shots), "entries", len(rows[0]), flush=True)

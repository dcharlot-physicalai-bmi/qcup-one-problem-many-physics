"""Does a Z fault reach the state? ry(pi/2), ry(-pi/2), measure, with a fault on every gate (X, Y or Z evenly).
If Z faults act: P(1) = 4/9 (both Selene's depolarizing model, fault before the gate, and the plugin, fault after);
if Z faults are lost: 5/9. Run under Selene's simple runtime and its soft-RZ runtime.
    python debug_z.py PLUGIN_LIB WORK"""
import importlib.util, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "python"))
import selene_sim
from selene_sim import DepolarizingErrorModel, Quest, SoftRZRuntime, SimpleRuntime
from guppylang import OptimizationLevel
from qcup_published_noise import PublishedNoise
LIB, WORK = sys.argv[1], sys.argv[2]
progs = {
 "ry_ry": "    ry(q0, angle(0.5))\n    ry(q0, angle(-0.5))\n",
 "rx_rx": "    rx(q0, angle(0.5))\n    rx(q0, angle(-0.5))\n",
}
for name, body in progs.items():
    text = ("from guppylang import guppy\nfrom guppylang.std.quantum import qubit, measure, rx, ry, rz\nfrom guppylang.std.angles import angle\n"
            "from guppylang.std.builtins import result\n\n\n@guppy\ndef main() -> None:\n    q0 = qubit()\n" + body + "    result(\"c000\", measure(q0).read())\n")
    w = tempfile.mkdtemp(dir=WORK); src = os.path.join(w, "p.py"); open(src, "w").write(text)
    spec = importlib.util.spec_from_file_location("p" + name, src); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    inst = selene_sim.build(m.main.with_opt_level(OptimizationLevel.Classical).compile(), build_dir=os.path.join(w, "b"))
    for rname, rt in (("simple", SimpleRuntime()), ("soft_rz", SoftRZRuntime(duration_ns_rzz=1, max_batch_size=1000000))):
        for ename, em in (("depolarizing", DepolarizingErrorModel(p_1q=1.0)), ("plugin", PublishedNoise(library=LIB, p1=1.0))):
            n = 20000; ones = sum(1 for s in inst.run_shots(Quest(), n_qubits=1, n_shots=n, random_seed=3, error_model=em, runtime=rt) if dict(list(s))["c000"])
            print(name, rname, ename, "P(1) = %.4f" % (ones / n), "(Z acts: 0.4444; Z lost: 0.5556)", flush=True)

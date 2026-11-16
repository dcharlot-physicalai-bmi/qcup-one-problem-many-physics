"""SHA-256 of every file in the evidence folder (except the manifest itself), and a short index of what each part holds.
    python3 -I make_manifest.py BASE"""
import hashlib, json, os, sys
B = os.path.abspath(sys.argv[1])
INDEX = {
    "params/": "Emulator_parameters.csv (Quantinuum's table, as plain data), the two Selene parameter files made from it (make_params.py), mapping.json (each column to Selene, or not representable), the circuit lists",
    "plugin/": "the Selene error-model plugin (rust/lib.rs, Cargo.toml, Cargo.lock), its Python wrapper, the selene-core 0.3.4 sources it was built against (selene-sim-v0.3.8 tag, hashes in vendor/selene-core-0.3.8-tag.sha256), the built library's hash",
    "scripts/": "host_setup.sh (both venvs), gen_guppy.py (gate list to Guppy), run_job.py (one Selene job), run_queue.py (all jobs), controls.py (positive controls), debug_z.py, timing_probe.py, analyze.py, summarize.py, make_params.py, make_manifest.py",
    "builder/": "the package builder's gate lists and OpenQASM 3 for the 84 core circuits and the 44 extension programs, SHA-256 equal to vendor/results/circuits/manifest_sha256.json, and its index",
    "rebuild/": "the same circuits rebuilt by build_circuits.py in the package's pinned environment, and the comparison with the builder's files",
    "runs/": "every Selene job's output: each shot's classical bits and the error model's per-shot metrics, with the settings it ran under",
    "results/": "selene_results.json (per circuit and per set: scores, intervals, no-fault fractions, model predictions, fits, admission, HQC), per_circuit.csv, summary.json (every figure the draft quotes)",
    "controls/": "positive controls of the plugin against closed forms (readout, memory, emission, crosstalk, Selene's depolarizing model, ideal)",
    "env/": "the corpus lock (selene-sim 0.3.8, guppylang 1.2.1) and the package pins, and the frozen venvs as built on the M3 Ultra",
    "docs-quantinuum/": "Quantinuum's Emulator Noise Model documentation page, as fetched, and its text",
    "selene-source-0.3.8/": "Selene 0.3.8 sources read for the error-model survey: the error models, runtimes, operation and plugin interfaces (from the tag), and the installed Python sources",
    "logs/": "queue logs",
}
man = {}
for root, dirs, files in os.walk(B):
    dirs.sort()
    for f in sorted(files):
        p = os.path.join(root, f); rel = os.path.relpath(p, B)
        if rel in ("MANIFEST.sha256", "manifest.json") or "/__pycache__/" in "/" + rel: continue
        man[rel] = hashlib.sha256(open(p, "rb").read()).hexdigest()
with open(os.path.join(B, "MANIFEST.sha256"), "w") as fh:
    for k in sorted(man): fh.write(f"{man[k]}  {k}\n")
json.dump({"files": len(man), "index": INDEX}, open(os.path.join(B, "manifest.json"), "w"), indent=1)
print(len(man), "files")

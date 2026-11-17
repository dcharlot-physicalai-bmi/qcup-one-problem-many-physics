"""SHA-256 of every file in the evidence folder (except the manifest itself), and a short index of what each part holds.
    python3 -I make_manifest.py BASE"""
import hashlib, json, os, sys
B = os.path.abspath(sys.argv[1])
INDEX = {
    "docs-quantinuum/": "Quantinuum's emulator and hardware documentation pages as fetched on 2026-11-17 (HTML, their text, SHA256SUMS), byte-identical to the fact-check's saved copies for the three emulator pages",
    "params/": "the three Selene parameter files made from the HTML tables (make_params_2025.py), mapping.json (each documented parameter to the plugin, or not representable, and why), the circuit lists",
    "plugin/": "the docs-noise Selene error-model plugin (rust/lib.rs, Cargo.toml, Cargo.lock), its Python wrapper, the selene-core 0.3.4 sources it builds against (selene-sim-v0.3.8 tag), the built library's hash",
    "scripts/": "host_setup.sh, make_params_2025.py, gen_guppy.py, run_job.py, run_queue.py, controls.py, controls_recheck.py, analyze.py, summarize.py, q8_power.py, build_drafts.py, check_draft.py, html2text.py, make_manifest.py",
    "builder/": "the package builder's gate lists and OpenQASM 3 for the 84 core circuits and the 44 extension programs (the same files as the 2024 run's builder/)",
    "controls/": "positive controls of the plugin against closed forms (controls.json), the emission control re-run at fresh seeds (controls_recheck.json), their logs, their job and gate inputs (inputs/), and the request program used for C5 and C6",
    "runs/": "every Selene job's output: each shot's classical bits and the error model's per-shot metrics, with the settings it ran under",
    "results/": "selene_results.json, per_circuit.csv, summary.json (every figure the drafts quote), q8_power.json, draft_replacements.json (the drafts, their anchors and figure paths), build_drafts.out (the drafts as text), check_draft.out, and the scripts' outputs",
    "env/": "the corpus lock (selene-sim 0.3.8, guppylang 1.2.1) and the frozen venv as built on the M3 Ultra",
    "logs/": "the queue log and the per-job logs",
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

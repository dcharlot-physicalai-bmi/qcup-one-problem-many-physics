# selene-params/: Selene with Quantinuum's published emulator parameters

Run 16 November 2026 on an M3 Ultra (finding 28 of the package README). Emulator evidence, not a device result.

## What was run

- **Circuits.** All 84 Quantinuum core circuits of the request (71 Aim 2 programs, the 8-qubit pulse-code circuit, 8
  transition-metal and 4 actinide circuits) and the 44 extension-tier programs, to 1,995 two-qubit gates, run for the
  fit only. The gate lists are the package builder's (builder.tar.xz), SHA-256 equal to
  vendor/results/circuits/manifest_sha256.json. A rebuild with build_circuits.py in the package's pinned environment gives
  the same two-qubit gate pairs in the same order on all 84 and identical gate lists on 47; elsewhere one-qubit counts
  differ by up to 20 for one gate kind (30 summed over rx, ry and rz; 13 net), and on the chemistry circuits the RZZ angles differ (by up to 0.46 rad), so the
  chemistry circuits do not rebuild exactly (rebuild/; its max_angle_diff is null wherever the lists differ).
- **Emulator.** A local copy of Selene 0.3.8 and guppylang 1.2.1 from the corpus lock (env/), state vector, soft-RZ
  runtime (RZ is a frame change, as on the device). The clock counts two-qubit layers only: RZZ gates on separate pairs share a
  layer, and each gate of a run on one pair takes its own.
- **Parameter sets.** Quantinuum's published emulator parameters for H2-1 (2024-05-20) and H2-2 (2024-12-06), the newest
  in its emulator parameter table (notebooks/Emulator parameters.csv in its quantinuum-hardware-specifications
  repository at commit 59e68bb). Here: params/Emulator_parameters.csv (that table as plain data), and
  params/H2-1_2024-05-20.json and params/H2-2_2024-12-06.json as made by make_params.py. params/mapping.json maps each column of the table to Selene.
  The meanings come from Quantinuum's Emulator Noise Model documentation page (SHA-256 of the page as fetched in
  sources/docs-quantinuum.sha256).
- **Error models.** Selene runs one error model at a time. Two were run: Selene's own depolarizing model (all but the
  4 actinide circuits), and our error-model plugin (plugin/rust/lib.rs, loaded through Selene's documented plugin
  interface), which replaces it and holds every term: the gate and readout terms, and emission and leakage, asymmetric
  readout, measurement crosstalk and memory error.
- **Shots.** 200, except the actinides: 200 for three of them on H2-1, 100 (the request's count) for the fourth on H2-1
  and all four on H2-2. One 26-qubit shot took about 240 to 350 s on Selene's state vector, with eight jobs at once.
- **Controls.** 124 ideal (no-noise) runs, and positive controls of the plugin against closed forms (controls/).

## How each column is held

- p1, p2: exact probabilities, uniform Paulis (Quantinuum's asymmetric weights are unpublished).
- p1_emission_ratio, p2_emission_ratio: plugin only. An emission is X a quarter of the time, Y a quarter, leakage half,
  as Quantinuum's documentation states. A leaked qubit reads 1, takes no gates and returns on reset, and the partner of a
  leaked qubit in a later RZZ gets I, X, Y or Z evenly: these two rules are our assumptions. So is applying the
  emission leakage branch to H2's sets at all: Quantinuum's documentation places its leakage model in the Helios
  emulators.
- dephasing_error: plugin only, approximate. Z with probability 1.5 × (dephasing_error − p1) per qubit per two-qubit
  layer of Selene's runtime (the application's rule; its model counts a run of gates on one pair as one layer); the
  table gives no rates or durations.
- p_crosstalk_meas: plugin only; the other qubits are measured and the result discarded. The leakage branch is not
  represented. p_crosstalk_init is blank for H2.
- p_meas_0, p_meas_1: exact in the plugin; Selene's depolarizing model can use only their mean.
- Not in the repository's table, so not represented: the angle dependence of two-qubit error (Quantinuum's emulator
  documentation publishes it for its defaults of 2025-07-16 and 2025-11-18, which these runs did not use, so every RZZ
  here carries the full p2), transport timing, and coherent quadratic dephasing (the 2025 defaults give a quadratic
  dephasing rate, but no published durations to apply it to). The plugin sees each RZZ's angle, so the documented angle
  dependence can be added.

Two Selene details: Guppy's project_z is a measurement, a fresh qubit and an X, so a readout error also flips the qubit
afterwards (it does not change a trace that is already wrong); RZZ gates at angle 0 are dropped (1,198 across the 12
chemistry circuits), while the HQC request still counts them.

## Results (results/summary.json, every figure quoted in the application and the package README)

- With every term, the 115 programs lose 0.165% (H2-1) and 0.162% (H2-2) per two-qubit gate, R² 0.97 and 0.95 on the 104
  and 103 programs with at least 20 correct traces; 30% near 715 and 720 by least squares (near 630 and 590 by
  final_request.py's median rule; 739 and 707 by least squares on the 71 core programs alone). Our model of the same
  figures gives 506 and 495 by the median rule (360 and 357 by least squares), so at the 30% point the model is the
  more cautious. Circuit by circuit it is not uniformly so: on the 35 core programs with at least 20 two-qubit gates
  Selene falls below the model on 15 and 16 (8 and 7 beyond its 95% interval, by at most 9% and 11%, phase R T5 at 115
  gates), and every one stays above 0.58.
- All 80 admitted circuits clear 30% on both sets (the chemistry and pulse-code circuits on error-free shots). Core programs keep 0.585 to 1.00 trace fidelity; the lowest is t59
  mod5-mod4 R T3 at 297 gates (0.585, against 0.48 modelled).
- Transition-metal circuits keep 0.43 to 0.70 of shots with the right electron numbers, against 0.45 to 0.68 modelled
  (per circuit 0.87 to 1.12 times the model). Under H2-1's set the 95% intervals of FeO_stretched, MnO_eq and
  MnO_stretched straddle 0.30 on error-free shots; under H2-2's only FeO_stretched does.
- The 4 actinide circuits keep 0.25 to 0.32 with the right electron numbers, against 0.16 to 0.24 modelled, and run
  free of any error in 0.07 to 0.15 of shots: below the line, as Q8 intends.
- Selene's depolarizing model alone: 0.083% and 0.089% per gate, 30% near 1,440 and 1,350.
- The package's HQC formula reproduces final_request.json's 4,694.2.

Error-free fractions for chemistry sit below the model's e^-b mainly from memory error. The model counts a run of
gates on one pair as one layer (19 to 35 layers on the transition-metal circuits), while Selene's runtime gives each
gate of such a run its own layer (34 to 52 layers), so the plugin charges memory on 1.6 to 2.2 times the model's qubit-layers: under H2-2's set the
runs show 0.22 to 0.67 memory events per shot, against the model's 0.12 to 0.39. The shares, which are what Q8
measures, agree with the model.

## Files

| Path | What it is |
|---|---|
| params/ | Quantinuum's parameter table as plain data, the two Selene parameter files, mapping.json, the circuit lists |
| plugin/ | The error-model plugin (rust/lib.rs, Cargo.toml, Cargo.lock), its Python wrapper, and the built library's SHA-256 |
| plugin/vendor/selene-core-0.3.8-tag.sha256 | SHA-256 of the selene-core 0.3.4 sources the plugin builds against, from the selene-sim-v0.3.8 tag of https://github.com/CQCL/selene (Apache 2.0); place them at plugin/vendor/selene-core to build |
| scripts/ | host_setup.sh (both environments; set UV to a uv binary), gen_guppy.py (gate list to Guppy), run_job.py (one job), run_queue.py (all jobs), controls.py, debug_z.py, timing_probe.py, analyze.py, summarize.py, make_params.py, make_manifest.py |
| controls/ | Positive controls against closed forms: readout, memory, emission, crosstalk, plugin against Selene's depolarizing model, ideal |
| results/ | selene_results.json (per circuit and set: scores, intervals, error-free fractions, model predictions, fits, admission, HQC), per_circuit.csv, summary.json, analyze.out |
| builder.tar.xz | The builder's gate lists and OpenQASM 3 for the 128 circuits, and its index (run_queue.py reads them as builder-circuits/) |
| runs.tar.xz | Every job's output: each shot's classical bits, the error model's per-shot fault counts, and the settings it ran under |
| rebuild/ | The comparison of a fresh rebuild with the builder's files |
| env/ | The corpus lock and the frozen environments as built |
| sources/full-run-MANIFEST.sha256 | SHA-256 of all 2,767 files of the original run folder, including the unpacked runs/ and builder/. Three files here were edited to remove local paths and no longer match their lines: scripts/host_setup.sh, scripts/analyze.py (its docstring) and plugin/built-dylib.sha256 |
| manifest_sha256.json | SHA-256 of every file in this folder except itself |

To check the archives: unpack runs.tar.xz and builder.tar.xz here and compare with sources/full-run-MANIFEST.sha256
(`shasum -a 256 -c`, on the lines for runs/ and builder/).

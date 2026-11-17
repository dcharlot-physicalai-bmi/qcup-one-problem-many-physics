# selene-2025/: Selene with Quantinuum's 2025 default emulator parameters

Run 17 November 2026 on an M3 Ultra (finding 28 of the package README). Emulator simulations, not device runs. The
first run, under the 2024 parameters of Quantinuum's hardware-specifications repository, is in ../selene-params/ and is
unchanged.

## What was run

- **Circuits.** All 84 Quantinuum core circuits of the request (71 Aim 2 programs, the 8-qubit pulse-code circuit, 8
  transition-metal and 4 actinide circuits) and the 44 extension-tier programs, to 1,995 two-qubit gates, run for the
  fit only. The gate lists are the package builder's, the same files as the 2024 run's: the run's builder/ folder is
  byte-identical to ../selene-params/builder.tar.xz (all 258 files match their lines in sources/full-run-MANIFEST.sha256),
  so it is not copied here.
- **Emulator.** A local copy of Selene 0.3.8 and guppylang 1.2.1 from the corpus lock (env/), state vector, soft-RZ
  runtime (RZ is a frame change, as on the device). The clock counts layers of two-qubit gates: RZZ gates on separate
  pairs share a layer, and each gate of a run on one pair takes its own.
- **Parameter sets.** The default noise parameters on Quantinuum's emulator pages: H2-1E and H2-2E of 2025-07-16
  (System Model H2 Emulators) and Helios-1E of 2025-11-18 (Quantinuum Helios emulators), read from the saved HTML by
  scripts/make_params_2025.py into params/<set>.json. On the H2 page both tables are captioned "H2-1E emulators from
  2025-07-16"; the second sits in the tab labelled H2-2E and its own first row names H2-2E, and the script keys each table
  by its tab. The pages as fetched on 17 November 2026 are listed by SHA-256 in sources/docs-quantinuum.sha256 and are not
  copied. params/mapping.json maps every row of the three tables to the plugin, or says why it is not represented.
- **Error model.** Our plugin (plugin/rust/lib.rs, loaded through Selene's documented error-model interface) holds p1
  and p2 (X, Y and Z evenly, since the asymmetric weights are not published), each RZZ's depolarizing fault scaled by the
  documented angle formula (1.518 |θ|/π + 0.241 on all three sets; the emission part unscaled, as documented), emission,
  initialisation faults, measurement and initialisation crosstalk and asymmetric readout. On Helios-1E qubits leak at
  initialisation and from emission and return by seepage, 1/3 per gate. On H2-1E and H2-2E no qubit leaks (the
  documentation says the H2 emulators have no leakage), so the leakage half of an emission is a depolarizing error. The
  devices' documented minimum gate angles round 522 RZZ and 23 one-qubit gates to zero, in 11 of the 12 chemistry
  circuits, in every run.
- **Dephasing.** Quantinuum publishes the dephasing rates and not the durations of the emulator's transport schedule
  they apply to (no H2 time at all; Helios's depth-1 program on all 98 qubits takes about 71 ms). Each set therefore ran
  twice: `docs`, with dephasing left out, and `docs_dephasing`, at an assumed 71 ms per two-qubit layer of Selene's
  runtime, in the documented incoherent form: a Z with probability 0.00057 per qubit per layer on H2-1E and H2-2E and
  0.00094 on Helios-1E (the 2024 run's memory term was 0.00070 and 0.00068). One gating round, about 10 ms, would make the
  term about 16 times smaller on H2. The two variants are two settings of dephasing; the incoherent form does not bound the documented coherent default, and a Helios time is applied to H2, so they do not bracket the term (params/mapping.json, kept as run, says they do).
- **Not represented.** The weights of the asymmetric channel, the leaking branch of crosstalk, and the transport
  schedule itself. Our assumptions: the duration per layer, the H2 reading of the leakage branch, the state a seeping qubit
  returns to, the rule for a leaked qubit's partner, and the memory placement.
- **Shots.** 200; the 4 actinide circuits 100, the request's count, in four chunks of 25. Ideal controls: 200 shots, and
  10 for each actinide circuit.
- **Controls.** 29 comparisons of the plugin with closed forms, all within 3σ and 26 within 2σ; the emission split, at
  2.4σ, came to 0.26σ at fresh seeds over 160,000 shots (controls/controls_recheck.json). The angle scaling matches its
  closed form at six angles under the documented fit and under an unequal one (|z| at most 1.81), and on every run the
  plugin's per-shot sum of the angle factor equals the closed form over the program's own RZZ angles, to rounding error.
  With no noise (128 ideal runs) every program gives its reference trace and every chemistry shot, the actinides
  included, the right electron numbers.

## Results (results/summary.json)

Without dephasing the 115 programs lose 0.061%, 0.076% and 0.050% per two-qubit gate on H2-1E, H2-2E and Helios-1E
(R² 0.97, 0.98 and 0.97; all 115 fitted), 30% near 1,960, 1,580 and 2,420 by least squares. With dephasing they lose
0.130%, 0.144% and 0.151% (R² 0.98, 0.97 and 0.95; 110, 108 and 108 programs with at least 20 correct traces fitted),
30% near 920, 830 and 780. By final_request.py's median rule, over the programs with at least one wrong trace, the points
are 1,820, 1,470 and 2,330 without dephasing and 880, 770 and 740 with it. Our model of the closest published 2025 sets
(H2-1 of April 2025, H2-2 of May 2025, and for Helios-1E, which it has no set for, H2-2 of August 2025) gives 930, 880
and 1,390 by that rule.

All 80 admitted circuits clear 30% on all three sets both ways, the chemistry and pulse-code circuits on error-free
shots: programs 0.785 to 1.00 without dephasing and 0.575 to 1.00 with it; the pulse-code circuit error-free in 0.865 to
0.955 and 0.46 to 0.64 of shots; the transition-metal circuits error-free in 0.68 to 0.90 and 0.305 to 0.715. The lowest
is MnO_eq on Helios-1E with dephasing, at 0.305, its 95% interval 0.245 to 0.372.

The transition-metal circuits keep 0.775 to 0.925 of shots with the right electron numbers without dephasing and 0.425
to 0.76 with it. Q8's ranges for them are 0.61 to 0.82 under the published figures we admit on and 0.83 to 0.94
under our generic law. The 4 actinide circuits run error-free in 0.38 to 0.78 of shots without dephasing, at or above
the line in all 12 circuit and set pairs, and in 0.09 to 0.33 with it, below the line in 10 of the 12 (6 of them with the
whole 95% interval below 0.30). They keep 0.48 to 0.88 of shots with the right electron numbers without dephasing and
0.21 to 0.47 with it, against Q8's ranges of 0.33 to 0.64 under the figures we admit on and 0.66 to 0.82 under the
generic law. The emulator's own settings put the actinides on either side of the line.

Under the 2024 table (../selene-params/) Selene gave 0.165% and 0.162% per two-qubit gate, 30% near 715 and 720, and
all 80 admitted circuits cleared 30%. The package's HQC formula reproduces the request's HQC at the actinides' former
100 shots, 4,694.2 (5,079.2 at the 150 shots Q8's range rule now sets).

## Q8

Q8's predictions now come from these runs (vendor/scripts/final_request.py, vendor/results/final_request.json
`steps.q8_ranges`; DECISIONS items 45, 49 and 50 of the check-3 round). Errors that keep the electron numbers matter:
per circuit and setting, the fraction of shots with an error that still kept them, k = (share − error-free) /
(1 − error-free), is 0.09 to 0.45, against at most 0.044 by chance. Each prediction is the range F + (1 − F)k over the
circuit's lowest to highest k on the six settings, the same k for the published figures and the generic law: on the
figures the application admits on, 0.61 to 0.82 against 0.83 to 0.94 for the transition-metal circuits and 0.33 to 0.64
against 0.66 to 0.82 for the actinides. In each group the published figures win if the median over its circuits of
(log distance to the generic range − log distance to the published range) is positive. There is a verdict only if the
group's median gap between the ranges is at least G (1.065 at 200 shots for the transition-metal circuits, 1.193 at 150
for the actinides; G and k are fixed now, and only F is recomputed from the figures current at the first run), and both
predictions are rejected beyond a factor of 1.25 or 1.5 from the range the verdict step chooses, with or without a
verdict.

Taken as the truth (2,000 draws, seed 20261115, at those shots and bands), these runs' shares favour the generic law
without dephasing, except the actinides on H2-2E, and the published figures with it. The transition-metal circuits on
Helios-1E with dephasing, 1.17 below the published range, are rejected in 3.75% of draws, the actinides there in 0.35%;
no other setting is rejected.

scripts/q8_power.py and results/q8_power.json hold Q8 as it stood before the ranges: point predictions that counted
every shot with an error as a random guess, the band read as the median over circuits of the measured share over the
nearer prediction, and its outcomes with these shares as the truth (generic law without dephasing and published figures
with it in both groups; no rejection at 1.25 and 1.5; reversal at most 1.95%; and a second reading with predictions from
the published set closest to each emulator). An independent check of the application showed that those predictions
lean toward the generic law, which is why the ranges replaced them.

## Files

| Path | What it is |
|---|---|
| params/ | The three parameter sets as read from the saved pages, mapping.json, the circuit lists |
| plugin/ | The error-model plugin (rust/lib.rs, Cargo.toml, Cargo.lock), its Python wrapper, and the built library's SHA-256 |
| plugin/vendor/selene-core-0.3.8-tag.sha256 | SHA-256 of the selene-core 0.3.4 sources the plugin builds against, from the selene-sim-v0.3.8 tag of https://github.com/CQCL/selene (Apache 2.0); place them at plugin/vendor/selene-core to build |
| scripts/ | host_setup.sh (set UV to a uv binary), make_params_2025.py, html2text.py, gen_guppy.py, run_job.py, run_queue.py, controls.py, controls_recheck.py, analyze.py, summarize.py, q8_power.py, make_manifest.py (the run folder's manifest) |
| controls/ | Positive controls against closed forms (controls.json), the emission control at fresh seeds (controls_recheck.json), their logs, their job and gate inputs (inputs/), and the request program used for C5 and C6 |
| results/ | selene_results.json (per circuit, set and variant: scores, intervals, error-free fractions, model predictions, fits, admission, HQC), per_circuit.csv, summary.json, q8_power.json, and the scripts' printed outputs |
| env/ | The corpus lock (selene-sim 0.3.8, guppylang 1.2.1) and the frozen environment as built |
| runs.tar.xz | All 972 job outputs: each shot's classical bits, the error model's per-shot fault counts and angle sums, and the settings each ran under |
| sources/full-run-MANIFEST.sha256 | SHA-256 of all 2,357 files of the original run folder, including the unpacked runs/ and builder/ |
| sources/docs-quantinuum.sha256 | SHA-256 of Quantinuum's documentation pages as fetched on 17 November 2026 (HTML, their text, one figure) |
| manifest_sha256.json | SHA-256 of every file in this folder except itself |

Left out, and listed in sources/full-run-MANIFEST.sha256: the saved Quantinuum pages; the queue and job logs, which name
the build host's paths; builder/ (identical to ../selene-params/builder.tar.xz); the upstream selene-core sources; and
the run's drafts of application text with the scripts that built and checked them (build_drafts.py, check_draft.py,
draft_replacements.json, build_drafts.out, check_draft.out), which the application's own wording and its source check
replace. Edited to remove local paths, so they no longer match their lines in the run manifest: scripts/host_setup.sh
(the default uv path) and the 21 controls/inputs/*.job.json files (paths made relative to the work folder).

To check the archives: unpack runs.tar.xz here and ../selene-params/builder.tar.xz here, then compare with
sources/full-run-MANIFEST.sha256 (`shasum -a 256 -c`, on the lines for runs/ and builder/). To rerun the analysis from
them: `python3 -I scripts/analyze.py . ../.. ../selene-params SCRATCH`, then `scripts/q8_power.py . ../..` and
`scripts/summarize.py . ../selene-params` (analyze.py imports the package's labs.py, which needs NumPy). This reproduces
selene_results.json and summary.json as data (the order of two keys can differ) and per_circuit.csv byte for byte;
q8_power.json's controls copy final_request.json's Q8 entries, which gained keys in v1.0.2.

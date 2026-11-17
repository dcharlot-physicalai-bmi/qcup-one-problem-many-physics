# v1.0.3 (17 November 2026): fresh-read round of the application

Published v1.0.2 (doi:10.5281/zenodo.24322590) is this folder before these changes. Nothing under results/ changed, and
vendor/selene-params/ and vendor/selene-2025/ are byte-identical. The application's sources_check_final.py passes 135
checks after this round (124 before it).

| File | Change |
|---|---|
| vendor/scripts/final_request.py | Two computations the fresh read asked for (DECISIONS items 52 and 53). `steps.q5_neglog_criterion`: Q5's second criterion, on −ln F′, for the IonQ and Quantinuum core programs: with the law exactly true (fitted to each device model's per-program fidelity in two-qubit gates, resets and idle qubit-layers), binomial trace counts by inverse CDF at the requested shots with the guessing floor and Q5's exclusions, fits on programs split alternately by position in the name order, both ways, 2,000 draws, seed 20261115; the 99th percentile of the median miss on −ln F′ over held-out programs predicted to lose at least 20 traces is 1.174 (IonQ) and 1.245 (Quantinuum), stated as 1.18 and 1.25 (exceeded in 0.6% and 1.0% of draws). `steps.q3_signal_floor`: Q3's floor in standard errors of the sample mean (Popoviciu's bound on the variance from the instance's energy range), first drafted as a single-circuit floor: 11.93 computed, 12 stated; at the device check's retention 45 of the 84 IBM and 24 of the 84 IQM QAOA circuits clear it, and a true law is falsified in none of 2,000 simulated draws (replaced after check 5 by the floor below; kept under `superseded_single_circuit_floor`) |
| vendor/results/final_request.json | Rerun. No earlier value changed or was removed; 2 keys added (`steps.q5_neglog_criterion`, `steps.q3_signal_floor`) |
| README.md | Finding 29: the two computations |
| vendor/README.md | final_request.py row: the two new outputs |
| vendor/manifest_sha256.json | Regenerated: vendor/README.md, scripts/final_request.py and results/final_request.json changed; none added or removed |
| vendor/scripts/final_request.py (after check 5) | DECISIONS item 54. Q5: the −ln F′ limit is a procedure, the 99th percentile under shot noise alone with the device's own fitted law exact, over draws with a qualifying program (a draw with none leaves only the F′ criterion, never a pass); recorded by error scale (`by_error_scale`: 1.0, 0.7, 0.5, 0.4, 0.3 of the models' −ln F′; limits 1.174 to 1.267 on IonQ and 1.245 to 1.559 on Quantinuum); programs split alternately by position in the name order, as fitlib.held_out does, for every Q5 key (the device-level keys equal the 1.0 row of `by_error_scale`). Q3: the floor set by the median-based test (`falsifier_floor`: the smallest of 2, 3, 4, 6, 8, 12 standard errors with at most 1% false falsification in 20,000 draws on IBM and IQM): 2, scoring all 84 IBM and 84 IQM circuits |
| vendor/results/final_request.json (after check 5) | Rerun. No value of v1.0.2 changed or was removed; 7 keys added (`q5_neglog_criterion.devices.*.by_error_scale`, `.alternation`, `.procedure`; `q3_signal_floor.floor_used`, `.floor_rule`, `.falsifier_floor`, `.superseded_single_circuit_floor.note`). `q3_signal_floor` opens with `floor_used` (2) and its rule; the fresh-read round's single-circuit floor (11.93, stated 12, its miss rates, and per device the circuits it scored, 45 IBM and 24 IQM) moved with its values unchanged under `superseded_single_circuit_floor`. The fresh-read round's device-level Q5 keys now use the one alternation: on Quantinuum the 99th percentile 1.2443 → 1.2451 (stated 1.25 either way), its false rate at 1.25 0.0095 → 0.010, and the medians 1.0064 → 1.0065 on F′ and 1.1248 → 1.1256 on −ln F′; IonQ's keys and every Q3 value are unchanged |
| README.md (after check 5) | Finding 29's fresh-round paragraph: the procedure, its values by error scale, and the falsifier-based floor |
| vendor/scripts/final_request.py (after check 6) | DECISIONS item 55. Q3's floor is a procedure at the device's fitted F′, as Q5's limit is: `q3_floor` gives the smallest of 2, 3, 4, 6, 8 and 12 standard errors (Popoviciu's bound) at which, with that F′, the median-based test falsifies a true law in at most 1% of 20,000 draws, and none (no Q3 verdict on that device) if no circuit is scored or no candidate qualifies. Recorded at the device check's retention scaled by 1.0, 0.5, 0.3 and 0.2 (`q3_signal_floor.by_fprime_scale`): IBM 2, 2, 2, none; IQM 2, 2, none, none. `floor_used` is the function's value at the check's retention, 2 on both |
| vendor/results/final_request.json (after check 6) | Rerun. No value of v1.0.2 changed or was removed; `q3_signal_floor.by_fprime_scale` added and `q3_signal_floor.floor_rule` restated for the procedure; every other value unchanged |
| README.md (after check 6) | Finding 29's Q3 passage: the floor as a procedure at the device's fitted F′, with its values by scale |

# v1.0.2 (17 November 2026): review round of the application

Published v1.0.1 is this folder before these changes. Nothing under results/ changed (results/manifest_sha256.json still
matches every file); in vendor/selene-params/ only one line of its README changed (the correction at the end of this
file), and its own manifest verifies. Every figure below is computed by a script and checked by the application's
sources_check_final.py (124 checks, 0 failed, after the check-4 rows below; 120 after the check-3 rows; 117 after the
Selene 2025 rows; 105 before them), after four independent checks of the application whose fixes are folded in below.

## Changed

| File | Change |
|---|---|
| vendor/scripts/final_request.py | IBM Aim 1 QAOA shots: a circuit expecting fewer than 20 optima in 4,000 shots at the device check's measured retention (0.258 of the ideal optimum probability at 130 CZ) is raised to 20 expected successes, rounded up to 1,000 shots, but only if its ideal success is at least twice a uniformly random guess's (n_ground / 2^n, 1/4096 here) (`--q12-target`, `--shot-step`, `--floor-mult`; `--q12-target 0` gives the v1.0.1 request's values, with the new keys added and `shots_per_circuit` written as [4000, 4000]; `--floor-mult 0` gives the first version of this change). 41 of 84 circuits fall short; 7 of them are below a random guess and 26 below twice it; 15 are raised, 17,000 to 143,000 shots each (the first version raised all 41, 17,000 to 1,155,000 each, 9,886,000 of its 11,075,000 added shots on the 26 at the floor). IBM's documented limits recorded in the docstring (10 million executions per Sampler job, per job; 3 hours per job). IQM keeps 2,000 shots. New outputs: IBM minutes with and without the raise; Q1 and Q2 eligibility per vendor; IonQ's emulator coverage of the 64 requested circuits; the contents of period 2 and its HQC over the eight published sets; family C at 60 variables (extension only); the ladder's mid-circuit programs under the check's excess over the budget script; the kept IonQ QAOA rows below 0.30 on the emulator. Also Q1's scored circuits and Q2's eligible instances under the guessing-floor rule (IBM: 58 of 84 scored; 18 of 19 seed-optimal and 6 of 23 seed-not-optimal instances), the ladder programs that separate step count, gate count and mid-circuit measurement (50 requested multi-step programs with none, 44 of them placed on the patch; IQM's 60 requested multi-step programs all measure mid-circuit), Q2's chance of a false verdict from shot noise with the law exact (`q2_shot_noise_power`: Poisson counts at the requested shots, 2,000 runs, seed 20261115; seed-not-optimal arm 84%, seed-optimal arm 0%, so only the seed-optimal arm carries a verdict), and, for the IonQ circuits not emulated, the reason recorded at the run and whether a seed state or a rounding energy is stored. Every earlier output is unchanged except the IBM Aim 1 shots, the IBM minutes and the totals |
| vendor/results/final_request.json | Output of the script above: period 1 is 961 circuits and 2,420,900 shots (1,231,900 before); IBM 514 circuits, 1,978,000 shots, 16.1 minutes by cost.py's formula and 11.8 at the device check's charged rate (5.2 and 4.7 before) |
| vendor/ibm-check/derived/derived.py, derived.json | Adds Q5's gate-count form under the second form's exclusions (F >= 0.01 and F >= twice the guessing floor: 2.26 on 8 predictions; 3.03 on floor-corrected fidelity; not preregistered; the preregistered 2.19 on 13 and the twice-floor-only 157 on 11 reproduce the re-score) and the calibration's age at the run (2.62 days). Earlier keys unchanged |
| README.md | Finding 11's pointer and finding 26's totals carry the new IBM shots and minutes; finding 28 and Limits say "the hardware-specifications repository's table" and note Quantinuum's newer emulator defaults (2025-07-16, 2025-11-18), which the Selene runs did not use; finding 29 added (the review round's figures) |
| vendor/README.md, vendor/ibm-check/README.md | The new scripts and outputs listed |
| vendor/manifest_sha256.json | Regenerated: 698 files (692 before; 6 added, 6 changed, none removed). vendor/selene-params/ is unchanged, so its own manifest still verifies. A stray `vendor/scripts/__pycache__/` (not written by this change) is left out, as .gitignore leaves it out |
| LICENSE-NOTE.md | Said CC0 1.0 covered results/ only, which left the data under vendor/ (device counts, emulator outputs, the sealed preregistration) with no stated licence. Now: code under Apache-2.0; the author's other material under results/ and vendor/ under CC0 1.0; three kinds of material from others keep their own terms (Quantinuum's emulator parameter table, an unchanged Apache-2.0 copy; IBM's calibration files; IQM's price read) |
| CITATION.cff (repository only) | Abstract's licence sentence matches LICENSE-NOTE.md. `license` stays one identifier (Apache-2.0), as Zenodo reads one |
| vendor/scripts/final_request.py (Selene 2025 round) | Q8's bands: the transition-metal and actinide groups decided separately, within a factor of 1.25 and 1.5 (`--q8-band-tm`, `--q8-band-act`). q8_power() also reports, from the same draws (seed 20261115, 2,000 draws per truth), the rate at which shot noise alone rejects both predictions at the group's band under the published and the generic shares as the truth, and the wrong-verdict rate with the generic shares as the truth; the v1.0.1 function is kept as `q8_power_v101` and asserted to give the same verdict rates on every call. The transition-metal circuits are also scored on every published set; `steps.q8_bands` holds the maxima over the eight sets (wrong verdict at most 0.75%, rejection at most 0.15%) |
| vendor/results/final_request.json (Selene 2025 round) | Rerun of the script above. Every key of the review-round output keeps its value (524 values compared, none changed or removed); 112 keys added: `parameters.q8_band_*`, `band`, `wrong_verdict_if_generic_true`, `rejected_both_if_published_true` and `rejected_both_if_generic_true` in each `q8_rule` entry, `by_figure_set[*].q8_rule_200_shots` for the transition-metal circuits, `2_actinide_test.max_over_published_sets_at_band`, `steps.q8_bands`. The printed table, totals and costs are unchanged |
| README.md (Selene 2025 round) | Finding 28 rewritten for the Selene runs under Quantinuum's 2025 emulator defaults, with the 2024 run kept as history; the request note on the Quantinuum check, the software line and the Limits line updated to match |
| vendor/README.md (Selene 2025 round) | The Selene evidence kinds, the final_request.py and final_request.json rows, the new selene-2025/ row, and how its analysis scripts run |
| vendor/manifest_sha256.json (Selene 2025 round) | Regenerated: 785 files (698 before; 87 added, all under selene-2025/; 3 changed: README.md, scripts/final_request.py, results/final_request.json; none removed). selene-params/ is byte-identical and its manifest verifies (43 files). The stray `vendor/scripts/__pycache__/` is left out |
| vendor/scripts/final_request.py (check-3 round) | Q8's range design (DECISIONS items 45, 49 and 50, after the independent check of the Selene 2025 round): a shot with an error can keep the right electron numbers, a fraction k = (share − error-free) / (1 − error-free) per chemistry circuit and Selene setting (0.09 to 0.45; read from vendor/selene-2025/results/selene_results.json), so each prediction is a range over the circuit's k_min to k_max, the same for the published figures and the generic law. Rule: per circuit the log distance from the measured share to each range (0 inside it); the published figures win if the group's median of (distance to generic − distance to published) is positive; a verdict only if the group's median range gap reaches G (found by moving the published figures toward the generic law until shot noise alone first gives a wrong verdict in more than 1% of 2,000 draws, k at its lowest, median and highest, either law as the truth: 1.065 for the transition-metal circuits at 200 shots, 1.193 for the actinides at 150); both rejected beyond the smallest listed band with rejection at most 1% (1.25, 1.5). The actinide shots follow the rule: 150, the smallest of 100, 150 and 200 at which the admitted figures get a verdict (`--act-shots` overrides). New key `steps.q8_ranges` (k, ranges, G by shot count, bands, outcome on every published set, sensitivity with each setting's own k, Selene scenarios); `hqc_by_shots` gains 150; wrong-verdict rates are counted, not subtracted, so 20 of 2,000 is 1% |
| vendor/results/final_request.json (check-3 round) | Rerun. Of 2,583 earlier values, the 10 that follow the actinide shots changed and no other: parameters.actinide_shots 100 → 150; step 2's shots and hqc_total (789.9 → 1,174.9); the Quantinuum Aim 1 table row (200 (150 for actinides), 2,400 shots); totals and period-1 shots 2,420,900 → 2,421,100; Quantinuum HQC 4,694.2 → 5,079.2 and its actinide part. Added: `steps.q8_ranges`, `hqc_by_shots.150`. The point-prediction summary `steps.q8_bands` stays at its recorded 100 shots |
| README.md (check-3 round) | Finding 28: Q8's ranges, rule, G, shots and Selene scenarios; the actinide pairing written out; finding 26 and 11: the actinides at 150 shots, 5,079 HQC, 2,421,100 shots; Limits: "two settings of dephasing" in place of "bracket"; "Simulations, in full": its Selene row replaced by the application's two rows (2025 defaults, 2024 history) |
| vendor/README.md (check-3 round) | final_request.py and final_request.json rows describe Q8's range design and the actinide shots |
| vendor/selene-2025/README.md (check-3 round) | The Q8 section describes the ranges built from these runs and their scenario outcomes, and keeps q8_power.json as the record of the earlier point predictions; "two settings" in place of "bracket" (params/mapping.json keeps its wording as run); the actinide pairing written out; the HQC sentence for 150 shots |
| vendor/selene-2025/manifest_sha256.json, vendor/manifest_sha256.json (check-3 round) | Regenerated: selene-2025 86 files (README.md changed); vendor 785 files (5 changed: README.md, scripts/final_request.py, results/final_request.json, selene-2025/README.md, selene-2025/manifest_sha256.json; none added or removed). selene-params/ is byte-identical and its manifest verifies |
| LICENSE-NOTE.md (check-3 round) | Names vendor/selene-2025/ and its plugin among the code, and adds a bullet: the parameters read from Quantinuum's emulator pages and the short passages mapping.json quotes keep Quantinuum's terms |
| vendor/scripts/final_request.py (check-4 round) | DECISIONS item 51, after the fourth independent check. G is frozen at 1.065 and 1.193 (`--q8-g-tm`, `--q8-g-act`) and derived along a fixed path from H2-1's figures of 20 October 2026, so a new `--qset` recomputes F and the ranges and moves neither G nor the actinide shots; the band test uses the range chosen by the verdict step, with or without a verdict. New outputs: the residual sensitivity (published figures exact, k above Selene's highest by 0.03, 0.05 and 0.10: the published figures win in 96.75%, 88.1% and 33.8% of 2,000 draws for the actinides, 99.95%, 99.45% and 86.95% for the transition-metal circuits; and the generic law's side, k below Selene's lowest), the no-noise flip (k above Selene's highest by 0.087 and 0.151), the rejection reach (no noise, device fidelity as a fraction of the published one: 0.745, 0.657 and 0.523 for the transition-metal circuits at Selene's lowest, median and highest k; 0.499, 0.215 and never for the actinides) and 40,000-draw precision estimates by inverse-CDF binomial counts (G 1.0650 and 1.1927; the actinides' G at 100 shots 1.249 and their wrong-verdict rate there 1.19%). `--out` writes the output elsewhere |
| vendor/results/final_request.json (check-4 round) | Rerun. Every earlier value is unchanged (3,021 compared); 20 keys added under `steps.q8_ranges` (`G_frozen`, `G_derivation_set`, `gap_margin_frozen`, `outcome_on_qset_figures`, `sensitivity_k_above_selene`, `sensitivity_k_below_selene_generic_true`, `no_noise_flip_k_above_selene`, `rejection_reach`, `precise` per group; `rule_band_test_range`, `G_frozen_note`) |
| README.md (check-4 round) | Finding 28: the rule in three numbered steps with the band test on the range chosen in step (1); G and k fixed; G's 40,000-draw values; the actinides' need at 100 shots (about 1.25, about 1.2% wrong); the rejection reach; the indistinguishable sets named; the residual sensitivity in place of the 99.9% that could not fail |
| vendor/README.md, vendor/selene-2025/README.md (check-4 round) | final_request.py's frozen G and new outputs; the selene-2025 Q8 section says G and k are fixed and the band test's range |
| vendor/selene-2025/manifest_sha256.json, vendor/manifest_sha256.json (check-4 round) | Regenerated after the README and script changes; selene-params/ byte-identical |

Note on vendor/selene-params/README.md (first left as run; corrected later in this release with the owner's approval,
see the end of this file): its line "the angle dependence of two-qubit error
(its parameters are unpublished …) could be added if the parameters were published" is out of date. Quantinuum's emulator
documentation publishes those parameters for its default noise models of 2025-07-16 (H2-1E, H2-2E) and 2025-11-18
(Helios-1E) (vendor/results/quantinuum-2025/emulator_defaults.json); the repository's table these runs used has none.
README finding 28 says so.

## Added

| Path | What |
|---|---|
| vendor/scripts/review_figures.py, vendor/results/review_figures.json | Wrong acceptances in the worked example with their Clopper-Pearson interval (2 of 10; 0.025 to 0.556); the trust check's and check 1's false alarms (findings 14 and 16); the Q9 circuits' product-state start and energy error; the Q7 circuits' exact distance; family C's certified gap at 24 to 60 variables; which scale-up instances the router sends out (A and C at 60 only: not proved, edge answer more than 1% above the bound); the IonQ emulator's 30% point by fit; the pulse-code growth rates |
| vendor/scripts/kingston_forecast.py, vendor/results/verify/kingston_forecast.json | The ibm_kingston forecast (median 0.638 over 22 circuits), recomputed from its public record at open-standards 2356016cc |
| vendor/scripts/quantinuum-2025/emulator_defaults.py, vendor/results/quantinuum-2025/emulator_defaults.json | The dates of Quantinuum's emulator default parameters (H2-1E and H2-2E 2025-07-16, Helios-1E 2025-11-18) and whether each lists the RZZ angle fit, read from saved pages named by SHA-256 (not copied) |
| vendor/selene-2025/ | Selene 0.3.8 runs, 17 November 2026, of all 84 Quantinuum core circuits and the 44 extension programs under the default noise parameters of Quantinuum's H2-1E and H2-2E (2025-07-16) and Helios-1E (2025-11-18) emulators, with dephasing left out and at an assumed 71 ms per two-qubit layer (emulator simulations; finding 28). The circuits are vendor/selene-params/builder.tar.xz, byte-identical to the run's builder/, so not copied |
| vendor/selene-2025/README.md | What was run, how each documented term is held, the results, Q8 with Selene's shares as the truth, the files, and what was left out |
| vendor/selene-2025/params/ | The three parameter sets read from the saved emulator pages by make_params_2025.py, mapping.json (every documented row to the plugin or why not), the circuit lists |
| vendor/selene-2025/plugin/ | The error-model plugin (rust/lib.rs, Cargo.toml, Cargo.lock), its Python wrapper, the built library's SHA-256, and the SHA-256 of the selene-core sources it builds against (not copied) |
| vendor/selene-2025/scripts/ | The run's scripts, as run, except host_setup.sh, whose default uv path was replaced by `uv`; the drafting scripts (build_drafts.py, check_draft.py) are left out |
| vendor/selene-2025/controls/ | Positive controls against closed forms and their re-run at fresh seeds, logs, and inputs; the 21 job files' paths made relative to the work folder |
| vendor/selene-2025/results/ | selene_results.json, per_circuit.csv, summary.json, q8_power.json and the scripts' printed outputs (the run's drafts of application text are left out). analyze.py, q8_power.py and summarize.py rerun from this folder reproduce them (two keys can change order) |
| vendor/selene-2025/env/ | The corpus lock and the frozen environment as built |
| vendor/selene-2025/runs.tar.xz | All 972 job outputs, archived with numeric owner 0 and a fixed time; every file matches its line in sources/full-run-MANIFEST.sha256 |
| vendor/selene-2025/sources/ | full-run-MANIFEST.sha256 (all 2,357 files of the run folder) and docs-quantinuum.sha256 (the saved Quantinuum pages, listed and not copied) |
| vendor/selene-2025/manifest_sha256.json | SHA-256 of every file in the folder except itself (86 files) |

# Changes to this copy of the package (qcup-final, 16 November 2026)

This copy is ~/wai-ci-tools/qcup-revision/package with the evidence the final application cites. The original
qcup_application folder is untouched. Nothing under results/ changed, so aggregate.py, results/summary.txt, the figures
and results/manifest_sha256.json are unaffected (the manifest was rechecked and still matches).

## Added

| Path | What |
|---|---|
| vendor/ibm-check/ | The first IBM device check (hardware): sealed preregistration, design and scripts, device results, the independent re-score, unmodified; a new README; derived/derived.py and derived.json for the as-compiled figures the application quotes. Replaces vendor/ibm-prereg/ |
| vendor/scripts/ladder_budget.py; vendor/results/ibm/ladder_budget.json, ladder_design.json | The IBM Aim 2 ladder to 234 CZ, placed as the check placed its circuits and costed by its sealed budget.py (run on a build host) |
| vendor/scripts/quantinuum_sets.py; vendor/results/models/quantinuum_sets.json | Per-circuit budgets under all eight published Quantinuum H2 figure sets (run on a build host) |
| vendor/scripts/quantinuum-2025/, vendor/results/quantinuum-2025/ | The 2025 Quantinuum figure check (fits of Quantinuum's raw data, validation, model drive), copied from qcup-quantinuum-2025 |
| vendor/scripts/iqm/, vendor/results/iqm/ | The IQM Resource Calculator estimate, price list and mock-of-Emerald records, copied from qcup-iqm without ids |
| vendor/selene-params/ | Selene 0.3.8 runs of all 84 Quantinuum core circuits and the 44 extension programs under Quantinuum's published emulator parameters for H2-1 (2024-05-20) and H2-2 (2024-12-06), with our error-model plugin: parameters, plugin, scripts, controls, results, the circuits and every shot as .tar.xz, the original run's SHA-256 manifest (finding 28). Quantinuum's documentation page and the upstream selene-core sources are listed by SHA-256, not copied |

## Changed

| File | Change |
|---|---|
| vendor/scripts/final_request.py | Rewritten for the final request: IBM and IQM Aim 1 at 117 CZ; the Aim 2 ladder to 234 CZ with the e^-b >= 0.30 rule for programs with mid-circuit measurement or reset; the Quantinuum figure set as a parameter (default H2-1, 20 October 2026); the actinide circuits counted once, at 100 shots; IQM credits by the Resource Calculator; IBM minutes with a cross-check against the device check's charged time; totals per period. Positive controls: the 2023 and 2024 sets reproduce admission.json's carried-over rule, and the calculator reproduces 873.1 credits for the earlier IQM set |
| vendor/results/final_request.json | Output of the script above |
| vendor/scripts/iqm/estimate.py, mock_run.py | Paths made relative to the package; estimate.py's check against final_request.json's table replaced by a check of the earlier set's size (it prices the earlier set, which final_request.json now supersedes). Rerun: estimate.json identical |
| vendor/scripts/iqm/_tok.py | Reads IQM_TOKEN from the environment in place of a local keychain item |
| README.md | Header (one device result); findings 11, 21 and 22 marked superseded where they are; findings 23 to 28 added; the Quantinuum request paragraph points to finding 28; Selene's fit given as 0.145% per gate (0.14454 to three decimals; it read 0.144%); Limits updated |
| vendor/README.md | Device result and new evidence listed; what is left out; how to run |

## After the final independent check (16 November 2026)

- vendor/ibm-check/derived/derived.py and derived.json: adds the five-step programs against the budget script (measured
  -ln F over -ln e^-b: 1.35 to 3.06 on 6 programs; not preregistered).
- vendor/ibm-check/README.md: the interval as the sealed analysis gives it (up to 261; 269 in the re-score), Q5's rule
  stated (alternate programs in the package's name order, F >= 0.01), the mid-circuit observation labelled as not
  preregistered.
- README.md: a note before "Hardware request" that it records the pre-check request (finding 26 is current); finding 23's
  interval, Q5 rule and labels; finding 25's kept-row wording (H2-2's August 2025 and October 2026 sets admit 3 and 1 more).

## Removed

- vendor/ibm-prereg/ (its two files are in vendor/ibm-check/, unmodified).

## Privacy check of this copy (16 November 2026)

Scanned every file for e-mail addresses, absolute paths with a user name, IBM CRNs, account, instance, submitter, project,
organization and user ids, API keys and tokens, estimate_context, UUIDs, and IQM job, calibration and device ids. Found:
- no key, token, CRN, account, instance, submitter, project or organization id, and no absolute path with a user name;
- e-mail: only the Institute's public contact address (relax_quantum.py and its demo receipt), as before;
- "crn:v1" only inside the redaction patterns of the sealed IBM scripts; estimate_context only as a word in README text;
- "dcharlot" only in the public GitHub organization name in aim1/Cargo.toml and neuro/Cargo.toml, as before;
- UUIDs: receipt ids in results/relax_quantum_demo.json (generated); IBM's usage-metric id in the check's metrics files;
  and IBM's open-plan id in the sealed submit.py, a plan identifier and not an account or instance id;
- a build-host volume path (/Volumes/..., no user name) in the sealed run_predict.sh and run_rest.sh;
- IBM job ids in the check's job records, counts and analyze.out: not account, submitter or project ids; analyze.py
  needs them to rerun.
The sealed IBM scripts name a local keychain item and a provider-registry path (~/.config/...) but hold no key or id; they
stay unmodified because prereg.txt hashes them.

# Earlier changes (qcup-revision, 15 November 2026)


This is a copy of `qcup_application/qcup-routing/`, made so that every figure the revised application adds traces to a
file in the package. The original folder is untouched. Nothing under `results/` changed, so `aggregate.py`,
`results/summary.txt`, the figures and `results/manifest_sha256.json` are unaffected and were not re-run.

## Why a package change was needed

The revised application quotes the vendor checks (IonQ emulator, IonQ cost estimates, device models from the makers'
figures, IBM calibration model, Selene with H2 noise) and a final request that moves the transition-metal circuits to
Quantinuum, adds the actinide test and merges the three identical H2 rows. None of that was in the package; it lived in
`~/wai-ci-tools/qcup-emulators/`. HANDOFF rule: every figure in the application traces to a result file in the package.

## Changed files

| File | Change |
|---|---|
| README.md | Request-cost note rewritten (the IonQ request is emulator-backed; Quantinuum's Nexus emulators were not run); finding 11 marked superseded; findings 19 to 22 added; Limits line on vendor emulators corrected |
| cost.py | Docstring only: IonQ's own estimates supersede the IonQ figures, and final_request.json is the stated request |
| aim1_request.py | Docstring only: trapped-ion rows are re-admitted per circuit in vendor/ |

## Added files

| File | What |
|---|---|
| vendor/README.md | What every file is, the labels, the corrections that apply, what was left out |
| vendor/scripts/*.py, ionq.sh | The builder's scripts and the checker's scripts (verify_*.py) |
| vendor/scripts/final_request.py | New: the request as the application states it |
| vendor/scripts/selene_fit.py | New: the Selene trace-fidelity fit, by the method of aggregate.py (the fit quoted in the builder's report was not stored) |
| vendor/results/ | Result summaries copied from the vendor checks, plus final_request.json and models/selene/selene_fit.json produced here |
| vendor/ibm-prereg/predictions.json, prereg.txt | The sealed predictions of the first IBM check (read only, unmodified; sha256 of predictions.json 1f742146…cd05, as prereg.txt records) |
| vendor/manifest_sha256.json | SHA-256 of every file in vendor/ |

## Corrected after the run

- `vendor/results/ionq/not_emulated_rows.json`: the reason field of the 34 five-step rows read "mid-circuit measurement or
  reset (IonQ refuses both)". It now reads "mid-circuit measurement or reset (could not run under IonQ's noise model)".
  The refusal reason was refuted by the independent check (VERIFY item 4); no other field changed.
- `vendor/scripts/ibm_reads.py`, `iqm_reads.py`, `ionq.sh`, `ionq_api.py`, `ionq_run.py`: key handling only. They read
  `IBM_API_KEY` and `IBM_INSTANCE_CRN`, `IQM_TOKEN` and `IONQ_API_KEY` from the environment, in place of named items in a
  local keychain and a local config file. The requests they send are unchanged.

## Re-run

- `vendor/scripts/final_request.py`, on a build host under a memory guard, in a scratch folder deleted afterwards. It wrote
  `vendor/results/final_request.json`: 2,380 circuits, 4,778,700 shots; IBM at most 26.0 minutes (588 IBM Aim 1 QAOA
  circuits, 150 to 424 at the calibration models' 30% points); IonQ core 940.4 credits (1,646,000 two-qubit gate-shots;
  0.87 hours of IonQ's estimated execution); Quantinuum core 84 circuits and 4,309.3 HQC on its newest published figures
  (re-admitted rows 2,695.4, transition-metal circuits 1,208.9, actinide test at 50 shots 405.0), against 15,861.4 first
  drafted; extension 44 circuits, 510.3 credits, 2,868.5 HQC (37 circuits and 7,317.0 HQC on the 2023 figures).
- `vendor/scripts/verify_readmit.py` reproduced the checker's `readmit.json` exactly (66 of 130 IonQ and 72 of 93
  Quantinuum core rows; 2,695.4 HQC, the 2023 edge of final_request.json). Run earlier on a build host.
- `vendor/scripts/selene_fit.py` wrote `selene_fit.json`: 0.1445% per two-qubit gate, R2 0.988, 30% at 818 gates, on the
  21 of 25 programs with at least 20 correct traces. Run earlier on a build host.

## Not changed, on purpose

- `aim2_request.py` still admits IonQ five-step programs up to 300 gates; the IonQ restriction to one-step programs
  within 147 gates is applied in `vendor/scripts/final_request.py`, so cost.py, cost.json and the README's "78 on IonQ"
  stay consistent with each other as the pre-check request.
- `chem.py` and `targets.py` still assign circuits as before (H2 three times; transition-metal circuits to IonQ); the
  merge and the move are applied in final_request.py.
- `results/targets/request.json` counts Nm as the qubit count (measurements only) and gives 1,539 HQC for the actinide
  circuits; final_request.py uses cost.py's convention (Nm = 2 x qubits, as for every other Aim 1 circuit), 1,560 HQC.

## Privacy check of this copy (15 November 2026)

Scanned every text file for e-mail addresses, absolute paths with a user name, IBM CRNs, account, submitter, project and
organization ids, API keys and estimate_context. Found: no absolute user paths, CRNs, ids or keys; estimate_context only
as a word in README finding 20. Two items predate this revision and were left as they are: the Institute's public
contact address in `relax_quantum.py` and `results/relax_quantum_demo.json` (the receipt issuer), and the public GitHub
organization URL in `aim1/Cargo.toml` and `neuro/Cargo.toml`. Raw IonQ responses, the IonQ job ledger, IonQ's private
estimate context and IQM account records were never copied.

- 2026-11-16, owner: the receipts' issuer contact is the PI's own address, david@physicalai-bmi.org, replacing contact@physicalai-bmi.org (relax_quantum.py and results/relax_quantum_demo.json; results/manifest_sha256.json updated).

## vendor/selene-params/README.md corrected (17 November 2026, owner's approval)

Its note on what the 2024 run could not represent said the angle dependence of two-qubit error was unpublished. That
was true only of the hardware-specifications repository's table the run used: Quantinuum's emulator documentation
publishes the angle-scaling parameters (przz_a to przz_power) for its defaults of 2025-07-16 (H2-1E, H2-2E) and
2025-11-18 (Helios-1E), recorded in vendor/results/quantinuum-2025/emulator_defaults.json. The sentence now says so; the
2024 run's results are unchanged. Checksums updated in selene-params/manifest_sha256.json and vendor/manifest_sha256.json.

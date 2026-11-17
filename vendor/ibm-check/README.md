# vendor/ibm-check: the first IBM device check (hardware)

Status: run. 24 circuits from the request ran on ibm_marrakesh on 16 November 2026 (UTC), in two arms, under IBM's free
open plan; no QCUP time was used. The predictions and the analysis code were sealed by hash before the run. The design
stage's own README said "Not submitted"; that described the state before the owner approved the submission and no longer
holds.

| Time (UTC) | Step | Record |
|---|---|---|
| 2026-11-15 23:50 | First device read for the design | (kept out: it carries account identifiers) |
| 2026-11-16 01:17:34 | Predictions sealed | prereg.txt (`sealed_utc`), sha256 of predictions.json 1f742146…c0cd05 |
| 2026-11-16 08:17:30 | As-compiled arm sent (job tags carry the prereg hash) | run/raw/metrics-dd_off.json |
| 2026-11-16 08:36:32 | As-compiled arm finished; 15 s of QPU time charged for 42,000 shots | run/raw/metrics-dd_off.json |
| 2026-11-16 08:38 | Scored by the sealed analyze.py | run/analyze.out, run/analysis.json |

## What is here

| Path | What it is |
|---|---|
| prereg.txt, predictions.json | The preregistration: predictions of every sealed model for every circuit, the analysis plan, and the sha256 of every file below that was fixed before the run. Unmodified. |
| design/ | design.json (circuits, layouts, executed CZ counts), the submitted OpenQASM 3 for each backend and arm with its manifest, the form order, the design-time calibrations and the model outputs (pred/). Unmodified; every hash in prereg.txt and every entry in qasm_manifest_sha256.json matches. |
| scripts/ | The sealed scripts (design, predict, budget, fitlib, assemble, submit, fetch, analyze, ibm_read). Unmodified, so they still name the local keychain item and provider registry they read the key and instance from; neither the key nor any instance or account identifier is in the package. |
| run/ | Device results: raw Sampler results for both arms, IBM's metrics (timestamps and charged time), the job records analyze.py reads (backend, arm, job id, time sent), the decoded counts, the calibration at submission, analyze.out and analysis.json. Unmodified. Job reads with user or instance fields, usage reads and logs are left out. |
| rescore/ | The independent re-score: a separate decoder and scorer, noiseless replays of the submitted QASM as a positive control, refits with a 4,000-draw bootstrap, and the per-circuit comparison of every sealed model with the measurements (scripts/, out/). Unmodified. |
| derived/ | derived.py and derived.json: the as-compiled figures the application quotes that the analysis prints but does not store (excess loss over the calibration simulation, reset failure on the zero-CZ control, QAOA share of ideal kept, five-step programs against the budget script). Added in this revision. From 17 November 2026 also Q5's gate-count form under the second form's exclusions (2.26 on 8 predictions; 3.03 floor-corrected; not preregistered) and the calibration's age at the run (2.62 days). |

## Result (as-compiled arm; the application quotes nothing else from the decoupled arm but its failed control)

- Controls passed: the zero-CZ program 0.860 (pass mark 0.85) and the mirror circuit 0.856 (0.80).
- Per circuit, measured over predicted -ln F, median over programs: the budget script's e^-b 0.91, the only sealed model
  whose implied 30% point lies inside the device's 95% interval; every other model 2.3 to 3.9.
- The 30% point is bounded: 117 CZ by the preregistered rule (95% interval -273 to 261 in the sealed analysis's 2,000 bootstrap draws; -276 to 269 in the re-score's 4,000), 258 without intercept,
  85 floor-corrected. Above 200 CZ the programs score near what a scrambled output gives, so these points set the slopes.
- Q5 held-out factor 2.19 against 1.25 (alternate programs in the package's name order, F >= 0.01): falsified, above the
  1.31 to 1.45 the sealed calibration models with idle error implied.
- Not preregistered: the largest extra loss came with mid-circuit measurement and reset. Reset failure is 3.5% to 5.3% per
  step on the zero-CZ control; the six five-step programs lose 3.4 to 8.7 times the calibration simulation's error, against
  1.7 to 2.3 times for circuits without mid-circuit measurement that score well above a scrambled output, and 1.4 to 3.1
  times the budget script's error, so the budget script is optimistic for them.
- The decoupled arm's zero-CZ control scored 0.828 against 0.85, so by the preregistration that arm is not interpreted.
- The three controls' targets read the same backwards, so they could not catch a reversed bit order; the re-score checked
  bit order directly (every non-palindromic target scores 0.000 to 0.078 reversed). Future controls should use targets that
  read differently backwards.

Rerun the analysis from a copy of this folder: `python3 -I scripts/analyze.py .` (it reads run/job-*.json and run/raw/ and writes
analysis.json beside prereg.txt); on 16 November 2026 it reproduced run/analyze.out and run/analysis.json exactly. Rerun the
derived figures: `python3 -I derived/derived.py .`

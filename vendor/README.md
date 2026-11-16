# vendor/: the vendor checks behind the hardware request

Run 15 and 16 November 2026 (findings 19 to 28 of the package README). One folder holds a device result: ibm-check/, the
first IBM device check (hardware, IBM's free open plan). Everything else is one of these kinds of evidence, each labelled
where it is used:

- **Emulator**: IonQ's cloud simulator under its Forte noise model (no charge; no QPU job was run).
- **Device models**: error budgets built from the makers' figures (Quantinuum's published H2-1 data of 2023-03-10,
  IonQ's Forte characterization of 2026-11-14) and from IBM's calibrations of 2026-11-13 (ibm_kingston, ibm_fez,
  ibm_marrakesh). A model is not a device.
- **Selene**: Quantinuum's open-source emulator, with its depolarizing model set to the H2 figures (results/models/selene/),
  and with Quantinuum's published emulator parameters for H2-1 and H2-2 plus our plugin for the terms it lacks
  (selene-params/, finding 28).
- **IQM mock**: IQM Resonance's mock of Emerald, priced at 0; it returns random bits, so it checks compilation and time.
- **Fits of published raw data**: our own fits of Quantinuum's 2023 to 2025 benchmark data (quantinuum-2025/).

## What is here

| Path | What it is |
|---|---|
| scripts/build_circuits.py, to_native.py | Rebuild every trapped-ion request circuit from the package and write OpenQASM 3, IonQ JSON and IonQ native-gate JSON |
| scripts/ionq_api.py, ionq_run.py, ionq.sh, score_ionq.py, fetch_compiled.py | IonQ REST client, emulator runs, scoring, compiled-circuit reads |
| scripts/models.py, sim_aim2.py, crosscheck.py, wai_suite.py, analyze.py | Device models from the makers' figures, Aer simulation of Aim 2 under them, the cross-check against a second implementation, the re-admission analysis |
| scripts/ibm_reads.py, ibm_sample.py, ibm_budget.py, ibm_analyze.py | IBM calibration reads (no job submitted) and the calibration-model analysis |
| scripts/selene_noisy.py, selene_fit.py | Selene runs with H2-matched noise, and the trace-fidelity fit (selene_fit.py added in this revision; the fit was not stored before) |
| scripts/iqm_reads.py | IQM price and backend reads (nothing submitted) |
| scripts/verify_*.py | The independent checker's scripts: re-admission, refit of the IonQ emulator law, IBM rerun, simulation of the sent circuits, IonQ probes |
| scripts/final_request.py | The request as the final application states it (finding 26); `--qset` picks the Quantinuum figure set (default H2-1, 20 October 2026) |
| results/final_request.json | Output of final_request.py: IBM and IQM admission at the device check's cap and the Aim 2 ladder, trapped-ion re-admission on every published Quantinuum set, the actinide and transition-metal circuits, the merged H2 rows, the table, costs per vendor and per period, IQM credits by the Resource Calculator |
| scripts/ladder_budget.py, results/ibm/ladder_budget.json, results/ibm/ladder_design.json | The IBM Aim 2 ladder: every program to 234 CZ placed on ibm_marrakesh as the device check placed its circuits and costed by the check's sealed budget.py (finding 24) |
| scripts/quantinuum_sets.py, results/models/quantinuum_sets.json | Per-circuit budgets under all eight published Quantinuum H2 figure sets, by models.py's own rules (finding 25) |
| scripts/quantinuum-2025/, results/quantinuum-2025/ | The 2025 figure check: randomized-benchmarking fits of Quantinuum's raw data, validation against the 51 published values, the model drive and its summaries |
| scripts/iqm/, results/iqm/ | IQM's Resource Calculator estimate for the earlier set, IQM Resonance's price list (no ids), the mock-of-Emerald job plan, job metrics and runtime estimates (no job, calibration or device ids) |
| results/ionq/ | Emulator scores, IonQ's cost estimates and the comparison with cost.py, compiled gate counts, run plans |
| results/models/ | Per-row admission, per-circuit predictions, the revised request before this revision, simulations, Selene results and fit, cross-check |
| results/ibm/, results/verify/ibm_analysis_rerun.json | IBM calibration analysis; the rerun is the current one (VERIFY item 8) |
| results/verify/ | The checker's recomputations: readmit.json, refit_ionq.json, sim_sent_aim2.json, ibm_leading_idle.json |
| results/analysis.json | The builder's summary of every check |
| results/circuits/ | Index of the 331 circuits, their OpenQASM 3 files and a SHA-256 manifest of the full circuit set (the IonQ JSON forms and score files listed in it are not copied; build_circuits.py and to_native.py regenerate them; in the pinned environment the gate pairs and their order rebuild exactly, but not every one-qubit gate, nor the chemistry circuits' RZZ angles: selene-params/rebuild/) |
| ibm-check/ | The first IBM device check: the sealed preregistration and design, the sealed scripts, the device results, the independent re-score and the derived figures (README there). Replaces ibm-prereg/, which held only the two sealed files |
| selene-params/ | Selene 0.3.8 runs of all 84 Quantinuum core circuits and the 44 extension programs under Quantinuum's published emulator parameters (H2-1 2024-05-20, H2-2 2024-12-06): parameters and their mapping, the error-model plugin, scripts, positive controls, results, and every shot (runs.tar.xz) (finding 28; README there) |
| manifest_sha256.json | SHA-256 of every file in this folder except itself |

## Corrections that apply to files kept as run

- results/ionq/not_emulated_rows.json: the reason for the 34 five-step rows was first recorded as "IonQ refuses both".
  That reason is withdrawn, and the field was corrected after the run to "could not run under IonQ's noise model": IonQ's JSON format has no measure or reset instruction,
  and every OpenQASM 3 job under the Forte noise model failed, including one with no mid-circuit measurement. IonQ's
  documentation says its simulator supports mid-circuit measurement (checker's report, item 4).
- results/models/revised_request.json is the builder's request before this revision; results/final_request.json
  supersedes it (transition-metal circuits moved to Quantinuum, actinide test added, H2 rows merged).
- results/ibm/ibm_analysis.json is the builder's IBM analysis; results/verify/ibm_analysis_rerun.json is the current one.
- The IonQ emulator 30% point (about 147 gates) comes from a fit on the 21 programs at least twice the guessing floor;
  see results/verify/refit_ionq.json for the other fits (127 to 155, and 390 by the plain rule).

## Left out on purpose

Raw IonQ responses (they carry submitter and project identifiers), IonQ's private estimate context, the IonQ job ledger
(job identifiers), IQM account records and raw job answers (job, calibration and device ids), the IBM check's account
reads, usage reads and logs, Quantinuum's papers and raw data (public: its repository at commit 59e68bb), and a helper
script with an absolute local path.

## Running

Scripts are kept as they were run, with paths relative to the working folder they ran in (~/wai-ci-tools/qcup-emulators),
except for key handling: after the run, ibm_reads.py, iqm_reads.py, ionq.sh and ionq_api.py were changed to read their keys
from environment variables (IBM_API_KEY and IBM_INSTANCE_CRN, IQM_TOKEN, IONQ_API_KEY) in place of a local keychain and
config file; scripts/iqm/_tok.py likewise reads IQM_TOKEN. The IBM check's sealed scripts are unmodified (their hashes are
in its prereg.txt), so they still name the local keychain item and registry they read from. Nothing here holds a key.
final_request.py, selene_fit.py, scripts/iqm/estimate.py and ibm-check/derived/derived.py run from the package with no
account: `python3 vendor/scripts/final_request.py .`. ladder_budget.py and quantinuum_sets.py need Qiskit and the gate
lists respectively (their docstrings say how); both ran on a build host.

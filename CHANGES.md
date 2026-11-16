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

## After the final independent check (verify/VERIFY-final.md, 16 November 2026)

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

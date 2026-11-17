# Licences

**Code: Apache-2.0** (LICENSE). This covers the Python, shell and Rust sources, including vendor/scripts/, the scripts
under vendor/ibm-check/, vendor/selene-params/ and vendor/selene-2025/, and the error-model plugins in
vendor/selene-params/plugin/ and vendor/selene-2025/plugin/.

**The author's other material: CC0 1.0** (https://creativecommons.org/publicdomain/zero/1.0/). This covers result files,
figures, circuits, instance definitions, the sealed preregistration, device counts, emulator outputs and documentation,
under results/ and vendor/.

**Material from others is covered by neither and keeps its own terms:**

- vendor/selene-params/params/Emulator_parameters.csv is Quantinuum's emulator parameter table, notebooks/Emulator
  parameters.csv in its quantinuum-hardware-specifications repository at commit 59e68bb, under Apache-2.0 (the licence
  text in LICENSE). It is copied unchanged apart from its file name (SHA-256
  93ce7fdd7045f09e94737024d5a744c2e982b91ba9891c97fd417c4dff58915f in both).
- The IBM backend configuration and properties files under vendor/ibm-check/design/calibration/ and
  vendor/ibm-check/run/calibration_at_submission/ are IBM's calibration data, kept as its service returned them.
- vendor/results/iqm/prices.json records IQM Resonance's prices and limits, read from its service at the time the file
  gives.
- vendor/selene-2025/params/*.json hold the default noise parameters read from Quantinuum's emulator documentation
  pages (listed by SHA-256 in vendor/selene-2025/sources/docs-quantinuum.sha256, not copied); params/mapping.json quotes
  short passages of those pages, which keep Quantinuum's terms.

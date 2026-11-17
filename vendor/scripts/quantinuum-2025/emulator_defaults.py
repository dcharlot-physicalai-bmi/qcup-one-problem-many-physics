"""Which default noise parameters Quantinuum's emulator documentation lists, and their dates (writes
vendor/results/quantinuum-2025/emulator_defaults.json). Added 17 November 2026 for the application's Quantinuum wording.

Quantinuum's pages are not copied into this package (as for its Performance Validation page); they were saved on
17 November 2026 and are named here by SHA-256:
  docs.quantinuum.com/systems/user_guide/emulator_user_guide/emulators/h2_emulators.html      (qe_h2_emulators.html)
  docs.quantinuum.com/systems/user_guide/emulator_user_guide/emulators/helios_emulators.html  (qe_helios_emulators.html)
  docs.quantinuum.com/systems/user_guide/emulator_user_guide/noise_model.html                 (qe_noise_model.html)
From each emulator page this reads every tab of "Default Noise Model Parameters": the tab's emulator name, the table's
caption (its date), and whether the table gives the angle-scaling fit of RZZ error (przz_a to przz_d, przz_power).
The H2 page captions both its H2-1E and its H2-2E tab "H2-1E emulators from 2025-07-16"; the H2-2E tab's own values
follow its label, so the date is taken as that tab's. The repository table the runs of finding 28 used
(quantinuum-hardware-specifications at 59e68bb, notebooks/Emulator parameters.csv) ends at H2-1 2024-05-20 and H2-2
2024-12-06 and has no przz columns; that is recorded from the README of vendor/selene-params, not re-read here.
Usage, from the package root: python3 -I vendor/scripts/quantinuum-2025/emulator_defaults.py . SAVED_PAGES_DIR"""
import hashlib, json, os, re, sys
B, D = sys.argv[1], sys.argv[2]
EXPECT = {"qe_h2_emulators.html": "5172975988d92446d4ce8890dc12e0ce136edbf6215cee5b9732d97e153ffd4a",
          "qe_helios_emulators.html": "8763eccf379a19da1312c7e060f6c7103ec8b044276c18d51c6dc06dbbdafaaa",
          "qe_noise_model.html": "8688e17aa44f6ad61d28c89fa1df258bef1871171536f93689f0c203279d6b76"}
out = {"pages": {}, "defaults": []}
for f, h in EXPECT.items():
    raw = open(os.path.join(D, f), "rb").read(); got = hashlib.sha256(raw).hexdigest()
    assert got == h, (f, got); out["pages"][f] = got
    if "emulators" not in f: continue
    t = raw.decode("utf-8"); body = t.split("<script", 1)[0] if "Default Noise Model Parameters" in t.split("<script", 1)[0] else t
    tabs = list(re.finditer(r'<label class="sd-tab-label"[^>]*>\s*([^<]+?)\s*</label>', body))
    for i, m in enumerate(tabs):
        seg = body[m.end(): tabs[i + 1].start() if i + 1 < len(tabs) else len(body)]
        cap = re.search(r'<span class="caption-text">([^<]+)</span>', seg)
        if not cap or "emulators from" not in cap.group(1): continue
        out["defaults"].append({"page": f, "tab": m.group(1), "caption": cap.group(1), "date": re.search(r"(\d{4}-\d{2}-\d{2})", cap.group(1)).group(1),
                                "rzz_angle_fit": all(k in seg for k in ("przz_a", "przz_b", "przz_c", "przz_d", "przz_power"))})
nm = open(os.path.join(D, "qe_noise_model.html"), encoding="utf-8").read()
out["noise_model_page_gives_rzz_angle_formula"] = "Parameterized Angle Scaling" in nm and all(k in nm for k in ("przz_a", "przz_b", "przz_c", "przz_d", "przz_{power}"))
out["by_emulator"] = {d["tab"]: d["date"] for d in out["defaults"]}
json.dump(out, open(os.path.join(B, "vendor", "results", "quantinuum-2025", "emulator_defaults.json"), "w"), indent=1)
print(json.dumps(out, indent=1))

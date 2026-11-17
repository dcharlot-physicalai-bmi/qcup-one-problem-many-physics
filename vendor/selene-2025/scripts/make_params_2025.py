"""Selene settings from Quantinuum's documented default emulator noise parameters: H2-1E and H2-2E of 2025-07-16
(System Model H2 Emulators page) and Helios-1E of 2025-11-18 (Quantinuum Helios emulators page), read from the saved
HTML (docs-quantinuum/fetched-2026-11-17/), not typed by hand.

    python3 -I make_params_2025.py DOCS_DIR OUT_DIR

Which table is which. Each page holds its tables in tabs. On the H2 page both tables carry the caption "H2-1E
emulators from 2025-07-16" (the second caption is a typo on the page): the second table sits in the tab labelled
"H2-2E" (<label class="sd-tab-label" for="sd-tab-item-1">H2-2E</label>) and its own first row reads "Default Settings |
H2-2E". This script keys every table by its tab label and checks that the table's first row names the same emulator.

Variants written for each set (the plugin's arguments, plugin/python/qcup_docs_noise.py):
  docs            every documented term the plugin can hold with the documented values. No memory term: the
                  documentation gives dephasing rates (per second) but not the durations they apply to.
  docs_dephasing  the same, plus the dephasing term at an assumed duration of DEPTH1_S seconds per layer of two-qubit
                  gates of Selene's runtime (see DEPTH1_S), in the documentation's incoherent form:
                      p_lin  = linear_dephasing_rate x d
                      p_quad = sin(pi x quadratic_dephasing_rate x coherent_to_incoherent_factor x d)^2
                               (rates "in units of 2 pi radians per second": angle = 2 pi f c d, P(Z) = sin(angle / 2)^2)
                      memory_pz = p_lin + p_quad - 2 p_lin p_quad   (a Z from either, not both)
                  charged per qubit per layer while the qubit holds a state a Z can change (the 2024 run's placement)."""
import json, math, os, re, sys

DOCS, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
PAGES = {"h2": "user_guide_emulator_user_guide_emulators_h2_emulators.html", "helios": "user_guide_emulator_user_guide_emulators_helios_emulators.html"}
# Assumed duration of one layer of two-qubit gates. Quantinuum documents no H2 durations. For Helios it documents a
# time budget for "a depth-1 program with arbitrary qubit permutations and 1Q and 2Q gates on all 98 qubits"
# (Helios Performance Maximization page, figure circuit_time_ms.png, "Total Program Time" about 71 ms; the Helios
# page says such a layer takes 7 gating rounds). The assumption: each layer of Selene's runtime lasts one such
# depth-1 time, on every set. The application's model and the 2024 run likewise charge memory per qubit per layer.
DEPTH1_S = 0.071
NAMES = {"H2-1E": "H2-1E_2025-07-16", "H2-2E": "H2-2E_2025-07-16", "Helios-1E": "Helios-1E_2025-11-18"}
KEY = {  # row label on the page -> parameter name
    "Qubits (Statevector)": "qubits_statevector", "Qubits (Stabilizer)": "qubits_stabilizer", "Connectivity": "connectivity",
    "Parallel 2-qubit operations": "parallel_2q_operations", "Wasm Enabled": "wasm_enabled",
    "1-Qubit Fault Probability (p1)": "p1", "2-Qubit Fault Probability (p2)": "p2",
    "Bit-Flip Measurement Probability (0 outcome) (p_meas)": "p_meas_0", "Bit-Flip Measurement Probability (1 outcome) (p_meas)": "p_meas_1",
    "Crosstalk Measurement Fault Probability (p_crosstalk_meas)": "p_crosstalk_meas", "Initialization Fault Probability (p_init)": "p_init",
    "Crosstalk Initialization Probability (p_crosstalk_init)": "p_crosstalk_init",
    "Ratio of 1-Qubit Spontaneous Emission to p1 (p1_emission_ratio)": "p1_emission_ratio",
    "Ratio of 1-Qubit Spontaneous Emission in 2-Qubit Gate to p2 (p2_emission_ratio)": "p2_emission_ratio",
    "Leakage Probability per Initialization (p_prep_leak_ratio)": "p_prep_leak_ratio", "Seepage Probability per 1-Qubit Gate (p1_seepage_prob)": "p1_seepage_prob",
    "Seepage Probability per 2-Qubit Gate (p2_seepage_prob)": "p2_seepage_prob", "Convert Leakage Errors to Depolarizing Errors (leak2depolar)": "leak2depolar",
    "Quadratic Dephasing Rate (quadratic_dephasing_rate)": "quadratic_dephasing_rate", "Linear Dephasing Rate (linear_dephasing_rate)": "linear_dephasing_rate",
    "Coherent to Incoherent Factor (coherent_to_incoherent_factor)": "coherent_to_incoherent_factor",
    "Fit Parameter 1 (przz_a)": "przz_a", "Fit Parameter 2 (przz_b)": "przz_b", "Fit Parameter 3 (przz_c)": "przz_c", "Fit Parameter 4 (przz_d)": "przz_d",
    "Polynomial (przz_power)": "przz_power"}
SECTIONS = ("General", "Physical Noise", "Leakage Noise", "Dephasing Noise", "Arbitrary Angle Noise Scaling")


def text(x): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip()


def tables(html):
    i = html.find("sd-tab-set"); j = html.find('id="performance"')
    out = {}
    for t in re.split(r"<input ", html[i:j])[1:]:
        label = text(re.search(r'<label class="sd-tab-label"[^>]*>(.*?)</label>', t, re.S).group(1))
        caption = text(re.search(r'<caption>(.*?)</caption>', t, re.S).group(1)).rstrip("¶").strip()
        rows = [[text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)] for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S)]
        assert rows[0] == ["Default Settings", label], (label, rows[0])        # the table names the emulator of its tab
        vals = {}
        for r in rows[1:]:
            if r[0] in SECTIONS: continue
            assert r[0] in KEY, "unknown row %r" % r[0]
            vals[KEY[r[0]]] = r[1]
        out[label] = {"caption": caption, "rows": vals}
    return out


def num(s):
    if s in ("True", "False"): return s == "True"
    try: return int(s)
    except ValueError: pass
    try: return float(s)
    except ValueError: return s


found = {}
for page, f in PAGES.items():
    for label, t in tables(open(os.path.join(DOCS, f), encoding="utf-8").read()).items():
        found[label] = dict(t, page=f)
assert set(found) == set(NAMES), found.keys()
summary = {}
for label, name in NAMES.items():
    T = {k: num(v) for k, v in found[label]["rows"].items()}
    helios = label.startswith("Helios")
    base = {k: T[k] for k in ("p1", "p1_emission_ratio", "p2", "p2_emission_ratio", "przz_a", "przz_b", "przz_c", "przz_d", "przz_power",
                              "p_meas_0", "p_meas_1", "p_init", "p_crosstalk_meas", "p_crosstalk_init")}
    if helios:
        base.update(leakage_model=True, leak2depolar=bool(T["leak2depolar"]), p_prep_leak_ratio=T["p_prep_leak_ratio"],
                    p1_seepage_prob=T["p1_seepage_prob"], p2_seepage_prob=T["p2_seepage_prob"])
    else:
        # "Leakage Noise ... The Helios emulators incorporate leakage noise ... This is not included in H2 emulators."
        base.update(leakage_model=False, leak2depolar=False, p_prep_leak_ratio=0.0, p1_seepage_prob=0.0, p2_seepage_prob=0.0)
    r, f, c = T["linear_dephasing_rate"], T["quadratic_dephasing_rate"], T["coherent_to_incoherent_factor"]
    p_lin = r * DEPTH1_S
    p_quad = math.sin(math.pi * f * c * DEPTH1_S) ** 2
    p_quad_coherent_one_layer = math.sin(math.pi * f * DEPTH1_S) ** 2
    mem = p_lin + p_quad - 2 * p_lin * p_quad
    out = {"name": name, "emulator": label, "source": {"page": found[label]["page"], "tab_label": label, "caption_on_page": found[label]["caption"]},
           "table": T,
           "angle_scale": {"at_0": (T["przz_b"] + T["przz_d"]) / 2, "at_pi_over_4": T["przz_c"] * 0.25 ** T["przz_power"] + T["przz_d"],
                           "at_pi_over_2": T["przz_c"] * 0.5 ** T["przz_power"] + T["przz_d"]},
           "dephasing_assumption": {"seconds_per_two_qubit_layer": DEPTH1_S, "p_linear": p_lin, "p_quadratic_incoherent": p_quad,
                                    "p_quadratic_coherent_single_layer_on_plus_state": p_quad_coherent_one_layer, "memory_pz": mem},
           "plugin_docs": dict(base, memory_pz=0.0), "plugin_docs_dephasing": dict(base, memory_pz=mem)}
    json.dump(out, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
    summary[name] = {k: out[k] for k in ("emulator", "source", "angle_scale", "dephasing_assumption")} | {"p1": T["p1"], "p2": T["p2"]}
print(json.dumps(summary, indent=1))

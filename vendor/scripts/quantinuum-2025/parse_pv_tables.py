"""Extract the per-machine component tables (H2-1, H2-2) and any 'Data collected on' dates from saved copies of
Quantinuum's Performance Validation documentation page. Plain text extraction only. python3 -I parse_pv_tables.py FILE..."""
import re, sys, html, json
ROWS = ["1-Qubit Gate Error", "1-Qubit Gate Leakage Error", "2-Qubit Gate Error", "2-Qubit Gate Leakage Error",
        "Memory Error per Depth-1 Circuit Time", "Measurement Crosstalk Error", "SPAM Error (0)", "SPAM Error (1)", "SPAM Error",
        # labels used by the page in mid-2025
        "1-qubit Gate Error", "1-qubit Leakage Error", "2-qubit Gate Error", "2-qubit Leakage Error", "1-qubit Memory Error",
        "MCMR Crosstalk Error", "Measurement Error (0)", "Measurement Error (1)"]
out = {}
for f in sys.argv[1:]:
    t = open(f, encoding="utf-8", errors="replace").read()
    dates = sorted(set(re.findall(r"[Dd]ata collected on (\d{4}/\d{2}/\d{2})", t)))
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S); t = re.sub(r"<[^>]+>", "\n", t); t = html.unescape(t)
    toks = [x.strip() for x in t.split("\n") if x.strip()]
    res = {}
    for i, tok in enumerate(toks):
        if tok in ("H1-1", "H2-1", "H2-2", "reimei", "Helios-1") and i + 2 < len(toks) and toks[i + 1] == "Infidelity":
            m = {}; j = i + 3
            while j + 2 < len(toks) and toks[j] in ROWS:
                m[toks[j]] = [toks[j + 1], toks[j + 2]]; j += 3
            res.setdefault(tok, m)
    out[f.split("/")[-1]] = {"tables": res, "data_collected_on": dates}
    print(f.split("/")[-1], "dates:", dates)
    for mach in ("H2-1", "H2-2"):
        print("  ", mach, json.dumps(res.get(mach)))
json.dump(out, open(sys.argv[1].rsplit("/", 1)[0] + "/parsed_tables.json", "w"), indent=1)

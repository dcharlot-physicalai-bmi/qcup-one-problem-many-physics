"""The second sealed IBM forecast, of 22 circuits on ibm_kingston (technical report doi:10.5281/zenodo.24285994, Section
3.2), recomputed from its public record (writes vendor/results/verify/kingston_forecast.json).

The forecast's receipts, the device's counts and the per-circuit table are in the open-standards repository at commit
2356016cc, wai/wai-quantum/tests/data/forecasts/2026-11-15/ (public at gitlab.com/transaction-science-group/open-standards).
This script reads that folder's README with `git show`, takes each circuit's predicted and measured figure, recomputes the
ratio of predicted to measured error (-ln F) from them, checks it against the table's own ratio (the table gives the
figures to four decimals, so the recomputed ratio is compared within 0.02), and reports the median ratio over the circuits
with signal, the count, and the inverse. It also records the git blob id of every file in the folder.
Usage, from the package root: python3 -I vendor/scripts/kingston_forecast.py . [OPEN_STANDARDS_CHECKOUT]
(default checkout: $QCUP_OPENSTD or ~/data-share/vibe-coding/open-standards)"""
import json, math, os, re, statistics as st, subprocess, sys
B = sys.argv[1] if len(sys.argv) > 1 else "."
OS = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else os.environ.get("QCUP_OPENSTD", "~/data-share/vibe-coding/open-standards"))
COMMIT, FD = "2356016cc", "wai/wai-quantum/tests/data/forecasts/2026-11-15"
def git(*a): return subprocess.run(["git", "-C", OS, *a], capture_output=True, text=True, check=True).stdout
readme = git("show", f"{COMMIT}:{FD}/README.md")
rows = []
for m in re.finditer(r"^\| ([a-z0-9-]+) \| ([0-9.]+) \| ([0-9.]+) \| ([0-9.]+) \| (-?[0-9.]+) \| ([0-9.]+) \|$", readme, flags=re.M):
    name, pred, meas, sd, z, ratio = m.group(1), *map(float, m.groups()[1:])
    rec = math.log(pred) / math.log(meas)
    assert abs(rec - ratio) < 0.02, (name, rec, ratio)
    rows.append({"circuit": name, "predicted": pred, "measured": meas, "sd": sd, "z": z, "ratio_table": ratio, "ratio_recomputed": round(rec, 4)})
assert len(rows) == 22, len(rows)
stated = re.search(r"Median ratio ([0-9.]+) .*?over (\d+) of (\d+) circuits with signal", readme)
med = st.median(r["ratio_table"] for r in rows)
assert f"{med:.3f}" == stated.group(1), (med, stated.group(1))
tree = git("ls-tree", "-r", COMMIT, FD)
out = {"source": f"open-standards {COMMIT}:{FD}/README.md", "commit": git("rev-parse", COMMIT).strip(),
       "files": {l.split("\t")[1].split("/")[-1]: l.split()[2] for l in tree.strip().split("\n")},
       "circuits": len(rows), "with_signal": int(stated.group(2)), "median_ratio_predicted_over_measured_error": round(med, 4),
       "median_ratio_from_recomputed": round(st.median(r["ratio_recomputed"] for r in rows), 4),
       "inverse_median": round(1 / med, 3), "abs_z_over_3": sum(1 for r in rows if abs(r["z"]) > 3), "rows": rows}
os.makedirs(os.path.join(B, "vendor", "results", "verify"), exist_ok=True)
json.dump(out, open(os.path.join(B, "vendor", "results", "verify", "kingston_forecast.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))

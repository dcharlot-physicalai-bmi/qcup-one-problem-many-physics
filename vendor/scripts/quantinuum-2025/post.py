"""Follow-ups on model_drive.py's output: which rows each figure set adds to the 72-row core, whether the kept sets
nest, and the Q8 actinide rule (final_request.py's method and seed) at 50, 100 and 200 shots with its HQC.

    python3 -I post.py MODELS_PY EMU_BASE PKG_ROOT FITS_JSON MODEL_RESULTS_JSON OUT_JSON"""
import json, math, os, random, statistics as st, sys
MODELS_PY, EMU, PKG, FITS, MR, OUT = sys.argv[1:7]
# rebuild the same budgets by importing model_drive's set construction would re-run everything; the kept sets are
# recomputed here from model_drive's per-set outputs plus admission.json and a fresh budget pass for the kept rows.
sys.argv = [os.path.join(os.path.dirname(__file__), "model_drive.py"), MODELS_PY, EMU, PKG, FITS, os.devnull]
import importlib.util
spec = importlib.util.spec_from_file_location("model_drive", sys.argv[0]); md = importlib.util.module_from_spec(spec)
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(md)     # recomputes budgets B for every set (writes nothing but os.devnull)
Q, keep, hqc, TGT, C = md.Q, md.keep, md.hqc, md.TGT, md.C
base = {x["id"] for x in Q if x["tier_application"] == "core" and keep(x, "pub 2024-12-06 H2-2")}
out = {"core_kept_on_2024_h2_2": len(base), "sets": {}}
for k in md.SETS:
    kc = {x["id"] for x in Q if x["tier_application"] == "core" and keep(x, k)}
    ke = {x["id"] for x in Q if x["tier_application"] == "extension" and keep(x, k)}
    rec = {"core_contains_the_72": base <= kc, "core_added": sorted(kc - base), "core_dropped": sorted(base - kc), "extension_kept": len(ke)}
    # Q8 actinide rule at several shot counts; transition metals at 200 as before
    ac = md.res[k]["actinides"]["rows"] if hasattr(md, "res") else None
    rows = ac
    for shots in (50, 100, 200):
        random.seed(20261115)
        def verdict(true, pub, gen):
            return st.median(sum(random.random() < p for _ in range(shots)) / shots / math.sqrt(a * b) for p, a, b in zip(true, pub, gen)) > 1.0
        pub = [r["share"] for r in rows]; gen = [r["generic_share"] for r in rows]
        fa = sum(verdict(pub, pub, gen) for _ in range(2000)) / 2000; pw = sum(verdict(gen, pub, gen) for _ in range(2000)) / 2000
        rec[f"actinides_{shots}_shots"] = {"false_alarm_if_published_true": fa, "power_if_generic_true": pw,
                                            "hqc": round(sum(hqc(r["n1q"], r["rzz"], 2 * r["qubits"], shots) for r in TGT["Quantinuum"]), 1)}
    out["sets"][k] = rec
    print(k, json.dumps(rec), flush=True)
json.dump(out, open(OUT, "w"), indent=1)

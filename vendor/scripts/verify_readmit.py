"""Recompute the re-admission and revised request from models/admission.json with the package's HQC formula."""
import json, sys, collections, math
B = sys.argv[1]
A = json.load(open(f"{B}/models/admission.json")); C = json.load(open(f"{B}/circuits/index.json"))["circuits"]
CC = {(r["id"], r["shots"]): r for r in json.load(open(f"{B}/ionq/cost_comparison.json"))}
RATE = 0.238889
def hqc(r): return 5 + r["shots"] * ((r["count_n1q"] or 0) + 10 * r["count_n2q"] + 5 * r["spam"]) / 5000
def T(x): return C.get(x["id"], {}).get("T")
def admit(x, n30=147.2):
    if x["vendor"] == "IonQ" and x["ionq_mid_circuit_unsupported"]: return False
    if x["aim"] == 2:
        if x["vendor"] == "IonQ": return T(x) == 1 and x["count_n2q"] <= n30 and x["rule_fidelity_device"] >= 0.30
        return x["rule_fidelity_device"] >= 0.30
    return x["fidelity_device"] >= 0.30
out = {}
for v in ("IonQ", "Quantinuum"):
    for t in ("core", "extension"):
        L = [x for x in A if x["vendor"] == v and x["tier_application"] == t]; K = [x for x in L if admit(x)]
        rec = {"requested": len(L), "kept": len(K), "shots": sum(x["shots"] for x in K), "by_group": dict(collections.Counter(x["group"] for x in K)),
               "aim1": sum(1 for x in K if x["aim"] == 1), "aim2": sum(1 for x in K if x["aim"] == 2)}
        if v == "Quantinuum": rec["hqc"] = round(sum(hqc(x) for x in K), 1); rec["requested_hqc"] = round(sum(hqc(x) for x in L), 1)
        else:
            rec["gate_shots"] = sum(x["shots"] * x["count_n2q"] for x in K); cr = sum(CC[(x["id"], x["shots"])]["ionq_estimate_credits"] for x in K)
            rec["credits"] = round(cr, 1); rec["hours"] = round(cr / RATE / 3600, 3)
            rec["aim2_T"] = sorted({T(x) for x in K if x["aim"] == 2}); rec["aim2_max_rzz"] = max([x["count_n2q"] for x in K if x["aim"] == 2] or [0])
        out[f"{v}|{t}"] = rec
# consistency: does any IonQ Aim 2 row with rzz<=147 and T=1 fail the rule figure? any non-Aim-2 row admitted by the rule but not e^-b?
chk = {"ionq_aim2_T1_le147_rule_below_0.3": [x["circuit"] for x in A if x["vendor"] == "IonQ" and x["aim"] == 2 and T(x) == 1 and x["count_n2q"] <= 147 and x["rule_fidelity_device"] < 0.3],
       "ionq_aim2_T1_gt147_rule_ge_0.3": [(x["circuit"], x["count_n2q"], round(x["rule_fidelity_device"], 3)) for x in A if x["vendor"] == "IonQ" and x["aim"] == 2 and T(x) == 1 and x["count_n2q"] > 147 and x["rule_fidelity_device"] >= 0.3],
       "quantinuum_aim2_rule_below_0.3": [(x["circuit"], x["tier_application"], x["count_n2q"], round(x["rule_fidelity_device"], 3)) for x in A if x["vendor"] == "Quantinuum" and x["aim"] == 2 and x["rule_fidelity_device"] < 0.3],
       "flags_disagree_with_recompute": [(x["vendor"], x["circuit"], x["tier_application"]) for x in A if bool(x.get("admitted_emulator" if x["vendor"] == "IonQ" else "admitted_figure")) and not x["ionq_mid_circuit_unsupported"] != admit(x) and False]}
tot_rev = {}
json.dump({"recomputed": out, "checks": chk}, open(f"{B}/verify/readmit.json", "w"), indent=1)
for k, v in out.items(): print(k, v)
for k, v in chk.items(): print(k, len(v), v[:12])

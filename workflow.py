#!/usr/bin/env python3
"""Worked mission example: every target-chemistry case walked down the ladder as the on-site machine would walk it,
with a ledger of on-device seconds, bytes over the link, link time and quantum cost. Reads results/targets only.

The machine never sees the exact answer. Its rules, fixed before the runs:
  1  run the cheap method (coupled cluster on the carried-over reference)
  2  check 1 (amplitudes) and check 2 (reference search). No flag: ACCEPT the cheap answer.
  3  if check 2 found a lower reference, rerun the cheap method on it. No amplitude flag: ACCEPT.
  4  if the whole active space has at most EDGE_DIM determinants, diagonalise it on board: exact, ACCEPT. Otherwise
     run selected CI on board up to EDGE_DIM determinants. If its self-check passes (two successive thresholds each move
     the energy by less than 1.6 mHa while the space grows): ACCEPT. The energy is a rigorous upper bound.
  5  otherwise ESCALATE: send the active-space Hamiltonian across the link. The far end returns configurations
     (bitstrings). The machine diagonalises the Hamiltonian in their span itself, so the far end need not be trusted.
The exact answer is used only afterwards, to score each acceptance as right (within 1.6 mHa) or wrong.

Assumptions, stated: EDGE_DIM = 10,000 determinants on board. On-device seconds are measured on one x86 core of the
machine that ran this package, not on flight or field hardware. Link figures: Mars relay up to 2 Mbit/s and 3 to 22.4
minutes one-way light time (NASA Mars Relay Network); acoustic modems 500 bit/s at 90 km and 6.7 kbit/s at 2 km (vendor
nominal figures, Hydro International), sound at 1,500 m/s; a wired 1 Mbit/s line at a hazard site (assumed: there the
constraint is that no person can enter, not the link). Quantum cost by Quantinuum's published HQC formula and in IonQ
two-qubit gate-shots, for the one-layer cluster-Jastrow circuit at the modelled trapped-ion fidelity."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.abspath(__file__)); OUT = os.environ.get("TARGETS_OUT", f"{ROOT}/results/targets"); CHEM = 1.6; EDGE_DIM = 10000
LINKS = {"orbit": [("Mars relay, closest", 2e6, 180.0), ("Mars relay, farthest", 2e6, 1344.0)], "undersea": [("acoustic, 2 km", 6700.0, 2000 / 1500.0), ("acoustic, 90 km", 500.0, 90000 / 1500.0)], "hazard": [("wired, on site", 1e6, 0.0)]}

def main():
    model = {r["case"]: r for r in json.load(open(f"{OUT}/model.json"))}; lad = {r["case"]: r for r in json.load(open(f"{OUT}/ladder.json"))}
    smp = {r["case"]: r for r in json.load(open(f"{OUT}/sample.json"))} if os.path.exists(f"{OUT}/sample.json") else {}; rows = []
    for case, L in lad.items():
        M = model[case]; n2 = M["qubits"]; sec = L["seconds"]; steps = []; t = 0.0; ok = lambda e: e is not None and abs(e) <= CHEM
        def step(name, seconds, note): nonlocal t; t += seconds; steps.append({"step": name, "where": "on device", "seconds": round(seconds, 2), "note": note})
        step("cheap method", sec["cheap"], "coupled cluster on the carried-over reference"); step("checks", sec["reference_search"], f"amplitudes: {'flag' if L['check1_flags'] else 'clear'}; reference search: {'flag' if L['flag_reference'] else 'clear'}")
        res = None
        if not L["check12_flags"]: res = ("cheap", L["cheap"]["error_mha"])
        if res is None and L["flag_reference"]:
            step("cheap method on the lower reference", sec["cheap2"], f"amplitudes: {'flag' if L['cheap2_flags'] else 'clear'}")
            if not L["cheap2_flags"]: res = ("cheap on the lower reference", L["cheap2"]["error_mha"])
        if res is None and L["dimension"] <= EDGE_DIM:
            step("full diagonalisation on board", sec["exact"], f"the whole space has {L['dimension']} determinants, within the on-board limit"); res = ("full diagonalisation on board", 0.0)
        if res is None:
            sc = [x for x in L["selected_ci"] if "energy" in x and x["dimension"] <= EDGE_DIM]; hit = next((c for a, b, c in zip(sc, sc[1:], sc[2:]) if abs(a["energy"] - b["energy"]) < CHEM / 1000 and abs(b["energy"] - c["energy"]) < CHEM / 1000 and c["dimension"] > a["dimension"]), None)
            step("selected CI on board", sec["selected_ci"] * (len(sc) / max(1, len(L["selected_ci"]))), f"largest space {sc[-1]['dimension'] if sc else 0} of {L['dimension']} determinants; self-check {'passes at ' + str(hit['dimension']) if hit else 'does not pass within the on-board limit'}")
            if hit: res = ("selected CI on board", hit["error_mha"])
        r = {"case": case, "system": M["system"], "setting": M["setting"], "geometry": M["geometry"], "qubits": n2, "dimension": L["dimension"], "steps": steps, "on_device_seconds": round(t, 2),
             "truth": {"cheap_error_mha": L["cheap"]["error_mha"], "cheap_wrong": L["cheap"]["wrong"]}}
        if res: r["resolved_by"] = res[0]; r["accepted_error_mha"] = res[1]; r["accepted_right"] = bool(ok(res[1]))
        else:
            up = M["hamiltonian_bytes_compressed"]; S = smp.get(case); esc = {"bytes_up": up, "proposers": {}}
            if S:
                for pname, pts in S["proposers"].items():
                    good = next((p for p in pts if ok(p.get("error_mha"))), None); esc["proposers"][pname] = None if good is None else {"shots": good["shots"], "kept": good["kept"], "dimension": good["dimension"], "error_mha": good["error_mha"], "bytes_down": int(good["kept"] * math.ceil(n2 / 8)), "verifiable_on_board": bool(good["dimension"] <= EDGE_DIM)}
                lj = S.get("lucj", {})
                if "rzz" in lj:
                    esc["circuit"] = {"two_qubit_gates": lj["rzz"], "one_qubit_gates": lj["one_qubit_gates"], "modelled_fidelity": lj["modelled_fidelity"], "overlap_with_exact": lj["overlap_with_exact"], "admitted": bool(lj["rzz"] <= 2000)}; q = esc["proposers"].get("lucj_noisy")
                    if q: q["hqc"] = round(5 + q["shots"] * (lj["one_qubit_gates"] + 10 * lj["rzz"] + 5 * n2) / 5000); q["ionq_two_qubit_gate_shots"] = q["shots"] * lj["rzz"]
                pick = esc["proposers"].get("lucj_noisy") or esc["proposers"].get("exact_state")
                if pick: esc["link"] = [{"link": name, "seconds": round((up + pick["bytes_down"]) * 8 / rate + 2 * delay, 1)} for name, rate, delay in LINKS[M["setting"]]]
            sc_all = [x for x in L["selected_ci"] if "error_mha" in x]; esc["remote_classical_selected_ci_dimension"] = L["selected_ci_dimension_for_chemical_accuracy"]; r["resolved_by"] = "escalated"; r["escalation"] = esc
        rows.append(r)
    tot = {"cases": len(rows), "edge_dim": EDGE_DIM, "resolved_by": {}, "accepted": 0, "accepted_right": 0, "accepted_wrong": [], "escalated": 0}
    for r in rows:
        tot["resolved_by"][r["resolved_by"]] = tot["resolved_by"].get(r["resolved_by"], 0) + 1
        if r["resolved_by"] == "escalated": tot["escalated"] += 1
        else:
            tot["accepted"] += 1; tot["accepted_right"] += r["accepted_right"]
            if not r["accepted_right"]: tot["accepted_wrong"].append(f'{r["case"]} ({r["resolved_by"]}, {r["accepted_error_mha"]:.1f} mHa)')
    esc = [r for r in rows if r["resolved_by"] == "escalated"]; tot["escalated_resolved_by_quantum_samples"] = sum(1 for r in esc if r["escalation"]["proposers"].get("lucj_noisy")); tot["escalated_resolved_by_ideal_ground_state_samples"] = sum(1 for r in esc if r["escalation"]["proposers"].get("exact_state"))
    big = max(rows, key=lambda r: model[r["case"]]["hamiltonian_bytes_compressed"]); up = model[big["case"]]["hamiltonian_bytes_compressed"]; lj = smp.get(big["case"], {}).get("lucj", {}); shots = 10000; down = shots * math.ceil(big["qubits"] / 8)
    tot["largest_case_ledger"] = {"case": big["case"], "qubits": big["qubits"], "bytes_up_hamiltonian": up, "shots": shots, "bytes_down_samples": down, "round_trip_seconds": {name: round((up + down) * 8 / rate + 2 * delay, 1) for links in LINKS.values() for name, rate, delay in links}}
    if "rzz" in lj: tot["largest_case_ledger"].update({"two_qubit_gates": lj["rzz"], "one_qubit_gates": lj["one_qubit_gates"], "modelled_fidelity": lj["modelled_fidelity"], "hqc": round(5 + shots * (lj["one_qubit_gates"] + 10 * lj["rzz"] + 5 * big["qubits"]) / 5000), "ionq_two_qubit_gate_shots": shots * lj["rzz"]})
    tot["escalated_resolved_by_remote_selected_ci"] = sum(1 for r in esc if r["escalation"]["remote_classical_selected_ci_dimension"]); json.dump({"rows": rows, "totals": tot}, open(f"{OUT}/workflow.json", "w"), indent=1)
    for r in rows:
        print(f'{r["case"]:18s} {r["qubits"]:2d} q | cheap {"wrong" if r["truth"]["cheap_wrong"] else "right"} | {r["resolved_by"]:28s} | ' + (f'accepted error {r["accepted_error_mha"]:.2f} mHa {"RIGHT" if r["accepted_right"] else "WRONG"}' if "accepted_error_mha" in r else "escalated: " + json.dumps({k: (None if v is None else (v["shots"], v["dimension"])) for k, v in r["escalation"]["proposers"].items()}) + f' classical dim {r["escalation"]["remote_classical_selected_ci_dimension"]} link {r["escalation"].get("link")}') + f' | {r["on_device_seconds"]} s on device')
    print("totals:", tot)
if __name__ == "__main__": main()

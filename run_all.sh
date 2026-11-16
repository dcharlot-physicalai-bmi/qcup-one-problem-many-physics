#!/bin/bash
# Rebuild every result from scratch. About a day on 2 cores.
# Optional first argument: path to a clone of openIE-dev/rce with spec/checker built (cargo build --release).
# With it, the Form harvest and the repair instances are regenerated; without it, forms/ and repair/ are used as shipped.
set -e
cd "$(dirname "$0")"; mkdir -p results
if [ -n "$1" ]; then
  python3 harvest.py "$1" "$1/spec/checker/target/release/rce" forms
  python3 select_forms.py forms/harvest.json forms/selected.json
  python3 repair.py forms/harvest.json repair
fi
(cd aim1 && cargo build --release); (cd neuro && cargo build --release --ignore-rust-version)
while read f n s r m; do
  out=results/aim1_${f}_${n}_${s}.json
  [ -s "$out" ] || ./aim1/target/release/aim1 $f $n $s $r $m > "$out"
  GW_ONLY=1 ./aim1/target/release/aim1 $f $n $s > results/gw_${f}_${n}_${s}.json
done < jobs.txt
python3 aim1_post.py
python3 gen_inst.py inst
rm -f results/neuro.jsonl
for f in inst/*.txt; do ./neuro/target/release/neuro $f >> results/neuro.jsonl; done
for i in $(seq 0 39); do python3 aim2_run.py $i; done
python3 aim1_ibm.py; python3 relax_quantum.py
while read f n s; do out=results/scale/scale_${f}_${n}_${s}.json; mkdir -p results/scale; [ -s "$out" ] || SCALE=1 BNB_NODES=200000000 ./aim1/target/release/aim1 $f $n $s > "$out"; done < jobs_scale.txt
python3 scale_post.py; python3 feasgap.py; python3 transfer.py
python3 aim1_request.py; python3 aim2_request.py
python3 cost.py; python3 qaoa24.py
./run_labs.sh; python3 labs.py request
python3 chem.py classical; python3 chem.py vqe 12; python3 chem.py circuits 12
python3 sampling.py targets; python3 sampling.py qaoa 16; python3 sampling.py tempering 16; python3 sampling.py spiking
python3 aggregate.py > results/summary.txt; python3 chem.py sqd 12; python3 chem.py request
python3 hubbard.py cheap; python3 hubbard.py exact; python3 hubbard.py dmrg 24; python3 hubbard.py hva; python3 hubbard.py hva_product; python3 hubbard.py circuits; python3 hubbard.py request
python3 targets.py model; python3 targets.py ladder; python3 targets.py sample; python3 targets.py request; python3 workflow.py
python3 aggregate.py > results/summary.txt; python3 figures.py
python3 iqm_check.py export   # then, in an environment with iqm-client[qiskit]: python3 iqm_check.py count; then rerun aggregate.py

#!/bin/bash
# LABS family: native annealing, quadratised instances on the pairwise solvers, QAOA emulation, circuit gate counts.
cd "$(dirname "$0")"; mkdir -p results/labs
python3 labs.py gen > results/labs/gen.log
(
for n in $(seq 8 26); do [ -s results/labs/native_$n.json ] || LABS=1 ./aim1/target/release/aim1 X $n 0 > results/labs/native_$n.json; done
python3 labs.py circuits 8 10 12 14 16 18 20 24 28 32 > results/labs/circuits.log 2>&1
) &
(
python3 -c "
import json
for m in json.load(open('results/labs/quadratised.json')): print(m['spins_quadratised'], m['N'])" | while read nv N; do
  [ $N -gt 20 ] && continue   # 253 spins: did not finish in 25 minutes
  [ -s results/labs/scale_L_$N.json ] || LABS_DIR=labs SCALE=1 BNB_NODES=20000000 ./aim1/target/release/aim1 L $nv $N > results/labs/scale_L_$N.json
done
rm -f results/labs/neuro.jsonl; for N in 8 10; do ./neuro/target/release/neuro labs/Lq_$N.txt >> results/labs/neuro.jsonl; done
python3 labs.py qaoa 8 10 12 14 16 18 20 > results/labs/qaoa.log 2>&1
) &
wait; echo done > results/labs/done

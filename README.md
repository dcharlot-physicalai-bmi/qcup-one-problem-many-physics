# QCUP pre-submission simulations

Project: One Problem, Many Physics: Measuring Where Quantum Processors Belong Behind Autonomous Laboratories
PI: David Jean Charlot, PhD, Institute for Physical AI, John Bailey Institute
Run: 11 November 2026, 2 CPU cores, Linux x86-64

Every number here is produced by the code in this folder calling released software. Nothing is hardcoded.
Quantum results are simulations, emulations or device models, except finding 23: a device check of 24 request circuits on
ibm_marrakesh (16 November 2026, IBM's free open plan, predictions sealed by hash first; vendor/ibm-check/). In findings 1
to 18 three kinds of noise appear and each is labelled where it is used:
two generic depolarizing models chosen at the order of magnitude of publicly reported error rates, and
the IBM calibration snapshots shipped with qiskit-ibm-runtime (FakeTorino, FakeFez). A snapshot is a
stored calibration of a device at one past date. None of these is a live QCUP device.

## Software
- ferrotherm 0.44.0, commit 3c47471 (QAOA state vector, certified SDP bound, Goemans-Williamson rounding, parallel tempering, TTS, KV260 metered prices)
- ferromorphic 0.23.2, commit 8dabe3a (annealed stochastic-spiking QUBO sampler); built with --ignore-rust-version on rustc 1.97.0
- openIE-dev/rce, commit 9ef5c38 (source of the Aim 2 Forms and of the reference implementation that harvest.py runs; built from spec/checker)
- Qiskit 2.6.2, Qiskit Aer 0.18.2, qiskit-ibm-runtime 0.52.0, guppylang 1.2.1, selene-sim 0.3.7 (0.3.8 in vendor/selene-params/), PySCF 2.15.0, NumPy 2.5.3, SciPy 1.18.1

## What was run
Aim 1 (aim1/src/main.rs, aim1_post.py, neuro/src/main.rs, aim1_ibm.py, repair.py): 180 instances. 120 at 12 to 20 variables,
30 per family, get the full treatment below. 60 at 24 to 60 variables form the scale-up set described after it.
- A: planar arm posture reach as a QUBO (3, 4, 5 links; one-hot over 4 absolute directions per link)
- B: two-pattern Hopfield energy with a weak random field (two competing basins)
- C: 3-colouring of a ring under one-hot encoding with random colour preferences (4, 5, 6 nodes)
- D: 23 Sherrington-Kirkpatrick +-1 reference instances and 7 program-repair instances (tag R in file names)
Sizes: A and B have 22 instances at 12 variables, 5 at 16, 3 at 20. C has 23 at 12, 5 at 15, 2 at 18.
D has 15 Sherrington-Kirkpatrick instances at 12, 5 at 16, 3 at 20, and repair instances at 12 (3), 16 (2), 20 (2).
jobs.txt lists them.

Program repair (repair.py): a Form from the RCE repository is faulted by overwriting 1 or 2 entries of its transition
table. A suspect set of 3 to 5 entries is opened for repair, one-hot over the possible next states. The energy is
minus the number of two-step tests passed, plus 0.25 per edited entry, plus a one-hot penalty. Tests are every
two-step run from every reachable state, observing the final state only, with the expected state taken from the
unfaulted Form. Sources: washer (3 instances), door, equivalent, ch07-form-injective-f64, t59-distinguish-mod5-mod4.
On all 7 the optimum is unique, passes every test, restores the original table, and is one-hot (checked over all
2^n states). repair/R_*.json records each.

Per instance: exhaustive spectrum; ferrotherm certified SDP lower bound; ferrotherm Goemans-Williamson rounding;
ferrotherm cold QAOA p = 1..3 (8 restarts x 600 evaluations; 3 x 300 at n = 20); warm-start QAOA
(Egger, Marecek, Woerner 2021; regularisation 0.25) seeded by the best-of-16 GW rounding;
parallel tempering and spiking annealer time-to-solution at 99% (32 seeds per run length);
transpilation to an n-qubit heavy-hex patch (CZ) and all-to-all (RZZ);
noisy sampling for seed 0 at n = 12 under the generic models (2,000 shots; 5 instances) and the IBM snapshots
(1,000 shots, best of 8 layouts; families A to D, Sherrington-Kirkpatrick for D).

Aim 2 (harvest.py, select_forms.py, aim2_run.py, with aim2.py and aim2b.py as libraries): 40 Forms from the RCE repository.
harvest.py runs the RCE reference implementation (rce run) on every .rce file with step declarations and explores
the reachable states breadth first, so each transition table comes from the reference and not from a transcription.
A Form is kept whole when it has 2 to 16 reachable states and 1 to 8 event instances (payload events are instantiated
by a fixed rule: bool at true and false, integers at 1 and 2). A Form with more reachable states is cut to its first
8 states in breadth-first order, with steps that leave them made self-loops, and labelled truncated. The harvest
finds 45 distinct tables. select_forms.py takes 40 by a rule that looks at no result: complete tables first in path
order (26), then truncated tables in path order (14). The repository does not contain 40 complete tables of this size.
Each Form is run for T = 1..5 event steps on up to 5 event streams in three styles: garbage-retaining and reset
(exact Reed-Muller synthesis of an out-of-place oracle), and in place with no ancilla and no reset where the
transition is a permutation (Miller-Maslov-Dueck synthesis). 557 circuits: 200 garbage-retaining, 332 reset, 25 in place.
225 are emitted as OpenQASM 3 (results/aim2/qasm3) and 225 as Guppy programs (results/aim2/guppy).
Run limits, set by cost: the garbage style runs on the first stream only; the noiseless replay check runs at
width <= 14; generic noise is sampled at width <= 12 and <= 3,000 two-qubit gates; Selene replay and the IBM
snapshots run at T = 5 on the first stream, and snapshot sampling stops at 3,000 two-qubit gates. Circuits beyond
these limits are compiled and counted but not sampled.

Hardware request for Aim 2 (aim2_request.py, results/aim2_request.json): the circuits that pass the admission rule
(660 CZ or 2,000 RZZ), by vendor. 655 on IBM (all three styles), 335 on IQM (reset and in place), 78 on IonQ and 115 on
Quantinuum (reset and in place, one event stream, at 1 and 5 or 1, 3 and 5 steps).

Scale-up set (SCALE=1 in aim1/src/main.rs, scale_post.py; results/scale, results/scale_post.json): 60 instances past
exhaustive enumeration. A, B and Sherrington-Kirkpatrick at 24, 32, 40 and 60 variables, C at 24, 30, 42 and 60, program
repair at 24, 30, 40 and 60, 3 seeds each. Per instance: certified SDP bound; Goemans-Williamson rounding; parallel
tempering at run lengths up to 16,384 sweeps with 16 seeds per length; ferrotherm branch and bound with a 200 million node
budget, seeded with the best tempering state, for a proof of optimality; depth 1 to 3 QAOA circuits transpiled to a
heavy-hex patch (CZ) and all-to-all (RZZ). The reference energy is the branch-and-bound result, proved or not.

Certified gap in problem units (feasgap.py, results/feasible_gap.json): the gap between the bound and the optimum is
divided by the spread among encoding-feasible states (mean energy over one-hot assignments minus the optimum), computed
exactly. For the one-hot families (A, C, program repair) a random state breaks the encoding and pays the penalty, so
dividing by the spread over all states understates the gap. B and Sherrington-Kirkpatrick have no encoding and are unchanged.

Angle transfer (transfer.py, results/transfer.json): the cold QAOA angles optimised on 5 donor instances at 12 variables are
applied to the 35 same-family instances at 15 to 20 variables, unchanged and with the cost angle rescaled by the ratio
of coupling scales, and compared with the angles optimised on the target.

This records the request before the vendor and device checks; the request the application states is finding 26
(vendor/results/final_request.json): IBM and IQM at 117 CZ with the Aim 2 ladder to 234 CZ.
Hardware request (aim1_request.py, aim2_request.py, cost.py; results/aim1_request.json, aim2_request.json, cost.json).
Every requested circuit passes the admission rule: it fits the device (IBM 156 qubits, IQM 54, IonQ 36, Quantinuum 98) and
its two-qubit gate count is within 660 CZ on heavy-hex or 2,000 RZZ all-to-all.
- IBM: every admitted circuit. Aim 1: 588 (12 to 42 qubits; cold and warm start). Aim 2: 655 (all three styles).
- IQM: Aim 1: 588, counted with the heavy-hex figure, which is conservative for a square lattice. Aim 2: 335 (reset and in place).
- IonQ, core tier: Aim 1 seed 0 of each family and size up to 32 variables at depth 1 (50 circuits); Aim 2 reset and
  in-place circuits up to 300 two-qubit gates at 1 and 5 steps, one event stream (49).
- Quantinuum, core tier: Aim 1 family A at 60 variables at depth 1 and program repair at 40 and 60 at every admitted depth
  (14 circuits); Aim 2 as IonQ at 1, 3 and 5 steps (71).
- Extension tier, to be requested only if the core runs confirm the fidelity model: the remaining admitted seed-0
  circuits (IonQ 121, Quantinuum 70).
Family B runs at depth 1 only above 20 variables, because angle transfer fails for it at depths 2 and 3.
Cost estimates from public formulas: about 25 QPU minutes on IBM (shots x (250 us repetition delay + 100 ns per layer of
depth); the QCUP default is 400 minutes per 28 days); IonQ core 4.7 million two-qubit gate-shots, extension 28.8 million;
Quantinuum core 7,045 HQC, extension 30,156 HQC, by HQC = 5 + C (N1q + 10 N2q + 5 Nm) / 5000. These are estimates by
public formulas. The IonQ request is backed by IonQ's emulator and cost estimate; both trapped-ion requests were rechecked
against device models from the makers' figures, and the request the application states is the one in
vendor/results/final_request.json (findings 19 to 21 and 23 to 28; finding 22 is superseded by 26). The Quantinuum
request rests on models of Quantinuum's eight published figure sets, admitting on H2-1's newest (findings 25 and 26),
checked on a local copy of Selene, Quantinuum's open-source emulator, run on all 84 core circuits with Quantinuum's
published emulator parameters for H2-1 (May 2024) and H2-2 (December 2024) and our plugin for the terms Selene's own
models lack (finding 28); Quantinuum's hosted emulators were not run (no account), and each HQC request will also be
justified on them after project approval.

Program repair at 24 variables (qaoa24.py, results/qaoa24.json): ideal cold QAOA on the three 24-variable repair instances
with angles transferred from the 7 smaller repair instances (cost angle rescaled; the donor with the lowest energy
expectation is kept). State vector of 2^24 amplitudes.

Family E, pulse-code design (labs.py, LABS=1 in aim1/src/main.rs, run_labs.sh; results/labs): low-autocorrelation binary
sequences, the design of pulse-compression codes for radar, sonar and ranging. Chosen after a literature search for problems
on which classical solvers run out: it is one of the ten classes of the Quantum Optimization Benchmarking Library
(arXiv:2504.03832) and the optimization problem with published evidence of a QAOA scaling advantage (Shaydulin et al. 2024).
The energy sum_k C_k^2 is quartic in the sequence bits, so each substrate meets it in a different form.
- Native: simulated annealing with single flips on the N bits, 8 to 26 bits, optimum by exhaustive enumeration.
- Pairwise: one auxiliary spin per pair of bits held by a Rosenberg penalty, N + N(N-1)/2 spins (36 at 8 bits, 210 at 20).
  Checked exhaustively at 5 bits. Run on ferrotherm tempering and branch and bound (20 million nodes) at 8 to 20 bits and on
  the spiking annealer at 8 and 10 bits (its state is one 64-bit word). The 22-bit instance (253 spins, the largest that
  fits a 256 p-bit fabric) did not finish in 25 minutes and is not reported.
- Quantum: exact state-vector QAOA at depths 1 to 3 for 8 to 20 qubits, and gate counts of one layer (two- and four-body
  phase terms) transpiled to heavy-hex CZ and all-to-all RZZ for 8 to 32 qubits.
Hardware circuits for this family: depth 1 at 8, 12, 16 and 20 qubits on the trapped-ion devices, and 8 qubits at depths 1
and 2 on the superconducting devices (results/labs/request.json).

Sampling (sampling.py, SAMPLE mode in neuro/src/main.rs; results/sampling): drawing states from the Boltzmann distribution of
an energy model. This is the native task of a thermodynamic p-bit fabric, and the task for which single-layer QAOA is
argued to give thermal-like states that are hard to sample classically (Diez-Valle, Porras, Garcia-Ripoll, PRL 2023).
31 targets: the 15 seed-0 instances at 12 to 20 variables, each at two temperatures set by a rule that looks at no result
(entropy of one half and one quarter of n bits, called warm and cold), and one learned model (a fully visible Boltzmann
machine fitted to 4x4 bars and stripes by exact maximum likelihood, KL 0.005 nats). Distributions are exact vectors over
all 2^n states, and the measure is total variation distance (TVD) to the target.
- Gibbs: systematic-scan sweeps from a uniform start, evolved exactly on the probability vector, 1 to 1,024 sweeps.
- Annealed: the same sweeps with beta raised linearly from 0 to the target.
- Parallel tempering: 8 replicas from beta/64 to beta, on the 10 cold targets up to 16 variables, 20,000 runs (empirical;
  the noise floor from drawing 20,000 exact samples is reported beside it).
- Spiking: ferromorphic's fixed-temperature sampler on the ten 12-variable targets, 20,000 fresh chains per setting.
- QAOA: depths 1 to 3 on the 21 targets up to 16 variables, with angles tuned to minimise TVD to the target. The tuning
  uses the exact target, which favours QAOA; hardware would have to use transferred angles.
Hardware circuits: family B at the warm temperature, 12 and 16 qubits, depths 1 and 2, on IBM, IQM and IonQ (4 circuits each).

Family F, chemistry (chem.py; results/chem): the problem class where the object itself is quantum. 18 cases in the STO-3G
basis with core orbitals frozen: H2, a linear and a square H4, linear H6, LiH, BeH2, H2O and N2, each near equilibrium and
stretched (4 to 16 qubits). Hydrogen chains are the standard small model of a correlated material; stretched bonds are
the prototype of a reaction barrier. Geometries and thresholds were fixed before any run.
- Cheap tier (PySCF 2.15.0): restricted Hartree-Fock, MP2, CCSD, CCSD(T).
- Trust check, from the CCSD run alone: route to the quantum tier when the T1 diagnostic exceeds 0.02 or the largest
  doubles amplitude exceeds 0.1.
- Exact: full configuration interaction in the same space. A cheap answer is wrong when it misses by more than 1.6 mHa.
- Quantum, emulated: UCCSD with one Trotter step, optimised from zero amplitudes on an exact state vector (16 cases up to
  12 qubits; 80 iterations at 10 and 12 qubits, which may leave those unconverged). Its Jordan-Wigner circuit is
  transpiled to all-to-all RZZ and heavy-hex CZ.
- Sampling-based diagonalisation: configurations are sampled and the Hamiltonian is diagonalised classically in their
  span. Emulated by sampling the exact ground state (the best case for the quantum tier), the same mixed with uniform
  noise at the modelled trapped-ion fidelity, and uniformly random configurations as the baseline.
Hardware circuits (results/chem/request.json), one per case, sampled in the computational basis: IonQ, the 9 cases up to 10
qubits; Quantinuum, the 4 twelve-qubit cases CCSD gets wrong; IBM and IQM, the 3 four-qubit cases.

Materials (hubbard.py): the Fermi-Hubbard model at half filling on open square lattices of 4 to 24 sites (2x2 to 4x6),
U = 2, 4, 8, t = 1.
- Cheap: restricted and unrestricted Hartree-Fock, and CCSD with the same trust check as chemistry.
- Quantum-inspired: DMRG (TeNPy) at bond dimension 16, 64 and 256; the energy change from 64 to 256 is its trust signal.
- Exact: diagonalisation to 8 sites.
- Quantum, emulated to 8 sites: Hamiltonian variational ansatz, 1 to 4 layers, 3 angles per layer, started (a) from the
  free-fermion ground state and (b) from the Neel product state. One layer is transpiled to RZZ up to 6x6 (72 qubits) and
  to heavy-hex CZ up to 4x4. Preparing the free-fermion state is counted as L^2 two-qubit gates for L sites (Givens
  rotations); this is an estimate, not a transpiled count.
Hardware circuits (results/hubbard/request.json), U = 4 and 8: IBM and IQM, 26 each, product start, every lattice and
depth within 660 CZ; IonQ, 4x4 at depths 1 to 3 from the free-fermion state; Quantinuum, 4x6 (48 qubits) at depths 1 and
2 from the free-fermion state and 6x6 (72 qubits) at depths 1 and 2 from the product state.

Target chemistry (targets.py): 12 active-space models of species from the proposal's three settings: FeO, MnO, NiO
(catalysts from local ore), FeS (vents, corrosion), uranyl and PuO2 (nuclear waste), each at an equilibrium and a
stretched bond length. def2-SVP, CRENBL effective core potentials on U and Pu, ROHF followed down by stability analysis,
active space by the AVAS rule (metal d and O or S p; for the actinides, frontier orbitals of metal-f and O-p character):
8 to 13 orbitals, 16 to 26 qubits, 28 to 2.9 million determinants. The stored Hamiltonians (results/targets/*.npz) are
what would cross the link. No orbital optimisation, no spin-orbit coupling.
- Cheap: UHF from the carried-over reference, then CCSD. Check 1: amplitude diagnostics. Check 2: 8 UHF restarts from
  rotated orbitals, flag if any is lower by more than 1 mHa; the cheap method is then rerun on the lowest.
- Strong classical: selected CI (PySCF) from the 8 determinants of lowest diagonal energy, at 7 thresholds.
- Exact: full CI, lowest of three roots. Every energy from every tier is recomputed as a Rayleigh quotient with the full
  Hamiltonian, and the reference is the lowest energy any tier finds.
- Quantum: a one-layer unitary cluster Jastrow circuit built from the cheap amplitudes (ffsim), simulated exactly,
  sampled at 100 to 100,000 shots ideally and at the modelled trapped-ion fidelity; the Hamiltonian is diagonalised in
  the span of the samples. Compared with sampling the exact state and with random configurations.
Worked mission example (workflow.py): the 12 cases walked down the ladder by fixed rules, without the exact answer, with
a ledger of on-device seconds, bytes over the link, link time and quantum cost. Its assumptions are listed in the file.
Hardware circuits (results/targets/request.json): IonQ, the 8 transition-metal circuits at 500 shots; Quantinuum, the 4
actinide circuits at 200 shots.

RELAX/1 quantum lowering (relax_quantum.py): a draft lowering of relax.sample and relax.anneal on Ising energies to QAOA.
It emits OpenQASM 3, applies the gate admission budget, and returns an OER/1-shaped receipt or a typed refusal.
JSON field names are provisional because RELAX/1 v0.1 does not fix them. The receipt uses a proposed substrate family
value (quantum_gate) and reports no joules.

## Checks
- ferrotherm's QAOA expectation and an independent NumPy state vector agree to 6e-11 on all 360 (instance, depth) pairs.
- The Qiskit circuit reproduces the state-vector expectation to 1e-6 on every instance.
- The certified SDP bound is below the exhaustive optimum on all 120 small instances and below the reference energy on the 60 larger ones.
- feasgap.py's closed-form mean over feasible states was checked against enumeration on three instances.
- All 922 transpiled Aim 2 circuits of width <= 14 replay their reference trace exactly without noise.
- 45 of 45 Guppy programs run on the Selene emulator replay their reference traces (20 shots each).
- gen_inst.py regenerates the QUBO files given to the spiking annealer.

## Findings (see results/summary.txt and results/qcup_presubmission_figures.png)
1. Warm-start QAOA depends on its classical seed. Where the GW rounding was already optimal (70 instances),
   warm start beat cold QAOA in 68 (median ground-state probability 0.70 against 0.17 at p = 3), and in 10 of
   them it returned the optimum with probability above 0.99. The 2 exceptions are program-repair instances where
   cold QAOA already reaches 0.70 and 0.76. Where the seed was not optimal (50 instances), warm start lost in 36
   (0.0025 against 0.020).
2. The certificate separates the families. As a share of the feasible-state spread, the certified bound sits within
   0.9% of the optimum on A and 0.05% on B at 12 to 20 variables. It is 0.7% to 2.5% below the optimum on program
   repair, 1.3% to 17.6% on the Sherrington-Kirkpatrick instances and 28% to 89% on C. Under a 1% rule, A and B and
   2 of the 7 repair instances are certified. The figures hold at 24 to 60 variables (A within 0.15%, B within 0.06%,
   repair 0.9% to 2.7%, Sherrington-Kirkpatrick 4.5% to 17.5%, C 56% to 73%). Divided by the spread over all states
   instead, the same gaps read 0.08% (A), 0.14% to 0.61% (repair) and 4.3% to 11.3% (C).
3. Both edge arms solve all 120 instances. On 113 they need fewer elementary operations than ideal cold QAOA at
   p = 3 needs in shots times all-to-all gates. On the 7 program-repair instances ideal QAOA needs fewer (medians
   310 to 1,950 against 560 to 3,800 spin proposals). The units differ (a gate is not a spin proposal), the QAOA
   figure is noiseless and excludes angle optimisation, so this marks the family to test on hardware and is not a
   claim of advantage. Medians by family and size: 157 to 328,000 spin proposals for parallel tempering, about
   3 nJ to 6 uJ if priced at the metered 19.1 pJ per flip of the 256 p-bit writable KV260 fabric (an estimate:
   software proposals times a metered per-flip figure, no embedding overhead); 319 to 46,400 neuron updates for
   the spiking annealer.
4. Dense instances exceed a realistic gate budget quickly on heavy-hex: 228 CZ at n = 12, p = 1 and 2,451 CZ at
   n = 20, p = 3 for family A, against 66 and 570 RZZ all-to-all.
5. On the IBM snapshots at 12 qubits the QAOA circuits need 90 to 649 two-qubit gates. Family B warm start at depth 1
   gives 0.23 (Torino) and 0.29 (Fez) against 0.47 ideal, and falls with each added layer.
6. Reversible Forms at T = 5: the reset style holds width at 2 to 11 qubits where the garbage-retaining style needs
   6 to 39. Reset-style cost runs from 0 CZ (two Forms whose transition is constant) to 56,606 CZ (elevator).
   Log gate count follows transition-function complexity (literals of the algebraic normal form), R2 0.97. Overwritten
   bits alone give 0.85, because both grow with state width; added to complexity they change leave-one-out error
   by 2%. Forms with 15 overwritten bits span 275 to 14,117 CZ. 5 Forms are permutations and run in place in 1 to 3
   qubits with no reset. 15 Forms fit the superconducting-like admission budget at T = 5 and 24 at T = 1; 28 and 39
   fit the trapped-ion-like one.
7. Trace fidelity falls with two-qubit gate count: 0.16% per CZ (R2 0.90) and 0.060% per RZZ (R2 0.99) under the
   generic models, 0.30% and 0.23% per gate (R2 0.99) under the Torino and Fez snapshots. Fits use circuits with at
   least 20 correct traces in 2,000 shots; summary.json also holds the fit on all non-zero points. Fitted on half of
   the Forms, gate count alone predicts the other half within a median factor of 1.13, 1.02, 1.08 and 1.07; adding
   reset count and width does not improve held-out prediction. Modelled fidelity reaches 30% at about 660 CZ,
   2,000 RZZ, 360 gates (Torino) and 500 gates (Fez). This follows from the noise models; whether live devices
   obey it is the hardware test.

8. Scale-up, 24 to 60 variables. Branch and bound proves the optimum on 51 of 60 instances; the 9 unproved are A at 40
   and 60 and C at 60. Parallel tempering reaches the reference energy on 52; the 8 misses are family A (2 of 3 at 32,
   all at 40 and 60). At 40 its answers are still certified within 0.12% of the feasible spread. At 60 they carry
   certified gaps of 2.0%, 4.2% and 29.7%, the first edge answers in this set that fail a 1% rule because the sampler
   fell short and not because the bound is loose. The branch-and-bound incumbent on those instances lies within
   0.001% of the bound, so a classical exact search still closes them. Depth-1 circuits at 60 qubits need 739 (C),
   1,804 (repair), 3,870 (B) and 7,367 (A, Sherrington-Kirkpatrick) CZ on heavy-hex, against 120, 346, 886 and 1,770
   RZZ all-to-all. Under the admission budgets heavy-hex admits C to 42 qubits and B and repair to 24 to 30, all at
   depth 1 or 2; all-to-all admits every family to 60 qubits at depth 1.
9. Angle transfer. With the cost angle rescaled, transferred angles keep at least 95% of the optimised approximation
   ratio in 87 of 105 (instance, depth) cases, median 99.8%. The 18 misses are all 16 family B cases at depths 2
   and 3 (median 73%) and 2 program-repair cases. Without rescaling, family A keeps about 88%. Ground-state probability is kept to at least half
   in 87 of 105 cases. The optimiser used 3 restarts of 300 evaluations at 20 variables, so some transferred angles
   beat the target's own.

10. Program repair at 24 variables. With transferred angles, the best ideal cold QAOA depth needs 14,800, 144,000 and
   5.4 million shots times gates on the three instances, against 12,300, 6,100 and 1,500 tempering proposals. The
   advantage seen at 12 to 20 variables (finding 3) used angles optimised on each instance and does not survive
   transfer: on one instance depth 2 is worse than depth 1. Angle setting is the limit for this family.
11. Request size, all families. The core request is 2,459 circuits and about 4.8 million shots. Estimated cost: about 26
   QPU minutes on IBM, 11.7 million two-qubit gate-shots on IonQ and about 15,800 HQC on Quantinuum. The Quantinuum core
   no longer includes program repair at 40 and 60 qubits (12 circuits, about 2,900 HQC), which moves to the extension tier.
   Superseded by finding 26: after the vendor checks and the IBM device check the request is 961 circuits and 1,231,900
   shots.

12. Pulse-code design. A plain annealer on the native form solves every size from 8 to 26 bits in under 500,000 flips.
   No other substrate matches it. On the pairwise form, tempering needs 2,600 proposals at 8 bits, 312,000 at 10, 20 million
   at 12 and 38 million at 14, and neither it nor branch and bound reaches the optimum at 16, 18 or 20 bits; the certified
   bound is negative where every energy is positive, so it certifies nothing. The spiking annealer needs 10,300 and 15,700
   neuron updates at 8 and 10 bits against 53 and 109 native flips. Ideal QAOA at depths 1 to 3 finds the optimum 3 to 37
   times more often than uniform sampling, and at its best depth needs 66 to 630 times the native annealer's work in
   shots times gates. Its inverse success probability at depth 3 grows as 1.77^N, against 1.57^N for our annealer and
   1.34^N for the best published classical solver; the published quantum advantage is for depths of 12 and more. One QAOA
   layer needs 96 RZZ at 8 qubits and 1,827 at 20, growing as N^3.16: about 71,000 at 64 bits and 292,000 at 100. The
   admission budget passes 20 qubits on trapped ions and 8 on heavy-hex, at depth 1. For 30% modelled fidelity one layer at
   64 bits needs a two-qubit error about 35 times below our trapped-ion model. The problem's structure (a quartic energy)
   decides the substrate here, not its size.

13. Sampling. Plain Gibbs sweeps come within 10% TVD on 24 of 31 targets, in 32 sweeps or fewer: all 15 warm targets, the
   learned model and 8 cold targets. They fail on 7 cold targets (arm reach at every size, the 12-variable two-mode
   instance, and the colouring instances), where 1,024 sweeps leave a TVD of 0.21 to 0.99; annealing lowers that but does
   not fix it. Parallel tempering reaches 10% on all 10 cold targets it was run on, in 4 to 256 rounds. The spiking sampler
   tracks Gibbs: at its noise floor on the warm targets, and failing on the same three cold ones at 12 variables. QAOA
   never comes within 10%: its lowest TVD over depths 1 to 3 is 0.12 to 0.92 across 21 targets. Gibbs matches that
   figure within 8 sweeps on 19 of them. On the other two (cold arm reach) QAOA at depth 3 is slightly closer than 1,024
   plain Gibbs sweeps (0.76 against 0.78, and 0.92 against 0.96), and tempering is far closer than either (below 0.05).
   Under a global depolarising approximation with the trapped-ion fidelity fit, the best QAOA case (family B, warm) moves
   from 0.12 to 0.15 ideal to about 0.18.

14. Chemistry. This is the first family where the affordable on-device method fails. CCSD misses chemical accuracy on 8
   of 18 cases, by 3.9 to 180 mHa: the broken H4 and H6 chains, square H4, stretched H6, BeH2 and H2O, and N2 at both
   geometries. The trust check routes all 8. It also routes 8 of the 10 cases CCSD gets right, so as fixed it sends 16
   of 18 cases onward. Ideal UCCSD is closer than CCSD on 4 of the 6 failing cases it was run on (4.6 against 18.3 mHa,
   21.5 against 180, 12.6 against 126, 0.8 against 9.7) and not on the other 2 (4.8 against 4.3, 11.9 against 7.8). Its
   circuits need 22 RZZ at 4 qubits, 269 to 296 at 8 to 10, and 1,176 to 1,505 at 12: all inside the 2,000-gate
   trapped-ion budget, with modelled circuit fidelity of 0.99, 0.84 and 0.41 to 0.50. On heavy-hex only the 4-qubit case
   fits (47 CZ). Sampling-based diagonalisation gains nothing at these sizes: sampling the exact ground state reaches
   chemical accuracy sooner than random configurations on 0 of 16 cases, because spaces of 4 to 400 configurations are
   covered by chance. Exact diagonalisation answers every case here, so real hardware matters only past the emulation
   ceiling.
15. Materials. CCSD is accurate at U = 2 on the 6- and 8-site lattices and fails at U = 8 (0.4 to 23 per site off, or no
   convergence); the trust check routes every case it could be evaluated on. Unrestricted Hartree-Fock stays within
   0.01 to 0.10 per site everywhere. DMRG is exact to 8 sites and still moves by 0.01 to 0.04 per site between bond
   dimension 64 and 256 at 12 to 24 sites, so it had not converged there at this budget. From the free-fermion state,
   four ansatz layers beat unrestricted Hartree-Fock on 8 of 9 cases (error 0 to 0.13 per site; the miss is 2x4 at
   U = 8). From the product state they beat it on 0 of 9 (0.09 to 0.23 per site). One layer needs 28, 58, 96, 176, 256,
   536 and 876 RZZ from 2x2 to 6x6. With state preparation, the free-fermion circuits need 1,112 and 1,648 gates at 4x6
   for one and two layers, inside the 2,000-gate budget, and 2,172 at 6x6 for one layer, outside it. So the largest
   circuit with emulated evidence of beating the on-device method is 48 qubits; the 72-qubit circuits fit only from the
   product start and test the device, not the method.
16. Target chemistry. CCSD is wrong on 7 of 12 cases, by 1.9 to 94 mHa. Check 1 flags 6 of the 7 (the miss is PuO2 at
   equilibrium, 1.9 mHa) and 3 of the 5 it gets right. Check 2 flags 3 cases, all already flagged, and rerunning on the
   lower reference brings 1 of the 3 within 1.6 mHa (unconverged). Selected CI reaches 1.6 mHa on all 12, with 4 to
   1,134 determinants on the transition-metal cases and 3,417 to 73,712 on the actinides. The circuits need 164 to 805
   RZZ (modelled fidelity 0.91 to 0.62). Samples from them reach 1.6 mHa on 5 of 12, all with full spaces under 1,200
   determinants, and on none of the 4 actinide cases; on 5 of the 7 cases CCSD gets wrong the circuit state overlaps
   the exact state by less than 0.25, so the circuit inherits the cheap method's error. Sampling the exact state
   reaches 1.6 mHa on 10 of 12; on the two PuO2 cases it needs 864 and 1,364 determinants against 3,430 and 3,417 for
   selected CI. An earlier exploratory pass with crude active spaces reported the check catching 3 of 6 failures; that
   result came from unstable Hartree-Fock references and is withdrawn.
17. Worked mission example. Under the fixed rules the machine accepts 10 of 12 answers on site (3 cheap, 6 by on-board
   diagonalisation, 1 by on-board selected CI) in 0.6 to 32 seconds on one x86 core. 8 are right. The 2 wrong: PuO2 at
   equilibrium (cheap accepted unflagged, 1.9 mHa) and stretched uranyl (selected-CI self-check passed early, 5.6 mHa).
   The 2 escalated cases (uranyl at equilibrium, stretched PuO2) are resolved by remote selected CI, 1 of them by
   sampling the exact state within 10,000 shots, and neither by the circuits. The largest Hamiltonian is 117 kB; with
   10,000 shots returned (40 kB) the round trip is 6 to 45 minutes over a Mars relay, 3 minutes over a 2 km acoustic
   link and 44 minutes over a 90 km one. Those 10,000 shots cost about 20,000 HQC by the published formula.
18. IQM device model. The admission rule counts CZ gates on a patch of Qiskit's heavy-hex code lattice, which has
   10-qubit cycles from 12 qubits up; IBM's Heron lattices have none shorter than 12, and on the devices the 29 largest IBM
   circuits need a median 1.00 and at most 1.16 times as many CZ (vendor/results/verify/ibm_analysis_rerun.json). All 294 distinct
   Aim 1 circuits requested on IQM were transpiled to IQMFakeAphrodite, the 54-qubit crystal-lattice fake backend in
   IQM's open-source client, in its native gates (iqm_check.py, results/iqm/check.json). All 294 stay within 660 CZ, at
   a median 0.83 of the heavy-hex count (range 0.57 to 1.05). The heavy-hex figure is therefore a conservative proxy for
   IQM; circuits it rejected were not re-tested and some may fit. A fake backend is a published device model, not a
   live device.
19. IonQ emulator (vendor/scripts/build_circuits.py, to_native.py, ionq_run.py, score_ionq.py; vendor/results/ionq/scores.json,
   vendor/results/analysis.json). 172 of the 251 IonQ request rows (167 circuits up to 24 qubits) ran on IonQ's cloud
   simulator under its Forte noise model at the requested shots, once in native gates as written and once through IonQ's
   own compiler. These are emulator results, not device results. Not run: 32 rows above the simulator's 29 qubits, 13
   warm-start rows whose seed the package does not store above 20 variables, and 34 five-step rows with mid-circuit
   measurement and reset, which could not be run under IonQ's noise model (IonQ's JSON format has no measure or reset
   instruction, and every OpenQASM 3 job under the Forte noise model failed, including one with no mid-circuit
   measurement; IonQ's documentation says its simulator supports mid-circuit measurement, so the reason first recorded,
   that IonQ refuses them, is withdrawn and was corrected in vendor/results/ionq/not_emulated_rows.json after the run). Sent as written, one-step Aim 2
   programs keep 0.53 of their traces at 89 two-qubit gates (door) and 0.24 at 182 (counter). Fitted on the 21 programs at least twice the
   guessing floor, trace fidelity falls 0.80% per two-qubit gate (R2 0.98; the generic model gives 0.060%) and reaches 30%
   near 147 gates; fits that handle the floor otherwise give 127 to 155, and the plain rule of finding 7 (at least 20
   correct traces) gives 390 because programs at the floor flatten it (vendor/results/verify/refit_ionq.json). IonQ's
   compiler removed every two-qubit gate from 35 of the 41 one-step programs that had any, and all 44 compiled circuits
   output one fixed state: a one-step program on a known input is a fixed classical computation, which the compiler
   evaluates in advance. Programs must therefore go in native gates, with the executed count read back. QAOA keeps a
   median 0.42, 0.20 and 0.13 of its ideal optimum probability at depths 1, 2 and 3. Sampling circuits come back 0.63 to
   0.73 from their target, against 0.31 to 0.48 for 500 shots of the ideal circuit. H2 keeps 0.80 of shots with the right
   electron numbers; the transition-metal circuits keep 10% to 23%, 0.93 to 1.15 times the IonQ device model's no-error
   probability; on the programs the emulator loses a median 1.6 times the model's error, and 3 of the 10 kept QAOA rows with
   an emulator figure fall below 0.30 on it (vendor/results/analysis.json).
20. IonQ's own cost (vendor/results/ionq/estimates.json, cost_comparison.json; estimate_context withheld). IonQ's estimator
   returns credits at a per-compute-second rate: 6,664 credits for the IonQ core as first requested (IonQ's estimated
   execution time 6.2 hours) and 14,267 for its extension; 940 and 510 credits after re-admission (0.87 and 0.47 hours).
   Job records on the account name the cost model 2QGE_operations, and OLCF records IonQ hardware use in two-qubit gate
   equivalents. cost.py's gate-shots are the package's count, not IonQ's unit.
21. Device models from the makers' figures (vendor/scripts/models.py, sim_aim2.py, analyze.py; vendor/results/models/).
   Every trapped-ion circuit was costed under the generic model and under device models built from Quantinuum's published
   H2-1 data of 2023-03-10 (each two-qubit gate at its angle on (2.9 theta/pi + 0.46)e-3, memory 1.95e-4 per qubit per
   two-qubit layer) and IonQ's Forte characterization of 2026-11-14. Simulated Aim 2 traces (115 programs up to 10
   qubits, 2,000 shots) fall 0.157% and 0.43% per two-qubit gate, 30% at 756 and 264 gates; the IonQ simulation has no
   idle term. A second implementation (WAI Quantum, Apache-2.0, developed by Transaction Science, Inc., a company the PI
   founded) agrees with the budgets to a median 0.99 and 1.01 on 19
   circuits each; this checks the arithmetic, not the figures. Selene with its depolarizing model set to the H2 figures
   gives 0.145% per gate and 30% near 818 on 21 of the 25 Quantinuum programs up to 2,000 gates
   (vendor/results/models/selene/selene_fit.json). Re-admitted circuit by circuit (trace fidelity for Aim 2, the chance of
   no error event otherwise; on IonQ, Aim 2 held to one-step programs within the emulator's 147 gates), the core keeps
   66 of 130 IonQ rows and 72 of 93 Quantinuum rows (2,695 HQC against 15,861). The memory term is an upper bound for
   some circuit classes, and the Quantinuum figures are H2's, not the 98-qubit device's. Quantinuum's newest published
   figures (H2-2, 2024-12-06, in its repository's "Spec sheet parameters.csv": two-qubit error 1.4e-3, transport
   one-qubit error 5.3e-4, readout 9e-4 and 1.8e-3) are models.py's "quantinuum-h2-2-2024" (memory 4.6e-4 = 5.3e-4 less
   the legacy one-qubit error, the two-qubit line scaled by 1.4/1.93, as the 2023 model was built). Under them the
   carried-over rule crosses 30% near 495 gates on the programs alone and 554 over all Quantinuum circuits (643 and 758
   on the 2023 figures, against the simulated 756; the 2024 figures were costed, not simulated, here; finding 28 runs them on Selene), the Quantinuum
   core keeps the same 72 rows and the extension 20 of 82 (37 on the 2023 figures). Quantinuum's later figures (2025 and
   October 2026) were found afterwards on its documentation page and are finding 25, which supersedes the 2024 admission
   here. Models of IBM's calibrations of 2026-11-13 (ibm_kingston, ibm_fez, ibm_marrakesh) put the 30% point at 224
   to 284 CZ (WAI Quantum's budgets) or 324 to 415 (the budget script alone), against 754 for the generic model counted
   the same way (660 with its fitted intercept), and 25 to 27 of the 29 largest IBM circuits below 30%
   (vendor/results/verify/ibm_analysis_rerun.json). At 224 and 415 CZ the 588 IBM Aim 1 QAOA circuits would fall to 150
   and 424. The device check (finding 23) superseded the generic rule; the IBM request is finding 26.
22. The request of the revision of 15 November 2026, superseded by finding 26 (the figures below were computed by the
   earlier final_request.py; the current script reproduces its IQM and Quantinuum 2023 and 2024 edges). The re-admission above, on Quantinuum's newest published figures, plus three decisions. The 8 transition-metal circuits
   move from IonQ (0.08 to 0.23) to Quantinuum, which admits them (0.45 to 0.66 on the 2024 figures, 0.52 to 0.67 on the
   2023 ones; 1,209 HQC at 200 shots): the 30% rule applied on the device that passes them, and the admitted chemistry
   arm of Q8. The 4 actinide circuits run on Quantinuum below the 30% line as a stated test, at 50 shots (405 HQC by
   cost.py's formula with Nm = 2 x qubits): the generic law puts their fidelity at 0.62 to 0.67, Quantinuum's figures at
   0.14 to 0.22 (2024) and 0.19 to 0.27 (2023). Q8's nearest-model rule on a log scale chose the wrong model in none of
   2,000 simulated runs at 200 shots (transition metals) and 50 (actinides). And the three H2 rows, one circuit because
   chem.py uses one placeholder angle for every excitation, run as one circuit with their shots combined on IBM, IQM and
   IonQ. Totals: 2,380 circuits, 4,778,700 shots; at most 26 IBM minutes; 940 IonQ credits (1.65 million two-qubit
   gate-shots); Quantinuum core 84 circuits and 4,309 HQC, a planning ceiling against 15,861 first drafted; extension 44
   circuits, 510 IonQ credits, 2,869 HQC. The IQM credit figure was then pending; finding 27 gives it.
23. IBM device check, hardware (vendor/ibm-check/; README there). 24 circuits from the request ran on ibm_marrakesh on
   16 November 2026 under IBM's free open plan, twice: as compiled and with client-side dynamical decoupling. 16 Aim 2
   programs (10 to 1,113 CZ) and two controls (a zero-CZ five-step program and a 6-qubit mirror circuit) at 1,000 shots, and
   6 QAOA circuits (12 to 20 qubits, 130 to 666 CZ) at 4,000 shots, each placed at its admission CZ count (one needed 200
   against 193). Predictions of every model and the analysis code were sealed by hash before the run (prereg.txt). An
   independent re-score with its own decoder and a noiseless positive control agrees with the analysis on all 48
   circuit-runs. As compiled: controls 0.860 and 0.856 (pass marks 0.85 and 0.80). Per circuit, measured over predicted
   -ln F, median over programs: the budget script's e^-b 0.91, the only sealed model whose implied 30% point lies inside
   the device's 95% interval; every other model 2.3 to 3.9 (calibration simulation with idle error 2.6, without it 3.7,
   generic models 2.6 to 3.9). The 30% point is bounded, not measured: 117 CZ by the preregistered rule (95% interval up to
   261 by the sealed analysis's 2,000 draws; 269 by the re-score's 4,000), 85 to 258 over the three preregistered fits, because above 200 CZ the programs score near what a scrambled output
   gives (no program above 0.31). Q5's held-out factor is 2.19 against 1.25 (alternate programs in the package's name order, F >= 0.01), above the
   1.31 to 1.45 the sealed calibration models with idle error implied. Not preregistered: the largest extra loss came with
   mid-circuit measurement and reset: on the zero-CZ control a reset fails 3.5% to 5.3% of the time per
   step, and the six five-step programs lose 3.4 to 8.7 times the calibration simulation's error, against 1.7 to 2.3 for
   circuits without mid-circuit measurement that score well above a scrambled output, and 1.4 to 3.1 times the budget
   script's error (vendor/ibm-check/derived/). QAOA keeps 26% of its ideal optimum probability
   at 130 CZ, 6% at 200 and at most 3% from 351. The decoupled arm's zero-CZ control scored 0.828 against 0.85, so by the
   preregistration that arm is not interpreted. One device, one day, with calibrations 2.6 days older than the run.
24. IBM ladder budgets (vendor/scripts/ladder_budget.py; vendor/results/ibm/ladder_budget.json, ladder_design.json). Every
   IBM Aim 2 program up to 234 CZ (twice the device check's 117; 157 programs, stream 0) was built by the package's code,
   placed on ibm_marrakesh exactly as the device check placed its circuits, and costed by the check's sealed budget.py on
   the design-time calibration, on a build host. 151 were placed; 6 garbage-retaining programs of 12 to 17 qubits use the
   heavy-hex patch's 10-qubit cycle, which Heron lattices lack, and are rechecked on the device transpilation. The check's
   own 5 circuits in this range reproduce their sealed e^-b exactly. Of the 68 programs that measure or reset qubits
   mid-circuit, 60 keep e^-b of at least 0.30 and 8 (24 circuits over their event streams) fall below it.
25. Quantinuum figures, 2023 to 2026 (vendor/results/quantinuum-2025/, vendor/scripts/quantinuum-2025/,
   vendor/scripts/quantinuum_sets.py, vendor/results/models/quantinuum_sets.json). Quantinuum published H2 figures for
   30 April, 29 May and 28 August 2025 and for 6 and 20 October 2026 on its documentation page (Performance Validation);
   its repository table ends at 6 December 2024. Our own randomized-benchmarking fits of its raw 2023 to 2025 data (our
   code, written from Moses et al. 2023 and Chen and Baldwin 2025; none of Quantinuum's code was run) reproduce 51 of 51
   published values within the published one-sigma. Every request circuit was costed under the eight published sets by
   models.py's own rules (the 2023 and 2024 sets reproduce models.py's predictions exactly). Carried over, the rule
   crosses 30% between 495 (H2-2, December 2024) and 1,387 (H2-2, August 2025) gates on the programs, and at 719 and
   1,147 on H2-1's and H2-2's figures of October 2026. Every set admits the same 72 core rows (H2-2's sets of August 2025 and October 2026 admit 3 and 1 more). H2-1's newest figures
   are worse than H2-2's on every modelled term; the request admits on them. On them the transition-metal circuits keep
   0.56 to 0.73 and the actinides 0.24 to 0.33 (0.45 to 0.83 and 0.14 to 0.55 over all eight sets), family A at 60 qubits
   0.10 to 0.11 (0.03 to 0.35), and the 48- and 72-qubit Hubbard circuits at most 1% (12% over all sets). The October
   2026 figures have no raw data, so they could not be refitted.
26. The request (vendor/scripts/final_request.py, which takes the Quantinuum figure set as a parameter, default H2-1 of 20
   October 2026; vendor/results/final_request.json). IBM and IQM Aim 1 is admitted at 117 CZ on the heavy-hex patch: 84
   QAOA circuits (all at 12 qubits, depth 1), the 2x2 Hubbard lattice at 1 and 2 layers and the merged H2 circuit, 89 in
   all; no pulse-code or sampling circuit fits. Aim 2 on IBM is the ladder of finding 24: 425 circuits (56 of them above
   117 CZ); on IQM its R and P styles, 210. IQM takes IBM's cap and ladder until its own device check. IonQ is unchanged.
   Quantinuum's core keeps 84 circuits: the 72 re-admitted rows (2,695 HQC), the 8 transition-metal circuits (1,209) and
   the 4 actinide circuits at 100 shots (790), each counted once (the earlier script would have counted the actinides
   twice on any figure set that admits them). At 100 shots shot noise alone gives Q8's nearest-model rule a wrong verdict
   in at most 0.75% of 2,000 runs over the eight published sets (3.9% at 50 shots). Totals: 961 circuits and 1,231,900
   shots in period 1; IBM about 5 minutes by cost.py's formula (4.7 at the device check's charged rate of 15 s per 42,000
   shots), against 26.0; IonQ 940 credits; Quantinuum 4,694 HQC. Period 2, if the mid-term exam passes: 61 circuits
   (24 IonQ, 37 Quantinuum), 19,400 shots, 510 IonQ credits and 7,444 HQC.
27. IQM cost (vendor/results/iqm/, vendor/scripts/iqm/). IQM's Resource Calculator formula, transcribed from its public
   page, at Emerald's price read from IQM Resonance (0.75 credits per second), without its discount for multiple jobs: 57
   credits for an IQM device check of the IBM design (both arms) and 225 for the provisional IQM set of 299 circuits and
   392,000 shots, 282 in all, inside the 400 credits QCUP gives a new project. The same formula gives 873.1 for the earlier
   set, as estimate.py computed. On IQM's mock of Emerald (priced at 0), 147 request circuits of the earlier set in 16 jobs
   compiled, 31 Aim 2 programs with mid-circuit resets among them; IQM's runtime estimate is 0.41 to 0.44 ms per shot. The
   mock returns random bits, so it checks compilation and time only. On IQM's 54-qubit device model the 42 distinct Aim 1
   circuits need at most 103 CZ.
28. Selene with Quantinuum's published emulator parameters (vendor/selene-params/; README there). All 84 Quantinuum core
   circuits and the 44 extension programs ran on Selene 0.3.8 (state vector, soft-RZ runtime) under Quantinuum's
   published emulator parameters for H2-1 (2024-05-20) and H2-2 (2024-12-06), the newest in its emulator parameter table, at 200 shots
   (the 4 actinide circuits at 100 to 200). Selene runs one error model at a time: its depolarizing model holds the gate terms and
   the mean readout figure, and our error-model plugin (vendor/selene-params/plugin/, loaded through Selene's documented
   plugin interface) replaces it and holds every term, adding emission and leakage, asymmetric readout, measurement
   crosstalk and memory error, one step per qubit per layer of Selene's runtime. Not representable
   from the table: the angle dependence of two-qubit error (every RZZ carries the full figure), transport timing and the
   weights of the asymmetric channel. With every term the 115 programs, to 1,995 two-qubit gates, lose 0.165% and 0.162%
   per two-qubit gate (R² 0.97 and 0.95; 104 and 103 programs with at least 20 correct traces fitted), 30% near 715 and
   720 by least squares (near 630 and 590 by final_request.py's median rule; 739 and 707 by least squares on the 71
   core programs alone), against 506 and 495 for our model of the same figures by final_request.py's rule (360 and 357
   by least squares), so at the 30% point the model is the more cautious. Circuit by circuit it is not uniformly so: on
   the 35 core programs with at least 20 two-qubit gates Selene falls below the model on 15 and 16 (8 and 7 beyond its
   95% interval, by at most 9% and 11%), and every one stays above 0.58. All 80 admitted circuits clear 30% on both sets
   (the chemistry and pulse-code circuits on error-free shots; under H2-1's set the 95% intervals of three
   transition-metal circuits straddle 0.30): programs 0.585 to 1.00; the transition-metal circuits keep 0.43 to 0.70 of shots with the right electron numbers against 0.45
   to 0.68 modelled, each within 13% of the model; the 4 actinide circuits keep 0.25 to 0.32 against 0.16 to 0.24 and
   run free of any error in 0.07 to 0.15 of shots, below the line as Q8 intends. Selene's depolarizing model alone gives
   0.083% and 0.089% per gate, 30% near 1,440 and 1,350. The plugin's positive controls (readout, memory, emission,
   crosstalk) fall within 2σ of closed form, and with no noise every program gives its reference trace and every
   transition-metal shot the right electron numbers (124 ideal runs; the 4 actinide circuits had none). The package's HQC formula reproduces final_request.json's
   4,694.2. Our assumptions: the plugin's rule for a leaked qubit's partner, the memory placement, and applying the emission
   leakage branch to H2's sets (Quantinuum's documentation places its leakage model in the Helios emulators).

## Detail moved from the application (16 November 2026)
The application was shortened for reading on 16 November 2026. What it no longer carries is kept here word for word: its
full Simulations section, then shorter passages grouped by the application section they came from. Every figure traces to
the findings above. In these passages "H2" in a chemistry row or circuit count is the hydrogen molecule (the application
now writes H₂); H2-1 and H2-2 are Quantinuum devices.

### Simulations, in full

Completed before submission, 11 to 16 November 2026, with ferrotherm 0.44.0, ferromorphic 0.23.2, Qiskit 2.6.2, Qiskit Aer 0.18.2, PySCF 2.15.0, TeNPy 1.1.1 and ffsim 0.0.86. Quantum results are simulations, emulations or device models, except the row marked hardware. Two noise models are generic depolarizing models at the order of magnitude of publicly reported error rates. Device models use the makers' figures (Quantinuum's published H2 figures of 2023 to 2026; IonQ's characterization of 14 November 2026) and IBM's calibrations of 13 November 2026; IonQ's cloud emulator ran under its Forte noise model, and IQM's mock of Emerald compiled our circuits. None of these is a device run.

| Run | What was measured | Result |
| --- | --- | --- |
| Certificate | ferrotherm certified semidefinite bound against the exhaustive optimum, 120 instances in 4 families, 12 to 20 variables | Valid on 120 of 120. As a share of the feasible-state spread: within 0.9% of the optimum on A and 0.05% on B; 0.7% to 2.5% below it on program repair, 1.3% to 18% on Sherrington–Kirkpatrick and 28% to 89% on C |
| Cold QAOA | ferrotherm exact state vector, depths 1 to 3 | Median ideal ground-state probability at depth 3 and 12 qubits: 0.66 (program repair), 0.25 (B), 0.12 (Sherrington–Kirkpatrick), 0.018 (A), 0.020 (C) |
| Warm-start QAOA | Egger et al. warm start seeded by Goemans–Williamson rounding, 120 instances up to 20 qubits, depth 3 | Seed optimal (70): beats cold in 68, median probability 0.70 against 0.17. Seed not optimal (50): beats cold in 14, median 0.0025 against 0.020. At depth 1: 70 of 70 and 25 of 50 |
| Edge arms | Parallel tempering and the spiking annealer, time-to-solution at 99%, 32 seeds per run length | Both solve all 120, in 157 to 328,000 spin proposals or 319 to 46,400 neuron updates; ideal depth-3 QAOA needs more shots times gates on 113 instances and fewer on the 7 program-repair instances |
| Scale-up, 24 to 60 variables | 60 instances: certified bound, branch and bound, parallel tempering and transpiled gate counts | Optimum proved on 51 of 60. Tempering misses 8 (family A at 32 to 60 variables), whose answers at 60 carry certified gaps of 2% to 30%. Depth-1 circuits at 60 qubits: 120 to 1,770 RZZ all-to-all |
| Angle transfer | Angles optimized at 12 variables applied to 35 instances at 15 to 20, depths 1 to 3 | At least 95% of the optimized approximation ratio kept in 87 of 105 cases; family B at depths 2 and 3 accounts for 16 of the 18 misses |
| Pulse-code design (family E) | Low-autocorrelation sequences of 8 to 26 bits: native quartic annealing, a pairwise form, exact QAOA emulation to 20 qubits | Native annealing solves every size in under 500,000 flips; the pairwise form fails from 16 bits up. QAOA needs 66 to 630 times the native annealer's work. One layer needs 96 RZZ at 8 qubits and, extrapolated, about 71,000 at 64 |
| Sampling | 31 targets with exact distributions; Gibbs sweeps, tempering, the spiking sampler, and QAOA at depths 1 to 3 to 16 qubits | Gibbs comes within 10% total variation on 24 of 31 targets and tempering on all 10 cold targets tested; QAOA's best error is 12% to 92% over 21 targets |
| Chemistry (family F) | 18 small-molecule cases (H2 to N2), coupled cluster with a trust check, full configuration interaction, UCCSD circuits | Coupled cluster misses chemical accuracy on 8 of 18, by 4 to 180 millihartree; the check routes all 8. Only the 4-qubit circuit fits heavy-hex (47 CZ) |
| Materials (Hubbard model) | Half filling on 2×2 to 4×6 lattices; Hartree–Fock, coupled cluster, DMRG, exact to 8 sites; Hamiltonian variational ansatz to 8 sites, circuits to 6×6 | Coupled cluster fails at U = 8; from the free-fermion state four ansatz layers beat unrestricted Hartree–Fock on 8 of 9 cases, from a product state on none. One layer needs 256 RZZ at 4×4 and 876 at 6×6 |
| Target chemistry (family F) | FeO, MnO, NiO, FeS, uranyl and PuO₂, each at two bond lengths, 16 to 26 qubits; coupled cluster with checks, selected CI, full CI, and a one-layer cluster-Jastrow circuit from the cheap amplitudes, sampled and diagonalized classically | Coupled cluster is wrong on 7 of 12, by 1.9 to 94 mHa; the amplitude check flags 6. Circuits need 164 to 805 RZZ (modelled fidelity 0.45 to 0.83 for the transition-metal circuits and 0.14 to 0.55 for the actinides under Quantinuum's figures of 2023 to 2026). Their samples reach chemical accuracy on 5 of 12 and on no actinide; sampling the exact state does on 10 of 12, with 864 and 1,364 determinants on the two PuO₂ models against 3,430 and 3,417 for selected CI. These models pose the routing question; they do not predict the real molecules |
| Worked mission example | The 12 target cases walked down the ladder under rules fixed in advance, then scored against the exact answer; link figures from NASA (Mars relay) and acoustic-modem data | Accepted on site: 10 of 12 in 0.6 to 32 seconds on one x86 core; right 8, wrong 2 (1.9 and 5.6 mHa). Escalated: 2 actinide cases. 10,000 returned shots take 6 to 45 minutes over a Mars relay and would cost about 20,000 HQC, so shot count is the binding cost |
| Reversible programs | 40 RCE programs (14 cut to 8 states), three styles, 1 to 5 steps, 557 circuits | Reset style holds width at 2 to 11 qubits at 5 steps. Log gate count follows transition-function complexity (R² 0.97); overwritten bits improve held-out prediction by 2% |
| Trace fidelity | 317 and 389 circuits up to 3,000 two-qubit gates, two generic noise models | Falls 0.16% per CZ (R² 0.90) and 0.060% per RZZ (R² 0.99); a fit on half the programs predicts the other half within a median factor of 1.13 and 1.02 |
| Emission and replay | 225 OpenQASM 3 circuits and 225 Guppy programs; 45 run on the open-source Selene emulator | 45 of 45 replay their reference traces |
| IonQ emulator | 172 of the 251 IonQ request rows on IonQ's cloud simulator under its Forte noise model, in native gates and through IonQ's compiler; not run: 32 rows above 29 qubits, 13 warm-start rows with no stored seed, 34 five-step rows that could not run under its noise model | One-step programs lose 0.80% per two-qubit gate (R² 0.98, 21 programs), 30% near 147; the emulator loses a median 1.6 times the IonQ device model's error on them. IonQ's compiler removed every two-qubit gate from 35 of 41 programs. QAOA keeps a median 0.42 of its ideal optimum probability at depth 1; sampling circuits 0.63 to 0.73 total variation; H2 keeps 0.80 of shots with the right electron numbers |
| IonQ cost estimate | IonQ's estimate endpoint for every IonQ circuit and shot count | Core: 6,664 credits as first requested, 940 as revised. Extension: 14,267 and 510 |
| IQM mock | 147 circuits of the earlier IQM request in 16 jobs on IQM's mock of Emerald, priced at 0 credits | All compiled, mid-circuit resets included; the mock returns random bits, so it checks compilation and time only. Runtime estimate 0.41 to 0.44 ms per shot |
| Device models from the makers' figures | Every trapped-ion request circuit costed under Quantinuum's eight published H2 figure sets, 2023 to 20 October 2026 (those of 2023 to 2025 refitted by us from Quantinuum's raw data, all 51 published values reproduced), and IonQ's characterization of 14 November 2026; 115 Aim 2 programs simulated under the 2023 Quantinuum and the IonQ figures | Aim 2 traces fall 0.157% (Quantinuum 2023) and 0.43% (IonQ) per two-qubit gate, 30% near 760 and 264; carried over to the later figures, 500 to 1,400 (720 on H2-1's newest). Kept: 66 of 130 IonQ core rows; on Quantinuum every set admits the same 72 of 93 core rows (H2-2's sets of August 2025 and October 2026 admit 3 and 1 more), and 37 of 82 extension rows on H2-1's newest. Family A at 60 qubits: 0.03 to 0.35 |
| Selene, H2's 2023 figures | The 25 Quantinuum Aim 2 programs at 5 steps on Selene, its depolarizing model set to H2's 2023 published figures, 200 shots | 0.145% loss per two-qubit gate (R² 0.99, 21 programs with at least 20 correct traces), 30% near 820 |
| Selene, Quantinuum's published emulator parameters | All 84 Quantinuum core circuits and the 44 extension programs on Selene 0.3.8 (state vector, soft-RZ runtime), with Quantinuum's emulator parameters for H2-1 (May 2024) and H2-2 (December 2024): Selene's depolarizing model (all but the 4 actinide circuits), and Selene with our plugin adding emission and leakage, asymmetric readout, measurement crosstalk and memory error (one step per qubit per layer of Selene's runtime); 200 shots (actinides 100 to 200). Not in Quantinuum's table, so not represented: angle-dependent two-qubit error, transport timing, the asymmetric channel's weights. With no noise every program gives its reference trace and every transition-metal shot the right electron numbers | With every term, 0.165% and 0.162% loss per two-qubit gate (R² 0.97 and 0.95), 30% near 715 and 720 (630 and 590 by our admission rule), against about 500 for our model by that rule. All 80 circuits we admit clear 30% (programs 0.585 to 1.00; chemistry and pulse-code circuits on error-free shots); transition-metal shares 0.43 to 0.70 against 0.45 to 0.68 modelled; actinides 0.25 to 0.32 against 0.16 to 0.24, below the line on error-free shots (0.07 to 0.15). Depolarizing model alone: 0.083% and 0.089%, 30% near 1,440 and 1,350 |
| IBM calibrations, 13 November 2026 | The largest IBM-requested circuit per family and size (29) on the ibm_kingston, ibm_fez and ibm_marrakesh calibrations, by a device model and a budget script | Budget a median 2.7 to 3.4 times the generic model's; 30% point 224 to 415 CZ, against about 750 for the generic model counted the same way |
| IBM device check (hardware) | 24 circuits from this request on ibm_marrakesh, 16 November 2026, IBM open plan: 16 Aim 2 programs (10 to 1,113 CZ) and two controls (a zero-CZ program, a 6-qubit mirror circuit) at 1,000 shots; 6 QAOA circuits (12 to 20 qubits, 130 to 666 CZ) at 4,000 shots; each at its admission CZ count (one needed 200 against 193); no twirling or mitigation; predictions and analysis sealed by hash first; run as compiled and with dynamical decoupling | As compiled: controls 0.86 and 0.86 (pass marks 0.85 and 0.80). Measured over predicted error, median over programs: 0.91 for the budget script, the only sealed model whose implied 30% point lies inside the device's interval; 2.3 to 3.9 for every other model. 30% point 117 CZ by the preregistered rule (95% interval up to 261), 85 to 258 over three preregistered fits; above 200 CZ no program kept more than 0.31. Q5 held-out factor 2.19 (limit 1.25; 1.31 to 1.45 implied by the sealed calibration models with idle error). Not preregistered: five-step programs lost 3.4 to 8.7 times the calibration simulation's error, circuits without mid-circuit measurement that score well above a scrambled output 1.7 to 2.3, and five-step programs 1.4 to 3.1 times the budget script's; reset failure 3.5% to 5.3% per step. QAOA kept 26% of its ideal optimum probability at 130 CZ, 6% at 200, at most 3% from 351. The decoupled arm is not interpreted: its zero-CZ control scored 0.828 against 0.85 |
| IBM ladder budgets | Every IBM Aim 2 program to 234 CZ placed on ibm_marrakesh as the device check placed its circuits, costed by the check's sealed budget script | 151 of 157 placed (6 use the patch's 10-qubit cycle); the check's own 5 circuits in range reproduce their sealed values exactly. Of 68 programs that measure or reset mid-circuit, 60 keep at least 0.30; the 8 below (24 circuits) are not requested |
| RELAX/1 quantum lowering | 3 RELAX/1 programs lowered to QAOA on the ideal emulator, each with an OER/1 receipt | One certified optimum, one certified gap of 8.4%, one refusal at 1,428 CZ against its budget |
| KV260 metered fabric | 256 p-bit fabric, INA260 board power, 8 paired shuffled passes (ferrotherm 0.44.0 at commit 3c47471, whose metering logs and recomputing test ship with ferrotherm, not with this package) | 25 million sweeps per second; 19.1 pJ per flip; 44.1 nJ per node write (one node's couplings) |
| ferrotherm exact cuts | Planar maximum cut; G-set upper bounds (source: TR-2026-47, physicalai-bmi.org, not this package) | Exact at 10,000 spins; G11 bound equals best-known cut 564 |

What the simulations say. On the decision problems tested, the on-device tier sufficed: it solved all 120 instances to 20 variables, in fewer operations than ideal QAOA on 113, and classical search proved 51 of 60 optima from 24 to 60 variables. The first uncertified on-device answers appear at 60 variables, which all-to-all devices admit under our generic model and, of the makers' figures, only under Quantinuum's H2-2 figures of August 2025 (modelled fidelity 0.03 to 0.35; 0.10 to 0.11 on H2-1's newest). Problem structure decides the substrate: a plain annealer solves pulse-code design at every size we can emulate, and simulated p-bit sampling with tempering comes within 10% of every target tested, which no QAOA depth up to 3 does. Chemistry is where the on-device method fails for a physical reason: on the oxide and actinide models the check flags 6 of 7 failures, and under rules fixed in advance the machine accepts 10 of 12 answers, 8 correctly, and escalates 2, which remote selected CI resolves and our circuits, which inherit the cheap method's error, do not. A remote tier is needed only past the emulation ceiling; whether it should be a quantum processor or a supercomputer is what larger runs must decide, and this request measures the device fidelity they would need. Under the makers' figures none of the 48- and 72-qubit Hubbard circuits keeps more than about 12% modelled fidelity (1% on H2-1's newest), so they are not requested. The exponential fidelity law holds in every noise model, but the trapped-ion device models and IonQ's emulator put the 30% point 1.4 to 13.5 times below our generic model's, and the IBM device check found the generic model underestimating each program's error by a median 2.6 to 3.9 times, so the rate has to be measured on each device. Limits: small sizes, naive oracle synthesis, 14 of 40 programs truncated, no crosstalk errors outside the Selene check, and short time-to-solution runs. The supporting package (code, per-instance results, figures, SHA-256 manifest) accompanies this application; if the form cannot take it, it goes to the OLCF Accounts Team at accounts@ccs.ornl.gov.

### Shorter passages, by application section

Scientific Significance:
- Tensor networks now treat iron–sulfur clusters with 36 to 102 active orbitals on large computers (Legeza et al. 2026).
- Cross-platform benchmarks map where a device's output becomes indistinguishable from random (linear-ramp QAOA on 24 processors from six vendors; Montañez-Barrera et al. 2025)
- our planning model sits 1.4 to 13.5 times above these sources
- QCUP users get the fidelity law per device and an admission rule, with scripts, that sizes a request before any device time; it cut this one.
- ours run in native gates, with the executed count read back.

Scientific Objectives:
- Q1: (0.03 to 0.35 across its figures of 2023 to 2026); the crossover is reported with its interval.
- Q5: above the 1.31 to 1.45 its sealed calibration models with idle error implied.
- Q6: about 71,000 two-qubit gates per layer at 64 bits, extrapolated, with the 8-qubit circuit as a measured point on the trapped-ion devices.
- Q8: Escalated chemistry returns as samples that the machine diagonalizes itself, so it accepts only a verified upper bound. The actinide circuits run across the line (0.24 to 0.33 on the figures we admit on, 0.14 to 0.55 over Quantinuum's figures of 2023 to 2026).
- Q7: simulated parallel tempering, the fabric's native sampler, does on every cold target tested.

Proposed Technical Approach:
- (A) planar arm posture reach
- (we admit on H2-1's newest)

Team Members:
- He wrote the open-source solvers and harness every classical arm runs on, and has run this project's pipeline on vendor systems: the 24-circuit IBM device check in Simulations, designed, sealed by hash, run in two arms and scored within one day; 172 rows of this request on IonQ's cloud emulator, with IonQ cost estimates, through IonQ's API in native gates and through IonQ's compiler; 147 circuits compiled on IQM's mock of its Emerald device; Selene replays of 45 Guppy programs; and a metered 256 p-bit FPGA fabric whose raw power logs ship with a test that recomputes them.

Justification for Resources:
- ferrotherm's QAOA matches an independent NumPy state vector to 6×10⁻¹¹ on all 360 instance and depth pairs; every compiled Aim 2 circuit of width 14 or less replays its reference trace exactly without noise; a 256 p-bit fabric on an AMD Kria KV260 is metered at 19.1 pJ per spin flip. The harness already lowers and submits circuits: it produced every circuit of the IBM device check.
- First device check, the full paragraph: On 16 November 2026, 24 circuits from this request ran on ibm_marrakesh under IBM's free open plan (no QCUP time was used): 16 Aim 2 programs, two controls and 6 QAOA circuits, with every prediction and the analysis code sealed by hash beforehand (package: vendor/ibm-check). Compared circuit by circuit with the measurements, the per-circuit error budget our budget script computes from IBM's calibrations came closest: measured error was a median 0.91 of its prediction, and it is the only sealed model whose implied 30% point lies inside the device's interval. Every other sealed model underestimated error by a median 2.3 to 3.9 times. The fits bound the 30% point without measuring it: our preregistered rule gives 117 CZ (95% interval up to 261) and the three preregistered fits give 85 to 258 CZ, against 660 for the generic model, because above 200 CZ no program kept more than 0.31 of its traces and most scored near what a scrambled output gives. Q5 failed at 2.19 against its limit of 1.25, above the 1.31 to 1.45 that the sealed calibration models with idle error implied. The largest extra loss came with mid-circuit measurement and reset, an observation the preregistration did not test: the zero-CZ control shows about 4% to 5% reset failure per step, and the six five-step programs, which measure qubits between steps, lost 3.4 to 8.7 times the calibration simulation's error, against 1.7 to 2.3 times for circuits without mid-circuit measurement that score well above a scrambled output. A second arm with dynamical decoupling is not interpreted, as preregistered, because its zero-CZ control scored 0.828 against the 0.85 pass mark. The check re-set the superconducting request: IBM's Aim 1 QAOA set fell from 588 circuits to 84, and its Aim 2 set from 655 to 425.
- IBM: The device runs the heavy-hex patch circuit unchanged, except 6 garbage-retaining programs of 12 to 17 qubits that use a 10-qubit cycle Heron lattices lack; those are rechecked on the device transpilation.
- IQM: the 42 distinct Aim 1 circuits need at most 103 CZ on IQM's own 54-qubit device model
- Risks: Seeding circuits from the on-board selected-CI state comes after this request, once the fidelity law can size those circuits.

Prepared Code:
- **ferromorphic 0.23.2** (Institute, Apache-2.0; every module checked against a closed form): neuromorphic computing stack with neuron models from Hodgkin–Huxley to resonate-and-fire, learning rules from STDP to EventProp, spiking QUBO, a NIR bridge and an energy ledger.
- **QCUP pre-submission harness** (Rust and Python, in the supporting package): instance generators, a transition-table harvester, a program-repair QUBO encoder, runners for ferrotherm and ferromorphic, warm-start QAOA, Qiskit circuit construction and transpilation, reversible-circuit synthesis from RCE programs, OpenQASM 3 and Guppy emission with a Selene replay check, noisy sampling, a draft RELAX/1 quantum lowering with OER/1 receipts and typed refusals, the chemistry, Hubbard and target-chemistry studies, the worked mission example, and the scripts that derive the request from the admission rule.
- Added before submission (vendor/ in the package): an IonQ API client, the device models, the Quantinuum figure fits, the IBM calibration analysis, the sealed IBM device check with its re-score, the IQM cost estimate and the script that sets the request. In development: the quantum lowering as a released package.

Data Models Used:
- an energy (Ising, factor graph or learned), a state type, a budget and a requested operation
- drawn from the public Form corpus

## Limits
Target chemistry: models that pose the routing question, not predictions for the real molecules. No orbital optimisation, no spin-orbit coupling on the actinides, minimal-size active spaces; the transition-metal spaces are small enough to diagonalise outright, so only the 4 actinide cases test the upper rungs. Selected CI is PySCF's simple product-space selection, not a state-of-the-art heat-bath or DMRG code, so the classical side is understated. The circuit is one layer seeded from CCSD amplitudes with no variational optimisation. Noise is modelled as a mixture with uniform bitstrings at the fitted fidelity. Several cases sit near mean-field instabilities: runs are single-threaded and seeded, the models reproduce exactly across three runs, and the final ladder was run once. Workflow: the 10,000-determinant on-board limit and the wired link are assumptions; seconds are for one x86 core, not field hardware.
Materials: half filling only, where quantum Monte Carlo has no sign problem and is exact, so these lattices do not test the limits of classical methods; the classically hard regime is doped lattices, with circuits of the same size, and was not run. DMRG stopped at bond dimension 256. The ansatz was emulated to 8 sites only and its angles above that are transferred, untested. State-preparation gate counts are estimates. Reference energies above 8 sites are unconverged DMRG values.
Small sizes (n <= 20). Naive oracle synthesis.
Family E: our annealer is a simple one with a fixed schedule and its scaling fit is noisy (r2 0.75); the classical tier never ran out at the sizes tested, so the sizes where it does are taken from the literature, not measured here. QAOA above depth 3 was not emulated. Generic noise with no idle, crosstalk or leakage errors.
Time-to-solution estimates at short run lengths rest on 1 to 3 successes in 32 and are noisy.
The spiking annealer's final temperature was chosen as the best of three declared values.
No joules are reported for any quantum circuit or for the neuromorphic arm.
Scale-up instances have 3 seeds per size and one tempering budget; a longer run or a tuned ladder may reach the family A optima.
QAOA quality above 20 variables is not simulated; only gate counts are.
Sampling: QAOA was emulated to 16 qubits and depth 3 only, and tempering to 16 variables; tempering and spiking figures are empirical with noise floors of 0.007 to 0.06; the larger targets were annealed to 256 sweeps only.
Chemistry: minimal basis and small molecules only; stronger classical methods (DMRG, selected CI) were not run; the trust-check thresholds were not tuned and over-route; UCCSD at 10 and 12 qubits was capped at 80 iterations; N2 has no UCCSD result.
14 of the 40 Aim 2 Forms are truncated to 8 states. No fidelity was sampled above 3,000 two-qubit gates.
The program-repair instances are small (3 to 6 suspect entries, 19 instances from 11 Forms) and use two-step tests only.
IonQ's cloud emulator was run (finding 19). Quantinuum's hosted emulators (H2-1E, H2-2E, Helios-1E) and its Nexus-hosted devices were not run before submission; Selene ran locally (finding 28), and each monthly HQC request is to be emulated first. Quantinuum's table gives no angle dependence of two-qubit error, transport timing or weights for the asymmetric channel, so the Selene check leaves them out. IQM's mock of Emerald was used for compilation and timing only (finding 27). The IQM device-model check covers Aim 1 circuits only. Device models are models: findings 19 to 22, 24, 25 and 28 are not device results. Finding 23 is one device on one day.

## Reproduce
pip install -r requirements.txt, then ./run_all.sh (about a day on 2 cores). The harvest needs a clone of openIE-dev/rce and its checker binary (cargo build --release in spec/checker); forms/ and repair/ hold the harvested tables and repair instances used here, so the later steps run without it. The Cargo files fetch ferrotherm and
ferromorphic at the commits above. results/manifest_sha256.json lists the SHA-256 of every JSON result file.

## License
Code: Apache-2.0 (LICENSE). Results, figures and instance definitions: CC0 1.0 (LICENSE-NOTE.md).

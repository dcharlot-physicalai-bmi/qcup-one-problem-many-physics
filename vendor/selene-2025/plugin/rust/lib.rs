//! A Selene error-model plugin that applies Quantinuum's documented default emulator noise parameters (H2-1E and
//! H2-2E of 2025-07-16, Helios-1E of 2025-11-18) as far as Quantinuum's Emulator Noise Model page defines them.
//! Written for the QCUP application's emulator check; it is ours, not Quantinuum's emulator. It extends the plugin of
//! the 2024 run (qcup-selene-params/plugin/rust/lib.rs) with the documented angle scaling of the two-qubit fault,
//! Helios's leakage and seepage terms, and the documented absence of leakage in the H2 emulators.
//!
//! Terms, per native operation Selene's runtime issues:
//!   one-qubit gate (rxy): a fault with probability p1, applied after the gate. A fraction p1_emission_ratio of p1 is
//!     spontaneous emission (X a quarter of the time, Y a quarter, the leakage branch half, as the documentation
//!     states); the rest is depolarizing (X, Y, Z evenly: Quantinuum's channel is asymmetric with weights it does not
//!     publish).
//!   rz: none (a frame change on the device; under Selene's soft-RZ runtime it never reaches the error model).
//!   two-qubit gate (rzz at angle theta): emission with probability p2 * p2_emission_ratio, on one of the two qubits
//!     chosen evenly ("the spontaneous emission error channel is the same for both ZZ() and RZZ(theta)"), and
//!     depolarizing (one of the 15 two-qubit Paulis, evenly) with probability p2 * (1 - p2_emission_ratio) * s(theta),
//!     where s is the documentation's "Parameterized Angle Scaling":
//!         s = przz_a |theta/pi|^przz_power + przz_b   (theta < 0)
//!         s = przz_c |theta/pi|^przz_power + przz_d   (theta > 0; the page prints "theta < 0" twice, a typo)
//!         s = (przz_b + przz_d) / 2                   (theta = 0)
//!     theta is taken as its remainder modulo 2 pi, in [-pi, pi]. The defaults (0, 1, 0, 1, 1) give s = 1 at every
//!     angle: the 2024 plugin's full p2 on every rzz.
//!   leakage branch: with --leakage-model=true and --leak2depolar=false (Helios-1E), the qubit leaks: it takes no
//!     gates, reads as 1, returns on reset, and is traced out when it leaks (reset in the simulator). Otherwise (the
//!     H2 emulators, whose documentation says leakage "is not included in H2 emulators", or leak2depolar=true) the
//!     branch is a depolarizing error instead: X, Y or Z evenly.
//!   seepage (leakage model only): a leaked qubit returns to the computational space with probability p1_seepage_prob
//!     at each one-qubit gate it is given and p2_seepage_prob at each two-qubit gate; the gate itself is not applied,
//!     and the qubit returns to |0> or |1> evenly (our assumption: the documentation does not say which state).
//!   a two-qubit gate with one leaked qubit is not applied, and the other qubit gets I, X, Y or Z evenly (our
//!     assumption, as in the 2024 run).
//!   memory: Z with probability memory_pz per elapsed unit of the runtime's clock (the soft-RZ runtime with only the
//!     rzz duration set, so one unit is one layer of two-qubit gates), charged to a qubit when it is next used, for the
//!     time since its last use, while it holds a state a Z can change. For k units: (1 - (1 - 2 memory_pz)^k) / 2.
//!     memory_pz = 0 unless a duration per layer is assumed (Quantinuum publishes the dephasing rates, not the
//!     durations of its transport schedule).
//!   measurement: a 0 is read as 1 with probability p_meas_0, a 1 as 0 with probability p_meas_1. Each measurement
//!     also, with probability p_crosstalk_meas for every other qubit in use, measures that qubit and discards the result
//!     (a Z with probability 1/2); the documentation's leaking branch of crosstalk is not split out, so it is not used.
//!   reset (initialisation, including each qubit's allocation): a fault with probability p_init: with the leakage model
//!     a fraction p_prep_leak_ratio of it leaks, the rest is an X; without it, an X. Crosstalk on other qubits in use
//!     with probability p_crosstalk_init, the same channel as the measurement crosstalk.
//! Metrics per shot: every fault applied, by kind, and their total; the sum of s(theta) and of the two-qubit fault
//! probabilities over the rzz applied, for the controls.
use anyhow::{Result, anyhow, bail};
use clap::{ArgAction, Parser};
use rand::{Rng, SeedableRng};
use rand_pcg::Pcg64Mcg;
use selene_core::error_model::interface::ErrorModelInterfaceFactory;
use selene_core::error_model::{BatchResult, ErrorModelInterface};
use selene_core::export_error_model_plugin;
use selene_core::runtime::{BatchOperation, Operation};
use selene_core::simulator::SimulatorInterface;
use selene_core::utils::MetricValue;
use std::f64::consts::PI;

#[derive(Parser, Debug)]
struct Params {
    #[arg(long, default_value = "0")]
    p1: f64,
    #[arg(long, default_value = "0")]
    p1_emission_ratio: f64,
    #[arg(long, default_value = "0")]
    p2: f64,
    #[arg(long, default_value = "0")]
    p2_emission_ratio: f64,
    #[arg(long, default_value = "0")]
    przz_a: f64,
    #[arg(long, default_value = "1")]
    przz_b: f64,
    #[arg(long, default_value = "0")]
    przz_c: f64,
    #[arg(long, default_value = "1")]
    przz_d: f64,
    #[arg(long, default_value = "1")]
    przz_power: f64,
    #[arg(long, default_value = "0")]
    p_meas_0: f64,
    #[arg(long, default_value = "0")]
    p_meas_1: f64,
    #[arg(long, default_value = "0")]
    p_init: f64,
    #[arg(long, default_value = "0")]
    p_crosstalk_meas: f64,
    #[arg(long, default_value = "0")]
    p_crosstalk_init: f64,
    #[arg(long, default_value_t = false, action = ArgAction::Set)]
    leakage_model: bool,
    #[arg(long, default_value_t = false, action = ArgAction::Set)]
    leak2depolar: bool,
    #[arg(long, default_value = "0")]
    p_prep_leak_ratio: f64,
    #[arg(long, default_value = "0")]
    p1_seepage_prob: f64,
    #[arg(long, default_value = "0")]
    p2_seepage_prob: f64,
    /// Z probability per unit of the runtime clock
    #[arg(long, default_value = "0")]
    memory_pz: f64,
    /// nanoseconds per clock unit
    #[arg(long, default_value = "1")]
    unit_ns: u64,
}

#[derive(Default)]
struct Stats {
    gates_1q: u64,
    gates_2q: u64,
    pauli_1q: u64,
    emission_xy_1q: u64,
    leak_1q: u64,
    leak_as_depolar_1q: u64,
    pauli_2q: u64,
    emission_xy_2q: u64,
    leak_2q: u64,
    leak_as_depolar_2q: u64,
    leaked_partner: u64,
    skipped_gates: u64,
    seep_1q: u64,
    seep_2q: u64,
    memory_z: u64,
    memory_units: u64,
    measurements: u64,
    meas_flips: u64,
    leaked_reads: u64,
    crosstalk_meas: u64,
    crosstalk_init: u64,
    inits: u64,
    init_errors: u64,
    leak_init: u64,
    clock_max: u64,
    rzz_scale_sum: f64,
    rzz_dep_prob_sum: f64,
    rzz_emis_prob_sum: f64,
    rzz_abs_angle_max: f64,
}

impl Stats {
    fn faults(&self) -> u64 {
        self.pauli_1q + self.emission_xy_1q + self.leak_1q + self.leak_as_depolar_1q + self.pauli_2q + self.emission_xy_2q
            + self.leak_2q + self.leak_as_depolar_2q + self.leaked_partner + self.memory_z + self.meas_flips + self.leaked_reads
            + self.crosstalk_meas + self.crosstalk_init + self.init_errors + self.leak_init
    }
}

pub struct DocsNoise {
    n_qubits: u64,
    rng: Pcg64Mcg,
    p: Params,
    leaked: Vec<bool>,
    active: Vec<bool>,
    in_use: Vec<bool>,
    t_last: Vec<u64>,
    stats: Stats,
}

#[derive(Clone, Copy)]
enum P1 {
    X,
    Y,
    Z,
}

/// theta modulo 2 pi, in [-pi, pi]
fn wrap(theta: f64) -> f64 {
    theta - (theta / (2.0 * PI)).round() * 2.0 * PI
}

impl DocsNoise {
    fn pauli_op(q: u64, p: P1) -> Operation {
        match p {
            P1::X => Operation::RXYGate { qubit_id: q, theta: PI, phi: 0.0 },
            P1::Y => Operation::RXYGate { qubit_id: q, theta: PI, phi: PI / 2.0 },
            P1::Z => Operation::RZGate { qubit_id: q, theta: PI },
        }
    }
    fn leak_enabled(&self) -> bool {
        self.p.leakage_model && !self.p.leak2depolar
    }
    /// The documentation's angle scaling of the two-qubit depolarizing fault.
    fn rzz_scale(&self, theta: f64) -> f64 {
        let t = wrap(theta);
        let x = (t.abs() / PI).powf(self.p.przz_power);
        if t < 0.0 {
            self.p.przz_a * x + self.p.przz_b
        } else if t > 0.0 {
            self.p.przz_c * x + self.p.przz_d
        } else {
            (self.p.przz_b + self.p.przz_d) / 2.0
        }
    }
    fn check(&self, q: u64) -> Result<()> {
        if q >= self.n_qubits {
            bail!("qubit {} out of range ({} qubits)", q, self.n_qubits);
        }
        Ok(())
    }
    fn flush(&mut self, pending: &mut Vec<Operation>, sim: &mut dyn SimulatorInterface, results: &mut BatchResult) -> Result<()> {
        if pending.is_empty() {
            return Ok(());
        }
        results.extend(sim.handle_operations(BatchOperation::error_model(std::mem::take(pending)))?);
        Ok(())
    }
    fn random_pauli(&mut self, q: u64, pending: &mut Vec<Operation>) {
        let k = ((self.rng.random::<f64>() * 3.0) as u32).min(2);
        pending.push(Self::pauli_op(q, [P1::X, P1::Y, P1::Z][k as usize]));
    }
    /// Memory: Z for the clock units since the qubit's last use, if it holds a state a Z can change.
    fn charge_memory(&mut self, q: u64, now: Option<u64>, pending: &mut Vec<Operation>) {
        let Some(t) = now else { return };
        let i = q as usize;
        if t > self.t_last[i] {
            let k = (t - self.t_last[i]) / self.p.unit_ns.max(1);
            if self.active[i] && !self.leaked[i] && self.p.memory_pz > 0.0 && k > 0 {
                self.stats.memory_units += k;
                let pz = (1.0 - (1.0 - 2.0 * self.p.memory_pz).powi(k as i32)) / 2.0;
                if self.rng.random::<f64>() < pz {
                    pending.push(Self::pauli_op(q, P1::Z));
                    self.stats.memory_z += 1;
                }
            }
            self.t_last[i] = t;
        }
        if t > self.stats.clock_max {
            self.stats.clock_max = t;
        }
    }
    fn leak(&mut self, q: u64, pending: &mut Vec<Operation>) {
        let i = q as usize;
        if !self.leaked[i] {
            self.leaked[i] = true;
            self.active[i] = false;
            // the qubit leaves the computational space: trace it out of the simulated state
            pending.push(Operation::Reset { qubit_id: q });
        }
    }
    /// A leaked qubit given a gate returns with probability prob, to |0> or |1> evenly. True if it returned.
    fn seep(&mut self, q: u64, prob: f64, pending: &mut Vec<Operation>) -> bool {
        let i = q as usize;
        if !self.leaked[i] || !self.leak_enabled() || prob <= 0.0 {
            return false;
        }
        if self.rng.random::<f64>() < prob {
            self.leaked[i] = false;
            self.active[i] = false;
            // the simulator's qubit is |0> (reset when it leaked, untouched since)
            if self.rng.random::<f64>() < 0.5 {
                pending.push(Self::pauli_op(q, P1::X));
            }
            return true;
        }
        false
    }
    /// Emission on one qubit: X 1/4, Y 1/4, the leakage branch 1/2. Returns 0 (X or Y), 1 (leaked), 2 (leakage
    /// branch made a depolarizing error).
    fn emission(&mut self, q: u64, pending: &mut Vec<Operation>) -> u8 {
        let u = self.rng.random::<f64>();
        if u < 0.25 {
            pending.push(Self::pauli_op(q, P1::X));
            0
        } else if u < 0.5 {
            pending.push(Self::pauli_op(q, P1::Y));
            0
        } else if self.leak_enabled() {
            self.leak(q, pending);
            1
        } else {
            self.random_pauli(q, pending);
            2
        }
    }
    fn fault_1q(&mut self, q: u64, pending: &mut Vec<Operation>) {
        self.stats.gates_1q += 1;
        let pe = self.p.p1 * self.p.p1_emission_ratio;
        let pd = self.p.p1 * (1.0 - self.p.p1_emission_ratio);
        let u = self.rng.random::<f64>();
        if u < pe {
            match self.emission(q, pending) {
                0 => self.stats.emission_xy_1q += 1,
                1 => self.stats.leak_1q += 1,
                _ => self.stats.leak_as_depolar_1q += 1,
            }
        } else if u < pe + pd {
            self.random_pauli(q, pending);
            self.stats.pauli_1q += 1;
        }
    }
    fn fault_2q(&mut self, a: u64, b: u64, theta: Option<f64>, pending: &mut Vec<Operation>) -> Result<()> {
        self.stats.gates_2q += 1;
        let s = match theta {
            Some(t) => {
                let w = wrap(t).abs();
                if w > self.stats.rzz_abs_angle_max {
                    self.stats.rzz_abs_angle_max = w;
                }
                self.rzz_scale(t)
            }
            None => 1.0,
        };
        let pe = self.p.p2 * self.p.p2_emission_ratio;
        let pd = self.p.p2 * (1.0 - self.p.p2_emission_ratio) * s;
        if !(0.0..=1.0).contains(&(pe + pd)) || pd < 0.0 {
            bail!("two-qubit fault probability {} (emission {}, depolarizing {}) out of range at angle {:?}", pe + pd, pe, pd, theta);
        }
        self.stats.rzz_scale_sum += s;
        self.stats.rzz_dep_prob_sum += pd;
        self.stats.rzz_emis_prob_sum += pe;
        let u = self.rng.random::<f64>();
        if u < pe {
            let q = if self.rng.random::<f64>() < 0.5 { a } else { b };
            match self.emission(q, pending) {
                0 => self.stats.emission_xy_2q += 1,
                1 => self.stats.leak_2q += 1,
                _ => self.stats.leak_as_depolar_2q += 1,
            }
        } else if u < pe + pd {
            let k = 1 + ((self.rng.random::<f64>() * 15.0) as u32).min(14); // 1..=15, never II
            let pa = k / 4;
            let pb = k % 4;
            for (q, p) in [(a, pa), (b, pb)] {
                match p {
                    1 => pending.push(Self::pauli_op(q, P1::X)),
                    2 => pending.push(Self::pauli_op(q, P1::Y)),
                    3 => pending.push(Self::pauli_op(q, P1::Z)),
                    _ => {}
                }
            }
            self.stats.pauli_2q += 1;
        }
        Ok(())
    }
    fn crosstalk(&mut self, source: u64, prob: f64, on_init: bool, pending: &mut Vec<Operation>) {
        if prob <= 0.0 {
            return;
        }
        for q in 0..self.n_qubits {
            let i = q as usize;
            if q == source || !self.in_use[i] || self.leaked[i] {
                continue;
            }
            if self.rng.random::<f64>() < prob {
                // a measurement whose result is discarded: Z with probability 1/2
                if self.rng.random::<f64>() < 0.5 {
                    pending.push(Self::pauli_op(q, P1::Z));
                }
                if on_init { self.stats.crosstalk_init += 1 } else { self.stats.crosstalk_meas += 1 }
            }
        }
    }
    fn read(&mut self, q: u64, result_id: u64, sim: &mut dyn SimulatorInterface, pending: &mut Vec<Operation>, results: &mut BatchResult) -> Result<Option<bool>> {
        self.flush(pending, sim, results)?;
        self.stats.measurements += 1;
        if self.leaked[q as usize] {
            self.stats.leaked_reads += 1;
            return Ok(None);
        }
        let r = sim.handle_operations(BatchOperation::error_model(vec![Operation::Measure { qubit_id: q, result_id }]))?;
        let Some(m) = r.bool_results.into_iter().next() else {
            bail!("no measurement result from the simulator");
        };
        let flip = if m.value { self.p.p_meas_1 } else { self.p.p_meas_0 };
        let v = if self.rng.random::<f64>() < flip {
            self.stats.meas_flips += 1;
            !m.value
        } else {
            m.value
        };
        Ok(Some(v))
    }
}

fn is_flip_or_identity(theta: f64) -> bool {
    let t = theta.rem_euclid(2.0 * PI);
    t < 1e-12 || (t - PI).abs() < 1e-12 || (2.0 * PI - t) < 1e-12
}

impl ErrorModelInterface for DocsNoise {
    fn shot_start(&mut self, _shot_id: u64, seed: u64) -> Result<()> {
        self.rng = Pcg64Mcg::seed_from_u64(seed);
        let n = self.n_qubits as usize;
        self.leaked = vec![false; n];
        self.active = vec![false; n];
        self.in_use = vec![false; n];
        self.t_last = vec![0; n];
        self.stats = Stats::default();
        Ok(())
    }
    fn shot_end(&mut self) -> Result<()> {
        Ok(())
    }
    fn exit(&mut self) -> Result<()> {
        Ok(())
    }
    fn handle_operations(&mut self, operations: BatchOperation, sim: &mut dyn SimulatorInterface) -> Result<BatchResult> {
        let now: Option<u64> = operations.runtime_source().map(|s| u64::from(s.start()));
        let mut results = BatchResult::default();
        let mut pending: Vec<Operation> = Vec::new();
        for op in operations {
            match op {
                Operation::RXYGate { qubit_id, theta, phi } => {
                    self.check(qubit_id)?;
                    self.charge_memory(qubit_id, now, &mut pending);
                    self.in_use[qubit_id as usize] = true;
                    if self.leaked[qubit_id as usize] {
                        self.stats.skipped_gates += 1;
                        let p = self.p.p1_seepage_prob;
                        if self.seep(qubit_id, p, &mut pending) {
                            self.stats.seep_1q += 1;
                        }
                        continue;
                    }
                    pending.push(Operation::RXYGate { qubit_id, theta, phi });
                    if !is_flip_or_identity(theta) {
                        self.active[qubit_id as usize] = true;
                    }
                    self.fault_1q(qubit_id, &mut pending);
                }
                Operation::RZGate { qubit_id, theta } => {
                    self.check(qubit_id)?;
                    self.charge_memory(qubit_id, now, &mut pending);
                    if !self.leaked[qubit_id as usize] {
                        pending.push(Operation::RZGate { qubit_id, theta });
                    }
                }
                Operation::RZZGate { qubit_id_1, qubit_id_2, theta } => {
                    self.check(qubit_id_1)?;
                    self.check(qubit_id_2)?;
                    self.charge_memory(qubit_id_1, now, &mut pending);
                    self.charge_memory(qubit_id_2, now, &mut pending);
                    let (l1, l2) = (self.leaked[qubit_id_1 as usize], self.leaked[qubit_id_2 as usize]);
                    if !l1 && !l2 {
                        pending.push(Operation::RZZGate { qubit_id_1, qubit_id_2, theta });
                        self.fault_2q(qubit_id_1, qubit_id_2, Some(theta), &mut pending)?;
                    } else {
                        self.stats.skipped_gates += 1;
                        if l1 != l2 {
                            let other = if l1 { qubit_id_2 } else { qubit_id_1 };
                            let k = (self.rng.random::<f64>() * 4.0) as u32;
                            match k {
                                1 => pending.push(Self::pauli_op(other, P1::X)),
                                2 => pending.push(Self::pauli_op(other, P1::Y)),
                                3 => pending.push(Self::pauli_op(other, P1::Z)),
                                _ => {}
                            }
                            self.stats.leaked_partner += 1;
                        }
                        let p = self.p.p2_seepage_prob;
                        for (q, l) in [(qubit_id_1, l1), (qubit_id_2, l2)] {
                            if l && self.seep(q, p, &mut pending) {
                                self.stats.seep_2q += 1;
                            }
                        }
                    }
                }
                Operation::RPPGate { qubit_id_1, qubit_id_2, theta, phi } => {
                    self.check(qubit_id_1)?;
                    self.check(qubit_id_2)?;
                    self.charge_memory(qubit_id_1, now, &mut pending);
                    self.charge_memory(qubit_id_2, now, &mut pending);
                    pending.push(Operation::RPPGate { qubit_id_1, qubit_id_2, theta, phi });
                    self.active[qubit_id_1 as usize] = true;
                    self.active[qubit_id_2 as usize] = true;
                    self.fault_2q(qubit_id_1, qubit_id_2, None, &mut pending)?;
                }
                Operation::Measure { qubit_id, result_id } => {
                    self.check(qubit_id)?;
                    self.charge_memory(qubit_id, now, &mut pending);
                    let v = self.read(qubit_id, result_id, sim, &mut pending, &mut results)?;
                    results.set_bool_result(result_id, v.unwrap_or(true));
                    self.active[qubit_id as usize] = false;
                    let p = self.p.p_crosstalk_meas;
                    self.crosstalk(qubit_id, p, false, &mut pending);
                }
                Operation::MeasureLeaked { qubit_id, result_id } => {
                    self.check(qubit_id)?;
                    self.charge_memory(qubit_id, now, &mut pending);
                    let v = self.read(qubit_id, result_id, sim, &mut pending, &mut results)?;
                    results.set_u64_result(result_id, match v { None => 2, Some(true) => 1, Some(false) => 0 });
                    self.active[qubit_id as usize] = false;
                    let p = self.p.p_crosstalk_meas;
                    self.crosstalk(qubit_id, p, false, &mut pending);
                }
                Operation::Reset { qubit_id } => {
                    self.check(qubit_id)?;
                    let i = qubit_id as usize;
                    if let Some(t) = now {
                        if t > self.t_last[i] { self.t_last[i] = t; }
                    }
                    self.leaked[i] = false;
                    self.active[i] = false;
                    self.in_use[i] = true;
                    pending.push(Operation::Reset { qubit_id });
                    self.stats.inits += 1;
                    if self.rng.random::<f64>() < self.p.p_init {
                        if self.leak_enabled() && self.rng.random::<f64>() < self.p.p_prep_leak_ratio {
                            self.leak(qubit_id, &mut pending);
                            self.stats.leak_init += 1;
                        } else {
                            pending.push(Self::pauli_op(qubit_id, P1::X));
                            self.stats.init_errors += 1;
                        }
                    }
                    let p = self.p.p_crosstalk_init;
                    self.crosstalk(qubit_id, p, true, &mut pending);
                }
                Operation::Custom { .. } => {}
                _ => bail!("DocsNoise: unsupported operation {:?}", op),
            }
        }
        self.flush(&mut pending, sim, &mut results)?;
        Ok(results)
    }
    fn get_metric(&mut self, nth: u8) -> Result<Option<(String, MetricValue)>> {
        let s = &self.stats;
        let (name, v) = match nth {
            0 => ("faults_total", MetricValue::U64(s.faults())),
            1 => ("gates_1q", MetricValue::U64(s.gates_1q)),
            2 => ("gates_2q", MetricValue::U64(s.gates_2q)),
            3 => ("pauli_1q", MetricValue::U64(s.pauli_1q)),
            4 => ("emission_xy_1q", MetricValue::U64(s.emission_xy_1q)),
            5 => ("leak_1q", MetricValue::U64(s.leak_1q)),
            6 => ("leak_as_depolar_1q", MetricValue::U64(s.leak_as_depolar_1q)),
            7 => ("pauli_2q", MetricValue::U64(s.pauli_2q)),
            8 => ("emission_xy_2q", MetricValue::U64(s.emission_xy_2q)),
            9 => ("leak_2q", MetricValue::U64(s.leak_2q)),
            10 => ("leak_as_depolar_2q", MetricValue::U64(s.leak_as_depolar_2q)),
            11 => ("leaked_partner", MetricValue::U64(s.leaked_partner)),
            12 => ("skipped_gates", MetricValue::U64(s.skipped_gates)),
            13 => ("seep_1q", MetricValue::U64(s.seep_1q)),
            14 => ("seep_2q", MetricValue::U64(s.seep_2q)),
            15 => ("memory_z", MetricValue::U64(s.memory_z)),
            16 => ("memory_units", MetricValue::U64(s.memory_units)),
            17 => ("measurements", MetricValue::U64(s.measurements)),
            18 => ("meas_flips", MetricValue::U64(s.meas_flips)),
            19 => ("leaked_reads", MetricValue::U64(s.leaked_reads)),
            20 => ("crosstalk_meas", MetricValue::U64(s.crosstalk_meas)),
            21 => ("crosstalk_init", MetricValue::U64(s.crosstalk_init)),
            22 => ("inits", MetricValue::U64(s.inits)),
            23 => ("init_errors", MetricValue::U64(s.init_errors)),
            24 => ("leak_init", MetricValue::U64(s.leak_init)),
            25 => ("clock_max", MetricValue::U64(s.clock_max)),
            26 => ("rzz_scale_sum", MetricValue::F64(s.rzz_scale_sum)),
            27 => ("rzz_dep_prob_sum", MetricValue::F64(s.rzz_dep_prob_sum)),
            28 => ("rzz_emis_prob_sum", MetricValue::F64(s.rzz_emis_prob_sum)),
            29 => ("rzz_abs_angle_max", MetricValue::F64(s.rzz_abs_angle_max)),
            _ => return Ok(None),
        };
        Ok(Some((name.to_string(), v)))
    }
}

#[derive(Default)]
pub struct DocsNoiseFactory;

impl ErrorModelInterfaceFactory for DocsNoiseFactory {
    type Interface = DocsNoise;
    fn init(self: std::sync::Arc<Self>, n_qubits: u64, args: &[impl AsRef<str>]) -> Result<Box<Self::Interface>> {
        let p = Params::try_parse_from(args.iter().map(|s| s.as_ref())).map_err(|e| anyhow!("docs-noise plugin arguments: {}", e))?;
        for (name, v) in [("p1", p.p1), ("p1_emission_ratio", p.p1_emission_ratio), ("p2", p.p2), ("p2_emission_ratio", p.p2_emission_ratio),
                          ("p_meas_0", p.p_meas_0), ("p_meas_1", p.p_meas_1), ("p_init", p.p_init), ("p_crosstalk_meas", p.p_crosstalk_meas),
                          ("p_crosstalk_init", p.p_crosstalk_init), ("p_prep_leak_ratio", p.p_prep_leak_ratio), ("p1_seepage_prob", p.p1_seepage_prob),
                          ("p2_seepage_prob", p.p2_seepage_prob), ("memory_pz", p.memory_pz)] {
            if !(0.0..=1.0).contains(&v) {
                bail!("{} = {} is not a probability", name, v);
            }
        }
        for (name, v) in [("przz_a", p.przz_a), ("przz_b", p.przz_b), ("przz_c", p.przz_c), ("przz_d", p.przz_d), ("przz_power", p.przz_power)] {
            if !v.is_finite() || v < 0.0 {
                bail!("{} = {} is not a non-negative number", name, v);
            }
        }
        let n = n_qubits as usize;
        Ok(Box::new(DocsNoise {
            n_qubits,
            rng: Pcg64Mcg::seed_from_u64(0),
            p,
            leaked: vec![false; n],
            active: vec![false; n],
            in_use: vec![false; n],
            t_last: vec![0; n],
            stats: Stats::default(),
        }))
    }
}

export_error_model_plugin!(crate::DocsNoiseFactory);

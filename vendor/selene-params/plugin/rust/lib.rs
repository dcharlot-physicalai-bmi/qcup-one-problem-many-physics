//! A Selene error-model plugin that applies the terms of a trapped-ion maker's published emulator parameter table,
//! as far as the table and the maker's emulator documentation define them. Written for the QCUP application's
//! emulator check; it is ours, not the maker's emulator.
//!
//! Terms, per native operation Selene's runtime issues:
//!   one-qubit gate (rxy): a fault with probability p1, applied after the gate. A fraction p1_emission_ratio of faults
//!     are spontaneous emission (X a quarter of the time, Y a quarter, leakage half, as the maker's emulator
//!     documentation states); the rest are depolarizing (X, Y, Z equally: the maker's channel is asymmetric with
//!     weights it does not publish).
//!   rz: none (a frame change on the device; under Selene's soft-RZ runtime it never reaches the error model).
//!   two-qubit gate (rzz, at any angle: the angle scaling parameters are not in the table): a fault with probability
//!     p2, applied after the gate. A fraction p2_emission_ratio of faults are an emission on one of the two qubits
//!     (chosen evenly; X, Y or leakage as above); the rest are one of the 15 two-qubit Paulis, evenly.
//!   memory: Z with probability memory_pz per elapsed unit of the runtime's clock (the soft-RZ runtime with only the
//!     rzz duration set, so one unit is one layer of two-qubit gates), charged to a qubit when it is next used, for the
//!     time since its last use, while it holds a state a Z can change (after an rxy whose angle is not 0 or pi, until it
//!     is measured or reset). For k units: (1 - (1 - 2 memory_pz)^k) / 2.
//!   measurement: a 0 is read as 1 with probability p_meas_0, a 1 as 0 with probability p_meas_1. Each measurement
//!     also, with probability p_crosstalk_meas for every other qubit in use, measures that qubit and discards the result
//!     (a Z with probability 1/2, the same channel); the maker's documentation says such crosstalk "effectively
//!     measures other qubits in the trap or cause them to leak", and does not split the two, so leakage is not used.
//!   reset: an X with probability p_init; crosstalk on other qubits with probability p_crosstalk_init.
//!   leakage: a leaked qubit takes no gates, reads as 1, and returns on reset; it is traced out when it leaks (reset in
//!     the simulator). A two-qubit gate with one leaked qubit is not applied, and the other qubit gets I, X, Y or Z
//!     evenly (our assumption: the maker does not publish this).
//! Metrics per shot: every fault applied, by kind, and their total.
use anyhow::{Result, anyhow, bail};
use clap::Parser;
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
    p_meas_0: f64,
    #[arg(long, default_value = "0")]
    p_meas_1: f64,
    #[arg(long, default_value = "0")]
    p_init: f64,
    #[arg(long, default_value = "0")]
    p_crosstalk_meas: f64,
    #[arg(long, default_value = "0")]
    p_crosstalk_init: f64,
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
    pauli_2q: u64,
    emission_xy_2q: u64,
    leak_2q: u64,
    leaked_partner: u64,
    skipped_gates: u64,
    memory_z: u64,
    memory_units: u64,
    measurements: u64,
    meas_flips: u64,
    leaked_reads: u64,
    crosstalk_meas: u64,
    crosstalk_init: u64,
    inits: u64,
    init_errors: u64,
    clock_max: u64,
}

impl Stats {
    fn faults(&self) -> u64 {
        self.pauli_1q + self.emission_xy_1q + self.leak_1q + self.pauli_2q + self.emission_xy_2q + self.leak_2q
            + self.leaked_partner + self.memory_z + self.meas_flips + self.leaked_reads + self.crosstalk_meas
            + self.crosstalk_init + self.init_errors
    }
}

pub struct PublishedNoise {
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

impl PublishedNoise {
    fn pauli_op(q: u64, p: P1) -> Operation {
        match p {
            P1::X => Operation::RXYGate { qubit_id: q, theta: PI, phi: 0.0 },
            P1::Y => Operation::RXYGate { qubit_id: q, theta: PI, phi: PI / 2.0 },
            P1::Z => Operation::RZGate { qubit_id: q, theta: PI },
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
    /// Emission on one qubit: X 1/4, Y 1/4, leakage 1/2. Returns true if it leaked.
    fn emission(&mut self, q: u64, pending: &mut Vec<Operation>) -> bool {
        let u = self.rng.random::<f64>();
        if u < 0.25 {
            pending.push(Self::pauli_op(q, P1::X));
            false
        } else if u < 0.5 {
            pending.push(Self::pauli_op(q, P1::Y));
            false
        } else {
            self.leak(q, pending);
            true
        }
    }
    fn fault_1q(&mut self, q: u64, pending: &mut Vec<Operation>) {
        self.stats.gates_1q += 1;
        if self.rng.random::<f64>() >= self.p.p1 {
            return;
        }
        if self.rng.random::<f64>() < self.p.p1_emission_ratio {
            if self.emission(q, pending) { self.stats.leak_1q += 1 } else { self.stats.emission_xy_1q += 1 }
        } else {
            let k = (self.rng.random::<f64>() * 3.0) as u32;
            pending.push(Self::pauli_op(q, [P1::X, P1::Y, P1::Z][k.min(2) as usize]));
            self.stats.pauli_1q += 1;
        }
    }
    fn fault_2q(&mut self, a: u64, b: u64, pending: &mut Vec<Operation>) {
        self.stats.gates_2q += 1;
        if self.rng.random::<f64>() >= self.p.p2 {
            return;
        }
        if self.rng.random::<f64>() < self.p.p2_emission_ratio {
            let q = if self.rng.random::<f64>() < 0.5 { a } else { b };
            if self.emission(q, pending) { self.stats.leak_2q += 1 } else { self.stats.emission_xy_2q += 1 }
        } else {
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

impl ErrorModelInterface for PublishedNoise {
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
                        self.fault_2q(qubit_id_1, qubit_id_2, &mut pending);
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
                    self.fault_2q(qubit_id_1, qubit_id_2, &mut pending);
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
                        pending.push(Self::pauli_op(qubit_id, P1::X));
                        self.stats.init_errors += 1;
                    }
                    let p = self.p.p_crosstalk_init;
                    self.crosstalk(qubit_id, p, true, &mut pending);
                }
                Operation::Custom { .. } => {}
                _ => bail!("PublishedNoise: unsupported operation {:?}", op),
            }
        }
        self.flush(&mut pending, sim, &mut results)?;
        Ok(results)
    }
    fn get_metric(&mut self, nth: u8) -> Result<Option<(String, MetricValue)>> {
        let s = &self.stats;
        let v = match nth {
            0 => ("faults_total", s.faults()),
            1 => ("gates_1q", s.gates_1q),
            2 => ("gates_2q", s.gates_2q),
            3 => ("pauli_1q", s.pauli_1q),
            4 => ("emission_xy_1q", s.emission_xy_1q),
            5 => ("leak_1q", s.leak_1q),
            6 => ("pauli_2q", s.pauli_2q),
            7 => ("emission_xy_2q", s.emission_xy_2q),
            8 => ("leak_2q", s.leak_2q),
            9 => ("leaked_partner", s.leaked_partner),
            10 => ("skipped_gates", s.skipped_gates),
            11 => ("memory_z", s.memory_z),
            12 => ("memory_units", s.memory_units),
            13 => ("measurements", s.measurements),
            14 => ("meas_flips", s.meas_flips),
            15 => ("leaked_reads", s.leaked_reads),
            16 => ("crosstalk_meas", s.crosstalk_meas),
            17 => ("crosstalk_init", s.crosstalk_init),
            18 => ("inits", s.inits),
            19 => ("init_errors", s.init_errors),
            20 => ("clock_max", s.clock_max),
            _ => return Ok(None),
        };
        Ok(Some((v.0.to_string(), MetricValue::U64(v.1))))
    }
}

#[derive(Default)]
pub struct PublishedNoiseFactory;

impl ErrorModelInterfaceFactory for PublishedNoiseFactory {
    type Interface = PublishedNoise;
    fn init(self: std::sync::Arc<Self>, n_qubits: u64, args: &[impl AsRef<str>]) -> Result<Box<Self::Interface>> {
        let p = Params::try_parse_from(args.iter().map(|s| s.as_ref())).map_err(|e| anyhow!("published-noise plugin arguments: {}", e))?;
        for (name, v) in [("p1", p.p1), ("p1_emission_ratio", p.p1_emission_ratio), ("p2", p.p2), ("p2_emission_ratio", p.p2_emission_ratio),
                          ("p_meas_0", p.p_meas_0), ("p_meas_1", p.p_meas_1), ("p_init", p.p_init), ("p_crosstalk_meas", p.p_crosstalk_meas),
                          ("p_crosstalk_init", p.p_crosstalk_init), ("memory_pz", p.memory_pz)] {
            if !(0.0..=1.0).contains(&v) {
                bail!("{} = {} is not a probability", name, v);
            }
        }
        let n = n_qubits as usize;
        Ok(Box::new(PublishedNoise {
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

export_error_model_plugin!(crate::PublishedNoiseFactory);

//! QCUP pre-submission simulations, Aim 1. Every number comes from ferrotherm calls or exhaustive
//! enumeration; nothing is hardcoded. Usage: aim1 <family> <n> <seed> [restarts max_evals]
use ferrotherm::graph::{Graph, GraphBuilder};
use ferrotherm::ledger::KV260_WRITABLE_METERED;
use ferrotherm::portfolio::{Budget, Search, Tempering};
use ferrotherm::qaoa::{Ansatz, Optimiser};
use ferrotherm::sdp;
use ferrotherm::tts::{tts, Trial};

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
    fn unif(&mut self) -> f64 { (self.next() >> 11) as f64 / (1u64 << 53) as f64 }
    fn range(&mut self, a: f64, b: f64) -> f64 { a + (b - a) * self.unif() }
    fn sign(&mut self) -> f64 { if self.next() & 1 == 1 { 1.0 } else { -1.0 } }
}

/// A QUBO cost  sum_i a_i x_i + sum_{i<j} b_ij x_i x_j  mapped to ferrotherm's
/// E(s) = -sum J s_i s_j - sum h s_i with x = (1+s)/2. The constant is dropped.
fn qubo_to_ising(n: usize, a: &[f64], b: &[Vec<f64>]) -> (Vec<f64>, Vec<(usize, usize, f64)>) {
    let mut h = vec![0.0; n];
    let mut edges = Vec::new();
    for i in 0..n {
        h[i] -= a[i] / 2.0;
        for j in (i + 1)..n {
            let bij = b[i][j];
            if bij != 0.0 {
                edges.push((i, j, -bij / 4.0));
                h[i] -= bij / 4.0;
                h[j] -= bij / 4.0;
            }
        }
    }
    (h, edges)
}

/// Family A: planar arm posture reach. m links, each link's absolute direction one-hot over q=4
/// angles (per-link random offset), random link lengths; target = end effector of a hidden random
/// posture plus a small offset. Cost = |end - target|^2 + A * sum_j (sum_k x_jk - 1)^2.
fn family_a(n: usize, seed: u64) -> (Vec<f64>, Vec<(usize, usize, f64)>, String) {
    let q = 4; let m = n / q; let mut r = Rng(0xA000 + seed);
    let len: Vec<f64> = (0..m).map(|_| r.range(0.6, 1.0)).collect();
    let off: Vec<f64> = (0..m).map(|_| r.range(0.0, std::f64::consts::FRAC_PI_2)).collect();
    let (mut cx, mut cy) = (vec![0.0; n], vec![0.0; n]);
    for j in 0..m { for k in 0..q {
        let th = off[j] + k as f64 * std::f64::consts::FRAC_PI_2;
        cx[j * q + k] = len[j] * th.cos(); cy[j * q + k] = len[j] * th.sin();
    }}
    let (mut tx, mut ty) = (r.range(-0.15, 0.15), r.range(-0.15, 0.15));
    for j in 0..m { let k = (r.next() % q as u64) as usize; tx += cx[j * q + k]; ty += cy[j * q + k]; }
    let total: f64 = len.iter().sum();
    let pen = total * total;
    let mut a = vec![0.0; n]; let mut b = vec![vec![0.0; n]; n];
    for i in 0..n {
        a[i] += cx[i] * cx[i] + cy[i] * cy[i] - 2.0 * (tx * cx[i] + ty * cy[i]);
        a[i] += -pen; // (sum x - 1)^2 = sum x (x=x^2) - 2 sum x + 2 sum_{k<l} x x + 1
        for j in (i + 1)..n {
            b[i][j] += 2.0 * (cx[i] * cx[j] + cy[i] * cy[j]);
            if i / q == j / q { b[i][j] += 2.0 * pen; }
        }
    }
    let (h, e) = qubo_to_ising(n, &a, &b);
    (h, e, format!("planar {m}-link arm reach, one-hot over {q} absolute directions per link, penalty {pen:.3}"))
}

/// Family B: two-mode energy. Hopfield couplings from two random patterns, plus a weak random field.
fn family_b(n: usize, seed: u64) -> (Vec<f64>, Vec<(usize, usize, f64)>, String) {
    let mut r = Rng(0xB000 + seed);
    let p1: Vec<f64> = (0..n).map(|_| r.sign()).collect();
    let p2: Vec<f64> = (0..n).map(|_| r.sign()).collect();
    let h: Vec<f64> = (0..n).map(|_| r.range(-0.05, 0.05)).collect();
    let mut e = Vec::new();
    for i in 0..n { for j in (i + 1)..n {
        let w = (p1[i] * p1[j] + p2[i] * p2[j]) / n as f64;
        if w != 0.0 { e.push((i, j, w)); }
    }}
    (h, e, "two-pattern Hopfield energy with weak random field (two competing basins)".into())
}

/// Family C: 3-colouring of a ring under one-hot encoding with random colour preferences.
fn family_c(n: usize, seed: u64) -> (Vec<f64>, Vec<(usize, usize, f64)>, String) {
    let q = 3; let m = n / q; let mut r = Rng(0xC000 + seed);
    let pen = 2.0;
    let mut a = vec![0.0; n]; let mut b = vec![vec![0.0; n]; n];
    for v in 0..m { for c in 0..q {
        let i = v * q + c;
        a[i] += r.range(0.0, 0.5) - pen;
        for c2 in (c + 1)..q { b[i][v * q + c2] += 2.0 * pen; }
        let w = (v + 1) % m;
        let j = w * q + c;
        let (lo, hi) = (i.min(j), i.max(j));
        b[lo][hi] += 1.0;
    }}
    let (h, e) = qubo_to_ising(n, &a, &b);
    (h, e, format!("3-colouring of a {m}-ring, one-hot, random colour preferences"))
}

/// Family D: Sherrington-Kirkpatrick +-1 reference (dense, no field).
fn family_d(n: usize, seed: u64) -> (Vec<f64>, Vec<(usize, usize, f64)>, String) {
    let mut r = Rng(0xD000 + seed);
    let mut e = Vec::new();
    for i in 0..n { for j in (i + 1)..n { e.push((i, j, r.sign() / (n as f64).sqrt())); } }
    (vec![0.0; n], e, "Sherrington-Kirkpatrick +-1/sqrt(n) reference".into())
}

/// Tag R: a bounded program-repair QUBO written by repair.py (the second part of family D), read as an Ising file.
fn family_r(n: usize, seed: u64) -> (Vec<f64>, Vec<(usize, usize, f64)>, String) {
    let dir = std::env::var("REPAIR_DIR").unwrap_or_else(|_| "repair".into());
    let txt = std::fs::read_to_string(format!("{dir}/R_{n}_{seed}.txt")).expect("repair instance file");
    let mut h = vec![0.0; n]; let mut e = Vec::new();
    for l in txt.lines().skip(1) {
        let v: Vec<&str> = l.split_whitespace().collect();
        if v[0] == "h" { h[v[1].parse::<usize>().unwrap()] = v[2].parse().unwrap(); }
        else { e.push((v[1].parse().unwrap(), v[2].parse().unwrap(), v[3].parse().unwrap())); }
    }
    (h, e, "bounded program repair of an RCE Form, one-hot over next states".into())
}

/// Tag L: a quadratised low-autocorrelation binary sequence instance written by labs.py, read as an Ising file.
/// Here n is the number of spins after quadratisation and seed is the sequence length N.
fn family_l(n: usize, seed: u64) -> (Vec<f64>, Vec<(usize, usize, f64)>, String) {
    let dir = std::env::var("LABS_DIR").unwrap_or_else(|_| "labs".into());
    let txt = std::fs::read_to_string(format!("{dir}/L_{n}_{seed}.txt")).expect("LABS instance file");
    let mut h = vec![0.0; n]; let mut e = Vec::new();
    for l in txt.lines().skip(1) {
        let v: Vec<&str> = l.split_whitespace().collect();
        if v[0] == "h" { h[v[1].parse::<usize>().unwrap()] = v[2].parse().unwrap(); }
        else { e.push((v[1].parse().unwrap(), v[2].parse().unwrap(), v[3].parse().unwrap())); }
    }
    (h, e, format!("low-autocorrelation binary sequence of length {seed}, quadratised with one auxiliary spin per pair"))
}

/// Sidelobe energy of a binary sequence held in the low `n` bits of `x`: sum over lags k of C_k^2.
fn labs_energy(x: u64, n: u32) -> i64 {
    let mut e = 0i64;
    for k in 1..n { let m = (1u64 << (n - k)) - 1; let c = (n - k) as i64 - 2 * (((x ^ (x >> k)) & m).count_ones() as i64); e += c * c; }
    e
}

/// LABS in its native form (LABS=1): exhaustive optimum, then simulated annealing with single flips on the N
/// sequence bits (the solver a microcontroller could run), time to solution at 99% over run length.
fn labs_native(n: u32) {
    let half = 1u64 << (n - 1);          // the top bit is fixed: flipping every bit leaves the energy unchanged
    let (mut e_min, mut count) = (i64::MAX, 0u64);
    for x in 0..half { let e = labs_energy(x, n); if e < e_min { e_min = e; count = 1; } else if e == e_min { count += 1; } }
    let lengths: Vec<u64> = (0..=14).map(|k| (n as u64) << k).collect();
    let (t_hi, t_lo) = (n as f64, 0.5f64);
    let trials: Vec<Trial> = lengths.iter().map(|&len| {
        let mut succ = 0usize;
        for s in 0..32u64 {
            let mut r = Rng(0x1AB5_0000 + 1000 * n as u64 + s);
            let mut x = r.next() & ((1u64 << n) - 1); let mut e = labs_energy(x, n); let mut best = e;
            for t in 0..len {
                let temp = t_hi * (t_lo / t_hi).powf(t as f64 / len as f64);
                let y = x ^ (1u64 << (r.next() % n as u64)); let ey = labs_energy(y, n);
                if ey <= e || r.unif() < (-((ey - e) as f64) / temp).exp() { x = y; e = ey; if e < best { best = e; } }
            }
            if best == e_min { succ += 1; }
        }
        Trial { length: len, successes: succ, trials: 32 }
    }).collect();
    let t = tts(&trials, 0.99);
    let curve: Vec<String> = trials.iter().map(|t| format!("[{},{}]", t.length, t.successes)).collect();
    println!("{{\"n\":{n},\"e_min\":{e_min},\"n_ground\":{},\"merit_factor\":{:.4},\"sa_tts99_flips\":{},\"sa_curve\":[{}]}}",
        2 * count, (n * n) as f64 / (2.0 * e_min as f64), t.as_ref().and_then(|t| t.tts).map_or("null".to_string(), |v| format!("{v:.1}")), curve.join(","));
}

fn build(n: usize, h: &[f64], e: &[(usize, usize, f64)]) -> Graph {
    let mut gb = GraphBuilder::new(n);
    for &(i, j, w) in e { gb.couple(i, j, w); }
    for (i, &hi) in h.iter().enumerate() { if hi != 0.0 { gb.bias(i, hi); } }
    gb.build()
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let fam = a[1].as_str(); let n: usize = a[2].parse().unwrap(); let seed: u64 = a[3].parse().unwrap();
    let restarts: usize = a.get(4).map_or(8, |s| s.parse().unwrap());
    let max_evals: usize = a.get(5).map_or(600, |s| s.parse().unwrap());
    if std::env::var("LABS").is_ok() { labs_native(n as u32); return; }
    let (h, edges, desc) = match fam { "A" => family_a(n, seed), "B" => family_b(n, seed), "C" => family_c(n, seed), "R" => family_r(n, seed), "L" => family_l(n, seed), _ => family_d(n, seed) };
    let g = build(n, &h, &edges);

    // Scale-up mode (SCALE=1): sizes past exhaustive enumeration. Certified bound, rounding, parallel tempering,
    // and ferrotherm's branch and bound for a proof of optimality where it finishes within the node budget.
    if std::env::var("SCALE").is_ok() {
        let (bound, _cert) = sdp::certified(&g, &sdp::Params::default(), 1);
        let gw16 = sdp::goemans_williamson(&g, &sdp::Params::default(), 1, 16);
        let lengths: Vec<u64> = (0..=14).map(|k| (n as u64) << k).collect();
        let mut runs: Vec<Vec<f64>> = Vec::new();
        let (mut best_e, mut best_s) = (f64::INFINITY, vec![1i8; n]);
        for &len in &lengths {
            let mut es = Vec::new();
            for s in 0..16u64 { let f = Tempering.solve(&g, Budget::new(len), 9_000 + s); if f.energy < best_e { best_e = f.energy; best_s = f.state.clone(); } es.push(f.energy); }
            runs.push(es);
        }
        let max_nodes: u64 = std::env::var("BNB_NODES").ok().and_then(|s| s.parse().ok()).unwrap_or(20_000_000);
        let t0 = std::time::Instant::now();
        let out = ferrotherm::branch::solve(&g, &ferrotherm::branch::Params { max_nodes, incumbent: Some(best_s.clone()), ..Default::default() });
        let secs = t0.elapsed().as_secs_f64();
        let e_ref = out.energy.min(best_e); let tol = 1e-9 * (1.0 + e_ref.abs());
        let trials: Vec<Trial> = lengths.iter().zip(&runs).map(|(&len, es)| Trial { length: len, successes: es.iter().filter(|&&e| e <= e_ref + tol).count(), trials: 16 }).collect();
        let t = tts(&trials, 0.99);
        let tts_work = t.as_ref().and_then(|t| t.tts);
        let curve: Vec<String> = trials.iter().map(|t| format!("[{},{}]", t.length, t.successes)).collect();
        let edges_s: Vec<String> = edges.iter().map(|(i, j, w)| format!("[{i},{j},{w:.12}]")).collect();
        println!("{{\"family\":\"{fam}\",\"n\":{n},\"seed\":{seed},\"desc\":\"{desc}\",\"h\":{h:?},\"edges\":[{}],\
\"sdp_bound\":{:.10},\"gw16_energy\":{:.10},\"pt_best_energy\":{best_e:.10},\"bnb_energy\":{:.10},\"bnb_proved_optimal\":{},\
\"bnb_nodes\":{},\"bnb_hit_limit\":{},\"bnb_bound\":{:.10},\"bnb_seconds\":{secs:.2},\"reference_energy\":{e_ref:.10},\
\"pt_tts99_proposals\":{},\"pt_curve\":[{}],\"pt_best_state\":{:?},\"bnb_state\":{:?},\"pt_energies\":{:?}}}",
            edges_s.join(","), bound.value, gw16.energy, out.energy, out.proved_optimal, out.nodes, out.hit_limit, out.bound,
            tts_work.map_or("null".to_string(), |v| format!("{v:.3}")), curve.join(","), best_s, out.state, runs);
        return;
    }

    // Exhaustive spectrum via the QAOA ansatz diagonal (E of every basis state), checked against Graph::energy.
    let ans = Ansatz::new(&g).expect("ansatz");
    let diag = ans.diagonal();
    let e_min = diag.iter().cloned().fold(f64::INFINITY, f64::min);
    let e_max = diag.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let tol = 1e-9 * (1.0 + e_min.abs());
    let ground: Vec<usize> = (0..diag.len()).filter(|&z| diag[z] <= e_min + tol).collect();
    let s0: Vec<i8> = (0..n).map(|i| if (ground[0] >> i) & 1 == 1 { 1 } else { -1 }).collect();
    assert!((g.energy(&s0) - e_min).abs() < 1e-9, "diagonal and Graph::energy disagree");
    let e_mean = diag.iter().sum::<f64>() / diag.len() as f64;

    // Certified SDP lower bound and Goemans-Williamson rounding (ferrotherm::sdp).
    let (bound, cert) = sdp::certified(&g, &sdp::Params::default(), 1);
    let gw1 = sdp::goemans_williamson(&g, &sdp::Params::default(), 1, 1);
    let gw16 = sdp::goemans_williamson(&g, &sdp::Params::default(), 1, 16);

    if std::env::var("GW_ONLY").is_ok() {
        println!("{{\"family\":\"{fam}\",\"n\":{n},\"seed\":{seed},\"gw16_energy\":{:.10},\"gw16_state\":{:?}}}", gw16.energy, gw16.state);
        return;
    }
    // Cold QAOA ladder p = 1..3 (ferrotherm::qaoa, exact state vector).
    let opt = Optimiser { restarts, max_evals, ..Optimiser::default() };
    let lad = opt.ladder(&ans, 3).expect("ladder");
    let mut q = Vec::new();
    for o in &lad {
        let run = ans.run(&o.angles).expect("run");
        let pr = run.probabilities();
        let pgs: f64 = ground.iter().map(|&z| pr[z]).sum();
        q.push(format!("{{\"p\":{},\"expectation\":{:.10},\"ratio\":{:.6},\"p_gs\":{:.8},\"evaluations\":{},\"gamma\":{:?},\"beta\":{:?}}}",
            o.angles.p(), o.expectation, (e_max - o.expectation) / (e_max - e_min), pgs, o.evaluations, o.angles.gamma(), o.angles.beta()));
    }

    // Classical edge arm: parallel tempering, TTS at 99% minimised over run length, 32 seeds per length.
    let lengths: Vec<u64> = (0..=12).map(|k| (n as u64) << k).collect();
    let trials: Vec<Trial> = lengths.iter().map(|&len| {
        let succ = (0..32u64).filter(|&s| { let f = Tempering.solve(&g, Budget::new(len), 9_000 + s); f.energy <= e_min + tol }).count();
        Trial { length: len, successes: succ, trials: 32 }
    }).collect();
    let t = tts(&trials, 0.99);
    let (tts_work, tts_len) = t.as_ref().map_or((f64::NAN, 0), |t| (t.tts.unwrap_or(f64::NAN), t.best_length));
    let curve: Vec<String> = trials.iter().map(|t| format!("[{},{}]", t.length, t.successes)).collect();

    let edges_s: Vec<String> = edges.iter().map(|(i, j, w)| format!("[{i},{j},{w:.12}]")).collect();
    println!("{{\"family\":\"{fam}\",\"n\":{n},\"seed\":{seed},\"desc\":\"{desc}\",\"h\":{h:?},\"edges\":[{}],\
\"e_min\":{e_min:.10},\"e_max\":{e_max:.10},\"e_mean\":{e_mean:.10},\"n_ground\":{},\"ground0\":{},\
\"sdp_bound\":{:.10},\"sdp_method\":\"{}\",\"sdp_homogenised\":{},\
\"gw1_energy\":{:.10},\"gw1_state\":{:?},\"gw16_energy\":{:.10},\"gw_guaranteed\":{},\
\"qaoa\":[{}],\"opt_restarts\":{restarts},\"opt_max_evals\":{max_evals},\
\"pt_tts99_proposals\":{},\"pt_best_length\":{tts_len},\"pt_curve\":[{}],\
\"kv260_writable_j_per_flip\":{:e}}}",
        edges_s.join(","), ground.len(), ground[0], bound.value, bound.method, cert.homogenised,
        gw1.energy, gw1.state, gw16.energy, gw16.guaranteed, q.join(","),
        if tts_work.is_nan() { "null".to_string() } else { format!("{tts_work:.3}") }, curve.join(","),
        KV260_WRITABLE_METERED.e_sample);
}

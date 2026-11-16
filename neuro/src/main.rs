//! Neuromorphic arm: ferromorphic's annealed stochastic-spiking QUBO sampler on the Aim 1 instances.
//! TTS at 99%, minimised over run length and over three declared final inverse temperatures.
use ferromorphic::optimise::{Annealer, Qubo};
use ferromorphic::rng::Rng;
fn main() {
    let path = std::env::args().nth(1).unwrap();
    let txt = std::fs::read_to_string(&path).unwrap();
    let mut it = txt.lines();
    let head: Vec<&str> = it.next().unwrap().split_whitespace().collect();
    let n: usize = head[0].parse().unwrap(); let e_min: f64 = head[1].parse().unwrap(); let off: f64 = head[2].parse().unwrap();
    let mut q = Qubo::zeros(n).unwrap(); q.offset = off;
    let mut row = vec![0.0f64; n];
    for l in it { let v: Vec<&str> = l.split_whitespace().collect(); let (i, j, w): (usize, usize, f64) = (v[0].parse().unwrap(), v[1].parse().unwrap(), v[2].parse().unwrap());
        q.add(i, j, w).unwrap(); row[i] += w.abs(); if i != j { row[j] += w.abs(); } }
    // Sampling mode (SAMPLE="beta sweeps samples"): the fixed-temperature spiking sampler, one fresh chain per sample from a
    // random state. Prints how often each state was returned, for comparison with the exact Boltzmann distribution.
    if let Ok(spec) = std::env::var("SAMPLE") {
        let v: Vec<f64> = spec.split_whitespace().map(|x| x.parse().unwrap()).collect();
        let (beta, sweeps, samples) = (v[0], v[1] as usize, v[2] as u64);
        let mut counts = vec![0u32; 1usize << n]; let mut updates = 0u64;
        for s in 0..samples {
            let mut rng = Rng::new(70_000 + s);
            let mut a = Annealer::new(q.clone());
            a.state = (((rng.next_u32() as u64) << 32) | rng.next_u32() as u64) & ((1u64 << n) - 1);
            for _ in 0..sweeps { let (e, _) = a.sweep(beta, &mut rng).unwrap(); updates += e; }
            counts[a.state as usize] += 1;
        }
        println!("{{\"n\":{n},\"beta\":{beta},\"sweeps\":{sweeps},\"samples\":{samples},\"neuron_updates\":{updates},\"counts\":{counts:?}}}");
        return;
    }
    let scale = row.iter().cloned().fold(0.0, f64::max);
    let tol = 1e-7 * (1.0 + e_min.abs());
    let (trials, mut best) = (32u64, (f64::INFINITY, 0usize, 0.0f64, 0usize));
    for &mult in &[10.0, 100.0, 1000.0] {
        for k in 0..=10 {
            let sweeps = 1usize << k;
            let mut succ = 0usize;
            for s in 0..trials {
                let mut rng = Rng::new(40_000 + s);
                let mut a = Annealer::new(q.clone());
                a.state = (((rng.next_u32() as u64) << 32) | rng.next_u32() as u64) & ((1u64 << n) - 1);
                let sol = a.anneal(1.0 / scale, mult / scale, sweeps, &mut rng).unwrap();
                if sol.energy <= e_min + tol { succ += 1; }
            }
            if succ == 0 { continue; }
            let p = succ as f64 / trials as f64;
            let runs = if p >= 0.99 { 1.0 } else { (0.01f64).ln() / (1.0 - p).ln() };
            let work = runs * (sweeps * n) as f64;
            if work < best.0 { best = (work, sweeps, mult, succ); }
        }
    }
    let tag = std::path::Path::new(&path).file_stem().unwrap().to_str().unwrap();
    if best.0.is_finite() {
        println!("{{\"tag\":\"{tag}\",\"n\":{n},\"tts99_neuron_updates\":{:.1},\"best_sweeps\":{},\"beta_end_mult\":{},\"successes\":{},\"trials\":{trials}}}", best.0, best.1, best.2, best.3);
    } else { println!("{{\"tag\":\"{tag}\",\"n\":{n},\"tts99_neuron_updates\":null}}"); }
}

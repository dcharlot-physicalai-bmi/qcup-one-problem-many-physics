// Evaluates the Resource Calculator's own expression, cut verbatim from IQM Academy's page script, against
// scripts/estimate.py's transcription. Usage: node calc_check.js <path to calc_0fw-zv5wrs59w.js>
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const m = src.match(/R=\(\)=>(.*?);return y\?/);
if (!m) { console.log("expression not found"); process.exit(1); }
console.log("page expression:", m[1]);
const R = new Function("e", "S", "w", "f", "return (" + m[1] + ")");   // e: computer, S: jobs, w: circuits per job, f: shots
const rate = { sirius: 0.3, garnet: 0.5, emerald: 0.75 };
const py = (J, C, S) => Math.pow(0.948749148221405, Math.min(J, 10)) * J * C * (0.022 + 0.00041 * S + 0.000301 * S) + 3.8;
for (const [J, C, S] of [[1, 10, 1000], [6, 100, 2000], [1, 20, 2000], [1, 1, 6000], [3, 100, 1000], [1, 35, 1000], [10, 62, 2000]]) {
  const page = R("Emerald", J, C, S);
  console.log(JSON.stringify({ jobs: J, circuits: C, shots: S, page_seconds: page, page_credits: (parseFloat(page) * rate.emerald).toPrecision(3), transcription_seconds: py(J, C, S).toPrecision(3) }));
}

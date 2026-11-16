OPENQASM 3.0;
include "stdgates.inc";
gate rzz(p0) _gate_q_0, _gate_q_1 {
  cx _gate_q_0, _gate_q_1;
  rz(p0) _gate_q_1;
  cx _gate_q_0, _gate_q_1;
}
bit[1] trace;
qubit[1] a;
qubit[1] b;
qubit[1] e;
ry(pi/2) b[0];
rz(-2.0344439357957027) b[0];
rzz(-pi/2) a[0], b[0];
rz(-pi/2) a[0];
rz(0.4636476090008048) b[0];
ry(-pi/2) b[0];
trace[0] = measure b[0];

OPENQASM 3.0;
include "stdgates.inc";
gate rzz(p0) _gate_q_0, _gate_q_1 {
  cx _gate_q_0, _gate_q_1;
  rz(p0) _gate_q_1;
  cx _gate_q_0, _gate_q_1;
}
bit[2] trace;
qubit[2] a;
qubit[2] b;
ry(pi/2) b[0];
rz(-2.0344439357957027) b[0];
rzz(-pi/2) a[0], b[0];
rz(-pi/2) a[0];
rz(0.4636476090008048) b[0];
ry(-pi/2) b[0];
ry(pi/2) b[1];
rz(-0.8743181142948071) b[1];
rzz(-pi/2) a[0], b[1];
rz(-pi/2) a[0];
rz(-0.6964782125000895) b[1];
ry(pi) b[1];
rzz(pi/2) a[1], b[1];
rz(-pi/2) a[1];
rz(pi/2) b[1];
ry(pi/2) b[1];
trace[0] = measure b[0];
trace[1] = measure b[1];

OPENQASM 3.0;
include "stdgates.inc";
bit[1] trace;
qubit[1] a;
qubit[1] b;
qubit[1] e;
rx(pi) b[0];
trace[0] = measure b[0];

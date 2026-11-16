OPENQASM 3.0;
include "stdgates.inc";
bit[2] trace;
qubit[2] s_0;
cx s_0[0], s_0[1];
x s_0[0];
trace[0] = measure s_0[0];
trace[1] = measure s_0[1];

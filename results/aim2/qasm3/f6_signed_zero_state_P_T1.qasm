OPENQASM 3.0;
include "stdgates.inc";
bit[1] trace;
qubit[1] s_0;
x s_0[0];
trace[0] = measure s_0[0];

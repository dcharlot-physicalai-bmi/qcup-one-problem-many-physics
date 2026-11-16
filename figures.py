#!/usr/bin/env python3
"""Figures from result files only. One axis per panel."""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.abspath(__file__))
import os
import json, glob, math, statistics as st
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
R=os.path.join(ROOT, "results"); BLUE,ORANGE,AQUA="#2a78d6","#eb6834","#1baf7a"; INK,MUTED,SURF="#0b0b0b","#52514e","#fcfcfb"
plt.rcParams.update({"font.size":9,"axes.edgecolor":"#c9c8c2","axes.labelcolor":MUTED,"xtick.color":MUTED,"ytick.color":MUTED,"axes.spines.top":False,"axes.spines.right":False,"figure.facecolor":SURF,"axes.facecolor":SURF,"axes.titlesize":10,"axes.titleweight":"bold","axes.titlelocation":"left"})
A={}
for p in glob.glob(f"{R}/aim1_[ABCDR]_*.json"):
    d=json.load(open(p)); A[(d["family"],d["n"],d["seed"])]=d
P={}
for p in glob.glob(f"{R}/post_*.json"):
    d=json.load(open(p)); P[(d["family"],d["n"],d["seed"])]=d
N={}
for l in open(f"{R}/neuro.jsonl"):
    r=json.loads(l); f,n,s=r["tag"].split("_"); N[(f,int(n),int(s))]=r["tts99_neuron_updates"]
fig,ax=plt.subplots(3,2,figsize=(11,12.4)); fig.subplots_adjust(hspace=0.5,wspace=0.28)
# A: warm vs cold P_gs at p=3, split by whether the GW seed was optimal
a=ax[0,0]
for good,col,lab in ((True,BLUE,"GW seed optimal"),(False,ORANGE,"GW seed not optimal")):
    xs=[(A[k]["qaoa"][2]["p_gs"],v["ws"][2]["p_gs"]) for k,v in P.items() if v["ws"] and v["gw16_is_optimal"]==good]
    a.scatter([max(x,1e-6) for x,_ in xs],[max(y,1e-6) for _,y in xs],s=34,color=col,edgecolor=SURF,linewidth=1,label=f"{lab} ({sum(y>x for x,y in xs)} of {len(xs)} above the line)",zorder=3)
a.plot([1e-6,1],[1e-6,1],color="#c9c8c2",lw=1,zorder=1); a.set_xscale("log"); a.set_yscale("log")
a.set_xlabel("cold QAOA ground-state probability, p = 3"); a.set_ylabel("warm-start QAOA ground-state probability, p = 3")
a.set_title("A. Warm start depends on its classical seed"); a.legend(frameon=False,loc="upper left",bbox_to_anchor=(0,-0.16),fontsize=8); a.set_ylim(3e-7,2)
# B: work to 99% success per arm, family medians at each size
b=ax[0,1]
fams="ABCDR"; names={"A":"A arm reach","B":"B two-mode","C":"C colouring","D":"D SK","R":"D repair"}
xt=[];xl=[]
x=0
for f in fams:
    for n in sorted({k[1] for k in A if k[0]==f}):
        ks=[k for k in A if k[0]==f and k[1]==n]
        pt=st.median(A[k]["pt_tts99_proposals"] for k in ks); nu=st.median(N[k] for k in ks)
        pg=st.median(A[k]["qaoa"][2]["p_gs"] for k in ks); shots=math.log(0.01)/math.log(1-pg) if pg<0.99 else 1
        cz=st.median(P[k]["transpile"][2]["all_to_all_rzz"] for k in ks)
        b.scatter([x],[pt],color=BLUE,s=30,zorder=3); b.scatter([x],[nu],color=AQUA,s=30,marker="s",zorder=3); b.scatter([x],[shots*cz],color=ORANGE,s=34,marker="^",zorder=3)
        xt.append(x); xl.append(f"{f}{n}"); x+=1
    x+=0.6
b.set_yscale("log"); b.set_xticks(xt); b.set_xticklabels(xl,fontsize=8); b.set_ylabel("elementary operations to 99% success (median)")
b.scatter([],[],color=BLUE,s=30,label="parallel tempering: spin proposals (ferrotherm)"); b.scatter([],[],color=AQUA,s=30,marker="s",label="spiking annealer: neuron updates (ferromorphic)"); b.scatter([],[],color=ORANGE,s=34,marker="^",label="cold QAOA p = 3: shots x two-qubit gates (ideal, all-to-all)")
b.set_ylim(top=3e11); b.legend(frameon=False,fontsize=7.5,loc="upper left"); b.set_title("B. Work to solution, by substrate (family and size)"); b.grid(axis="y",color="#ebeae6",lw=0.6)
# C: certified gap per instance, as a share of the spread among encoding-feasible states
c=ax[1,0]; x=0; xt=[];xl=[]
FG=json.load(open(f"{R}/feasible_gap.json"))
for f in fams:
    for st_,col,mk in (("small",BLUE,"o"),("scale",ORANGE,"s")):
        g=[max(r["gap_pct_of_feasible_spread"],1e-4) for r in FG if r["family"]==f and r["set"]==st_]
        dx=-0.16 if st_=="small" else 0.16
        c.scatter([x+dx+0.10*(i-len(g)/2)/len(g)*2 for i in range(len(g))],g,color=col,marker=mk,s=18,edgecolor=SURF,linewidth=0.3,zorder=3)
    xt.append(x); xl.append(names[f]); x+=1
c.axhline(1,color=MUTED,lw=0.8,ls=(0,(4,3)),zorder=1); c.text(0.6,1.3,"1% routing threshold",fontsize=7.5,color=MUTED,ha="left")
c.scatter([],[],color=BLUE,s=18,label="12 to 20 variables (120 instances)"); c.scatter([],[],color=ORANGE,marker="s",s=18,label="24 to 60 variables (60 instances)")
c.set_yscale("log"); c.set_ylim(5e-5,300); c.legend(frameon=False,fontsize=7.5,loc="lower right")
c.set_xticks(xt); c.set_xticklabels(xl); c.set_ylabel("certified gap (% of feasible-state spread)"); c.set_title("C. How tight the certificate is, per instance"); c.grid(axis="y",color="#ebeae6",lw=0.6)
# D: Aim 2 trace fidelity vs two-qubit gates
d=ax[1,1]; a2=[r for p in glob.glob(f"{R}/aim2/*.json") for r in json.load(open(p))]
for t,col,mk,lab in (("sc_like",BLUE,"o","superconducting-like noise, heavy-hex CZ"),("ion_like",ORANGE,"o","trapped-ion-like noise, all-to-all RZZ")):
    rs=[r[t] for r in a2 if "trace_fidelity" in r[t]]
    d.scatter([r["two_qubit_gates"] for r in rs],[max(r["trace_fidelity"],1e-3) for r in rs],s=20,color=col,edgecolor=SURF,linewidth=0.6,label=lab,zorder=3)
rs=[r[b] for r in a2 for b in ("ibm_torino_snapshot","ibm_fez_snapshot") if b in r and "trace_fidelity" in r[b]]
d.scatter([r["two_qubit_gates"] for r in rs],[max(r["trace_fidelity"],1e-3) for r in rs],s=22,color=AQUA,marker="s",edgecolor=SURF,linewidth=0.6,label="IBM Torino and Fez calibration snapshots",zorder=3)
d.set_yscale("log"); d.set_xlabel("two-qubit gates after transpilation"); d.set_ylabel("probability the whole trace is correct"); d.legend(frameon=False,fontsize=8,loc="lower left")
d.set_title("D. 40 reversible RCE Forms: trace fidelity against gate count"); d.grid(axis="y",color="#ebeae6",lw=0.6)
# E: one actinide model, energy error against subspace size, by who proposed the configurations
e=ax[2,0]; CASE="PuO2_eq"
L=[r for r in json.load(open(f"{R}/targets/ladder.json")) if r["case"]==CASE][0]; S=[r for r in json.load(open(f"{R}/targets/sample.json")) if r["case"]==CASE][0]
sc=[(x["dimension"],x["error_mha"]) for x in L["selected_ci"] if "error_mha" in x and x["dimension"]>1]
e.plot([d for d,_ in sc],[max(v,1e-2) for _,v in sc],color=BLUE,lw=2,marker="o",ms=5,label="classical selection (selected CI)",zorder=3)
for key,col,mk,fc,lab in (("exact_state",AQUA,"s",AQUA,"samples of the exact state (best any circuit could do)"),("lucj_ideal",ORANGE,"^",ORANGE,"samples of our circuit, no noise"),("lucj_noisy",ORANGE,"^",SURF,"samples of our circuit, modelled trapped-ion noise")):
    pts=[(x["dimension"],x["error_mha"]) for x in S["proposers"][key] if "error_mha" in x and x["dimension"]>1]
    e.plot([d for d,_ in pts],[max(v,1e-2) for _,v in pts],color=col,lw=1.2,ls=(0,(3,2)),marker=mk,ms=6,markerfacecolor=fc,markeredgecolor=col,label=lab,zorder=3)
e.axhline(1.6,color=MUTED,lw=0.8,ls=(0,(4,3)),zorder=1); e.text(2.2,1.9,"chemical accuracy, 1.6 mHa",fontsize=7.5,color=MUTED,ha="left")
e.set_xscale("log"); e.set_yscale("log"); e.set_xlabel("determinants in the subspace the machine diagonalizes"); e.set_ylabel("energy error (mHa)")
e.set_title(f"E. Plutonium dioxide model, {L['qubits']} qubits: error against subspace size"); e.legend(frameon=False,fontsize=7.5,loc="lower left"); e.grid(axis="y",color="#ebeae6",lw=0.6)
# F: the worked mission example, where each of the 12 target cases was settled
f_=ax[2,1]; W=json.load(open(f"{R}/targets/workflow.json"))["rows"]
tiers=[("cheap","Cheap method,\nchecks clear"),("full diagonalisation on board","Diagonalized\non board"),("selected CI on board","Selected CI\non board"),("escalated","Escalated across\nthe link")]
for i,(k,lab) in enumerate(tiers):
    rs=[r for r in W if r["resolved_by"]==k]; right=sum(1 for r in rs if r.get("accepted_right")); wrong=sum(1 for r in rs if r.get("accepted_right") is False); esc=len(rs)-right-wrong; y=len(tiers)-1-i; x0=0
    for v,col,word in ((right,BLUE,"right"),(wrong,ORANGE,"wrong"),(esc,"#9a9993","not settled on site")):
        if v: f_.barh(y,v-0.04,left=x0+0.02,color=col,height=0.5,zorder=3); f_.text(x0+v/2,y,f"{v} {word}",ha="center",va="center",fontsize=8,color=SURF if col!="#9a9993" else INK,zorder=4); x0+=v
f_.set_yticks(range(len(tiers))); f_.set_yticklabels([lab for _,lab in tiers][::-1],fontsize=8); f_.set_xlim(0,7); f_.set_xlabel("target-chemistry cases (12 in all)")
f_.set_title("F. Worked example: where the on-site rules settled each case"); f_.grid(axis="x",color="#ebeae6",lw=0.6)
fig.suptitle("QCUP pre-submission simulations (ferrotherm 0.44.0, ferromorphic 0.23.2, Qiskit 2.6.2, Aer 0.18.2, PySCF 2.15.0, ffsim 0.0.86). 180 optimization instances, 40 programs,\n12 target-chemistry models. Noise is generic models or IBM calibration snapshots, never a live device.",fontsize=9,color=MUTED,x=0.01,ha="left",y=0.975)
fig.savefig(os.path.join(ROOT, "results/qcup_presubmission_figures.png"),dpi=200,bbox_inches="tight")

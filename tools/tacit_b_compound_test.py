"""Hosted producer test of exact A1 resolver, real ORIENT factory and composition."""
import argparse,copy,sys
from pathlib import Path
from tacit_b_patterns import PatternBridge
from tacit_b_kuiper import ZIP,MANIFEST
from tacit_b_admission import member
from tacit_b_convergence import oracle
from tacit_b_compound import execute_compound,verify_compound
from tacit_b_composition import refusal

A1="c4d6d309940d131d2a1ae6181701086aa7221839"
COMMAND="Calculate the distance and initial bearing from point A to point B and from point A to point C, then identify the nearer destination."

def main():
    p=argparse.ArgumentParser()
    for k in ("factory","d","bonds","nearest","nsources","esources","archive","build","a1","semantic-root","prior","out"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    sys.path[:0]=[str(a.factory/"tools"),str(a.d/"tools"),str(a.a1/"tools")]
    import package_factory as f
    import typed_package_execution as t
    from kuiper_select import Space
    from tacit_a1_semantics import Resolver
    import subprocess
    f.need(subprocess.check_output(["git","rev-parse","HEAD"],cwd=a.a1,text=True).strip()==A1,"SEMANTIC_HEAD")
    resolver=Resolver(a.semantic_root)
    b=PatternBridge(f,t,Space,member(f,a.bonds,ZIP,"bonds.json",MANIFEST),a.archive.read_bytes(),f.strict(a.build.read_bytes()),a.nearest,a.nsources,a.esources)
    checks={}
    def check(k,ok):f.need(ok,k);checks[k]="PASS"
    def reject(k,fn,reason):check(k,refusal(fn)==reason)
    # Explicit test-only epoch guard; E1 owns actual live Ledger integration.
    class Guard:
        def __init__(self,fail_at=None):self.calls=0;self.fail_at=fail_at
        def __call__(self):
            self.calls+=1
            f.need(self.calls!=self.fail_at,"STALE_DEPENDENCY")
    context={"generation":1,"selection_receipt_sha256":"a"*64,"challenge":"b"*64}
    def run(plan,c=context,guard=None):return execute_compound(b,resolver,plan,c,Guard() if guard is None else guard)
    def points(a,b,c):
        return {"crs":"WGS84","unit":"degrees","points":{k:dict(zip(("longitude","latitude"),v)) for k,v in zip("ABC",(a,b,c))}}
    fixtures=[points((-0.45,51.48),(-1.9,52.48),(0.12,52.21)),
              points((151.21,-33.86),(144.96,-37.81),(153.03,-27.47)),
              points((179.7,40),(-179.5,41),(178.3,43))]
    rows=[]
    for i,x in enumerate(fixtures):
        plan=resolver.resolve(COMMAND,x);g=Guard();r=run(plan,guard=g)
        check("two_actual_steps_"+str(i),r["state"]=="PARTIAL_EXECUTED" and len(r["steps"])==2 and g.calls==6)
        check("comparison_refusal_"+str(i),r["comparison"]["value"] is None and r["comparison"]["state"]=="REFUSED_NOT_ADMITTED")
        check("links_"+str(i),[z["receipt_sha256"] for z in r["comparison"]["inputs"]]==[s["bound_receipt"]["receipt_sha256"] for s in r["steps"]])
        for s in r["steps"]:
            def coords(label):
                p=x["points"][label];return p["longitude"],p["latitude"]
            ref=oracle(coords(s["from_point"]),coords(s["to_point"]))
            v=s["values"]
            check("oracle_"+str(i)+s["id"],abs(v["distance_km"]-ref["distance_km"])<1e-6 and abs((v["initial_bearing_deg"]-ref["initial_bearing_deg"]+180)%360-180)<1e-7)
        verify_compound(b,resolver,plan,context,Guard(),r);rows.append(r)
    check("changed_inputs",len({r["steps"][0]["bound_receipt"]["pattern_receipt"]["result_sha256"] for r in rows})==3)
    x=fixtures[0];plan=rows[0]["plan"]
    r=run(resolver.resolve("Orient A to C and A to B",x))
    check("text_controls_order",r["state"]=="EXECUTED_INTERNAL" and [s["to_point"] for s in r["steps"]]==["C","B"] and r["comparison"] is None)
    check("text_controls_count",len(run(resolver.resolve("Orient A to B",x))["steps"])==1)
    check("paraphrase",run(resolver.resolve("Orient A to B and C, then report the nearer destination",x))["steps"]==rows[0]["steps"])
    tie=run(resolver.resolve(COMMAND,points((0,45),(-1,45),(1,45))))
    check("equal_distance_no_tie_break",abs(tie["steps"][0]["values"]["distance_km"]-tie["steps"][1]["values"]["distance_km"])<1e-9 and tie["comparison"]["value"] is None)
    refusals={}
    for cmd,inp in (("Orient A to D",x),("Calculate distance and bearing from A to B in miles",x),
                    ("Find the three nearest 132 kV substations to this solar farm",x),("Calculate electrical cable losses",x),
                    ("Orient A to B or C",x),("Orient A to B",{**x,"unit":"radians"})):
        g=Guard();r=run(resolver.resolve(cmd,inp),guard=g)
        check("refuse "+cmd+str(inp["unit"]),r["state"]=="ABSTAIN" and not r["steps"] and g.calls==0);refusals[cmd]=r
    def reseal(p):return {**p,"plan_sha256":f.sha(f.canonical({k:v for k,v in p.items() if k!="plan_sha256"}))}
    fake=copy.deepcopy(plan);fake["steps"][0]["keys"].reverse()
    reject("forged_selection",lambda:run(reseal(fake)),"PLAN_REINTERPRETATION")
    fake=copy.deepcopy(plan);fake["comparison"]["state"]="ADMITTED"
    reject("forged_admission",lambda:run(reseal(fake)),"PLAN_REINTERPRETATION")
    fake=copy.deepcopy(rows[0]);fake["steps"][0]["values"]["distance_km"]=0
    fake=b.seal({k:v for k,v in fake.items() if k!="receipt_sha256"})
    reject("forged_intermediate",lambda:verify_compound(b,resolver,plan,context,Guard(),fake),"COMPOUND_REPLAY_MISMATCH")
    reject("stale_mid_plan",lambda:run(plan,guard=Guard(4)),"STALE_DEPENDENCY")
    reject("old_context",lambda:verify_compound(b,resolver,plan,{**context,"generation":2},Guard(),rows[0]),"COMPOUND_REPLAY_MISMATCH")
    check("prior_proof_unchanged",f.sha(a.prior.read_bytes())=="19ac2440bdef87adc49763fd9ae0f8f69e21760b9c8bb9bba70e55e2644e41dc")
    b.check_stage();check("registry_unchanged",True)
    report={"schema":"tacit-b1.compound-proof.v1","a1_commit":A1,"actual_receipts":rows,"equal_distance":tie,
            "refusals":refusals,"checks":checks,"comparison":"NOT_ADMITTED","independent_review":"OPEN",
            "guard":"test callback only; E1 live Ledger and signed browser integration separate","rights":"BLOCKED"}
    a.out.write_bytes(f.canonical(report))
    print(f.canonical({"checks":len(checks),"sha256":f.sha(a.out.read_bytes()),"outputs":[[s["values"] for s in r["steps"]] for r in rows]}).decode(),end="")
if __name__=="__main__":main()

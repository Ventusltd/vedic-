"""T17: consume A1 semantic plans through the existing admitted Package Factory.
No parser, generated code, comparison admission, or origin-signing authority.
"""
import copy,re,math
from tacit_b_kuiper import MANIFEST
from tacit_b_convergence import bind_execution,checked_bytes

UNITS={"distance_km":"km","initial_bearing_deg":"degrees"}
PLAN_FIELDS=("schema","instruction","inputs","state","steps","comparison","reason","manifest_sha256","plan_sha256")
STEP_FIELDS=("id","operation","meaning_id","keys","inputs","from_point","to_point","depends_on","outputs")

def execute_compound(bridge,resolver,plan,context,assert_current):
    """Trusted host supplies exact A1 Resolver and a mandatory Ledger guard.
    Guard raises on stale or unknown epoch; caller must hold host authority.
    """
    f=bridge.f
    f.need(callable(assert_current),"LEDGER_GUARD_REQUIRED")
    f.keys(context,("generation","selection_receipt_sha256","challenge"))
    f.need(type(context["generation"]) is int and 0<=context["generation"]<=9007199254740991,"GENERATION")
    for k in ("selection_receipt_sha256","challenge"):
        f.need(isinstance(context[k],str) and re.fullmatch(r"[0-9a-f]{64}",context[k]) is not None,"CONTEXT_DIGEST")
    plan=f.strict(checked_bytes(f,plan));f.keys(plan,PLAN_FIELDS)
    f.need(plan["schema"]=="vedic.compound-plan.v1","PLAN_SCHEMA")
    f.need(plan["plan_sha256"]==f.sha(f.canonical({k:v for k,v in plan.items() if k!="plan_sha256"})),"PLAN_DIGEST")
    expected=resolver.resolve(plan["instruction"],plan["inputs"])
    f.need(checked_bytes(f,expected)==checked_bytes(f,plan),"PLAN_REINTERPRETATION")
    state=plan["state"];steps=plan["steps"];comparison=plan["comparison"]
    f.need(state in ("PLAN_PROPOSED","PARTIAL_PLAN","ABSTAIN") and isinstance(steps,list) and len(steps)<=8,"PLAN_STATE")
    if state=="ABSTAIN":
        f.need(not steps and comparison is None,"ABSTAIN_STEPS")
        return bridge.seal({"schema":"tacit-b.compound-execution.v1","plan":plan,"context":copy.deepcopy(context),
                            "state":"ABSTAIN","steps":[],"comparison":None,"independent_review":"OPEN","rights":"BLOCKED"})
    f.need(plan["manifest_sha256"]==MANIFEST and 1<=len(steps)<=8,"PLAN_MANIFEST")
    inputs=plan["inputs"];f.keys(inputs,("crs","unit","points"))
    f.need(inputs["crs"]=="WGS84" and inputs["unit"]=="degrees","PLAN_UNITS")
    points=inputs["points"];f.need(isinstance(points,dict) and 2<=len(points)<=9,"PLAN_POINTS")
    bridge.check_stage()
    # Validate the entire plan before doing any work. No caller-provided executable or admission flag.
    ids=[];requests=[]
    for i,s in enumerate(steps,1):
        f.keys(s,STEP_FIELDS)
        f.need(s["id"]=="s"+str(i) and s["depends_on"]==[],"STEP_ORDER")
        f.need(s["operation"]=="orient" and s["meaning_id"]=="GG2050-VEDIC-000006","STEP_NOT_ADMITTED")
        f.need(s["outputs"]==UNITS and s["keys"]==bridge.keys("orient"),"STEP_PORTS")
        a,b=s["from_point"],s["to_point"]
        f.need(isinstance(a,str) and isinstance(b,str) and a in points and b in points and a!=b,"STEP_POINTS")
        f.need(s["inputs"]=={"crs":"WGS84","unit":"degrees","point_a":points[a],"point_b":points[b]},"STEP_INPUT_BINDING")
        ids.append(s["id"]);requests.append(bridge.request_v2("orient",s["inputs"]))
    if comparison is None:
        f.need(state=="PLAN_PROPOSED","COMPARISON_STATE")
    else:
        f.need(state=="PARTIAL_PLAN" and len(steps)>=2,"COMPARISON_STATE")
        f.keys(comparison,("operation","depends_on","state","quantity","unit"))
        f.need(comparison=={"operation":"nearer_destination","depends_on":ids,"state":"REFUSED_NOT_ADMITTED","quantity":"distance_km","unit":"km"},"COMPARISON_NOT_ADMITTED")
    assert_current()
    results=[]
    for s,q in zip(steps,requests):
        assert_current()
        r=bind_execution(bridge,q,context)
        assert_current()
        result=r["pattern_receipt"]["result"]
        f.need(result["state"]=="EXECUTED_INTERNAL" and result["admission"] is True,"STEP_REFUSED")
        v=result["output"]
        f.keys(v,UNITS)
        f.need(all(type(x) in (int,float) and math.isfinite(x) for x in v.values()) and
               v["distance_km"]>=0 and 0<=v["initial_bearing_deg"]<360,"STEP_OUTPUT")
        results.append({"id":s["id"],"from_point":s["from_point"],"to_point":s["to_point"],
                        "values":v,"units":dict(UNITS),"bound_receipt":r})
    comp=None
    if comparison is not None:
        # Dependency linkage only, not a hidden comparison, ranking, tie resolution or result.
        comp={**comparison,"inputs":[{"step_id":x["id"],"field":"distance_km","unit":"km",
                 "receipt_sha256":x["bound_receipt"]["receipt_sha256"]} for x in results],"value":None}
    assert_current()
    return bridge.seal({"schema":"tacit-b.compound-execution.v1","plan":plan,"context":copy.deepcopy(context),
                        "state":"PARTIAL_EXECUTED" if comp else "EXECUTED_INTERNAL","steps":results,"comparison":comp,
                        "independent_review":"OPEN","rights":"BLOCKED"})

def verify_compound(bridge,resolver,plan,context,assert_current,receipt):
    actual=execute_compound(bridge,resolver,plan,context,assert_current)
    bridge.f.need(checked_bytes(bridge.f,actual)==checked_bytes(bridge.f,receipt),"COMPOUND_REPLAY_MISMATCH")
    return actual

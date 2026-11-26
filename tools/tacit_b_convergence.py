"""Additive host-context receipt for the existing factory. No origin signer."""
import argparse,copy,math,re,sys
from pathlib import Path
from tacit_b_patterns import PatternBridge,DECISIONS
from tacit_b_kuiper import MANIFEST,ZIP
from tacit_b_admission import member,A,C,C_JSON
from tacit_b_composition import refusal

EARTH={"coordinate_fields":["longitude","latitude"],"crs":"WGS84","coordinate_unit":"degrees",
       "model":"sphere","radius_km":6378.137,"distance":"great-circle haversine km",
       "bearing":"initial clockwise from true north degrees [0,360)",
       "undefined_heading":"coincident, antipodal or polar-origin within inherited 1e-9 degree tolerance",
       "not":"ellipsoidal geodesic, road or conductor route"}

def checked_bytes(f,obj):
    try:
        raw=f.canonical(obj);f.strict(raw);return raw
    except (TypeError,ValueError,OverflowError,RecursionError) as e:
        if isinstance(e,f.Refusal):raise
        raise f.Refusal("INVALID_CONTEXT_JSON") from e

def bind_execution(bridge,q,context):
    """Trusted host context AFTER selection verification; no caller experiment flag."""
    f=bridge.f;bridge.check_stage()
    f.keys(context,("generation","selection_receipt_sha256","challenge"))
    g=context["generation"]
    f.need(type(g) is int and 0<=g<=9007199254740991,"GENERATION")
    for k in ("selection_receipt_sha256","challenge"):
        x=context[k];f.need(isinstance(x,str) and re.fullmatch(r"[0-9a-f]{64}",x) is not None,"CONTEXT_DIGEST")
    q=f.strict(checked_bytes(f,q));r=bridge.execute_v2(q);p=r["pattern"]
    f.need(r["request_sha256"]==f.sha(f.canonical(q)) and
           r["pattern_sha256"]==f.sha(f.canonical(p)) and
           r["result_sha256"]==f.sha(f.canonical(r["result"])),"RECEIPT_BINDING")
    f.need(r["receipt_sha256"]==f.sha(f.canonical({k:v for k,v in r.items() if k!="receipt_sha256"})),"RECEIPT_BINDING")
    provenance={"orient_archive_sha256":p["orient_archive_sha256"],"descriptor_sha256":p["descriptor_sha256"],
                "closure_sha256":p["closure_sha256"],"manifest_sha256":MANIFEST,"sources":p["sources"],
                "build_receipt_sha256":f.sha(f.canonical(bridge.build)) if p["orient_archive_sha256"] else None,
                "earth_model":copy.deepcopy(EARTH) if p["orient_archive_sha256"] else None}
    return bridge.seal({"schema":"tacit-b.execution-context.v1","context":copy.deepcopy(context),"request":q,
                        "pattern_receipt":r,"provenance":provenance,"origin_authentication":"HOST_REQUIRED",
                        "independent_review":"OPEN","rights":"BLOCKED"})

def verify_bound_execution(bridge,q,context,receipt):
    f=bridge.f;actual=bind_execution(bridge,q,context)
    f.need(checked_bytes(f,actual)==checked_bytes(f,receipt),"BOUND_REPLAY_MISMATCH")
    return actual

def orient(a,b):
    return {"crs":"WGS84","unit":"degrees","point_a":dict(zip(("longitude","latitude"),a)),
            "point_b":dict(zip(("longitude","latitude"),b))}

def oracle(a,b):
    """Independent mathematical formulation; 3D vector angle and tangent projection."""
    lon,lat=map(math.radians,a);L,P=map(math.radians,b)
    u=(math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat))
    v=(math.cos(P)*math.cos(L),math.cos(P)*math.sin(L),math.sin(P))
    dot=lambda x,y:sum(a*b for a,b in zip(x,y))
    cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    east=(-math.sin(lon),math.cos(lon),0)
    north=(-math.sin(lat)*math.cos(lon),-math.sin(lat)*math.sin(lon),math.cos(lat))
    return {"distance_km":6378.137*math.atan2(math.hypot(*cross),dot(u,v)),
            "initial_bearing_deg":math.degrees(math.atan2(dot(v,east),dot(v,north)))%360}

def main():
    p=argparse.ArgumentParser()
    for k in ("factory","d","bonds","nearest","nsources","esources","archive","build","decision","prior","out"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();sys.path[:0]=[str(a.factory/"tools"),str(a.d/"tools")]
    import package_factory as f
    import typed_package_execution as t
    from kuiper_select import Space
    raw=member(f,a.bonds,ZIP,"bonds.json",MANIFEST)
    bridge=PatternBridge(f,t,Space,raw,a.archive.read_bytes(),f.strict(a.build.read_bytes()),a.nearest,a.nsources,a.esources)
    checks={}
    def check(k,ok):f.need(ok,k);checks[k]="PASS"
    def reject(k,fn,reason):check(k,refusal(fn)==reason)
    prior=f.strict(a.prior.read_bytes())
    check("legacy_v2_bytes",f.sha(a.prior.read_bytes())=="a5540a0978117750fd54739e423dbd4e7c0150ce1eba81d5139609ed2db7ee97")
    check("archive_pin",f.sha(bridge.archive)==t.ARCHIVE)
    for q,r in zip(prior["requests"],prior["results"]):bridge.replay_v2(q,r)
    check("legacy_v2_actual_replay",True)
    # Deterministic TEST context, not an issued authentication token.
    c={"generation":1,"selection_receipt_sha256":"a"*64,"challenge":"b"*64}
    fixtures=[("north",(0,0),(0,2)),("west",(0,0),(-3,0)),
              ("non_equatorial",(-0.1276,51.5072),(-3.1883,55.9533)),
              ("south_cross",(18.4,-33.9),(151.2,-33.8)),
              ("dateline",(179.8,25),(-179.7,26)),("near_pole",(35,89.9),(40,89.8)),
              ("near_antipodal",(0,10),(179.9,-10)),("destination_pole",(15,40),(15,90))]
    rows={}
    for name,a0,b0 in fixtures:
        q=bridge.request_v2("orient",orient(a0,b0));r=bind_execution(bridge,q,c)
        v=r["pattern_receipt"]["result"]["output"];ref=oracle(a0,b0)
        de=abs(v["distance_km"]-ref["distance_km"]);be=abs((v["initial_bearing_deg"]-ref["initial_bearing_deg"]+180)%360-180)
        check(name+"_distance",de<1e-6);check(name+"_bearing",be<1e-7)
        verify_bound_execution(bridge,q,c,r)
        rows[name]={"receipt":r,"oracle":ref,"distance_error_km":de,"bearing_error_deg":be}
    q=rows["non_equatorial"]["receipt"]["request"];r=rows["non_equatorial"]["receipt"]
    c2={**c,"generation":2,"challenge":"c"*64};r2=bind_execution(bridge,q,c2)
    check("ABA_new_context_same_semantics",r2["pattern_receipt"]==r["pattern_receipt"] and r2["receipt_sha256"]!=r["receipt_sha256"])
    reject("ABA_old_receipt",lambda:verify_bound_execution(bridge,q,c2,r),"BOUND_REPLAY_MISMATCH")
    reject("challenge_only",lambda:verify_bound_execution(bridge,q,{**c,"challenge":"d"*64},r),"BOUND_REPLAY_MISMATCH")
    reject("selection_only",lambda:verify_bound_execution(bridge,q,{**c,"selection_receipt_sha256":"e"*64},r),"BOUND_REPLAY_MISMATCH")
    reject("bad_generation",lambda:bind_execution(bridge,q,{**c,"generation":True}),"GENERATION")
    reject("bad_challenge",lambda:bind_execution(bridge,q,{**c,"challenge":"x"}),"CONTEXT_DIGEST")
    reject("authority_in_context",lambda:bind_execution(bridge,q,{**c,"admitted":True}),"FIELDS")
    for name,mut in (("source",lambda x:x["provenance"]["sources"][0]["source"].update(blob="0"*40)),
                     ("earth",lambda x:x["provenance"]["earth_model"].update(radius_km=6371)),
                     ("result",lambda x:x["pattern_receipt"]["result"]["output"].update(distance_km=0)),
                     ("origin",lambda x:x.update(origin_authentication="VERIFIED")),
                     ("rights",lambda x:x.update(rights="CLEARED"))):
        fake=copy.deepcopy(r);mut(fake);fake=bridge.seal({k:v for k,v in fake.items() if k!="receipt_sha256"})
        reject("rehashed_"+name,lambda:verify_bound_execution(bridge,q,c,fake),"BOUND_REPLAY_MISMATCH")
    old=copy.deepcopy(bridge.manifest);bridge.manifest["source_entries"][0]["source"]["blob"]="0"*40
    reject("stage_manifest_mutation",lambda:bind_execution(bridge,q,c),"MANIFEST_STAGE_MUTATION")
    bridge.manifest=old
    old=bridge.build;bridge.build={**old,"reproducible":False}
    reject("stage_build_mutation",lambda:bind_execution(bridge,q,c),"FACTORY_STAGE_MUTATION");bridge.build=old
    for name,a0,b0 in (("coincident",(10,30),(10,30)),("wrapped_coincident",(180,10),(-180,10)),
                       ("antipodal",(20,30),(-160,-30)),("polar_origin",(0,90),(20,50))):
        reject(name,lambda:bind_execution(bridge,bridge.request_v2("orient",orient(a0,b0)),c),"UPSTREAM_RESULT_REFUSED")
    packet=f.strict(a.decision.read_bytes())
    check("decision_packet_pin",f.sha(a.decision.read_bytes())=="79ca2bf68b94c2c06c4d21063cc1a4acd4442acc43bb9630f8cd32a7d01daa2a")
    decision={}
    for op,family in (("nearest-orient","nearest-substation"),("electrical","electrical")):
        row=packet["families"][family];q=prior["candidate_requests"][op];blocked=bind_execution(bridge,q,c)
        check(op+"_default_refused",blocked["pattern_receipt"]["result"]["state"]=="REFUSED" and not blocked["pattern_receipt"]["result"]["admission"])
        actual=bridge.execute_v2(q,experiment=True)
        check(op+"_actual_pre_admission",actual==prior["candidates"][op] and actual["result"]["state"]=="PRE_ADMISSION_EXECUTED" and not actual["result"]["admission"])
        check(op+"_exact_descriptor",f.sha(f.canonical(row["descriptor"]))==DECISIONS[family] and row["archive"] is None and row["rights"]=="BLOCKED")
        decision[family]={"state":"DECISION_ONLY_NOT_ADMITTED","decision":row,"source_candidate_artifact":15137841195,
                          "source_candidate_zip_sha256":A,"review_artifact":15138980638,"review_zip_sha256":C,
                          "review_member_sha256":C_JSON,"actual_candidate_receipt":actual,"normal_runtime_refusal":blocked,
                          "owner_authorisation":"OPEN","rights":"BLOCKED","handler":"REVIEW_REQUIRED_NO_REGISTRY_MUTATION"}
    bridge.check_stage();check("registry_unchanged",True)
    report={"schema":"tacit-b1.convergence-proof.v1","checks":checks,"fixtures":rows,"context_replay":r2,
            "admission_decisions":decision,"prior_sha256":f.sha(a.prior.read_bytes()),"original_archive_sha256":t.ARCHIVE,
            "earth_model":EARTH,"independent_review":"OPEN","context_limit":"Test challenge only; E1 host origin authentication separate","rights":"BLOCKED"}
    a.out.write_bytes(f.canonical(report))
    print(f.canonical({"checks":len(checks),"sha256":f.sha(a.out.read_bytes()),
                      "max_distance_error_km":max(x["distance_error_km"] for x in rows.values()),
                      "max_bearing_error_deg":max(x["bearing_error_deg"] for x in rows.values())}).decode(),end="")
if __name__=="__main__":main()

"""Additive v2 pattern contract using inherited Bridge and Package Factory."""
import argparse, copy, sys
from pathlib import Path
from tacit_b_kuiper import Bridge, IDS, MANIFEST, ZIP
from tacit_b_admission import PINS, member
from tacit_b_composition import refusal

SCHEMA="tacit-b.kuiper-request.v2"
DECISIONS={"nearest-substation":"d6d42cc3babcc598b1c44e55ac134fd3fc299b0d17caa0a6a663520a8c71b0d4",
           "electrical":"f5a406e399c66a8dbe5baa2be0cada3fae3317b5c2f5366441853472a863e456"}
PAIRS={"orient":set(),"nearest-orient":{("nearestSubstation.id","selected_location.id"),
       ("selected_location.point_a","orient.point_a"),("selected_location.point_b","orient.point_b")},
       "electrical":{("voltageDropVolts.value","dropPercent.dropVolts"),
                     ("lossesWatts.value","annualLossKwh.peakLossWatts")}}

class PatternBridge(Bridge):
    def __init__(self,f,t,space_type,manifest_raw,archive,build,nearest,nsources,esources):
        super().__init__(f,t,space_type,manifest_raw,archive,copy.deepcopy(build),nearest,nsources,esources)
        self._manifest_raw=manifest_raw
        self._build_canonical=f.canonical(self.build)

    def check_stage(self):
        f=self.f
        f.need(f.sha(self._manifest_raw)==MANIFEST and
               f.canonical(self.manifest)==f.canonical(f.strict(self._manifest_raw)),"MANIFEST_STAGE_MUTATION")
        f.need(f.sha(self.archive)==self.t.ARCHIVE and
               f.canonical(self.build)==self._build_canonical,"FACTORY_STAGE_MUTATION")
        f.need(set(f.ADMISSIONS)=={"orient"} and f.REVIEWED_RECEIPTS=={},"REGISTRY_MUTATED")

    def pattern(self,op):
        f=self.f;t=self.t;keys=self.keys(op)
        rows={str(x["kuiper"]["key"]):x for x in self.manifest["source_entries"]}
        f.need(len(rows)==8 and all(k in rows for k in keys),"OCCURRENCE_JOIN")
        sources=[{"key":k,"meaning_id":rows[k]["meaning_id"],"source":copy.deepcopy(rows[k]["source"])} for k in keys]
        edges=[copy.deepcopy(x) for x in self.manifest["typed_bonds"] if (x["from"],x["to"]) in PAIRS[op]]
        f.need(len(edges)==len(PAIRS[op]) and {(x["from"],x["to"]) for x in edges}==PAIRS[op],"TYPED_GRAPH")
        family="orient" if op=="orient" else "nearest-substation" if op=="nearest-orient" else "electrical"
        raw=(f.ADMISSIONS[family] if family=="orient" else f.PENDING[family]).read_bytes()
        d=f.strict(raw)
        if family=="orient":
            f.validate(d)
        else:
            # Pending electrical intentionally lacks the formal receipt; authenticate
            # the exact incomplete descriptor, then preserve the formal refusal.
            expected={"nearest-substation":"3c5dda175a100837e0c320a829dec07ea488f13d",
                      "electrical":"2c45c4359ea87b7c636af7b4f3d280acc338b656"}
            f.need(f.digest(raw,"git-blob-sha1")==expected[family],"PENDING_DESCRIPTOR_PIN")
        descriptor=f.sha(f.canonical(d))
        closure={"descriptor_inputs":d["inputs"],"external_dependencies":d["dependencies"]}
        if family=="orient":
            f.need(f.sha(self.archive)==t.ARCHIVE and descriptor==t.DESCRIPTOR and f.admit(d)==d,"ORIENT_PIN")
            f.need(self.build.get("archive_sha256")==t.ARCHIVE and self.build.get("descriptor_sha256")==t.DESCRIPTOR,"BUILD_PIN")
            graph={"ports":copy.deepcopy(self.manifest["orient"]),"shared_inputs":True,"conditional_bonds":edges}
            review={"source_receipt_sha256":next(x["digest"] for x in d["inputs"] if x["role"]=="receipt"),
                    "closure_status":"ADMITTED_DESCRIPTOR_INPUT_PINS"}
        else:
            f.need(refusal(lambda:f.admit(d)) in ("SOURCE_RECEIPT_PENDING","FAMILY_NOT_ADMITTED"),"ADMISSION_CHANGED")
            graph={"ports":copy.deepcopy(self.manifest["electrical"] if family=="electrical" else
                  {k:self.manifest[k] for k in ("nearest","selected_location","orient")}),"conditional_bonds":edges}
            review={"source_candidate_sha256":PINS[family][0],"closure_candidate_sha256":PINS[family][1],
                    "decision_descriptor_sha256":DECISIONS[family],"closure_status":"REVIEWED_CANDIDATE_NOT_ADMITTED"}
        return {"schema":"tacit-b.kuiper-pattern.v2","operation":op,"manifest_sha256":MANIFEST,"keys":keys,"sources":sources,
                "typed_graph":graph,"descriptor_sha256":descriptor,"closure":closure,
                "closure_sha256":f.sha(f.canonical(closure)),"review_pins":review,
                "orient_archive_sha256":t.ARCHIVE if op!="electrical" else None,
                "orient_descriptor_sha256":t.DESCRIPTOR if op!="electrical" else None,
                "identity_status":"GIT_SOURCE_VERIFIED_STARS_INCOMPLETE"}

    def request_v2(self,op,inputs):
        f=self.f;p=self.pattern(op)
        return {"schema":SCHEMA,"operation":op,"manifest_sha256":MANIFEST,"keys":p["keys"],
                "pattern_sha256":f.sha(f.canonical(p)),"inputs":copy.deepcopy(inputs)}

    def execute_v2(self,q,*,experiment=False):
        f=self.f
        f.keys(q,("schema","operation","manifest_sha256","keys","pattern_sha256","inputs"))
        f.need(q["schema"]==SCHEMA and q["manifest_sha256"]==MANIFEST,"REQUEST_PIN")
        op=q["operation"];f.need(isinstance(op,str) and op in IDS,"UNKNOWN_OPERATION")
        p=self.pattern(op);pin=f.sha(f.canonical(p))
        f.need(q["keys"]==p["keys"],"SELECTION_KEYS")
        f.need(q["pattern_sha256"]==pin,"PATTERN_BINDING")
        try: raw=f.canonical(q)
        except (TypeError,ValueError,OverflowError,RecursionError) as e: raise f.Refusal("INVALID_INPUT_JSON") from e
        f.need(f.strict(raw)==q and isinstance(q["inputs"],dict),"INPUT_FIELDS")
        legacy=self.execute(self.request(op,q["inputs"]),experiment=experiment)
        output={"state":legacy["state"],"output":legacy["output"],"nodes":legacy["nodes"],
                "admission":legacy["admission"],"formal_gate":legacy["formal_gate"],
                "runtime_receipt_sha256":legacy.get("runtime_receipt_sha256")}
        body={"schema":"tacit-b.kuiper-execution.v2","pattern":p,"pattern_sha256":pin,"request_sha256":f.sha(raw),
              "result_sha256":f.sha(f.canonical(output)),"result":output,"legacy_receipt":legacy,
              "independent_verification":"PENDING_EXACT_REQUEST_REVIEW","rights":"BLOCKED"}
        return self.seal(body)

    def execute_raw(self,raw):
        """Strict untrusted wire JSON; no experiment flag available to callers."""
        return self.execute_v2(self.f.strict(raw))

    def replay_v2(self,q,r,*,experiment=False):
        self.f.need(self.execute_v2(q,experiment=experiment)==r,"EXECUTION_REPLAY_MISMATCH")

def main():
    p=argparse.ArgumentParser()
    for k in ("factory","d","bonds","nearest","nsources","esources","archive","build","electrical","decision","out"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();sys.path[:0]=[str(a.factory/"tools"),str(a.d/"tools")]
    import package_factory as f
    import typed_package_execution as t
    from kuiper_select import Space
    raw=member(f,a.bonds,ZIP,"bonds.json",MANIFEST)
    bridge=PatternBridge(f,t,Space,raw,a.archive.read_bytes(),f.strict(a.build.read_bytes()),a.nearest,a.nsources,a.esources)
    checks={}
    def check(name,ok):
        f.need(ok,name);checks[name]="PASS"
    def reject(name,fn,reason):check(name,refusal(fn)==reason)
    def points(lon,lat):
        return {"crs":"WGS84","unit":"degrees","point_a":{"longitude":0,"latitude":0},
                "point_b":{"longitude":lon,"latitude":lat}}
    q1=bridge.request_v2("orient",points(0,2));q2=bridge.request_v2("orient",points(-3,0))
    r1=bridge.execute_raw(f.canonical(q1));r2=bridge.execute_raw(f.canonical(q2))
    check("same_reusable_pattern",r1["pattern_sha256"]==r2["pattern_sha256"])
    check("different_request",r1["request_sha256"]!=r2["request_sha256"])
    check("different_result",r1["result_sha256"]!=r2["result_sha256"])
    for i,q,r,dist,bear in ((1,q1,r1,222.63898158654712,0),(2,q2,r2,333.9584723798207,270)):
        o=r["result"]["output"]
        check("fresh_orient_"+str(i),r["result"]["state"]=="EXECUTED_INTERNAL" and
              abs(o["distance_km"]-dist)<1e-8 and abs(o["initial_bearing_deg"]-bear)<1e-8)
        bridge.replay_v2(q,r);check("replay_"+str(i),True)
        check("legacy_parity_"+str(i),r["legacy_receipt"]==bridge.execute(bridge.request("orient",q["inputs"])))
    reject("stale_result",lambda:bridge.replay_v2(q2,r1),"EXECUTION_REPLAY_MISMATCH")
    reject("wrong_pattern",lambda:bridge.execute_v2({**q1,"pattern_sha256":"0"*64}),"PATTERN_BINDING")
    reject("wrong_manifest",lambda:bridge.execute_v2({**q1,"manifest_sha256":"0"*64}),"REQUEST_PIN")
    reject("wrong_key",lambda:bridge.execute_v2({**q1,"keys":q1["keys"][::-1]}),"SELECTION_KEYS")
    reject("caller_authority",lambda:bridge.execute_v2({**q1,"experiment":True}),"FIELDS")
    reject("unknown_operation",lambda:bridge.execute_v2({**q1,"operation":"eval"}),"UNKNOWN_OPERATION")
    reject("duplicate_wire",lambda:bridge.execute_raw(b'{"schema":1,"schema":2}'),"DUPLICATE_KEY")
    reject("wrong_unit",lambda:bridge.execute_v2(bridge.request_v2("orient",{**points(1,0),"unit":"radians"})),"INPUT_UNITS")
    reject("nonfinite",lambda:bridge.execute_v2(bridge.request_v2("orient",points(float("nan"),0))),"INVALID_INPUT_JSON")
    fake=copy.deepcopy(r1);fake["result"]["output"]["distance_km"]=0
    fake["result_sha256"]=f.sha(f.canonical(fake["result"]));fake=bridge.seal({k:v for k,v in fake.items() if k!="receipt_sha256"})
    reject("forged_rehash",lambda:bridge.replay_v2(q1,fake),"EXECUTION_REPLAY_MISMATCH")
    nearest=f.strict((a.nearest/"packages/nearest-candidate/consumer-fixture.json").read_bytes())["input"]
    electrical=f.strict(a.electrical.read_bytes())["request"]
    candidates={};refusals={};candidate_requests={}
    for op,x in (("nearest-orient",nearest),("electrical",electrical)):
        q=bridge.request_v2(op,x);candidate_requests[op]=q
        r=bridge.execute_raw(f.canonical(q));refusals[op]=r
        check(op+"_default_refusal",r["result"]["state"]=="REFUSED" and r["result"]["output"] is None and not r["result"]["admission"])
        r=bridge.execute_v2(q,experiment=True);candidates[op]=r
        check(op+"_experiment",r["result"]["state"]=="PRE_ADMISSION_EXECUTED" and not r["result"]["admission"])
        bridge.replay_v2(q,r,experiment=True);check(op+"_replay",True)
    changed=copy.deepcopy(nearest);changed["minimumKv"]=275
    threshold=bridge.execute_v2(bridge.request_v2("nearest-orient",changed),experiment=True)
    check("nearest_threshold",threshold["result"]["output"]["id"]=="far")
    def rec(id,lon):return {"id":id,"name":id,"location":{"longitude":lon,"latitude":0},"voltages_kv":[132]}
    tie={**nearest,"records":[rec("east",1),rec("west",-1)],"minimumKv":132}
    ties=[bridge.execute_v2(bridge.request_v2("nearest-orient",x),experiment=True) for x in (tie,{**tie,"records":tie["records"][::-1]})]
    check("nearest_ordered_ties",[x["result"]["output"]["id"] for x in ties]==["east","west"] and ties[0]["request_sha256"]!=ties[1]["request_sha256"])
    changed=copy.deepcopy(electrical);changed["route"]["value"]=500
    ehalf=bridge.execute_v2(bridge.request_v2("electrical",changed),experiment=True)
    check("explicit_route_metres",ehalf["result"]["output"]["energy"]==13140)
    check("electrical_base",candidates["electrical"]["result"]["output"]["energy"]==26280)
    packet=f.strict(a.decision.read_bytes())
    for family,pin in DECISIONS.items():
        row=packet["families"][family]
        check(family+"_reviewed_descriptor",row["descriptor_sha256"]==pin and
              f.sha(f.canonical(row["descriptor"]))==pin and row["archive"] is None and row["rights"]=="BLOCKED")
    check("registry_unchanged",set(f.ADMISSIONS)=={"orient"} and f.REVIEWED_RECEIPTS=={})
    result={"schema":"tacit-b1.pattern-proof.v1","requests":[q1,q2],"results":[r1,r2],"candidate_requests":candidate_requests,
            "candidates":candidates,"refusals":refusals,"threshold":threshold,"ties":ties,"half_route":ehalf,
            "archive_sha256":f.sha(bridge.archive),"decision_packet_sha256":f.sha(a.decision.read_bytes()),"checks":checks,
            "independent_review":"OPEN","redistribution":"BLOCKED"}
    a.out.write_bytes(f.canonical(result))
    print(f.canonical({"checks":len(checks),"sha256":f.sha(a.out.read_bytes()),"orient":[r["result"]["output"] for r in (r1,r2)]}).decode(),end="")
if __name__=="__main__":main()

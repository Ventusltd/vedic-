"""Bounded Kuiper → existing VEDIC/factory runtime adapter; no arbitrary source execution."""
import argparse,copy,io,sys,subprocess,zipfile
from pathlib import Path
from tacit_b_composition import load_bond,validate_selected_contract,refusal
from tacit_b_admission import member
from tacit_b_ranking import Ranking
from tacit_b_electrical import execute as electrical_execute

MANIFEST="821abf96d3e4c2f42e61d578dcefdfbda366c145b067f9cc9206fdaa91b6cf2d"
ZIP="649209e8723af1efd4c73f85ebd90b524a2312907d8a5e24759c8bf72ad1f72a"
IDS={"orient":(1,5),"nearest-orient":(1,5,15,16),"electrical":(24,25,26,27)}
MODULES={"orient":("Vg",),"nearest-orient":("Vg","Vn"),"electrical":("Vd",)}
class Bridge:
    def __init__(self,f,t,space_type,manifest_raw,archive,build,nearest,nsources,esources):
        f.need(isinstance(manifest_raw,bytes) and f.sha(manifest_raw)==MANIFEST,"MANIFEST_AUTHENTICATION")
        manifest=f.strict(manifest_raw)
        self.f,self.t,self.space,self.manifest=f,t,space_type(manifest),manifest
        self.archive,self.build=archive,build
        self.nearest,self.nsources,self.esources=nearest,nsources,esources
    def keys(self,op):
        f=self.f;f.need(op in IDS,"UNKNOWN_OPERATION")
        semantic=sorted({k for i in IDS[op] for k in self.space.select(meaning="GG2050-VEDIC-%06d"%i)})
        machine=sorted({k for module in MODULES[op] for k in self.space.select(module=module)})
        f.need(semantic==machine and len(semantic)==len(IDS[op]),"SELECTION_PARITY")
        return [str(k) for k in semantic]
    def request(self,op,inputs):
        return {"schema":"tacit-b.kuiper-request.v1","operation":op,"manifest_sha256":MANIFEST,"keys":self.keys(op),"inputs":inputs}
    def orient(self,points):
        t=self.t
        return t.execute({"schema":t.SCHEMA,"family":"orient","export":"orient","descriptor_sha256":t.DESCRIPTOR,
                         "archive_sha256":t.ARCHIVE,"ports":dict(t.PORTS),"input":points},self.archive,self.build)
    def execute(self,q,*,experiment=False):
        f=self.f;t=self.t
        f.keys(q,("schema","operation","manifest_sha256","keys","inputs"))
        f.need(q["schema"]=="tacit-b.kuiper-request.v1" and q["manifest_sha256"]==MANIFEST,"REQUEST_PIN")
        op=q["operation"];f.need(isinstance(op,str) and op in IDS,"UNKNOWN_OPERATION")
        f.need(q["keys"]==self.keys(op),"SELECTION_KEYS")
        f.need(isinstance(q["inputs"],dict),"INPUT_FIELDS")
        pattern={"operation":op,"manifest_sha256":MANIFEST,"keys":q["keys"]}
        body={"schema":"tacit-b.kuiper-execution.v1","request_sha256":f.sha(f.canonical(q)),
              "pattern_sha256":f.sha(f.canonical(pattern)),"pattern":pattern,
              "runtime":{"python":sys.version.split()[0],"node":subprocess.check_output(["node","--version"],text=True).strip()},
              "independent_verification":"PENDING_EXACT_REQUEST_REVIEW","rights":"BLOCKED"}
        d=None
        if op!="orient":
            family="nearest-substation" if op=="nearest-orient" else "electrical"
            d=f.strict(f.PENDING[family].read_bytes())
            gate=refusal(lambda:f.admit(d))
            body.update(formal_gate=gate,admission=False,archive_sha256=None)
            if not experiment:
                body.update(state="REFUSED",nodes=[],output=None)
                return self.seal(body)
        if op=="orient":
            obs=self.orient(q["inputs"])
            body.update(state="EXECUTED_INTERNAL",admission=True,formal_gate="ADMITTED_ORIENT_ONLY",
               archive_sha256=t.ARCHIVE,descriptor_sha256=t.DESCRIPTOR,nodes=["distanceKm","initialBearingDeg"],
               output=obs["pattern"]["output"],runtime_receipt_sha256=f.sha(f.canonical(obs)))
        elif op=="nearest-orient":
            rank=Ranking(f,d,self.nsources)
            ranked=rank.run(q["inputs"]);result=rank.replay(q["inputs"],ranked)
            body.update(descriptor_sha256=rank.descriptor_sha,ranking_receipt_sha256=ranked["receipt_sha256"],
                        ranking_request_sha256=ranked["request_sha256"],nodes=["nearestSubstation","ranking-replay"])
            if result is None:body.update(state="NO_ELIGIBLE_RECORD",output=None)
            else:
                bond=load_bond(self.nearest/"packages/nearest-candidate/kuiper_bond.py")
                actual=[]
                def calculate(points):
                    obs=self.orient(points);actual.append(obs);return obs["pattern"]["output"]
                validate_selected_contract(bond,q["inputs"],result,bond.sha(bond.canonical(q["inputs"])),calculate)
                f.need(len(actual)==1,"ORIENT_CALL_COUNT")
                obs=actual[0]
                body["nodes"]+=["selected_location","distanceKm","initialBearingDeg"]
                body.update(state="PRE_ADMISSION_EXECUTED",output={"id":result["id"],**obs["pattern"]["output"]},
                  selected_location=ranked["selected_location"],orient_archive_sha256=t.ARCHIVE,
                  runtime_receipt_sha256=f.sha(f.canonical(obs)))
        else:
            obs=electrical_execute(f,d,self.esources,q["inputs"])
            body.update(state="PRE_ADMISSION_EXECUTED",descriptor_sha256=obs["descriptor_sha256"],
              nodes=["voltageDropVolts","dropPercent","lossesWatts","annualLossKwh"],
              output={k:v["value"] for k,v in obs["outputs"].items()},
              runtime_receipt_sha256=f.sha(f.canonical({k:v for k,v in obs.items()})))
        return self.seal(body)
    def seal(self,body):
        return {**body,"receipt_sha256":self.f.sha(self.f.canonical(body))}
    def replay(self,q,receipt,*,experiment=False):
        self.f.need(self.execute(q,experiment=experiment)==receipt,"EXECUTION_REPLAY_MISMATCH")

def main():
    p=argparse.ArgumentParser()
    for k in ("factory","d","bonds","nearest","nsources","esources","archive","build","electrical","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();sys.path[:0]=[str(a.factory/"tools"),str(a.d/"tools")]
    import package_factory as f
    import typed_package_execution as t
    from kuiper_select import Space
    m=member(f,a.bonds,ZIP,"bonds.json",MANIFEST)
    def create(raw):return Bridge(f,t,Space,raw,a.archive.read_bytes(),f.strict(a.build.read_bytes()),a.nearest,a.nsources,a.esources)
    bridge=create(m)
    fixture=f.strict((a.nearest/"packages/nearest-candidate/consumer-fixture.json").read_bytes())["input"]
    electrical=f.strict(a.electrical.read_bytes())["request"]
    orient={"crs":"WGS84","unit":"degrees","point_a":{"longitude":0,"latitude":0},"point_b":{"longitude":1,"latitude":0}}
    requests={op:bridge.request(op,x) for op,x in (("orient",orient),("nearest-orient",fixture),("electrical",electrical))}
    results={op:bridge.execute(q,experiment=True) for op,q in requests.items()}
    refusals={op:bridge.execute(requests[op]) for op in ("nearest-orient","electrical")}
    checks={}
    def check(name,ok):f.need(ok,name);checks[name]="PASS"
    def reject(name,fn,reason):check(name,refusal(fn)==reason)
    changed=f.strict(m);changed["source_entries"][0]["kuiper"]["key"]+=1
    reject("raw_manifest_key_mutation",lambda:create(f.canonical(changed)),"MANIFEST_AUTHENTICATION")
    reject("raw_manifest_object",lambda:create(changed),"MANIFEST_AUTHENTICATION")
    for op,q in requests.items():
        bridge.replay(q,results[op],experiment=True);check(op+":replay",True)
    check("nearest_real",results["nearest-orient"]["output"]["id"]=="eligible" and abs(results["nearest-orient"]["output"]["distance_km"]-111.31949079327356)<1e-8 and results["nearest-orient"]["output"]["initial_bearing_deg"]==90)
    check("electrical_real",results["electrical"]["output"]["energy"]==26280)
    check("orient_real",results["orient"]["admission"] is True)
    check("refusals",all(x["state"]=="REFUSED" and x["nodes"]==[] and x["output"] is None for x in refusals.values()))
    q=copy.deepcopy(requests["nearest-orient"]);q["inputs"]["records"]=[]
    check("empty",bridge.execute(q,experiment=True)["state"]=="NO_ELIGIBLE_RECORD")
    q=copy.deepcopy(requests["nearest-orient"]);q["inputs"]["minimumKv"]=275
    check("alternate_threshold",bridge.execute(q,experiment=True)["output"]["id"]=="far")
    q=copy.deepcopy(requests["electrical"]);q["inputs"]["route"]["value"]=500
    check("alternate_length",bridge.execute(q,experiment=True)["output"]["energy"]==13140)
    q=copy.deepcopy(requests["orient"]);q["keys"]=q["keys"][::-1]
    reject("reordered_keys",lambda:bridge.execute(q),"SELECTION_KEYS")
    q=copy.deepcopy(requests["orient"]);q["manifest_sha256"]="0"*64
    reject("manifest_mutation",lambda:bridge.execute(q),"REQUEST_PIN")
    q=copy.deepcopy(requests["orient"]);q["operation"]="eval"
    reject("unknown_operation",lambda:bridge.execute(q),"UNKNOWN_OPERATION")
    q=copy.deepcopy(requests["orient"]);q["admission"]=True
    reject("caller_authority",lambda:bridge.execute(q),"FIELDS")
    fake=copy.deepcopy(results["nearest-orient"]);fake["output"]["id"]="far";fake=bridge.seal({k:v for k,v in fake.items() if k!="receipt_sha256"})
    reject("forged_rehash",lambda:bridge.replay(requests["nearest-orient"],fake,experiment=True),"EXECUTION_REPLAY_MISMATCH")
    report={"schema":"tacit-b.kuiper-bridge-proof.v1","requests":requests,"results":results,"refusals":refusals,
        "checks":checks,"selection_producer_commit":"4859abbdd7166ecab566ecc86337b56e0bd75125","rights":"BLOCKED"}
    a.out.write_bytes(f.canonical(report));print(f.canonical({"checks":len(checks),"sha256":f.sha(a.out.read_bytes()),"states":{k:v["state"] for k,v in results.items()}}).decode(),end="")
if __name__=="__main__":main()

"""Use existing factory validation for exact A/C reviewed candidates; never admit them."""
import argparse,copy,io,sys,zipfile
from pathlib import Path
from tacit_b_composition import refusal

A="c1ea563a7be0c1343d547d5678f46b86952a73bc8d5346d330a0faf8e7667772"
C="8d48284a1ed870d16d99504707c81e0650a23c24693a1e491a787e809bb08ffa"
C_JSON="76080746a09f0c3fa6693211147acfa98716be50caeb766f4ee01a68fc9ac303"
A_HEAD="5ae1e8d4d0f5d9f852aa589a0894e52f112eed6e"
PINS={
 "electrical":("3526d5fc61fc79e4a843b525d66f4dd956643ac84b110244553bdcb7f5736c0a","c5b16903919c91337df664c8482095c3ac9dbd36df3bfb9b06991a43afd9c7f4"),
 "nearest-substation":("0aef7559f3b6a662d9556fc514ee4fbd7c5b37bcf31c2d9d58675fa05fbc30c9","3901fac7ad2612bed7690f6e7f71d7be272a2ed4287e537cfb0125f875768bd6")}
def member(f,path,zip_pin,name,member_pin):
    raw=path.read_bytes()
    f.need(len(raw)<=8_000_000 and f.sha(raw)==zip_pin,"ARTIFACT_PIN")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        hits=[x for x in z.infolist() if x.filename==name or x.filename.endswith("/"+name)]
        f.need(len(hits)==1 and hits[0].file_size<=f.LIMIT,"ARTIFACT_MEMBER")
        v=z.read(hits[0])
    f.need(f.sha(v)==member_pin,"MEMBER_PIN")
    return v
def candidate(f,family,descriptor,sr,cr,review_raw,modules):
    f.need(family in PINS,"UNKNOWN_FAMILY")
    f.need(f.sha(review_raw)==C_JSON,"INDEPENDENT_REVIEW_PIN")
    c=f.strict(review_raw); short="nearest" if family=="nearest-substation" else family
    row=c["source_and_closure"][short]
    f.need(c["candidate_head"]==A_HEAD and c["result"]=="BOUNDED_EVIDENCE_HONOURED" and c["formal_factory_admission"] is False and c["publication"] is False,"REVIEW_AUTHORITY")
    sd,cd=PINS[family]
    f.need(row["source_candidate_sha256"]==sd and row["closure_candidate_sha256"]==cd and row["source"]["verdict"]==row["closure"]["verdict"]=="HONOURED" and row["source"]["formal_acceptance"]==row["closure"]["formal_acceptance"]=="OPEN","REVIEW_FAMILY")
    pending=f.strict(f.PENDING[family].read_bytes())
    f.need(f.canonical(descriptor)==f.canonical(pending),"PENDING_DESCRIPTOR_PIN")
    # Descriptor pins are independently checked against real input bytes.
    required=[x for x in pending["inputs"] if x["role"] in ("module","local_dependency")]
    f.need(set(modules)=={x["path"] for x in required},"MODULE_SET")
    for x in required:f.need(f.digest(modules[x["path"]],x["algorithm"])==x["digest"],"MODULE_PIN")
    def contract(s,cl):
        want={x["path"]:{"blob":f.digest(modules[x["path"]],"git-blob-sha1"),"sha256":f.sha(modules[x["path"]])} for x in required}
        return (s["family"]==cl["family"]==short and s["modules"]==cl["modules"]==want
          and s["source_commit"]==cl["source_commit"]==required[0]["commit"]
          and s["dictionary_commit"]==pending["edition"] and s["identity_complete"] is False
          and s["independent_acceptance"] is False and cl["independent_acceptance"] is False
          and s["rights"]=="BLOCKED" and cl["runtime_verified"] is False and cl["execution_edges"]==[]
          and s["candidate_state"]==cl["candidate_state"]=="REFUSED_REVIEW_PENDING")
    pin={"receipt_sha256":sd,"closure_sha256":cd,"schema":"vedic.tacit-a.source-review-candidate.v1",
         "closure_schema":"vedic.tacit-a.closure-review-candidate.v1",
         "source_sha256":{x["path"]:f.sha(modules[x["path"]]) for x in required},"validate":contract}
    # Same validator used by formal registry; candidate pin is never inserted there.
    f.check_receipt_pin(pin,sr,modules,cr)
    d=copy.deepcopy(pending)
    d["inputs"]=[x for x in d["inputs"] if x["role"] not in ("receipt","closure")]
    for role,digest in (("receipt",sd),("closure",cd)):
        kind="source" if role=="receipt" else "closure"
        d["inputs"].append({"role":role,"filename":role+".json","repo":"Ventusltd/vedic-","commit":A_HEAD,
            "path":"family-review/"+short+"-"+kind+".json","algorithm":"sha256","digest":digest,"output":role+"-receipt.json"})
    d["evidence"]+=["https://github.com/Ventusltd/vedic-/actions/artifacts/15137841195","https://github.com/Ventusltd/neural-link-between-agents/actions/artifacts/15138980638"]
    d["obligations"]+=["Candidate artifact member paths, not Git tree paths; owner decision and explicit factory registry admission required"]
    # Real structural validator, not a custom replacement.
    f.validate(d)
    gate=refusal(lambda:f.admit(d));review_gate=refusal(lambda:f.review_receipt(family,sr,modules,cr))
    f.need(gate in ("SOURCE_RECEIPT_PENDING","FAMILY_NOT_ADMITTED") and review_gate=="REVIEWED_RECEIPT_NOT_PINNED","FORMAL_GATE_CHANGED")
    return {"family":family,"state":"REVIEWED_CANDIDATE_NOT_ADMITTED","descriptor":d,"descriptor_sha256":f.sha(f.canonical(d)),
        "source_sha256":sd,"closure_sha256":cd,"review_sha256":C_JSON,"formal_gate":gate,"formal_review_gate":review_gate,
        "archive":None,"rights":"BLOCKED","input_locator":"A artifact 15137841195 members, not Git tree files",
        "owner_decision":"Authorise exact candidate review pins and family handler for internal-only admission; retain rights block; no public release",
        "rollback":"Remove only approved family registration; preserve ORIENT and historical receipts"}
def main():
    p=argparse.ArgumentParser()
    for k in ("factory","a","c","nearest","electrical","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.factory/"tools"))
    import package_factory as f
    review=member(f,a.c,C,"a-review.json",C_JSON)
    rows={};checks={}
    for family,(sd,cd) in PINS.items():
        short="nearest" if family=="nearest-substation" else family
        sr=member(f,a.a,A,"family-review/"+short+"-source.json",sd)
        cr=member(f,a.a,A,"family-review/"+short+"-closure.json",cd)
        d=f.strict(f.PENDING[family].read_bytes())
        root=a.nearest if short=="nearest" else a.electrical
        modules={x["path"]:f.read_file(root,x["filename"]) for x in d["inputs"] if x["role"] in ("module","local_dependency")}
        def run(ds=d,s=sr,c=cr,rv=review,m=modules):return candidate(f,family,ds,s,c,rv,m)
        rows[family]=run()
        def reject(label,fn,reason):
            f.need(refusal(fn)==reason,label);checks[family+":"+label]=reason
        reject("forged_review",lambda:run(rv=review+b" "),"INDEPENDENT_REVIEW_PIN")
        reject("wrong_source",lambda:run(s=cr),"RECEIPT_DIGEST")
        reject("wrong_closure",lambda:run(c=sr),"CLOSURE_DIGEST")
        changed=copy.deepcopy(d);changed["version"]="9.9.9"
        reject("stale_descriptor",lambda:run(ds=changed),"PENDING_DESCRIPTOR_PIN")
        changed=copy.deepcopy(d);changed["licence"]="CLEARED"
        reject("rights_escalation",lambda:run(ds=changed),"PENDING_DESCRIPTOR_PIN")
        bad=dict(modules);key=next(iter(bad));bad[key]+=b" "
        reject("source_mutation",lambda:run(m=bad),"MODULE_PIN")
        f.need(run()==rows[family],"REPEAT")
    f.need(set(f.ADMISSIONS)=={"orient"} and f.REVIEWED_RECEIPTS=={},"REGISTRY_MUTATED")
    out={"schema":"tacit-b.admission-decision-packet.v1","families":rows,"checks":checks,"admitted":["orient"],"rights":"BLOCKED"}
    a.out.write_bytes(f.canonical(out));print(f.canonical({"checks":len(checks),"families":{k:v["descriptor_sha256"] for k,v in rows.items()},"sha256":f.sha(a.out.read_bytes())}).decode(),end="")
if __name__=="__main__":main()

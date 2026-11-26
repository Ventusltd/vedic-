"""Four pinned source occurrences only. No producer-code execution or new identity."""
import argparse, copy, hashlib, json, statistics, subprocess, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
LIMIT=2*1024*1024
RECEIPT_SHA="83147e90c0f0831ee1f82ce5e721a3521dc843421a96ae9cba3425343d0b3c19"
def need(ok,msg):
    if not ok: raise ValueError(msg)
def canonical(x): return (json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def keys(x,expected): need(isinstance(x,dict) and set(x)==set(expected.split()),"UNKNOWN_OR_MISSING_FIELD")
def read(p):
    b=p.read_bytes();need(len(b)<=LIMIT,"INPUT_SIZE");return b
def verify(b,p):
    need(blob(b)==p["blob"],"GIT_BLOB_MISMATCH")
    need(p.get("sha256") in (None,sha(b)),"SHA256_MISMATCH")
def derive(row,root,receipt):
    keys(row,"family source selected_exports descriptor test runtime_state")
    s=row["source"];keys(s,"repo commit path blob sha256")
    keys(row["descriptor"],"commit path blob");keys(row["test"],"run job head")
    family=row["family"];need(family in ("orient","electrical","nearest","solar"),"FAMILY")
    raw=read(root/(family+".mjs"));verify(raw,s)
    d_raw=read(root/(family+".json"));verify(d_raw,row["descriptor"]);d=json.loads(d_raw)
    run=json.loads(read(root/(family+"-run.json")));job=json.loads(read(root/(family+"-job.json")))
    need(run["id"]==row["test"]["run"] and run["head_sha"]==row["test"]["head"] and job["id"]==row["test"]["job"] and job["run_id"]==run["id"],"TEST_PIN")
    need(run["conclusion"]=="success" and job["conclusion"]=="success","TEST_NOT_GREEN")
    parsed=json.loads(subprocess.check_output(["node",str(HERE/"parse.mjs"),str(root/(family+".mjs"))],timeout=20))
    need(parsed["module_sha256"]==sha(raw),"PARSER_DIGEST")
    exports={e["name"]:e for e in parsed["exports"]}
    need(set(row["selected_exports"])<=set(exports),"EXPORT_MISSING")
    expected=["./v9-geodesy.js"] if family=="nearest" else []
    need(parsed["imports"]==expected,"DEPENDENCY_CLOSURE_CHANGED")
    identity={k:s[k] for k in ("repo","commit","path","blob")}
    identity["sha256"]=sha(raw)
    joins=[]
    for name in row["selected_exports"]:
        j={"export":name,"span":exports[name],"meaning_id":None,"kuiper_key":None,"stars_occurrence":None,"join_state":"NOT_REVIEWED"}
        if family=="orient":
            c=next(c for c in receipt["components"] if c["export"]==name)
            need(c["source"]["blob"]==s["blob"] and c["source"]["commit"]==s["commit"] and c["source"]["path"]==s["path"],"RECEIPT_SOURCE")
            need(c["kuiper"]["state"]=="PINNED_PRODUCER_RECEIPT_MATCH_NOT_WAFER_REPLAY","KEY_TIER")
            p=c["parser"];need(all(exports[name][k]==p[k] for k in ("first","last","col0","col1")),"SPAN_MISMATCH")
            j.update(meaning_id=c["gg_id"],kuiper_key=c["kuiper"]["key"],join_state=c["kuiper"]["state"],stars_state=c["stars"]["state"])
        joins.append(j)
    properties={"bytes":len(raw),"export_count":len(exports),"static_dependency_count":len(parsed["imports"]),"static_dependencies":parsed["imports"],"module_exports":parsed["exports"],"declared_package_ports":d["ports"],"package_exports":d["exports"],"observed_tests":{"run":run["id"],"job":job["id"],"head":run["head_sha"],"conclusion":job["conclusion"]},"rights":"BLOCKED","runtime_state":row["runtime_state"],"independent_acceptance":False}
    source_url="https://github.com/"+s["repo"]+"/blob/"+s["commit"]+"/"+s["path"]
    desc_url="https://github.com/Ventusltd/vedic-/blob/"+row["descriptor"]["commit"]+"/"+row["descriptor"]["path"]
    run_url="https://github.com/Ventusltd/vedic-/actions/runs/"+str(run["id"])
    receipt_url="https://github.com/Ventusltd/vedic-/actions/artifacts/15126683549"
    property_rows=[]
    def prop(occ,name,value,unit,method,input_sha,evidence,state,reason=None):
        need(state in ("OBSERVED","DERIVED","UNKNOWN"),"PROPERTY_STATE")
        need((value is None and bool(reason)) if state=="UNKNOWN" else (value is not None and reason is None),"UNKNOWN_RULE")
        property_rows.append({"source_occurrence":occ,"property":name,"definition_version":"tacit4b.seed-properties.v1","value":value,"unit":unit,"method":method,"input_sha256":input_sha,"evidence_ref":evidence,"state":state,"unknown_reason":reason})
    prop(identity,"bytes",len(raw),"bytes","exact Git blob byte length",sha(raw),source_url,"OBSERVED")
    prop(identity,"export_count",len(exports),"count","Acorn 8.15.0 named exports",sha(raw),source_url,"DERIVED")
    prop(identity,"static_dependency_count",len(parsed["imports"]),"count","unique static ESM import specifiers",sha(raw),source_url,"DERIVED")
    prop(identity,"declared_package_ports",d["ports"],None,"pinned descriptor, not inferred from source",sha(d_raw),desc_url,"OBSERVED")
    prop(identity,"test_conclusion",job["conclusion"],None,"exact-head run and job metadata",sha(canonical({"run":run["id"],"head":run["head_sha"],"job":job["id"],"conclusion":job["conclusion"]})),run_url,"OBSERVED")
    prop(identity,"runtime_state",row["runtime_state"],None,"historical package evidence tier",sha(d_raw),desc_url,"OBSERVED")
    prop(identity,"redistribution_rights",None,None,"no clearance receipt",sha(raw),source_url,"UNKNOWN","RIGHTS_UNRESOLVED")
    for j in joins:
        occ={**identity,"export":j["export"],"span":j["span"]}
        for k in ("meaning_id","kuiper_key","stars_occurrence"):
            val=j[k]
            prop(occ,k,val,None,"pinned producer receipt" if family=="orient" else "await specialist receipt",RECEIPT_SHA if family=="orient" else sha(raw),receipt_url if family=="orient" else source_url,"OBSERVED" if val is not None else "UNKNOWN",None if val is not None else ("STARS_OCCURRENCE_NOT_INDEXED" if family=="orient" else "EXACT_JOIN_NOT_REVIEWED"))
    return {"family":family,"source":identity,"joins":joins,"properties":properties,"property_rows":property_rows,"property_sha256":sha(canonical(property_rows)),"provenance":{"parser":parsed["parser"],"descriptor":row["descriptor"],"receipt_sha256":RECEIPT_SHA if family=="orient" else None,"derivation":"tacit4b.seed-properties.v1","dependency_count_basis":"unique static ESM import specifiers; not transitive graph or free-variable proof"}}
def main():
    p=argparse.ArgumentParser();p.add_argument("root",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    cohort=json.loads(read(HERE/"cohort.json"));need(len(cohort)==4,"COHORT_SIZE")
    r=read(a.root/"orient-receipt.json");need(sha(r)==RECEIPT_SHA,"RECEIPT_DIGEST");receipt=json.loads(r)
    need(receipt["module_sha256"]==cohort[0]["source"]["sha256"] and receipt["identity_complete"] is False,"RECEIPT_STATE")
    timings=[];results=[]
    for _ in range(3):
        start=time.perf_counter_ns();result=[derive(row,a.root,receipt) for row in cohort];timings.append(time.perf_counter_ns()-start);results.append(canonical(result))
    need(results[0]==results[1]==results[2],"NONDETERMINISTIC")
    rows=json.loads(results[0]);need([j["kuiper_key"] for j in rows[0]["joins"]]==[86415575118,86415575222],"KEY_MISMATCH")
    solar=rows[3];need({j["export"] for j in solar["joins"]}=={"tableShape","formatRefusal"},"SOLAR_EXPORTS")
    checks=0
    for altered in ("digest","unknown"):
        row=copy.deepcopy(cohort[3])
        if altered=="digest": row["source"]["blob"]="0"*40
        else: row["invented_property"]=1
        try: derive(row,a.root,receipt)
        except ValueError as e: need(str(e)==("GIT_BLOB_MISMATCH" if altered=="digest" else "UNKNOWN_OR_MISSING_FIELD"),"WRONG_REFUSAL");checks+=1
        else: raise AssertionError("tamper accepted")
    changed=copy.deepcopy(solar);changed["property_rows"][0]["value"]+=1
    need(changed["source"]==solar["source"] and sha(canonical(changed["property_rows"]))!=solar["property_sha256"],"PROPERTY_IDENTITY_COUPLED");checks+=1
    required=set("source_occurrence property definition_version value unit method input_sha256 evidence_ref state unknown_reason".split())
    for row in rows:
        for prop in row["property_rows"]:
            need(set(prop)==required,"PROPERTY_FIELDS")
            need(prop["state"]!="UNKNOWN" or (prop["value"] is None and prop["unknown_reason"]),"UNKNOWN_RULE")
    checks+=1
    report={"schema":"tacit4b.seed-properties.v1","cohort_size":4,"records":rows,"identity_allocation":False,"independent_acceptance":False}
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"seed-properties.json").write_bytes(canonical(report))
    bench={"scope":"four local sources + descriptors + receipt + CI metadata; includes Node process startup and formal parse; excludes acquisition","repeats":3,"elapsed_ns":timings,"median_ns":int(statistics.median(timings)),"device":"CPU","gpu_executed":False,"repeated_bytes_equal":True,"adversarial_checks":checks,"sidecar_sha256":sha(canonical(report))}
    (a.output/"cpu-benchmark.json").write_bytes(canonical(bench))
    print(json.dumps(bench,sort_keys=True))
    print(json.dumps([{"family":x["family"],"bytes":x["properties"]["bytes"],"exports":x["properties"]["export_count"],"dependencies":x["properties"]["static_dependency_count"]} for x in rows]))
if __name__=="__main__": main()

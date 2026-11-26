"""Tenth-turn cold recovery of the existing A/B/C/D evidence chain. No runtime authority."""
import argparse,copy,json,subprocess,sys,zipfile
from pathlib import Path
from tacit_a_closure import canonical,sha,need,GRID,COMMIT,VEDIC
from tacit_a_index_grain import member,C_REPO,FAMILIES,C_SHA
from tacit_a_bonds import download,identity
from tacit_a_recovery import acquire as acquire_old,verify as verify_old,source_guard,property_guard,relation_guard,BOND_SHA,BOND_ZIP
from tacit_a_impact import impact,REPAIR_ZIP,REPAIR_SHA,IMPACT_ZIP,IMPACT_SHA,C_RANK_SHA,C_ELEC_SHA,occurrence
OLD_CAPSULE_SHA="ae4ef39ac1886e2b1eadd57ffeebe7d08099efa38d3f6594ed1dcfd4a771bf7d"
BRIDGE_ZIP="74fe853f050765545dfeb6404c8c84c9d9413754c0d8ec38131182544c7a4149"
BRIDGE_SHA="7bb9e81ca066cafbaeae75a358da42768bb9db6a63746710025d88b7e0701796"
C_ID_ZIP="00434d8a3c59dbb160986df65831c22c8ad48a736e190de4d84dc00e4b7b6c8c"
C_ID_SHA="9dc9d328f5c55206648180acb925447306da29a09ad9dd442ef8be5b53d7bea7"
C_GATE_ZIP="a6fa111dfc5df17aa09dab86203ed20c2e68df7133e4130f83a5c1e106a8132f"
C_GATE_SHA="303ad784d6d8775e7dc16b98f8dd4a9c5eef113abc7cde0c87129a3065c02b5b"
D_ZIP="00564dcd406c280c9a6529feb63a55dc59fb65eb59c5c4ea699073458e8d9fbd"
D_RECEIPT="a763f68e9a0efa6de3156a92e5bf45a5ce48167cd22341639c4c7b23b7cfadda"
def acquire(root):
    acquire_old(root)
    for n,i in (("repair",15141151895),("impact",15140897950),("bridge",15140148659)):download(root,n,i)
    for name,repo,id in (("c-identity",C_REPO,15140568401),("c-gate",C_REPO,15141600096),("d", "Ventusltd/kuiper-belt",15141615078)):
        with (root/(name+".zip")).open("xb") as f:subprocess.run(["gh","api",f"repos/{repo}/actions/artifacts/{id}/zip"],stdout=f,check=True,timeout=90)
def exact_json(path,pin,digest=None):
    need(sha(path.read_bytes())==pin,"ZIP_PIN")
    with zipfile.ZipFile(path) as z:
        data=[z.read(i) for i in z.infolist() if i.filename.endswith(".json") and i.file_size<=2_000_000]
    if digest is not None:data=[r for r in data if sha(r)==digest]
    need(len(data)==1,"JSON_MEMBER_PIN")
    return json.loads(data[0]),sha(data[0])
def factory_hash(x):return sha(canonical(x)+b"\n")
def verify(root,out):
    # Re-execute the original cold-recovery consumer, not a narrative or a new producer.
    verify_old(root,root/"old-capsule.json")
    raw=(root/"old-capsule.json").read_bytes();need(sha(raw)==OLD_CAPSULE_SHA,"ORIGINAL_COLD_PARITY")
    old=json.loads(raw)
    m=member(root/"impact.zip",IMPACT_ZIP,"impact.json",IMPACT_SHA)
    repair=member(root/"repair.zip",REPAIR_ZIP,"repair.json",REPAIR_SHA)
    bridge=member(root/"bridge.zip",BRIDGE_ZIP,"tacit-b-kuiper.json",BRIDGE_SHA)
    ci,_=exact_json(root/"c-identity.zip",C_ID_ZIP,C_ID_SHA)
    cg,_=exact_json(root/"c-gate.zip",C_GATE_ZIP,C_GATE_SHA)
    d,ds=exact_json(root/"d.zip",D_ZIP)
    tests=[]
    def test(n,ok):need(ok,n);tests.append(n)
    def reject(n,fn):
        try:fn()
        except (ValueError,KeyError):tests.append(n)
        else:raise AssertionError("EXPECTED_REFUSAL:"+n)
    test("original recovery capsule byte parity",sha(raw)==OLD_CAPSULE_SHA)
    test("independent identity and gate observations",ci["counts"]=={"PASS":13,"FAIL":0,"OPEN":1} and cg["counts"]=={"PASS":26,"FAIL":0,"OPEN":2})
    test("D actual sparse proof",d["count"]==36 and d["cohort"]==8 and d["properties"]==32 and d["conditional_bonds"]==5 and d["receipt_sha256"]==D_RECEIPT and d["selection_only"] is True and d["rights"]=="BLOCKED")
    test("immutable v1 manifest and reviews",m["base_manifest_sha256"]==BOND_SHA and m["family_reviews"]==old["family_reviews"])
    test("dry-run never allocates",repair["permanent_allocations"]==0 and repair["namespace_restored"] and repair["temporary_count_delta"]=={"line":0,"tablet":0,"element":0,"family":0,"tablet_element":0,"occurrence":3,"scan":0,"commit_info":0})
    test("original producer callable census",sum(x["original_parser_callable_count"] for x in repair["files"])==16 and all(x["temporary_ast_match_count"]==1 for x in repair["rows"]))
    oldrows={r["meaning_id"]:r for r in old["source_entries"]};rr={r["meaning_id"]:r for r in repair["rows"]}
    test("same eight meanings",len(m["source_entries"])==len(oldrows)==len(rr)==8)
    for r in m["source_entries"]:
        s=r["source"];a=oldrows[r["meaning_id"]];p=rr[r["meaning_id"]]
        source_guard(s,(root/Path(s["path"]).name).read_bytes())
        test(r["meaning_id"]+" cold address/tuple/module",identity(r)==identity(a)==identity(p) and r["module_classification"]==a["module_classification"]==p["module_classification"])
        test(r["meaning_id"]+" unresolved exact Stars membership",a["stars"]["tablet_id"] is None and p["exact_occurrence_status"]=="MISSING_IN_PINNED_PRODUCER")
    test("properties stable",m["properties"]==old["properties"] and len(m["properties"])==32)
    for prop in m["properties"]:property_guard(prop)
    test("all static edges remain static",old["static_source_graph"]["execution_edges"]==[])
    for e in old["static_source_graph"]["edges"]:relation_guard(e)
    test("original Spider context only",old["spider_channels"]["live_integration"] is False and old["spider_channels"]["execution_edges"]==0 and old["spider_channels"]["projection_verified"])
    test("five original pairs preserved",{(x["from"],x["to"]) for x in m["bond_details"]}=={(x["from"],x["to"]) for x in old["typed_bonds"]} and len(m["bond_details"])==5 and m["incompatible_bonds"]==old["incompatible_bonds"])
    def bond_guard(e):
        need(e["relationship_state"]=="CONDITIONAL_CANDIDATE" and e["direction"]=="source_output_to_target_input","RELATIONSHIP_STATE")
        for end in ("source_endpoint","target_endpoint"):
            z=e[end];need(bool(z.get("sources") or z.get("adapters")),"MISSING_ENDPOINT")
            for x in z.get("sources",[]):need(x["source"]==oldrows[x["meaning_id"]]["source"] and x["kuiper_key"]==oldrows[x["meaning_id"]]["kuiper"]["key"],"ENDPOINT_PIN")
        for f,p in e["family_receipts"].items():need((p["source_sha256"],p["closure_sha256"])==FAMILIES[f],"FAMILY_RECEIPT")
    for e in m["bond_details"]:bond_guard(e)
    reject("unknown relationship",lambda:bond_guard({**m["bond_details"][0],"relationship_state":"EXECUTED"}))
    reject("missing endpoint",lambda:bond_guard({**m["bond_details"][0],"source_endpoint":{}}))
    unknown=next(p for p in m["properties"] if p["state"]=="UNKNOWN")
    reject("malformed unknown property",lambda:property_guard({**unknown,"value":True}))
    s=m["source_entries"][0]["source"];source=(root/Path(s["path"]).name).read_bytes()
    reject("changed source",lambda:source_guard(s,source+b" "))
    reject("stale revision",lambda:source_guard({**s,"commit":"0"*40},source))
    # A CLI impact input is a pinned archive, not a raw mutable manifest or a caller-supplied hash.
    fake=root/"altered-impact.zip";fake.write_bytes((root/"impact.zip").read_bytes()+b" ")
    reject("rehashed/mutated impact artifact cannot authenticate",lambda:member(fake,IMPACT_ZIP,"impact.json",IMPACT_SHA))
    test("original impact examples replay",all(impact(m,x["event"])==x["result"] for x in m["impact_examples"]))
    # Bind exact B request/pattern/receipt hashes, no recomputation or independent-review impersonation.
    patterns=copy.deepcopy(m["patterns"]);bindings={}
    test("B bridge operations match three existing patterns",set(bridge["requests"])==set(bridge["results"])=={x["operation"] for x in patterns})
    for p in patterns:
        op=p["operation"];q=bridge["requests"][op];r=bridge["results"][op]
        test(op+" exact selected key envelope",q["schema"]=="tacit-b.kuiper-request.v1" and q["operation"]==op and q["manifest_sha256"]==BOND_SHA and q["keys"]==p["keys"])
        pattern={"operation":op,"manifest_sha256":BOND_SHA,"keys":p["keys"]}
        test(op+" request/pattern/receipt digest",r["request_sha256"]==factory_hash(q) and r["pattern"]==pattern and r["pattern_sha256"]==factory_hash(pattern) and r["receipt_sha256"]==factory_hash({k:v for k,v in r.items() if k!="receipt_sha256"}))
        test(op+" authority",r["admission"]==(op=="orient") and r["state"]==("EXECUTED_INTERNAL" if op=="orient" else "PRE_ADMISSION_EXECUTED") and r["rights"]=="BLOCKED" and r["independent_verification"]=="PENDING_EXACT_REQUEST_REVIEW")
        if op!="orient":
            f=bridge["refusals"][op]
            test(op+" default refusal",f["state"]=="REFUSED" and f["nodes"]==[] and f["output"] is None and not f["admission"] and f["receipt_sha256"]==factory_hash({k:v for k,v in f.items() if k!="receipt_sha256"}))
        p["receipts"]=sorted(set(p["receipts"]+[BRIDGE_SHA,r["receipt_sha256"],r["request_sha256"],r["pattern_sha256"]]))
        bindings[op]={"keys":p["keys"],"request_sha256":r["request_sha256"],"pattern_sha256":r["pattern_sha256"],"receipt_sha256":r["receipt_sha256"],"state":r["state"],"formal_admission":r["admission"],"independent_exact_request_review":r["independent_verification"],"rights":r["rights"]}
    extended={**m,"patterns":patterns}
    changed=next(x for x in m["impact_examples"] if x["event"]["kind"]=="source")
    affected=impact(extended,changed["event"])
    test("actual bridge receipts now traced on invalidation",all(bindings[op]["receipt_sha256"] in {x["sha256"] for x in affected["affected_receipts"]} for op in affected["affected_patterns"]))
    test("old receipt status historical only",all(x["state"]=="STALE_FOR_NEW_INPUT_HISTORICAL_PRESERVED" for x in affected["affected_receipts"]) and not affected["addresses_changed"])
    test("new bridge evidence does not grant rights",bridge["rights"]=="BLOCKED" and old["rights"]=="BLOCKED" and m["live_consumer"] is False)
    report={"schema":"vedic.tacit-a.recovery-8-10.v1","pins":{"base_manifest":BOND_SHA,"original_capsule":OLD_CAPSULE_SHA,"repair":REPAIR_SHA,"impact":IMPACT_SHA,"b_bridge":BRIDGE_SHA,"c_source_review":C_SHA,"c_identity_review":C_ID_SHA,"c_gate_review":C_GATE_SHA,"d_sparse_proof_json":ds},
      "source_entries":old["source_entries"],"properties":m["properties"],"conditional_bonds":m["bond_details"],"incompatible_bonds":m["incompatible_bonds"],"family_reviews":m["family_reviews"],"static_source_graph":old["static_source_graph"],
      "spider_channels":old["spider_channels"],"periodic_state":old["periodic_state"],"patterns":patterns,"actual_bridge_bindings":bindings,"impact_example":affected,
      "repair_decision":repair["owner_decision"],"historical_repair_review":"C_INDEPENDENT_DRY_RUN_PASS_OWNER_AUTHORITY_OPEN","prior_independent_runtime":[C_RANK_SHA,C_ELEC_SHA],"live_integration":False,"redistribution":"BLOCKED","admission":"UNCHANGED_ORIENT_ONLY",
      "next_action":"Owner may separately approve three exact historical occurrence inserts using original Stars ingestFile; repeat fresh namespace check and independent review before any production write. B formal admissions remain separately gated.",
      "tests":tests}
    out.write_bytes(canonical(report)+b"\n")
    print(json.dumps({"checks":len(tests),"addresses":8,"properties":32,"bonds":5,"bridge_operations":3,"sha256":sha(out.read_bytes())},sort_keys=True))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify"]);p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    else:verify(a.root,a.out)

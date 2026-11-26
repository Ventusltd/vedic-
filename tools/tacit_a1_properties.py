"""A1 bounded evidence selection; existing A identity/impact producer remains authoritative."""
import argparse, copy, json, re
from pathlib import Path
from tacit_a_closure import canonical, sha, need
from tacit_a_index_grain import member, FAMILIES
from tacit_a_bonds import download
from tacit_a_recovery import BOND_SHA, BOND_ZIP, property_guard
from tacit_a_impact import IMPACT_SHA, IMPACT_ZIP, impact, occurrence
from tacit_a_final import exact_json, factory_hash
from tacit_a_final import acquire as acquire_cold, verify as verify_cold

B_FINAL_ZIP="79a5bf16c0e2a8676af99df14a462f4c76d68952c518540a8e2ed638d716612a"
B_FINAL_SHA="3dd66b31abeb7ccf1734da8d2719a16be7d77bd5731a41096f4b9307f4a18e24"
COLD_SHA="816fcc85b9f43a4006470652172a42cc8c219126dee01beb9520b7a749ff4efe"
STATES={"DECLARED","DERIVED","OBSERVED","UNKNOWN"}
SCHEMA="vedic.tacit-a1.property-selection.v1"

def digest(obj): return sha(canonical(obj))
def receipt(obj): return {**obj,"receipt_sha256":digest(obj)}
def decimal(key):
    need(type(key) in (str,int) and re.fullmatch(r"0|[1-9][0-9]{0,19}",str(key)) is not None,"KEY_FORMAT")
    return str(key)
def fields(obj, required, optional=()):
    need(isinstance(obj,dict) and set(required)<=set(obj)<=set(required)|set(optional),"FIELDS")
def acquire(root):
    acquire_cold(root)
    download(root,"b-final",15140134078)

class Space:
    """Construct only from pinned artifacts; no caller-supplied manifest hash."""
    def __init__(self,root):
        self.b=member(root/"bonds.zip",BOND_ZIP,"bonds.json",BOND_SHA)
        self.m=member(root/"impact.zip",IMPACT_ZIP,"impact.json",IMPACT_SHA)
        b,m=self.b,self.m
        need(m["base_manifest_sha256"]==BOND_SHA and m["source_entries"]==b["source_entries"] and m["properties"]==b["properties"],"BASE_JOIN")
        need(len(b["source_entries"])==8 and len(b["properties"])==32 and len(m["bond_details"])==5 and len(b["incompatible_bonds"])==6,"COHORT")
        self.rows={decimal(r["kuiper"]["key"]):r for r in b["source_entries"]}
        need(len(self.rows)==8 and len({occurrence(r["source"]) for r in self.rows.values()})==8,"IDENTITY")
        self.props={}
        for p in b["properties"]:
            property_guard(p)
            k=self.key_for(p["source_occurrence"])
            pair=(k,p["property"])
            need(pair not in self.props,"DUPLICATE_PROPERTY")
            self.props[pair]=p
        self.bonds=[self.bond_receipt(e) for e in m["bond_details"]]
        need({(e["from"],e["to"]) for e in self.bonds}=={(e["from"],e["to"]) for e in b["typed_bonds"]},"BOND_PAIRS")
        self.bridge,_=exact_json(root/"b-final.zip",B_FINAL_ZIP,B_FINAL_SHA)
        self.bound=copy.deepcopy(m)
        for p in self.bound["patterns"]:
            op=p["operation"]; q=self.bridge["requests"][op]; r=self.bridge["results"][op]
            need(q["schema"]=="tacit-b.kuiper-request.v1" and q["operation"]==op and q["manifest_sha256"]==BOND_SHA and q["keys"]==p["keys"],"PEER_SELECTION")
            need(r["request_sha256"]==factory_hash(q) and r["pattern_sha256"]==factory_hash(r["pattern"]) and r["receipt_sha256"]==factory_hash({k:v for k,v in r.items() if k!="receipt_sha256"}),"PEER_RECEIPT")
            need(r["pattern"]=={"operation":op,"manifest_sha256":BOND_SHA,"keys":p["keys"]},"PEER_PATTERN")
            need(r["admission"]==(op=="orient") and r["rights"]=="BLOCKED","PEER_AUTHORITY")
            p["receipts"]=sorted(set(p["receipts"]+[B_FINAL_SHA,r["receipt_sha256"],r["request_sha256"],r["pattern_sha256"]]))
    def key_for(self,s):
        keys=[k for k,r in self.rows.items() if r["source"]==s]
        need(len(keys)==1,"UNKNOWN_OR_STALE_OCCURRENCE")
        return keys[0]
    def exact_join(self,k,s):
        need(type(k) is str and decimal(k) in self.rows and self.rows[k]["source"]==s,"KEY_OCCURRENCE_JOIN")
        return self.rows[k]
    def bond_receipt(self,e):
        # Only an exact inherited typed bond may be receipted, never a caller's modified edge.
        need(e in self.m["bond_details"],"UNAUTHENTICATED_BOND")
        need(e["direction"]=="source_output_to_target_input" and e["relationship_state"]=="CONDITIONAL_CANDIDATE" and e["formal_admission"]=="UNCHANGED","BOND_AUTHORITY")
        for end in ("source_endpoint","target_endpoint"):
            z=e[end];need(bool(z.get("sources") or z.get("adapters")),"MISSING_ENDPOINT")
            for x in z.get("sources",[]):
                r=self.exact_join(decimal(x["kuiper_key"]),x["source"])
                need(r["meaning_id"]==x["meaning_id"],"MEANING_JOIN")
        for f,p in e["family_receipts"].items():
            need(f in FAMILIES and (p["source_sha256"],p["closure_sha256"])==FAMILIES[f],"FAMILY_PIN")
        for port in ("source_port","target_port"):
            need(bool(e[port]["quantity"]) and bool(e[port]["unit"]),"TYPED_PORT")
        need(bool(e["required_data"]),"CONDITIONS")
        return receipt({"schema":"vedic.tacit-a1.conditional-bond.v1","base_manifest_sha256":BOND_SHA,"impact_sha256":IMPACT_SHA,**e})
    def property_receipt(self,k,name):
        need(type(k) is str and k in self.rows and (k,name) in self.props,"UNKNOWN_PROPERTY")
        p=self.props[k,name];property_guard(p)
        self.exact_join(k,p["source_occurrence"])
        return receipt({"schema":"vedic.tacit-a1.property.v1","base_manifest_sha256":BOND_SHA,"key":k,"evidence":p})
    def validate_pred(self,p):
        fields(p,("field",),("value","name","state"))
        f=p["field"]
        if f=="property":
            fields(p,("field","name","state"),("value",))
            need(type(p["name"]) is str and p["name"] in {n for k,n in self.props} and p["state"] in STATES,"PROPERTY_PREDICATE")
            need(not (p["state"]=="UNKNOWN" and "value" in p),"UNKNOWN_VALUE")
        else:
            fields(p,("field","value"))
            need(f in ("module","meaning","key","depends_on") and type(p["value"]) is str,"PREDICATE")
            valid={"module":{r["module_classification"]["symbol"] for r in self.rows.values()},"meaning":{r["meaning_id"] for r in self.rows.values()},"key":set(self.rows),"depends_on":set(self.rows)}[f]
            need(p["value"] in valid,"UNKNOWN_PREDICATE_VALUE")
    def matches(self,k,p):
        r=self.rows[k];f=p["field"]
        if f=="module":return r["module_classification"]["symbol"]==p["value"]
        if f=="meaning":return r["meaning_id"]==p["value"]
        if f=="key":return k==p["value"]
        if f=="depends_on":
            # Strict module reverse dependency; not a runtime call or self membership.
            path=self.rows[p["value"]]["source"]["path"]; found=set();todo=[path]
            while todo:
                t=todo.pop()
                for e in self.m["module_dependencies"]:
                    if e["target"]==t and e["source"] not in found:
                        found.add(e["source"]);todo.append(e["source"])
            return r["source"]["path"] in found
        q=self.props.get((k,p["name"]))
        if q is None:return None
        if q["state"]=="UNKNOWN" and p["state"]!="UNKNOWN":return None
        if q["state"]!=p["state"]:return False
        return "value" not in p or canonical(q["value"])==canonical(p["value"])
    def select(self,expr):
        fields(expr,("all","none"))
        need(all(type(expr[k]) is list and len(expr[k])<=8 for k in ("all","none")) and len(expr["all"])+len(expr["none"])>0,"BOUNDED_QUERY")
        need(len(canonical(expr))<=16384,"QUERY_SIZE")
        for p in expr["all"]+expr["none"]:self.validate_pred(p)
        selected=[];unknown=[]
        for k in sorted(self.rows,key=int):
            checks=[self.matches(k,p) for p in expr["all"]]
            checks += [None if (v:=self.matches(k,p)) is None else not v for p in expr["none"]]
            if False in checks:continue
            if None in checks:unknown.append(k)
            else:selected.append(k)
        return receipt({"schema":SCHEMA,"base_manifest_sha256":BOND_SHA,"impact_sha256":IMPACT_SHA,"expression":expr,"keys":selected,"unknown_keys":unknown,
                        "occurrences":[{"key":k,"meaning_id":self.rows[k]["meaning_id"],"source":self.rows[k]["source"]} for k in selected],"authority":"SELECTION_ONLY"})
    def verify_selection(self,r):
        need(r==self.select(r["expression"]),"SELECTION_RECEIPT")
        return True
    def reverse_impact(self,event):
        return receipt({"schema":"vedic.tacit-a1.reverse-impact.v1","base_manifest_sha256":BOND_SHA,"peer_bridge_sha256":B_FINAL_SHA,"event":event,**impact(self.bound,event)})

def verify(root,out):
    s=Space(root); tests=[]
    def check(name,ok):need(ok,name);tests.append(name)
    def reject(name,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):tests.append(name)
        else:raise AssertionError("EXPECTED_REFUSAL:"+name)
    def expr(*all_,none=()):return {"all":list(all_),"none":list(none)}
    def mod(v):return {"field":"module","value":v}
    def prop(n,state,**kw):return {"field":"property","name":n,"state":state,**kw}
    def key(k):return {"field":"key","value":k}
    vg=s.select(expr(mod("Vg")));vn=s.select(expr(mod("Vn")));vd=s.select(expr(mod("Vd")))
    check("2/2/4 exact module keys",[len(x["keys"]) for x in (vg,vn,vd)]==[2,2,4])
    check("ORIENT exact peer keys",vg["keys"]==s.bridge["requests"]["orient"]["keys"])
    check("nearest exact peer keys",sorted(vg["keys"]+vn["keys"],key=int)==s.bridge["requests"]["nearest-orient"]["keys"])
    check("electrical exact peer keys",vd["keys"]==s.bridge["requests"]["electrical"]["keys"])
    for k,r in s.rows.items():
        q=s.select(expr({"field":"meaning","value":r["meaning_id"]}))
        check("meaning/key parity "+k,q["keys"]==[k] and s.verify_selection(q))
        for name in ("producer_needs","producer_standalone","runtime_effects","typed_ports"):
            p=s.property_receipt(k,name)
            check("property receipt "+k+" "+name,p["receipt_sha256"]==digest({x:y for x,y in p.items() if x!="receipt_sha256"}))
    u=s.select(expr(prop("runtime_effects","UNKNOWN")))
    check("explicit unknown eight",len(u["keys"])==8 and not u["unknown_keys"])
    x=s.select(expr(prop("runtime_effects","OBSERVED")))
    check("unknown not false",not x["keys"] and len(x["unknown_keys"])==8)
    x=s.select(expr(mod("Vg"),none=(prop("runtime_effects","OBSERVED"),)))
    check("exclusion cannot promote unknown",not x["keys"] and x["unknown_keys"]==vg["keys"])
    check("intersection",s.select(expr(mod("Vg"),prop("runtime_effects","UNKNOWN")))["keys"]==vg["keys"])
    check("exclusion",s.select(expr(mod("Vg"),none=(key(vg["keys"][0]),)))["keys"]==vg["keys"][1:])
    check("dependency reverse",s.select(expr({"field":"depends_on","value":vg["keys"][0]}))["keys"]==vn["keys"])
    check("declared state accepted but not invented",not s.select(expr(prop("typed_ports","DECLARED")))["keys"])
    reject("unknown with value",lambda:s.select(expr(prop("runtime_effects","UNKNOWN",value=False))))
    reject("invented state",lambda:s.select(expr(prop("runtime_effects","VERIFIED"))))
    reject("forged key",lambda:s.select(expr(key("99999999999999999999"))))
    reject("wrong occurrence",lambda:s.exact_join(vg["keys"][0],s.rows[vd["keys"][0]]["source"]))
    reject("forged selection",lambda:s.verify_selection({**vg,"keys":vd["keys"]}))
    reject("unbounded clauses",lambda:s.select(expr(*[mod("Vg")]*9)))
    e=s.m["bond_details"][0]
    for field,value in (("source_endpoint",{}),("relationship_state","EXECUTED"),("direction","reverse"),("source_port",{"quantity":"forged","unit":"W"})):
        reject("forged bond "+field,lambda field=field,value=value:s.bond_receipt({**e,field:value}))
    check("five conditional bonds preserved",len(s.bonds)==5 and all(b["relationship_state"]=="CONDITIONAL_CANDIDATE" for b in s.bonds))
    effects=[]
    for cohort,ops in ((vg,["nearest-orient","orient"]),(vn,["nearest-orient"]),(vd,["electrical"])):
        for k in cohort["keys"]:
            source=s.rows[k]["source"]
            event={"kind":"source","source":source,"new_blob":"0"*40}
            result=s.reverse_impact(event)
            check("reverse impact "+k,result["affected_patterns"]==ops and not result["addresses_changed"])
            check("exact B receipt impact "+k,all(s.bridge["results"][op]["receipt_sha256"] in {r["sha256"] for r in result["affected_receipts"]} for op in ops))
            check("historical receipts preserved "+k,all(r["state"]=="STALE_FOR_NEW_INPUT_HISTORICAL_PRESERVED" for r in result["affected_receipts"]))
            for field in ("display_colour","classification_description"):
                check("presentation stable "+k+" "+field,not s.reverse_impact({"kind":"presentation","source":source,"field":field})["affected_patterns"])
            effects.append(result)
    check("final B member unchanged",exact_json(root/"b-final.zip",B_FINAL_ZIP,B_FINAL_SHA)[1]==B_FINAL_SHA)
    cold=root/"cold-replay.json";verify_cold(root,cold)
    check("cold recovery exact original bytes",sha(cold.read_bytes())==COLD_SHA)
    c=json.loads(cold.read_bytes())
    check("actual inherited Spider projection",c["spider_channels"]["projection_verified"] and c["spider_channels"]["execution_edges"]==0 and not c["spider_channels"]["live_integration"])
    check("exact source and Stars joins",all(s.exact_join(decimal(r["kuiper"]["key"]),r["source"]) and r["stars"]["tablet_id"] is None for r in c["source_entries"]))
    result={"schema":"vedic.tacit-a1.property-impact-manifest.v1","base_manifest_sha256":BOND_SHA,"impact_sha256":IMPACT_SHA,"cold_sha256":COLD_SHA,"peer_bridge_sha256":B_FINAL_SHA,
            "source_entries":c["source_entries"],"properties":s.b["properties"],"property_receipts":[s.property_receipt(k,n) for k,n in sorted(s.props,key=lambda x:(int(x[0]),x[1]))],
            "bond_receipts":s.bonds,"incompatible_bonds":s.b["incompatible_bonds"],"selection_examples":[vg,vn,vd,u],"reverse_impacts":effects,"spider_channels":c["spider_channels"],
            "tests":tests,"counts":{"PASS":len(tests),"FAIL":0,"OPEN":3},"open":["fresh B1 peer receipts","production Stars occurrence repair owner authority","independent C1 review"],"authority":"EVIDENCE_ONLY","redistribution":"BLOCKED"}
    out.write_bytes(canonical(result)+b"\n")
    print(json.dumps({"counts":result["counts"],"keys":8,"properties":32,"bonds":5,"sha256":sha(out.read_bytes())},sort_keys=True))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify","select","impact"]);p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path);p.add_argument("--input",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    elif a.mode=="verify":verify(a.root,a.out)
    else:
        space=Space(a.root);q=json.loads(a.input.read_bytes())
        print(canonical(space.select(q) if a.mode=="select" else space.reverse_impact(q)).decode())

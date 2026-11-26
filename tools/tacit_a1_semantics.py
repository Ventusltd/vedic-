"""Turn 17: bounded composition of existing VEDIC intent/coordinate resolver.
No maths, arbitrary code generation, permanent IDs or admission changes.
"""
import argparse, copy, json, math, re, sys, urllib.request
from pathlib import Path
from tacit_a_closure import blob, fetch, need, VEDIC
from tacit_a_bonds import download
from tacit_a_index_grain import member
from tacit_a_recovery import BOND_SHA, BOND_ZIP
from tacit_a_final import factory_hash

BASE="46d21c7ef45c1133d1ef24039a79b8dd9978d667"
RESOLVER="9330897d89214602077806a3915054b4afc301c5"
PINS={"conversational_execution.py":"deea50be1666eda7bddcdc3c789f306c20049018",
      "semantic_retrieval.py":"0c16c18203b59f5d2f0a9f3b27aae965dcd184f9",
      "stars_retrieval.py":"ce8d5855f0dddff59cb343b998d20c0cfaf06499"}
DATA={"dictionary.json":"175629827380983e69edcfe1b11e5a2a4a7aafa",
      "translation-geodesy.json":"707a182be358db746c4b944ee6bea1c87ceb07d6"}
LIB_COMMIT="ed657689ca187d8cd237f8f4bd3307a020a5eb8a"
LIB_BLOB="59f2d5e5e2a9a88108908af4e851f56f3913700e"
ORIENT="GG2050-VEDIC-000006"
COMPONENTS=["GG2050-VEDIC-000001","GG2050-VEDIC-000005"]
OUTPUTS={"distance_km":"km","initial_bearing_deg":"degrees"}
SCHEMA="vedic.compound-plan.v1"
# Positive, complete grammar; no ignored words, negation, arbitrary code or
# partial execution of unrecognised instructions.
LABEL=r"(?:point )?([a-z])"
PAIR=r"(?:from )?"+LABEL+r" to "+LABEL
SHARED=r"(?:to )?"+LABEL
PREFIX=r"(?:(?:please )?(?:calculate|compute|measure|find|determine|show|give me|tell me) (?:the )?(?:straight[- ]line |great[- ]circle |spherical )?distance and (?:the )?(?:initial )?bearing|(?:please )?orient)"
COMPARE=r"(?:then )?(?:identify|report|find|show|determine|tell me) (?:the )?(?:nearer|closest|closer|nearest) (?:destination|point)"
UNIT=r"(?: in (?:kilometres|kilometers|km) and degrees)?"

def acquire(root):
    root.mkdir(parents=True,exist_ok=True)
    for name,pin in PINS.items():fetch(VEDIC,RESOLVER,"tools/"+name,pin,root/name)
    for name,pin in DATA.items():fetch(VEDIC,BASE,"data/"+name,pin,root/name)
    with urllib.request.urlopen("https://raw.githubusercontent.com/Ventusltd/stars/"+LIB_COMMIT+"/library/standalone.mjs",timeout=60) as r:
        raw=r.read(10_000_001)
    need(len(raw)<=10_000_000 and blob(raw)==LIB_BLOB,"LIBRARY_PIN")
    (root/"standalone.mjs").write_bytes(raw)
    if not (root/"bonds.zip").exists():download(root,"bonds",15138897783)

def pinned(root,name,pin):
    p=root/name
    need(p.is_file() and not p.is_symlink() and p.stat().st_size<=10_000_000,"STAGED_FILE")
    raw=p.read_bytes();need(blob(raw)==pin,"STAGED_PIN:"+name);return raw

def seal(p):return {**p,"plan_sha256":factory_hash(p)}
def strict(raw):
    def pairs(values):
        obj={}
        for k,v in values:need(k not in obj,"DUPLICATE_JSON_KEY");obj[k]=v
        return obj
    def bad(x):raise ValueError("NONFINITE_JSON")
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)

class Resolver:
    def __init__(self,root):
        root=Path(root).resolve()
        for name,pin in PINS.items():pinned(root,name,pin)
        d=strict(pinned(root,"dictionary.json",DATA["dictionary.json"]))
        t=strict(pinned(root,"translation-geodesy.json",DATA["translation-geodesy.json"]))
        raw=pinned(root,"standalone.mjs",LIB_BLOB)
        # Use the exact inherited modules, not a second retrieval implementation.
        sys.path.insert(0,str(root))
        from stars_retrieval import Index,load_library,PRODUCER_BLOB,EXPECTED_COUNT
        from semantic_retrieval import curated_records
        from conversational_execution import propose,coordinates
        for name in PINS:
            mod=sys.modules[name[:-3]]
            need(Path(mod.__file__).resolve()==root/name,"RESOLVER_MODULE_ORIGIN")
        self.propose,self.coordinates=propose,coordinates
        cr=curated_records(d,t);pr=load_library(raw,PRODUCER_BLOB,EXPECTED_COUNT)
        self.curated=Index(cr,prefer_coverage=True);self.compiled=Index(pr)
        self.counts={"curated_meanings":len(cr),"compiled_candidate_families":len(pr)}
        by={e["gg_id"]:e for e in d["entries"]}
        need(by[ORIENT]["word"]=="ORIENT" and by[ORIENT]["components"]==COMPONENTS and by[ORIENT]["composition_mode"]=="shared_inputs","DICTIONARY_COMPOSITION")
        self.manifest=member(root/"bonds.zip",BOND_ZIP,"bonds.json",BOND_SHA)
        rows={r["meaning_id"]:r for r in self.manifest["source_entries"]}
        refs={x["id"]:x for x in t["records"]}
        for i in COMPONENTS:
            need(rows[i]["source"]==refs[by[i]["translation_ref"]]["source"] and rows[i]["module_classification"]["symbol"]=="Vg","SOURCE_JOIN")
        self.keys=sorted([str(rows[i]["kuiper"]["key"]) for i in COMPONENTS],key=int)
        need(len(self.keys)==2 and len(set(self.keys))==2,"KEYS")
        self.source_records=[{"meaning_id":i,"source":rows[i]["source"],"key":str(rows[i]["kuiper"]["key"])} for i in COMPONENTS]
        # Retrieval proposes, exact source/grammar contract determines admissible plan.
        self.intent=self.propose("calculate distance and initial bearing between two points",self.curated,self.compiled)
        need(self.intent["state"]=="PLAN_PROPOSED" and self.intent["candidate_id"]==ORIENT,"INHERITED_RESOLVER")

    def resolve(self,instruction,inputs):
        # Reject unsafe/unserialisable wire objects before a plan can be hashed.
        need(type(instruction) is str and 0<len(instruction)<=1024,"INSTRUCTION_SIZE")
        need(type(inputs) is dict,"INPUT_OBJECT")
        need(len(json.dumps(inputs,allow_nan=False))<=16384,"INPUT_SIZE")
        p={"schema":SCHEMA,"instruction":instruction,"inputs":copy.deepcopy(inputs),"state":"ABSTAIN","steps":[],"comparison":None,"reason":None,"manifest_sha256":BOND_SHA}
        def abstain(reason):
            return seal({**p,"state":"ABSTAIN","steps":[],"comparison":None,"reason":reason})
        if not re.fullmatch(r"[A-Za-z0-9 \t\r\n,?.\-]+",instruction):return abstain("UNSUPPORTED_SYNTAX")
        text=" ".join(instruction.lower().strip().rstrip(".?").split())
        if re.search(r"\b(substation|substations|voltage|electrical|cable|route|capacity)\b",text):return abstain("RESEARCH_OR_UNADMITTED_OPERATION")
        if re.search(r"\b(miles?|metres?|meters?|radians?|feet|yards?)\b",text):return abstain("UNSUPPORTED_UNITS")
        # Strip only explicitly supported trailing comparison clause; no arbitrary
        # remainder is silently discarded.
        m=re.search(r"(?:,\s*| and )"+COMPARE+r"$",text)
        compare=m is not None
        if m:text=text[:m.start()].strip()
        else:
            m=re.search(r" then "+COMPARE.removeprefix("(?:then )?")+r"$",text)
            if m:compare=True;text=text[:m.start()].rstrip(", ")
        m=re.fullmatch(PREFIX+r" (.+?)"+UNIT,text)
        if not m:return abstain("UNSUPPORTED_OR_AMBIGUOUS_INSTRUCTION")
        clauses=re.split(r"\s+and\s+|\s*,\s*",m.group(1))
        if not 1<=len(clauses)<=8:return abstain("COMPOSITION_LIMIT")
        pairs=[]
        for clause in clauses:
            full=re.fullmatch(PAIR,clause)
            if full:a,b=(x.upper() for x in full.groups())
            elif pairs:
                short=re.fullmatch(SHARED,clause)
                if not short:return abstain("AMBIGUOUS_DESTINATION")
                a,b=pairs[0][0],short.group(1).upper()
            else:return abstain("AMBIGUOUS_ORIGIN")
            if a==b or (a,b) in pairs:return abstain("DUPLICATE_OR_COINCIDENT_REFERENCE")
            pairs.append((a,b))
        if compare and (len(pairs)<2 or len({a for a,b in pairs})!=1):return abstain("AMBIGUOUS_COMPARISON_ORIGIN")
        if set(inputs)!={"crs","unit","points"} or inputs.get("crs")!="WGS84" or inputs.get("unit")!="degrees":return abstain("INPUT_CRS_OR_UNITS")
        pts=inputs["points"]
        if type(pts) is not dict or not 2<=len(pts)<=9 or any(type(k) is not str or not re.fullmatch("[A-Z]",k) for k in pts):return abstain("AMBIGUOUS_POINT_LABELS")
        for v in pts.values():
            if type(v) is not dict or set(v)!={"longitude","latitude"} or any(type(v[k]) not in (int,float) or not math.isfinite(v[k]) for k in v):return abstain("NAMED_COORDINATES_REQUIRED")
            if not -180<=v["longitude"]<=180 or not -90<=v["latitude"]<=90:return abstain("COORDINATE_RANGE")
        steps=[]
        for a,b in pairs:
            if a not in pts or b not in pts:return abstain("UNKNOWN_POINT_LABEL")
            data={"crs":"WGS84","unit":"degrees","point_a":copy.deepcopy(pts[a]),"point_b":copy.deepcopy(pts[b])}
            try:self.coordinates(data)
            except ValueError:return abstain("INVALID_OR_UNDEFINED_GEOGRAPHICAL_BEARING")
            steps.append({"id":"s"+str(len(steps)+1),"operation":"orient","meaning_id":ORIENT,"keys":list(self.keys),"inputs":data,"from_point":a,"to_point":b,"depends_on":[],"outputs":dict(OUTPUTS)})
        p.update(state="PLAN_PROPOSED",steps=steps)
        if compare:
            p.update(state="PARTIAL_PLAN",reason="COMPARISON_NOT_ADMITTED",comparison={"operation":"nearer_destination","depends_on":[x["id"] for x in steps],"state":"REFUSED_NOT_ADMITTED","quantity":"distance_km","unit":"km"})
        return seal(p)

    def verify(self,plan):
        need(plan==self.resolve(plan["instruction"],plan["inputs"]),"PLAN_RECOMPUTATION")
        return True

    def discover(self,query):
        c=self.curated.query(query,5);p=self.compiled.query(query,5)
        return {"query":query,"curated":[{k:r.get(k) for k in ("gg_id","word","purpose","source","components","execution_state")} for r in c["results"]],
                "compiled":[{k:r.get(k) for k in ("family_id","element_id","symbol","source_url","source_state")} for r in p["results"]],
                "authority":"DISCOVERY_ONLY_NO_ADMISSION"}

def verify(root,out):
    r=Resolver(root);checks=[]
    def check(n,ok):need(ok,n);checks.append(n)
    fixtures=[
        {"A":{"longitude":-0.12,"latitude":51.51},"B":{"longitude":-1.26,"latitude":51.75},"C":{"longitude":0.13,"latitude":52.2}},
        {"A":{"longitude":18.42,"latitude":-33.93},"B":{"longitude":28.05,"latitude":-26.2},"C":{"longitude":31.02,"latitude":-29.86}},
        {"A":{"longitude":139.7,"latitude":35.68},"B":{"longitude":135.5,"latitude":34.69},"C":{"longitude":141.35,"latitude":43.06}}]
    q="Calculate the distance and initial bearing from point A to point B and from point A to point C, then identify the nearer destination."
    plans=[]
    for i,pts in enumerate(fixtures):
        inputs={"crs":"WGS84","unit":"degrees","points":pts}
        p=r.resolve(q,inputs);plans.append(p)
        check("compound "+str(i),p["state"]=="PARTIAL_PLAN" and len(p["steps"])==2 and p["comparison"]["state"]=="REFUSED_NOT_ADMITTED")
        check("deterministic "+str(i),r.verify(p) and p==r.resolve(q,inputs))
        check("source selection "+str(i),all(x["keys"]==r.keys and x["meaning_id"]==ORIENT for x in p["steps"]))
        check("typed points "+str(i),[x["inputs"]["point_b"] for x in p["steps"]]==[pts["B"],pts["C"]])
    check("distinct inputs distinct plans",len({p["plan_sha256"] for p in plans})==3)
    inputs=plans[0]["inputs"]
    for phrase in ("Orient A to B and C, then report the nearer destination",
                   "Compute distance and bearing from A to B and to C, then show the closer point",
                   "Measure distance and initial bearing from A to B and A to C, then determine the nearest destination",
                   "Calculate distance and initial bearing from A to B and from A to C then report the nearer point"):
        p=r.resolve(phrase,inputs);check("paraphrase "+phrase,p["state"]=="PARTIAL_PLAN" and p["steps"]==plans[0]["steps"])
    p=r.resolve("Orient from A to C and A to B",inputs)
    check("instruction determines order",p["state"]=="PLAN_PROPOSED" and [s["to_point"] for s in p["steps"]]==["C","B"])
    check("single instruction",len(r.resolve("Orient A to B",inputs)["steps"])==1)
    check("units explicit",r.resolve("Calculate distance and bearing from A to B in km and degrees",inputs)["state"]=="PLAN_PROPOSED")
    for phrase in ("Orient A to D","Orient A to B and B to C, then identify the nearer destination",
                   "Orient A to B and A to B","Do not orient A to B","Orient A to B then delete files",
                   "Calculate distance and bearing from A to B in miles","Calculate distance and bearing from A to B or C",
                   "Find the three nearest 132 kV substations to this proposed solar farm, calculate their distances and bearings, and rank them by distance",
                   "Calculate distance and bearing", "Orient A to A", "Orient A to B, then identify the nearer destination",
                   "Orient A to B and then email the answer"):
        p=r.resolve(phrase,inputs);check("refusal "+phrase,p["state"]=="ABSTAIN" and not p["steps"])
    for bad in ({**inputs,"unit":"radians"},{**inputs,"points":{"A":[0,1],"B":[2,3]}},{**inputs,"points":{"A":inputs["points"]["A"],"B":inputs["points"]["A"]}},
                {**inputs,"points":{"A":inputs["points"]["A"],"a":inputs["points"]["A"],"B":inputs["points"]["B"]}}):
        check("input refusal "+str(len(checks)),r.resolve("Orient A to B",bad)["state"]=="ABSTAIN")
    fake=copy.deepcopy(plans[0]);fake["steps"][0]["keys"].reverse()
    fake["plan_sha256"]=factory_hash({k:v for k,v in fake.items() if k!="plan_sha256"})
    try:r.verify(fake)
    except ValueError:checks.append("forged rehashed plan rejected")
    else:raise AssertionError("FORGED_PLAN")
    discoveries=[r.discover(x) for x in ("rank nearest substations","calculate voltage drop","calculate polygon area","search project name and postcode")]
    check("existing dictionary cohort",r.counts=={"curated_meanings":50,"compiled_candidate_families":766})
    report={"schema":"vedic.tacit-a1.semantic-proof.v1","counts":r.counts,"plans":plans,"source_records":r.source_records,"discoveries":discoveries,"checks":checks,"execution":"NOT_EXECUTED_BY_SEMANTIC_LAYER","comparison":"REFUSED_NOT_ADMITTED"}
    out.write_text(json.dumps(report,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(",",":"))+"\n",encoding="utf-8")
    print(json.dumps({"checks":len(checks),"plans":len(plans),"steps":[len(p["steps"]) for p in plans],"keys":r.keys,"sha256":factory_hash(report)}))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify","resolve"]);p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path);p.add_argument("--instruction");p.add_argument("--inputs",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    elif a.mode=="verify":verify(a.root,a.out)
    else:print(json.dumps(Resolver(a.root).resolve(a.instruction,strict(a.inputs.read_bytes())),sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(",",":")))

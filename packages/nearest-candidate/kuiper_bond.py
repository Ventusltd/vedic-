"""Sparse consumer of TACIT10's pinned identity evidence; not a key generator."""
import argparse, hashlib, json, math, pathlib, subprocess, sys, urllib.request, zipfile
from collections import defaultdict
HERE=pathlib.Path(__file__).resolve().parent
EDITION="0ee52af60036f32358759a67836578dce6d7da51"
BRIDGE="70d08339226f052f0da64fcb1b7d59f53286b58c"
ARTIFACT=15126683549
ZIP_SHA="c4b7a4d582b56af8380ae33ab0c64782ec33b1e05c99d88af83a3b494eb4ead5"
RECEIPT_SHA="83147e90c0f0831ee1f82ce5e721a3521dc843421a96ae9cba3425343d0b3c19"
PRODUCER="eec3f1891294af9e93ce6613c10cdf71806802f2"
SOURCE_COMMIT="487ec7bd38dfa5aecb1c75da53b4a866ab2101cb"
MODULES={"engine/v9-nearest-search.js":"d2ab3b111eb09f7af3df3a9fce9ad0a9dc1dea99","engine/v9-geodesy.js":"14023f06d4ef2ea806437863bd35dee954c46b11"}
KNOWN={1:86415575118,5:86415575222}
COHORT={1,5,15,16}
STATE="PINNED_PRODUCER_RECEIPT_MATCH_NOT_WAFER_REPLAY"
def require(ok, reason):
    if not ok: raise ValueError(reason)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def blob(raw): return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def mid(n): return f"GG2050-VEDIC-{n:06d}"
def fetch(repo,commit,path,expected):
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{commit}/{path}",timeout=25) as r:
        b=r.read(2_000_001)
    require(len(b)<=2_000_000 and blob(b)==expected,"GIT_BLOB_MISMATCH")
    return b
def acquire(root):
    root.mkdir(exist_ok=False)
    with (root/"identity.zip").open("xb") as f:
        subprocess.run(["gh","api",f"repos/Ventusltd/vedic-/actions/artifacts/{ARTIFACT}/zip"],stdout=f,check=True,timeout=60)
    require(sha((root/"identity.zip").read_bytes())==ZIP_SHA,"ARTIFACT_DIGEST")
    (root/"identity_bridge.py").write_bytes(fetch("Ventusltd/vedic-",BRIDGE,"tools/identity_bridge.py","f3e6519aab67d2bc9fbc818318abca478ca2ef7e"))
    for path,pin in MODULES.items():
        (root/pathlib.Path(path).name).write_bytes(fetch("Ventusltd/ventus-grid-engine",SOURCE_COMMIT,path,pin))
def occurrence(s):
    return tuple(s[k] for k in ("repo","commit","path","blob","first","last"))
def indexes(rows):
    meaning={}; reverse=defaultdict(list); source=defaultdict(list)
    for r in rows:
        require(r["gg_id"] not in meaning,"DUPLICATE_MEANING")
        meaning[r["gg_id"]]=r
        source[occurrence(r["source"])].append(r["gg_id"])
        k=r["kuiper"]["key"]
        if k is not None: reverse[k].append(r["gg_id"])
    return meaning,reverse,source
def lookup_key(reverse,key):
    require(type(key) is int and key in reverse,"UNKNOWN_KEY")
    return sorted(reverse[key])
def lookup_source(source,s):
    ids=source.get(occurrence(s))
    require(bool(ids),"UNKNOWN_OCCURRENCE")
    return sorted(ids)
def point(p):
    require(isinstance(p,dict) and set(p)=={"longitude","latitude"},"NAMED_COORDINATES")
    for k,maxval in (("longitude",180),("latitude",90)):
        require(type(p[k]) in (int,float) and math.isfinite(p[k]) and abs(p[k])<=maxval,"COORDINATE_RANGE")
    return dict(p)
def selected_location(request,result,input_sha256):
    require(sha(canonical(request))==input_sha256,"INPUT_DIGEST_MISMATCH")
    require(request.get("crs")=="EPSG:4326","INCOMPATIBLE_CRS")
    records=request.get("records")
    require(isinstance(records,list),"DATASET_REQUIRED")
    by_id={}
    for r in records:
        i=r.get("id")
        require(isinstance(i,str) and i.strip() and i not in by_id,"MISSING_OR_DUPLICATE_ID")
        by_id[i]=point(r.get("location"))
    require(result is not None,"NO_ELIGIBLE_RECORD")
    require(isinstance(result,dict) and set(result)=={"id","distance_km"},"RESULT_TYPE")
    i=result["id"]; km=result["distance_km"]
    require(isinstance(i,str) and i in by_id,"SELECTED_ID_NOT_IN_DATASET")
    require(type(km) in (int,float) and math.isfinite(km) and km>=0,"DISTANCE_UNIT_OR_VALUE")
    # Same named lon/lat degrees, explicit label mapping; no projection or new formula.
    return {"crs":"WGS84","unit":"degrees","point_a":point(request["query"]),"point_b":by_id[i]}
def reject(fn,reason):
    try: fn()
    except ValueError as e: require(str(e)==reason,"WRONG_REFUSAL:"+str(e))
    else: raise AssertionError("EXPECTED_REFUSAL:"+reason)
def verify(root,out):
    import copy
    sys.path.insert(0,str(root.resolve()))
    from identity_bridge import kuiper_join
    zpath=root/"identity.zip"
    require(sha(zpath.read_bytes())==ZIP_SHA,"ARTIFACT_DIGEST")
    with zipfile.ZipFile(zpath) as z:
        def member(name):
            info=z.getinfo(name); require(info.file_size<=10_000_000,"MEMBER_SIZE")
            return z.read(info)
        report=json.loads(member("identity-bridge.json"))
        raw=member("kuiper-producer.json"); producer=json.loads(raw)
        receipt_bytes=member("source-receipt/receipt.json"); receipt=json.loads(receipt_bytes)
        require(sha(receipt_bytes)==RECEIPT_SHA,"ORIENT_RECEIPT_DIGEST")
    require(receipt["dictionary_commit"]==EDITION and receipt["identity_complete"] is False,"ORIENT_EDITION")
    require(receipt["kuiper_producer_commit"]==PRODUCER==report["kuiper_producer_commit"],"PRODUCER_PIN")
    require(sha(raw)==receipt["kuiper_receipt_sha256"]==report["kuiper_receipt_sha256"],"KUIPER_RECEIPT_DIGEST")
    base=HERE.parents[1]
    dictionary_raw=(base/"data/dictionary.json").read_bytes()
    require(sha(dictionary_raw)==receipt["dictionary_sha256"],"DICTIONARY_DIGEST")
    dictionary=json.loads(dictionary_raw)
    translations=json.loads((base/"data/translation-geodesy.json").read_text())
    tr={r["id"]:r["source"] for r in translations["records"]}
    meanings={e["gg_id"]:e for e in dictionary["entries"]}
    report_rows={e["gg_id"]:e for e in report["entries"]}
    require(len(report_rows)==len(report["entries"]),"DUPLICATE_REPORT_MEANING")
    rows=[]
    for n in sorted(COHORT):
        m=mid(n); e=meanings[m]; r=report_rows[m]; s=r["source"]
        require(s==(e.get("source") or tr[e["translation_ref"]]),"DICTIONARY_SOURCE_MISMATCH")
        require(s["commit"]==SOURCE_COMMIT and MODULES[s["path"]]==s["blob"],"SOURCE_PIN")
        b=(root/pathlib.Path(s["path"]).name).read_bytes()
        require(blob(b)==s["blob"],"SOURCE_BLOB")
        lines=b.splitlines(keepends=True)
        require(1<=s["first"]<=s["last"]<=len(lines),"SPAN_BOUNDS")
        joined=kuiper_join(s,producer)
        require(joined==r["kuiper"],"PRODUCER_JOIN_MISMATCH")
        if n in KNOWN:
            require(joined["state"]==STATE and joined["key"]==KNOWN[n],"KNOWN_KEY_MISMATCH")
            component=next(c for c in receipt["components"] if c["gg_id"]==m)
            require(component["source"]==s and component["kuiper"]==joined,"ORIENT_COMPONENT_MISMATCH")
        rows.append({"gg_id":m,"word":e["word"],"source":s,"source_sha256":sha(b),
                     "span_sha256":sha(b"".join(lines[s["first"]-1:s["last"]])),
                     "kuiper":joined,"stars":r["stars"],"rights":"BLOCKED_PRIVATE_UNLICENSED",
                     "runtime":"SOURCE_EVIDENCE_ONLY","receipt_artifact":ARTIFACT})
    by_meaning,by_key,by_source=indexes(rows)
    tests=[]
    def check(name,condition):
        require(condition,name); tests.append(name)
    for r in rows:
        m=r["gg_id"]; k=r["kuiper"]["key"]
        check(m+" source roundtrip",m in lookup_source(by_source,by_meaning[m]["source"]))
        if k is not None: check(m+" key roundtrip",m in lookup_key(by_key,k))
    s=rows[0]["source"]
    wrong={**s,"commit":"0"*40}
    reject(lambda:lookup_source(by_source,wrong),"UNKNOWN_OCCURRENCE")
    check("wrong commit same blob producer refusal",kuiper_join(wrong,producer)["key"] is None)
    wrong_path={**s,"path":"sources/v9-extracts/geodesy.mjs"}
    reject(lambda:lookup_source(by_source,wrong_path),"UNKNOWN_OCCURRENCE")
    check("different path same blob producer refusal",kuiper_join(wrong_path,producer)["key"] is None)
    reject(lambda:lookup_key(by_key,-1),"UNKNOWN_KEY"); tests.append("missing key refusal")
    reject(lambda:lookup_key(by_key,str(KNOWN[1])),"UNKNOWN_KEY"); tests.append("string key refusal")
    reject(lambda:indexes(rows+[rows[0]]),"DUPLICATE_MEANING"); tests.append("duplicate meaning refusal")
    fixture=json.loads((HERE/"consumer-fixture.json").read_text())
    request=fixture["input"]; result=fixture["expected"]; request_digest=sha(canonical(request))
    bound=selected_location(request,result,request_digest)
    check("typed selected point",bound=={"crs":"WGS84","unit":"degrees","point_a":{"longitude":0,"latitude":0},"point_b":{"longitude":1,"latitude":0}})
    reject(lambda:selected_location(request,None,request_digest),"NO_ELIGIBLE_RECORD");tests.append("null refusal")
    reject(lambda:selected_location(request,{"id":"absent","distance_km":0},request_digest),"SELECTED_ID_NOT_IN_DATASET");tests.append("missing ID refusal")
    changed=copy.deepcopy(request);changed["records"].append(changed["records"][0])
    reject(lambda:selected_location(changed,result,sha(canonical(changed))),"MISSING_OR_DUPLICATE_ID");tests.append("duplicate ID refusal")
    reject(lambda:selected_location(changed,result,request_digest),"INPUT_DIGEST_MISMATCH");tests.append("stale dataset refusal")
    changed=copy.deepcopy(request);changed["crs"]="EPSG:27700"
    reject(lambda:selected_location(changed,result,sha(canonical(changed))),"INCOMPATIBLE_CRS");tests.append("wrong CRS refusal")
    reject(lambda:selected_location(request,{"id":"eligible","distance_km":"111 km"},request_digest),"DISTANCE_UNIT_OR_VALUE");tests.append("wrong distance type refusal")
    graph={"schema":"tacit3b.nearest-orient-bond.v1","relationship_state":"PROPOSED_TYPED_COMPATIBILITY_NOT_RUNTIME_DEPENDENCY",
      "nodes":[{"operation":"nearestSubstation","meanings":[mid(15),mid(16)],"state":"FAMILY_NOT_ADMITTED"},
               {"operation":"selected_location","meaning":None,"state":"LOCAL_ADAPTER_CANDIDATE"},
               {"operation":"orient","meanings":[mid(1),mid(5),mid(6)],"state":"INDEPENDENT_ADMITTED_ORIENT_NOT_COMPOSED"}],
      "edges":[{"from":"nearestSubstation","to":"selected_location","type":"candidate_typed_data_bond","port":"result.id + original request digest","null":"refuse"},
               {"from":"selected_location","to":"orient","type":"candidate_typed_data_bond","port":"WGS84 named points / degrees","null":"refuse"}],
      "existing_spider_edges":json.loads((base/"data/nearest-spider.json").read_text())["edges"],
      "input_sha256":request_digest,"fixture_provenance":"synthetic","fixture_nearest_result":result,
      "orient_input":bound,"expected_orient":{"distance_km":111.31949079327356,"initial_bearing_deg":90},
      "composition_execution":"REFUSED_NEAREST_NOT_ADMITTED","execution_receipt":None,
      "source_revisions":[{"gg_id":r["gg_id"],"source":r["source"],"span_sha256":r["span_sha256"]} for r in rows]}
    graph["candidate_pattern_sha256"]=sha(canonical(graph))
    sidecar={"schema":"tacit3b.vedic-kuiper-sparse.v1","dictionary_commit":EDITION,
       "producer_commit":PRODUCER,"producer_receipt_sha256":sha(raw),"identity_artifact_sha256":ZIP_SHA,
       "source_receipt_sha256":RECEIPT_SHA,"entries":rows,
       "reverse_key_to_meanings":{str(k):sorted(v) for k,v in sorted(by_key.items())},
       "tests":tests,"test_count":len(tests),"wafer_replayed":False,"visual_activation":False,"independent_acceptance":False,
       "graph":graph}
    out.parent.mkdir(exist_ok=True,parents=True);out.write_bytes(canonical(sidecar)+b"\n")
    print(json.dumps({"keys":{r["gg_id"]:r["kuiper"]["key"] for r in rows},"tests":len(tests),"graph":graph["composition_execution"],"sidecar_sha256":sha(out.read_bytes())},sort_keys=True))
def main():
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify"]);p.add_argument("--root",type=pathlib.Path,required=True);p.add_argument("--out",type=pathlib.Path)
    a=p.parse_args()
    if a.mode=="acquire": acquire(a.root)
    else: verify(a.root,a.out)
if __name__=="__main__": main()

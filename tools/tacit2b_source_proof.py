"""Electrical candidate source proof, not a TACIT10 identity receipt.
Reuses exact pinned TACIT10 identity_bridge and Kuiper edition_keys producer.
No new addresses, no producer writes, no source redistribution.
"""
import argparse, copy, hashlib, json, os, subprocess, sys, urllib.request
from pathlib import Path
from tacit2b_electrical_acquire import git_blob, PIN, BLOB, PATH
REPO="Ventusltd/ventus-grid-engine"
VEDIC="0ee52af60036f32358759a67836578dce6d7da51"
DICT_SHA="327803457f1528803278959ad7c107caed76489cfb2263db7143973a151b3c96"
TACIT10="70d08339226f052f0da64fcb1b7d59f53286b58c"
KUIPER="eec3f1891294af9e93ce6613c10cdf71806802f2"
MODULE_SHA="8c3d99ca10b0d02722b54c6da21ebf1acb77936fe440cbd413b457266a994287"
FUNCTIONS={"voltageDropVolts":("GG2050-VEDIC-000024",95,129),"dropPercent":("GG2050-VEDIC-000025",135,150),"lossesWatts":("GG2050-VEDIC-000026",158,181),"annualLossKwh":("GG2050-VEDIC-000027",190,206)}
def sha(b): return hashlib.sha256(b).hexdigest()
def need(ok,msg):
    if not ok: raise ValueError(msg)
def write(p,x):
    with p.open("x") as f: json.dump(x,f,sort_keys=True,indent=2);f.write("\n")
def get(repo,commit,path,blob,out):
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{commit}/{path}",timeout=30) as r: data=r.read(2*1024*1024+1)
    need(len(data)<=2*1024*1024 and git_blob(data)==blob,"pinned helper byte mismatch "+path)
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
def run(args,timeout=60,**kw):
    subprocess.run(list(map(str,args)),check=True,timeout=timeout,**kw)
def verify(raw,dict_raw,parsed):
    need(git_blob(raw)==BLOB and sha(raw)==MODULE_SHA,"source pin mismatch")
    need(sha(dict_raw)==DICT_SHA,"dictionary edition mismatch")
    need(parsed["module_sha256"]==MODULE_SHA and parsed["imports"]==[],"parser pin/import mismatch")
    rows=json.loads(dict_raw)["entries"]
    need(len(rows)==50 and len({r["gg_id"] for r in rows})==50,"dictionary census mismatch")
    lines=raw.splitlines(keepends=True)
    result=[]
    for name,(mid,first,last) in FUNCTIONS.items():
        matches=[r for r in rows if r["gg_id"]==mid]
        need(len(matches)==1,"meaning missing")
        e=matches[0];s=e["source"];p=parsed["functions"][name]
        need(e["translation_ref"]=="engine:voltage-drop:"+name and s=={"repo":REPO,"commit":PIN,"path":PATH,"blob":BLOB,"first":first,"last":last},"meaning/source mismatch")
        need(p["exported"] and (p["first"],p["last"],p["col0"],p["col1"],p["export_col0"])==(first,last,7,1,0),"formal span mismatch")
        result.append({"meaning_id":mid,"meaning":e["word"],"export":name,"source":dict(s,col0=p["col0"],col1=p["col1"]),
                       "physical_span_sha256":sha(b"".join(lines[first-1:last])),
                       "parser":p,"dictionary_inputs":e["inputs"],"dictionary_output":e["output"]})
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument("--module",type=Path,required=True);p.add_argument("--dictionary",type=Path,required=True);p.add_argument("--parser",type=Path,required=True);p.add_argument("--work",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    a.work.mkdir();a.out.mkdir()
    raw=a.module.read_bytes();d=a.dictionary.read_bytes();parsed=json.loads(a.parser.read_text())
    rows=verify(raw,d,parsed)
    helper=a.work/"identity_bridge.py"
    get("Ventusltd/vedic-",TACIT10,"tools/identity_bridge.py","f3e6519aab67d2bc9fbc818318abca478ca2ef7e",helper)
    sys.path.insert(0,str(a.work))
    from identity_bridge import request, kuiper_join
    producer=a.work/"producer"
    for path,blob in (("tools/edition_keys.py","2a7144e76c3701372266a79c20ba8a5b6c940a1b"),("cosmos/wafer.tsv","54dafc60dbd38ce949c683a3ec21697255e58eb1"),("cosmos/repos.tsv","c456212d863b85848f5976278db61648b9cf0269")):
        get("Ventusltd/kuiper-belt",KUIPER,path,blob,producer/path)
    roots=a.work/"roots";roots.mkdir();clone=roots/"ventus-grid-engine";clone.mkdir()
    run(["git","init","-q",clone])
    run(["git","-C",clone,"fetch","--depth=1","https://github.com/"+REPO+".git",PIN],timeout=90)
    need(subprocess.check_output(["git","-C",str(clone),"rev-parse","FETCH_HEAD"],text=True).strip()==PIN,"Git fetch mismatch")
    requests=[request(r["source"],r["meaning_id"]) for r in rows]
    write(a.out/"kuiper-requests.json",requests)
    receipt=a.work/"kuiper-producer.json"
    run([sys.executable,producer/"tools/edition_keys.py","--bodies",a.out/"kuiper-requests.json","--roots",roots,"--out",receipt],timeout=90)
    receipt_raw=receipt.read_bytes();producer_result=json.loads(receipt_raw)
    for r in rows:
        r["kuiper"]=kuiper_join(r["source"],producer_result)
        r["stars"]={"state":"TACIT10_EXACT_OCCURRENCE_REVIEW_PENDING","tablet_id":None,"element_id":None,"family_id":None,"line_ids":None}
        r["source_address_state"]="CANDIDATE_NOT_INDEPENDENTLY_ACCEPTED"
        need(r["kuiper"]["key"] is not None,"producer receipt refused "+r["export"])
    need(len({r["kuiper"]["key"] for r in rows})==4,"duplicate keys")
    # Actual producer join controls: changed commit, blob, line and duplicate receipt.
    for field,val in (("commit","0"*40),("blob","0"*40),("first",1)):
        bad=dict(rows[0]["source"],**{field:val})
        need(kuiper_join(bad,producer_result)["key"] is None,"incorrect pin accepted")
    duplicated=copy.deepcopy(producer_result);duplicated["bodies"].append(duplicated["bodies"][0])
    need(kuiper_join(rows[0]["source"],duplicated)["key"] is None,"duplicate receipt accepted")
    for args in ((raw+b" ",d,parsed),(raw,d+b" ",parsed)):
        try: verify(*args)
        except ValueError: pass
        else: raise ValueError("tampered bytes accepted")
    bad=copy.deepcopy(parsed);bad["functions"]["voltageDropVolts"]["first"]+=1
    try: verify(raw,d,bad)
    except ValueError: pass
    else: raise ValueError("wrong AST span accepted")
    # Source text in producer receipt stays in runner; export provenance-only fields.
    sanitized=copy.deepcopy(producer_result)
    for r in sanitized["bodies"]: r.pop("line_text",None)
    write(a.out/"kuiper-producer-redacted.json",sanitized)
    write(a.out/"parser.json",parsed)
    ports_raw=(Path(__file__).resolve().parents[1]/"packages/electrical/typed-ports.json").read_bytes()
    ports=json.loads(ports_raw)
    need(ports["schema"]=="vedic.electrical-typed-ports-candidate.v1" and set(ports["functions"])==set(FUNCTIONS),"typed ports export mismatch")
    for row in rows:
        typed=ports["functions"][row["export"]]
        need(typed["meaning_id"]==row["meaning_id"],"typed meaning mismatch")
        row["typed_ports"]=typed
    need(ports["functions"]["lossesWatts"]["input"]["lengthM"]["quantity"]=="one_way_conductor_route_length","route quantity mismatch")
    need(ports["functions"]["lossesWatts"]["output"]["value"]["unit"]=="W" and ports["functions"]["annualLossKwh"]["output"]["value"]["unit"]=="kWh","power/energy unit mismatch")
    write(a.out/"typed-ports.json",ports)
    result={"schema":"vedic.electrical-source-proof-candidate.v1","owner":"TACIT 2b","review_owner":"TACIT 10","dictionary_commit":VEDIC,"dictionary_sha256":DICT_SHA,"module_sha256":MODULE_SHA,"source_blob":BLOB,"source_bytes":len(raw),"kuiper_producer_commit":KUIPER,"kuiper_wafer_sha256":sha((producer/"cosmos/wafer.tsv").read_bytes()),"raw_producer_receipt_sha256":sha(receipt_raw),"redacted_producer_receipt_sha256":sha((a.out/"kuiper-producer-redacted.json").read_bytes()),"components":rows,"controls_passed":7,"typed_ports_source_sha256":sha(ports_raw),"formal_imports":[],"identity_complete":False,"independent_acceptance":False,"admission":"BLOCKED_TACIT10_REVIEW","rights":"BLOCKED_PRIVATE_UNLICENSED","execution_verified_by_this_receipt":False}
    write(a.out/"candidate-source-proof.json",result)
    print("Candidate proof SHA256:",sha((a.out/"candidate-source-proof.json").read_bytes()))
    for row in rows: print("Source address:",json.dumps({"meaning_id":row["meaning_id"],"export":row["export"],"kuiper":row["kuiper"],"span_sha256":row["physical_span_sha256"]},sort_keys=True))
    print("Source proof controls: 7/7; candidate only; not TACIT10 receipt")
if __name__=="__main__":main()

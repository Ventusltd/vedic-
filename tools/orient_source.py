"""Acquire/validate the pinned original ORIENT module. Never execute source here."""
import argparse,json
from pathlib import Path
from identity_bridge import git_blob,sha,require
from validate_translation import fetch

PIN={"repo":"Ventusltd/ventus-grid-engine","commit":"487ec7bd38dfa5aecb1c75da53b4a866ab2101cb","path":"engine/v9-geodesy.js","blob":"14023f06d4ef2ea806437863bd35dee954c46b11"}
EDITION="0ee52af60036f32358759a67836578dce6d7da51"
DICT_SHA="327803457f1528803278959ad7c107caed76489cfb2263db7143973a151b3c96"
COMPONENTS={"GG2050-VEDIC-000001":("distanceKm",29,47,86415575118),"GG2050-VEDIC-000005":("initialBearingDeg",133,139,86415575222)}
def physical(raw):
    p=raw.split(b"\n")
    return [x+b"\n" for x in p[:-1]]+([p[-1]] if p[-1] else [])
def module_check(raw):
    require(git_blob(raw)==PIN["blob"],"original Git blob mismatch")
    return sha(raw)
def acquire(out):
    raw=fetch(PIN["repo"],PIN["commit"],PIN["path"])
    module_check(raw)
    with Path(out).open("xb") as f: f.write(raw)
def check_component(e, raw, parser):
    name,first,last,key=COMPONENTS[e["gg_id"]]; s=e["source"]
    require(all(s[k]==v for k,v in PIN.items()) and (s["first"],s["last"])==(first,last),"source edition mismatch")
    a=parser["functions"][name]
    require((a["first"],a["last"],a["col0"],a["col1"])==(first,last,7,1),"formal boundary mismatch")
    require(a["scope"]=="top-level exported declaration" and a["parameters"]==["lon1","lat1","lon2","lat2"],"formal signature mismatch")
    require(a["module_dependencies"]==(["DEG","EARTH_RADIUS_KM"] if name=="distanceKm" else ["DEG"]),"module dependency mismatch")
    require(e["kuiper"]["state"]=="PINNED_PRODUCER_RECEIPT_MATCH_NOT_WAFER_REPLAY" and e["kuiper"]["key"]==key,"Kuiper key mismatch")
    span=sha(b"".join(physical(raw)[first-1:last]))
    require(e["stars"].get("span_sha256") in (None,span),"Stars span mismatch")
    return {"gg_id":e["gg_id"],"export":name,"source":s,"span_sha256":span,"parser":a,"stars":e["stars"],"kuiper":e["kuiper"]}
def complete(rows):
    return all(e["stars"]["state"]=="EXACT_INDEXED_PHYSICAL_SPAN" and all(e["stars"].get(k) is not None for k in ("tablet_id","element_id","family_id","line_ids")) for e in rows)
def build(report,raw,parser,dictionary):
    require(sha(dictionary)==DICT_SHA,"wrong V2 dictionary edition")
    mod_sha=module_check(raw)
    require(parser["module_sha256"]==mod_sha,"parser/module mismatch")
    rows=[check_component(e,raw,parser) for e in report["entries"] if e["gg_id"] in COMPONENTS]
    require(len(rows)==2 and {e["gg_id"] for e in rows}==set(COMPONENTS),"missing/duplicate component")
    return {"schema":"vedic.orient-module-receipt.v1","dictionary_commit":EDITION,"dictionary_sha256":DICT_SHA,
            "source":PIN,"module_sha256":mod_sha,"module_bytes":len(raw),"composition":"GG2050-VEDIC-000006",
            "components":rows,"parser":parser,"stars_snapshot_sha256":report["snapshot_sha256"],
            "kuiper_producer_commit":report["kuiper_producer_commit"],"kuiper_wafer_sha256":report["kuiper_wafer_sha256"],
            "kuiper_receipt_sha256":report["kuiper_receipt_sha256"],"identity_complete":complete(rows),
            "tier":"GIT_AND_STARS_PHYSICAL_SPANS_VERIFIED" if complete(rows) else "GIT_SOURCE_VERIFIED_STARS_INCOMPLETE",
            "execution_verified":False}
def validate(receipt,raw,expected_receipt_sha,receipt_bytes):
    require(sha(receipt_bytes)==expected_receipt_sha and json.loads(receipt_bytes)==receipt,"receipt digest mismatch")
    require(receipt["schema"]=="vedic.orient-module-receipt.v1" and receipt["dictionary_commit"]==EDITION and receipt["dictionary_sha256"]==DICT_SHA,"receipt edition mismatch")
    require(receipt["source"]==PIN and receipt["module_sha256"]==module_check(raw) and receipt["module_bytes"]==len(raw),"module pin mismatch")
    require(receipt["parser"]["module_sha256"]==sha(raw),"parser/module mismatch")
    require(receipt["composition"]=="GG2050-VEDIC-000006","composition mismatch")
    rows=receipt["components"]
    require(len(rows)==2 and {e["gg_id"] for e in rows}==set(COMPONENTS),"component mismatch")
    require(all(check_component(e,raw,receipt["parser"])==e for e in rows),"component evidence mismatch")
    require(receipt["identity_complete"] is complete(rows) and receipt["tier"]==("GIT_AND_STARS_PHYSICAL_SPANS_VERIFIED" if complete(rows) else "GIT_SOURCE_VERIFIED_STARS_INCOMPLETE"),"unsupported identity tier")
    require(receipt["execution_verified"] is False,"source receipt is not runtime evidence")
    return receipt
def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("acquire");a.add_argument("--module",type=Path,required=True)
    b=sub.add_parser("build")
    for k in ("module","report","parser","dictionary","receipt"): b.add_argument("--"+k,type=Path,required=True)
    v=sub.add_parser("validate")
    for k in ("module","receipt"): v.add_argument("--"+k,type=Path,required=True)
    v.add_argument("--receipt-sha",required=True)
    a=p.parse_args()
    if a.cmd=="acquire": acquire(a.module)
    elif a.cmd=="build":
        r=build(json.loads(a.report.read_text()),a.module.read_bytes(),json.loads(a.parser.read_text()),a.dictionary.read_bytes())
        with a.receipt.open("x") as f: json.dump(r,f,sort_keys=True,indent=2);f.write("\n")
        print("Module receipt SHA256:",sha(a.receipt.read_bytes()),"Module SHA256:",r["module_sha256"],"Tier:",r["tier"])
        for e in r["components"]: print("Component:",json.dumps(e,sort_keys=True))
    else:
        raw=a.receipt.read_bytes();r=validate(json.loads(raw),a.module.read_bytes(),a.receipt_sha,raw)
        print(r["tier"])
if __name__=="__main__": main()

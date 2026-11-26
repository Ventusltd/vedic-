"""Exact producer-declared module classifications, separate from unknown family memberships.
Reuses Star-maker's permanent table and Stars' classification catalogue; no ID allocation."""
import argparse,json,subprocess,zipfile
from pathlib import Path
from tacit_a_closure import canonical,sha,fetch,need,blob,VEDIC
from tacit_a_stars import STARS_HEAD
MAKER="f65c2f381d91eeb1eba75a97ae6765c24e32197d"
TABLE_BLOB="aaa1f27d2d4acf372c8c6868987072779bb90d8a"
CATALOGUE_BLOB="38e0fbb0ead2d21467889563d31a1cbf0b306ac1"
CROSSWALK_ARTIFACT=15138207819
CROSSWALK_ZIP="2ae770734cdfe12d307e8fc3a3bd063fac172d0c7964a7f743efecc49024eddc"
CROSSWALK_SHA="cb496073d32a84d1d4dc8ff73d75552eaf05867b3186f0d19aea9db8f7bd1d7f"
def classify(source,table,catalogue):
    need(source["repo"]=="Ventusltd/ventus-grid-engine","ENGINE_REPOSITORY_REQUIRED")
    path=source["path"]
    need(path.startswith("engine/") and path.count("/")==1,"ENGINE_PATH_REQUIRED")
    matches=[e for e in table["elements"] if e["key"]=="engine:"+path]
    need(len(matches)==1,"EXACT_MODULE_TABLE_KEY_REQUIRED")
    e=matches[0]
    need(e["family"]=="engine" and e["name"]==Path(path).name and type(e["number"]) is int and 13<=e["number"]<=31,"TABLE_ENGINE_IDENTITY")
    category=catalogue["engine_categories"].get(e["name"])
    need(category is not None and len([c for c in catalogue["categories"] if c["id"]==category])==1,"EXACT_CATEGORY_REQUIRED")
    return {"state":"PRODUCER_DECLARED_MODULE_CLASSIFICATION_ONLY","number":e["number"],"symbol":e["symbol"],"key":e["key"],"category":category,
      "module_state":e["state"],"table_identity":e["identity"],"name":e["name"]}
def acquire(root):
    root.mkdir()
    fetch("Ventusltd/star-maker",MAKER,"elements/table.json",TABLE_BLOB,root/"table.json")
    fetch("Ventusltd/stars",STARS_HEAD,"modular-star/blocks-catalogue.json",CATALOGUE_BLOB,root/"catalogue.json")
    with (root/"crosswalk.zip").open("xb") as f:
        subprocess.run(["gh","api",f"repos/{VEDIC}/actions/artifacts/{CROSSWALK_ARTIFACT}/zip"],stdout=f,check=True,timeout=90)
    need(sha((root/"crosswalk.zip").read_bytes())==CROSSWALK_ZIP,"CROSSWALK_ZIP")
def verify(root,out):
    raw=(root/"crosswalk.zip").read_bytes();need(sha(raw)==CROSSWALK_ZIP,"CROSSWALK_ZIP")
    with zipfile.ZipFile(root/"crosswalk.zip") as z:data=z.read("crosswalk.json")
    need(sha(data)==CROSSWALK_SHA,"CROSSWALK_SHA")
    cross=json.loads(data);rows=cross["entries"]
    tr=(root/"table.json").read_bytes();cr=(root/"catalogue.json").read_bytes()
    need(blob(tr)==TABLE_BLOB and blob(cr)==CATALOGUE_BLOB,"PRODUCER_BLOB_PIN")
    table=json.loads(tr);catalogue=json.loads(cr)
    allrows=table["elements"]
    need(len({e["number"] for e in allrows})==len({e["symbol"] for e in allrows})==len({e["key"] for e in allrows})==len(allrows),"DUPLICATE_PERMANENT_TABLE_ENTRY")
    tests=[];result=[]
    def test(name,ok):need(ok,name);tests.append(name)
    def reject(name,fn):
        try:fn()
        except ValueError:tests.append(name)
        else:raise AssertionError("EXPECTED_REFUSAL:"+name)
    for r in rows:
        source=r["source"];mapped=classify(source,table,catalogue)
        test(r["meaning_id"]+" exact module path",mapped["key"]=="engine:"+source["path"])
        test(r["meaning_id"]+" no membership promotion",r["periodic"]["number"] is None and r["current_stars"]["family_id"] is None)
        result.append({"meaning_id":r["meaning_id"],"word":r["word"],"source":source,"kuiper":r["kuiper"],"module_classification":mapped,
            "exact_function_family_membership":r["periodic"],"previous_curated_classification":r["classification_candidate"],
            "properties":[{"source_occurrence":source,"property":"module_periodic_symbol","definition_version":"tacit-a-module-v1","value":mapped["symbol"],"unit":None,"method":"exact Star-maker engine key","input_sha256":sha(tr),"evidence_ref":"star-maker/elements/table.json@"+MAKER,"state":"DERIVED","unknown_reason":None},
            {"source_occurrence":source,"property":"exact_function_periodic_membership","definition_version":"tacit-a-module-v1","value":None,"unit":None,"method":"Modular Star exact occurrence then family list","input_sha256":CROSSWALK_SHA,"evidence_ref":"artifact "+str(CROSSWALK_ARTIFACT),"state":"UNKNOWN","unknown_reason":"OCCURRENCE_NOT_INDEXED"}],
            "admission":"REFUSED_REVIEW_PENDING"})
    s=rows[0]["source"]
    reject("other repo",lambda:classify({**s,"repo":"Ventusltd/gridatlas"},table,catalogue))
    reject("name only or same blob different path",lambda:classify({**s,"path":"engine/other.js"},table,catalogue))
    reject("duplicate key",lambda:classify(s,{"elements":table["elements"]*2},catalogue))
    reject("missing category",lambda:classify(s,table,{**catalogue,"engine_categories":{}}))
    test("distinct module classifications",len({(r["module_classification"]["number"],r["module_classification"]["symbol"]) for r in result})==3)
    report={"schema":"vedic.tacit-a.module-classification-candidate.v1","source_crosswalk_sha256":CROSSWALK_SHA,
       "star_maker_commit":MAKER,"star_maker_table_blob":TABLE_BLOB,"stars_catalogue_commit":STARS_HEAD,"stars_catalogue_blob":CATALOGUE_BLOB,
       "entries":result,"exact_module_classifications":len(result),"exact_function_memberships":0,
       "tests":tests,"test_count":len(tests),"admission":"REFUSED_REVIEW_PENDING","independent_acceptance":False}
    out.write_bytes(canonical(report)+b"\n")
    print(json.dumps({"checks":len(tests),"module_classifications":len(result),"module_blocks":sorted({(r["module_classification"]["number"],r["module_classification"]["symbol"],r["module_classification"]["category"]) for r in result}),"exact_function_memberships":0,"sha256":sha(out.read_bytes())},sort_keys=True))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify"]);p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    else:verify(a.root,a.out)

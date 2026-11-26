"""Digest-bound intake of A's candidate projections; does not grant admission."""
import argparse
import copy
import io
from pathlib import Path
import sys
import zipfile

ZIP_SHA="c1ea563a7be0c1343d547d5678f46b86952a73bc8d5346d330a0faf8e7667772"
CANDIDATE_SHA="5f5cc4c75515ca0059fb67e2f511c4b22d7e048096916cff569ecd630578a831"
FAMILIES={"nearest":"nearest-substation","electrical":"electrical"}
EDITION="0ee52af60036f32358759a67836578dce6d7da51"
COMMIT="487ec7bd38dfa5aecb1c75da53b4a866ab2101cb"

def main():
    p=argparse.ArgumentParser()
    for k in ("factory","archive","out"):p.add_argument("--"+k,type=Path,required=True)
    p.add_argument("--review",type=Path)
    a=p.parse_args()
    sys.path.insert(0,str(a.factory/"tools"))
    import package_factory as f
    def member(z,name):
        matches=[i for i in z.infolist() if i.filename==name or i.filename.endswith("/"+name)]
        f.need(len(matches)==1 and matches[0].file_size<=2_000_000,"CANDIDATE_MEMBER:"+name)
        return z.read(matches[0])
    def gate(fn,reason):
        try:fn()
        except ValueError as e:
            f.need(str(e)==reason,"WRONG_REFUSAL:"+str(e));return reason
        raise AssertionError("UNEXPECTED_ACCEPTANCE:"+reason)
    raw=a.archive.read_bytes()
    f.need(len(raw)<=8_000_000 and f.sha(raw)==ZIP_SHA,"CANDIDATE_ARTIFACT_DIGEST")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        candidate=member(z,"candidate.json")
        f.need(f.sha(candidate)==CANDIDATE_SHA,"CANDIDATE_CONTENT_DIGEST")
        manifest_raw=member(z,"family-review/manifest.json")
        m=f.strict(manifest_raw)
        f.need(m["schema"]=="vedic.tacit-a.family-review-manifest.v1" and
               m["status"]=="CANDIDATE_ONLY" and m["authority"]=="NO_ADMISSION","CANDIDATE_AUTHORITY")
        names={family+"-"+kind+".json" for family in ("nearest","electrical","orient") for kind in ("source","closure")}
        f.need(set(m["files"])==names,"CANDIDATE_FILE_SET")
        projections={}
        for name in sorted(names):
            v=member(z,"family-review/"+name)
            f.need(f.sha(v)==m["files"][name],"CANDIDATE_PROJECTION_DIGEST")
            projections[name]=v
    c_review=None
    if a.review:
        c_raw=a.review.read_bytes()
        f.need(len(c_raw)<=8_000_000 and f.sha(c_raw)=="8d48284a1ed870d16d99504707c81e0650a23c24693a1e491a787e809bb08ffa","C_REVIEW_ARTIFACT_DIGEST")
        with zipfile.ZipFile(io.BytesIO(c_raw)) as z:c_json=member(z,"a-review.json")
        f.need(f.sha(c_json)=="76080746a09f0c3fa6693211147acfa98716be50caeb766f4ee01a68fc9ac303","C_REVIEW_CONTENT_DIGEST")
        c_review=f.strict(c_json)
        f.need(c_review["schema"]=="vedic.tacit-c.independent-source-closure-review.v1" and
               c_review["reviewer"]=="TACIT C" and c_review["result"]=="BOUNDED_EVIDENCE_HONOURED" and
               c_review["candidate_artifact"]=="15137841195" and c_review["candidate_head"]=="5ae1e8d4d0f5d9f852aa589a0894e52f112eed6e" and c_review["candidate_zip_sha256"]==ZIP_SHA and
               c_review["candidate_sha256"]==CANDIDATE_SHA and c_review["formal_factory_admission"] is False and
               c_review["publication"] is False,"C_REVIEW_BOUNDARY")
        for family in ("nearest","electrical","orient"):
            row=c_review["source_and_closure"][family]
            f.need(row["source_candidate_sha256"]==f.sha(projections[family+"-source.json"]) and
                   row["closure_candidate_sha256"]==f.sha(projections[family+"-closure.json"]),"C_REVIEW_PROJECTION")
            f.need(row["source"]["verdict"]==row["closure"]["verdict"]=="HONOURED" and
                   row["source"]["formal_acceptance"]==row["closure"]["formal_acceptance"]=="OPEN","C_REVIEW_FORMAL_STATE")
    def bind(family,source,closure,descriptor):
        f.need(source["schema"]=="vedic.tacit-a.source-review-candidate.v1" and
               closure["schema"]=="vedic.tacit-a.closure-review-candidate.v1","CANDIDATE_SCHEMA")
        f.need(source["family"]==closure["family"]==family and
               source["source_commit"]==closure["source_commit"]==COMMIT and
               source["dictionary_commit"]==EDITION,"CANDIDATE_OCCURRENCE")
        f.need(source["candidate_state"]==closure["candidate_state"]=="REFUSED_REVIEW_PENDING"
               and source["independent_acceptance"] is False and closure["independent_acceptance"] is False
               and source["rights"]=="BLOCKED" and closure["runtime_verified"] is False
               and closure["execution_edges"]==[],"CANDIDATE_OVERREACH")
        f.need(source["modules"]==closure["modules"],"CANDIDATE_CLOSURE_SOURCE_MISMATCH")
        modules=[x for x in descriptor["inputs"] if x["role"] in ("module","local_dependency")]
        f.need(set(source["modules"])=={x["path"] for x in modules},"CANDIDATE_MODULE_SET")
        for x in modules:
            observed=source["modules"][x["path"]]
            k="blob" if x["algorithm"]=="git-blob-sha1" else "sha256"
            f.need(x["commit"]==COMMIT and observed[k]==x["digest"],"CANDIDATE_SOURCE_PIN")
    report={}
    for family,registered in FAMILIES.items():
        sr=projections[family+"-source.json"];cr=projections[family+"-closure.json"]
        source=f.strict(sr);closure=f.strict(cr)
        desc=f.strict((a.factory/"packages/factory/pending"/(registered+".json")).read_bytes())
        bind(family,source,closure,desc)
        wrong=copy.deepcopy(source);wrong["independent_acceptance"]=True
        overreach=gate(lambda:bind(family,wrong,closure,desc),"CANDIDATE_OVERREACH")
        wrong=copy.deepcopy(closure);wrong["modules"]={}
        wrong_modules=gate(lambda:bind(family,source,wrong,desc),"CANDIDATE_CLOSURE_SOURCE_MISMATCH")
        # Ask the real factory gate. Candidate source bytes are deliberately not
        # provided: empty reviewed registry must refuse before source validation.
        review=gate(lambda:f.review_receipt(registered,sr,{},cr),"REVIEWED_RECEIPT_NOT_PINNED")
        report[registered]={"source_sha256":f.sha(sr),"closure_sha256":f.sha(cr),
                            "descriptor_sha256":f.sha(f.canonical(desc)),
                            "candidate_source_pins_match":True,"factory_review":review,
                            "negative_checks":[overreach,wrong_modules],
                            "admission":False,"runtime_executed":False}
    out={"schema":"tacit-b.candidate-intake.v1","artifact_id":15137841195,"artifact_sha256":ZIP_SHA,
         "candidate_sha256":CANDIDATE_SHA,"manifest_sha256":f.sha(manifest_raw),
         "families":report,"independent_review":"TACIT_C_REQUIRED","redistribution":"BLOCKED"}
    if c_review:
        out["schema"]="tacit-b.candidate-intake.v2"
        out["independent_review"]="BOUNDED_EVIDENCE_HONOURED_FORMAL_AUTHORITY_OPEN"
        out["review_artifact"]={"repo":"Ventusltd/neural-link-between-agents","id":15138980638,
          "zip_sha256":f.sha(c_raw),"receipt_sha256":f.sha(c_json)}
        for family,registered in FAMILIES.items():
            out["families"][registered]["review"]=c_review["source_and_closure"][family]
    a.out.write_bytes(f.canonical(out))
    print(f.canonical(out).decode(),end="")

if __name__=="__main__":
    main()

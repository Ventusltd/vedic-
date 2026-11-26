"""Cold join of A's exact bond metadata to actual B execution and C review."""
import argparse, io, sys, zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    for k in ("factory","archive","ranking","review","electrical","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.factory/"tools"))
    import package_factory as f
    raw=a.archive.read_bytes()
    f.need(len(raw)<=8_000_000 and f.sha(raw)=="649209e8723af1efd4c73f85ebd90b524a2312907d8a5e24759c8bf72ad1f72a","BOND_ARTIFACT_PIN")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        hits=[i for i in z.infolist() if i.filename=="bonds.json" or i.filename.endswith("/bonds.json")]
        f.need(len(hits)==1 and hits[0].file_size<=2_000_000,"BOND_MEMBER")
        data=z.read(hits[0])
    f.need(f.sha(data)=="821abf96d3e4c2f42e61d578dcefdfbda366c145b067f9cc9206fdaa91b6cf2d","BOND_CONTENT_PIN")
    m=f.strict(data);rank_raw=a.ranking.read_bytes();rank=f.strict(rank_raw)
    review=f.strict(a.review.read_bytes());elec=f.strict(a.electrical.read_bytes())
    f.need(m["schema"]=="vedic.tacit-a.typed-bond-manifest.v1" and m["admission"]=="UNCHANGED" and m["redistribution"]=="BLOCKED","BOND_AUTHORITY")
    f.need(m["source_candidate_sha256"]==review["candidate_sha256"] and m["c_review_sha256"]==review["review_artifact"]["receipt_sha256"],"REVIEW_BINDING")
    f.need(m["b_ranking_sha256"]==f.sha(rank_raw) and m["runtime_observation"]["ranking_receipt_sha256"]==rank["ranking"]["receipt_sha256"] and m["runtime_observation"]["request_sha256"]==rank["ranking"]["request_sha256"] and m["runtime_observation"]["result"]==rank["ranking"]["result"],"RUNTIME_BINDING")
    f.need(m["runtime_observation"]["independent_acceptance"] is False and m["static_source_graph"]["execution_edges"]==[],"STATIC_IS_NOT_RUNTIME")
    for family,key in (("nearest","nearest-substation"),("electrical","electrical")):
        x=m["family_reviews"][family];y=review["families"][key]
        f.need(x["source_sha256"]==y["source_sha256"] and x["closure_sha256"]==y["closure_sha256"] and x["review"]==y["review"],"FAMILY_REVIEW_BINDING")
    pairs={(x["from"],x["to"]) for x in m["typed_bonds"]}
    f.need(pairs=={("nearestSubstation.id","selected_location.id"),("selected_location.point_a","orient.point_a"),("selected_location.point_b","orient.point_b"),("voltageDropVolts.value","dropPercent.dropVolts"),("lossesWatts.value","annualLossKwh.peakLossWatts")},"BOND_PAIR_SET")
    f.need(len(m["source_entries"])==8 and len(m["properties"])==32 and len(m["incompatible_bonds"])==6,"BOND_CENSUS")
    f.need(m["orient"]["archive_sha256"]==rank["composition"]["orient"]["pattern"]["archive_sha256"],"ORIENT_ARCHIVE_BINDING")
    f.need(elec["request"]["route"]["origin"]=="explicit_caller_input" and elec["request"]["current"]["context"]=="explicit_peak_model_current" and elec["request"]["factorBasis"]=="loss-load-factor","ELECTRICAL_CONTEXT")
    f.need(elec["archive"] is None and rank["nearest_archive"] is None and elec["admission"]=="SOURCE_RECEIPT_PENDING" and rank["factory_admission"]=="FAMILY_NOT_ADMITTED","NO_ADMISSION_ESCALATION")
    report={"schema":"tacit-b.abc-bond-intake.v1","a_manifest_sha256":f.sha(data),"c_review_sha256":m["c_review_sha256"],
            "b_ranking_sha256":f.sha(rank_raw),"b_electrical_sha256":f.sha(a.electrical.read_bytes()),
            "typed_bonds":sorted([list(x) for x in pairs]),"incompatibility_count":len(m["incompatible_bonds"]),
            "state":"MATCHED_CANDIDATE_METADATA_TO_ACTUAL_PRE_ADMISSION_EXECUTION",
            "admission":"UNCHANGED","redistribution":"BLOCKED","independent_manifest_review":"SEPARATE"}
    a.out.write_bytes(f.canonical(report))
    print(f.canonical(report).decode(),end="")

if __name__=="__main__":main()

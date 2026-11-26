"""Fourth-turn bounded integration; reuses 1b, 3b, 5b and 8, no admission authority."""
import argparse
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

NEAREST_INSTRUCTION = ("Find the nearest candidate substation at or above 132 kV, "
                       "then calculate geographical distance and initial bearing to that point.")
ORIENT_INSTRUCTION = "Calculate the distance and initial bearing between two points"

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def refusal(fn):
    try:
        fn()
    except ValueError as exc:
        return str(exc)
    raise AssertionError("expected refusal")

def load_bond(path):
    spec = importlib.util.spec_from_file_location("tacit3b_bond", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    p = argparse.ArgumentParser()
    for key in ("factory", "app", "nearest", "activation", "archive", "receipt", "out"):
        p.add_argument("--"+key, type=Path, required=True)
    a = p.parse_args()
    sys.path[:0] = [str(a.factory/"tools"), str(a.app/"tools")]
    import package_factory as f
    import typed_package_execution as t
    from tacit5b_activation import Activation
    bond = load_bond(a.nearest/"packages/nearest-candidate/kuiper_bond.py")
    fixture_raw = (a.nearest/"packages/nearest-candidate/consumer-fixture.json").read_bytes()
    fixture = f.strict(fixture_raw)
    request = fixture["input"]
    request_digest = bond.sha(bond.canonical(request))
    raw = a.archive.read_bytes()
    receipt_raw = a.receipt.read_bytes()
    receipt = f.strict(receipt_raw)
    need(f.sha(raw)==t.ARCHIVE, "ARCHIVE_PIN")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        package = {i.filename:z.read(i) for i in z.infolist()}
    activation = Activation(a.activation, package)
    # Explicit, separately supplied coordinate inputs; never use the fixture's
    # expected nearest result as a runtime output or derive a cable length.
    inputs = {"crs":"WGS84","unit":"degrees",
              "point_a":{"longitude":0,"latitude":0},
              "point_b":{"longitude":1,"latitude":0}}
    q = {"schema":t.SCHEMA,"family":"orient","export":"orient",
         "descriptor_sha256":t.DESCRIPTOR,"archive_sha256":t.ARCHIVE,
         "ports":dict(t.PORTS),"input":inputs}
    full = activation.resolve({"instruction":NEAREST_INSTRUCTION,"inputs":inputs,"key":""})
    need(full["state"]=="REFUSED" and full["reason"]=="UNSUPPORTED_INTENT_OR_UNADMITTED_FAMILY",
         "FULL_INSTRUCTION_NOT_REFUSED")
    nearest_gate = refusal(lambda:t.request({**q,"family":"nearest-substation","export":"nearestSubstation"}))
    need(nearest_gate=="NEAREST_NOT_ADMITTED","NEAREST_GATE_CHANGED")
    electrical = f.strict((a.factory/"packages/factory/pending/electrical.json").read_bytes())
    electrical_gate = refusal(lambda:f.admit(electrical))
    need(electrical_gate=="SOURCE_RECEIPT_PENDING","ELECTRICAL_GATE_CHANGED")
    semantic = activation.resolve({"instruction":ORIENT_INSTRUCTION,"inputs":inputs,"key":""})
    need(semantic["state"]=="PLAN_PROPOSED" and semantic["selected_meaning"]=="GG2050-VEDIC-000006",
         "ORIENT_PLAN")
    graph = semantic["graph"]
    need(graph["args"]==[0,0,1,0] and graph["outputs"]=={"distance_km":"km","initial_bearing_deg":"degrees"},
         "ORIENT_PORTS")
    actual = t.execute(q,raw,receipt)
    output = actual["pattern"]["output"]
    need(abs(output["distance_km"]-111.31949079327356)<=1e-8 and
         abs(output["initial_bearing_deg"]-90)<=1e-8,"REFERENCE_MISMATCH")
    # Bond regression uses an explicitly labelled synthetic contract assertion.
    # No candidate runtime is called and no nearest ID is emitted as a result.
    expected = fixture["expected"]
    need(bond.selected_location(request,expected,request_digest)==inputs,"BOND_FIXTURE_CONTRACT")
    tests = {}
    def check(name,fn,reason):
        got=refusal(fn)
        need(got==reason,name+":"+got)
        tests[name]=got
    check("null_candidate",lambda:bond.selected_location(request,None,request_digest),"NO_ELIGIBLE_RECORD")
    changed=copy.deepcopy(request);changed["records"].append(changed["records"][0])
    check("duplicate_id",lambda:bond.selected_location(changed,expected,bond.sha(bond.canonical(changed))),"MISSING_OR_DUPLICATE_ID")
    check("stale_dataset",lambda:bond.selected_location(changed,expected,request_digest),"INPUT_DIGEST_MISMATCH")
    check("unknown_id",lambda:bond.selected_location(request,{"id":"absent","distance_km":1},request_digest),"SELECTED_ID_NOT_IN_DATASET")
    check("invalid_distance",lambda:bond.selected_location(request,{"id":"eligible","distance_km":"1 km"},request_digest),"DISTANCE_UNIT_OR_VALUE")
    check("wrong_units",lambda:t.request({**q,"input":{**inputs,"unit":"radians"}}),"INPUT_UNITS")
    check("unknown_export",lambda:t.request({**q,"export":"arbitrary"}),"EXPORT_NOT_ADMITTED")
    check("tampered_archive",lambda:t.execute(q,raw+b"x",receipt),"ARCHIVE_PIN")
    check("missing_receipt",lambda:t.execute(q,raw,{}),"BUILD_RECEIPT")
    check("forged_receipt",lambda:t.execute(q,raw,{**receipt,"archive_sha256":"0"*64}),"BUILD_RECEIPT")
    check("unknown_key",lambda:activation.resolve({"instruction":ORIENT_INSTRUCTION,"inputs":inputs,"key":"999"}),"UNKNOWN_KUIPER_KEY")
    # Distinct input contract for engineering: no geodesic output consumed.
    report = {"schema":"tacit-b.composition-receipt.v1","fixture_sha256":f.sha(fixture_raw),
              "caller_dataset_sha256":request_digest,"nearest":{"state":"REFUSED","reason":nearest_gate,
              "semantic_reason":full["reason"],"selected_id":None,"output":None},
              "bond_contract":"SYNTHETIC_EXPECTED_RESULT_ONLY_NOT_EXECUTED",
              "orient_fallback":{"input_provenance":"explicit independent synthetic coordinates",
              "semantic_plan":graph,"source_records":semantic["rows"],"execution":actual,
              "build_receipt_sha256":f.sha(receipt_raw)},
              "electrical":{"state":"REFUSED","reason":electrical_gate,
              "route_length_source":"caller supplied one-way cable route only","geodesic_transfer":False,
              "power_and_energy_distinct":True},"negative_checks":tests,
              "independent_acceptance":False,"redistribution":"BLOCKED"}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_bytes(f.canonical(report))
    print(json.dumps({"nearest":nearest_gate,"electrical":electrical_gate,"orient":output,
                      "negative_checks":len(tests),"receipt_sha256":f.sha(a.out.read_bytes())},sort_keys=True))

if __name__=="__main__":
    main()

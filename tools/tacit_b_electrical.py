"""Exercise existing electrical exports as conditional pre-admission bonds."""
import argparse,copy,json,os,subprocess,sys,tempfile
from pathlib import Path
from tacit_b_composition import need,refusal

def execute(f,d,root,request):
    # Context is mandatory rather than guessed from a naked numerical length/current.
    f.keys(request,("route","current","phases","nominalVolts","nominalVoltageBasis","resistanceOhmPerKm","reactanceOhmPerKm","powerFactor","lossLoadFactor","factorBasis","hours"))
    r=request["route"];i=request["current"]
    need(r.get("quantity")=="one_way_conductor_route_length" and r.get("unit")=="m" and r.get("origin")=="explicit_caller_input","NOT_ROUTE_LENGTH")
    need(i.get("quantity")=="conductor_current_rms" and i.get("unit")=="A" and i.get("context")=="explicit_peak_model_current","PEAK_CONTEXT_REQUIRED")
    need(request["factorBasis"]=="loss-load-factor","FACTOR_BASIS_MISMATCH")
    data,pins=f.verified_inputs(d,root)
    with tempfile.TemporaryDirectory(prefix="vedic-electrical-bond-") as tmp:
        tmp=Path(tmp);pkg=tmp/"node_modules"/d["name"];pkg.mkdir(parents=True)
        for name,raw in {"voltage-drop.mjs":data["module"],"adapter.mjs":data["adapter"],"index.mjs":f.ELECTRICAL_INDEX,
                         "package.json":f.canonical({"name":d["name"],"private":True,"type":"module","exports":{".":"./index.mjs"}})}.items():
            (pkg/name).write_bytes(raw)
        (tmp/"input.json").write_bytes(f.canonical(request))
        (tmp/"run.mjs").write_text("""import * as e from '@ventus-internal/vedic-electrical';
import * as direct from './node_modules/@ventus-internal/vedic-electrical/index.mjs';
import {readFileSync} from 'node:fs';
if(Object.keys(e).some(k=>e[k]!==direct[k]))throw Error('import mismatch');
const x=JSON.parse(readFileSync('input.json','utf8'));
const wire={mode:'ac-rms',phases:x.phases,currentA:x.current.value,lengthM:x.route.value,resistanceOhmPerKm:x.resistanceOhmPerKm,resistanceBasis:'caller-specified-operating-resistance'};
try{
 const drop=e.voltageDropVolts({...wire,reactanceOhmPerKm:x.reactanceOhmPerKm,powerFactor:x.powerFactor,powerFactorBasis:'lagging-or-unity'});
 const percent=e.dropPercent({mode:'ac-rms',phases:x.phases,nominalVoltageBasis:x.nominalVoltageBasis,dropVolts:drop.value,nominalVolts:x.nominalVolts});
 const loss=e.lossesWatts(wire);
 const energy=e.annualLossKwh({peakLossWatts:loss.value,lossLoadFactor:x.lossLoadFactor,hours:x.hours,factorBasis:x.factorBasis});
 console.log(JSON.stringify({ok:true,drop,percent,loss,energy}));
}catch(e){console.log(JSON.stringify({ok:false}));}
""")
        result=f.strict(subprocess.check_output(["node","--no-addons","run.mjs"],cwd=tmp,env={"PATH":os.environ["PATH"]},timeout=20))
    need(result["ok"] is True,"ELECTRICAL_INPUT_REFUSED")
    return {"schema":"tacit-b.electrical-pre-admission.v1","state":"PRE_ADMISSION_EXECUTED",
            "request":request,"request_sha256":f.sha(f.canonical(request)),"descriptor_sha256":f.sha(f.canonical(d)),
            "source_pins":pins,"outputs":{k:v for k,v in result.items() if k!="ok"},
            "admission":"SOURCE_RECEIPT_PENDING","archive":None,"independent_acceptance":False,"redistribution":"BLOCKED"}

def main():
    p=argparse.ArgumentParser()
    for k in ("factory","inputs","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.factory/"tools"))
    import package_factory as f
    d=f.strict((a.factory/"packages/factory/pending/electrical.json").read_bytes())
    need(refusal(lambda:f.admit(d))=="SOURCE_RECEIPT_PENDING","ADMISSION_CHANGED")
    request={"route":{"quantity":"one_way_conductor_route_length","unit":"m","origin":"explicit_caller_input","value":1000},
             "current":{"quantity":"conductor_current_rms","unit":"A","context":"explicit_peak_model_current","value":100},
             "phases":"three","nominalVolts":400,"nominalVoltageBasis":"line-to-line","resistanceOhmPerKm":0.2,
             "reactanceOhmPerKm":0,"powerFactor":1,"lossLoadFactor":0.5,"factorBasis":"loss-load-factor","hours":8760}
    def run(x):return execute(f,d,a.inputs,x)
    result=run(request);need(result==run(request),"NONDETERMINISTIC")
    vals={k:v["value"] for k,v in result["outputs"].items()}
    expected={"drop":34.64101615137755,"percent":8.660254037844387,"loss":6000,"energy":26280}
    need(all(abs(vals[k]-v)<=1e-8 for k,v in expected.items()),"REFERENCE")
    checks={}
    def reject(name,mut,reason):
        q=copy.deepcopy(request);mut(q);need(refusal(lambda:run(q))==reason,name);checks[name]=reason
    reject("geodesic_to_route",lambda q:q["route"].update(quantity="geographical_distance"),"NOT_ROUTE_LENGTH")
    reject("kilometres_to_metres",lambda q:q["route"].update(unit="km"),"NOT_ROUTE_LENGTH")
    reject("mean_current",lambda q:q["current"].update(context="mean_current"),"PEAK_CONTEXT_REQUIRED")
    reject("energy_as_power",lambda q:q["current"].update(quantity="annual_energy_loss",unit="kWh"),"PEAK_CONTEXT_REQUIRED")
    reject("ordinary_load_factor",lambda q:q.update(factorBasis="ordinary-load-factor"),"FACTOR_BASIS_MISMATCH")
    reject("wrong_voltage_basis",lambda q:q.update(nominalVoltageBasis="across-supply"),"ELECTRICAL_INPUT_REFUSED")
    reject("invalid_power_factor",lambda q:q.update(powerFactor=1.1),"ELECTRICAL_INPUT_REFUSED")
    reject("invalid_hours",lambda q:q.update(hours=9000),"ELECTRICAL_INPUT_REFUSED")
    result["checks"]=checks;result["reproducible"]=True
    a.out.write_bytes(f.canonical(result))
    print(json.dumps({"outputs":vals,"checks":len(checks),"sha256":f.sha(a.out.read_bytes()),"admission":result["admission"]},sort_keys=True))

if __name__=="__main__":main()

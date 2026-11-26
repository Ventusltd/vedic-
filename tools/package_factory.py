"""Additive descriptor-driven internal package factory. No network acquisition or publishing."""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import zipfile

LIMIT = 2 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
ADMISSIONS = {"orient": ROOT / "packages/factory/admissions/orient.json"}
PENDING = {"electrical": ROOT / "packages/factory/pending/electrical.json",
           "nearest-substation": ROOT / "packages/factory/pending/nearest-substation.json",
           "solar-shape": ROOT / "packages/factory/pending/solar-shape.json"}
TOP = "schema candidate name version runtime family edition identity_tier licence exports ports dependencies inputs evidence obligations build".split()
INPUT = "role filename repo commit path algorithm digest output".split()
RESERVED = {"package.json", "manifest.json", "index.mjs", "README.md"}

class Refusal(ValueError):
    pass

def need(ok, code):
    if not ok:
        raise Refusal(code)

def unique(pairs):
    out = {}
    for key, val in pairs:
        need(key not in out, "DUPLICATE_KEY")
        out[key] = val
    return out

def strict(raw):
    need(len(raw) <= LIMIT, "INPUT_SIZE")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda _: need(False, "NONFINITE_JSON"))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as e:
        raise Refusal("INVALID_JSON") from e

def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def digest(raw, alg):
    if alg == "sha256":
        return sha(raw)
    need(alg == "git-blob-sha1", "DIGEST_ALGORITHM")
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def match(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None

def keys(value, expected):
    need(isinstance(value, dict) and set(value) == set(expected), "FIELDS")

def portable(name):
    # v1 deliberately restricts output to flat portable ASCII filenames.
    need(match(name, r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}") and
         not name.endswith(".") and name.split(".")[0].upper() not in
         {"CON", "PRN", "AUX", "NUL", *("COM"+str(i) for i in range(1,10)),
          *("LPT"+str(i) for i in range(1,10))}, "UNSAFE_PATH")
    return name.casefold()

def strings(value):
    need(isinstance(value, list) and bool(value) and
         all(isinstance(x, str) and 0 < len(x) <= 512 for x in value), "STRING_LIST")
    need(len(set(value)) == len(value), "DUPLICATE_VALUE")

def validate(d):
    keys(d, TOP)
    need(d["schema"] == "vedic.package-descriptor.v1", "SCHEMA")
    need(match(d["candidate"], r"local:[a-z0-9-]+:[a-z0-9-]+"), "CANDIDATE")
    need(match(d["name"], r"@ventus-internal/[a-z0-9-]+"), "PACKAGE_NAME")
    need(match(d["version"], r"[0-9]+\.[0-9]+\.[0-9]+"), "VERSION")
    need(match(d["family"], r"[a-z0-9-]+"), "FAMILY")
    need(d["runtime"] == "node-esm-18" and d["dependencies"] == [], "RUNTIME")
    need(match(d["edition"], r"[0-9a-f]{40}"), "EDITION")
    need(d["identity_tier"] in ("GIT_SOURCE_VERIFIED_STARS_INCOMPLETE",
         "MODULAR_STAR_JOINED", "INDEPENDENTLY_VERIFIED", "SYNTHETIC_TEST_ONLY"), "TIER")
    need(d["licence"] == "BLOCKED_PRIVATE_UNLICENSED", "LICENCE")
    need(d["build"] == "reviewed-family-adapter-v1", "BUILD")
    for field in ("exports", "evidence", "obligations"):
        strings(d[field])
    need(all(match(x, r"[A-Za-z_$][A-Za-z0-9_$]*") for x in d["exports"]), "EXPORT")
    need(all(x.startswith("https://github.com/Ventusltd/") for x in d["evidence"]), "EVIDENCE")
    keys(d["ports"], ("input", "output"))
    for ports in d["ports"].values():
        need(isinstance(ports, dict) and ports and all(
            match(k, r"[A-Za-z_][A-Za-z0-9_]*") and isinstance(v,str) and
            0 < len(v) <= 256 for k,v in ports.items()), "PORTS")
    need(isinstance(d["inputs"], list) and 1 <= len(d["inputs"]) <= 32, "INPUTS")
    roles, names, outputs = set(), set(), {x.casefold() for x in RESERVED}
    for item in d["inputs"]:
        keys(item, INPUT)
        role = item["role"]
        need(match(role, r"[a-z][a-z0-9_-]*") and role not in roles, "ROLE")
        roles.add(role)
        name = portable(item["filename"])
        need(name not in names, "PATH_COLLISION")
        names.add(name)
        need(match(item["repo"], r"Ventusltd/[A-Za-z0-9_.-]+") and
             match(item["commit"], r"[0-9a-f]{40}"), "SOURCE_PIN")
        p = item["path"]
        need(isinstance(p,str) and 0 < len(p) <= 512 and all(
            portable(s) for s in p.split("/")), "SOURCE_PATH")
        alg = item["algorithm"]
        need(alg in ("sha256", "git-blob-sha1"), "DIGEST_ALGORITHM")
        need(match(item["digest"], r"[0-9a-f]{64}" if alg=="sha256" else r"[0-9a-f]{40}"),
             "DIGEST")
        if item["output"] is not None:
            name = portable(item["output"])
            need(name not in outputs, "PATH_COLLISION")
            outputs.add(name)
    need("licence" in roles and "receipt" in roles, "REQUIRED_INPUT")
    need(all(next(i for i in d["inputs"] if i["role"]==r)["output"] is not None
             for r in ("licence","receipt")), "REQUIRED_OUTPUT")
    return d

def read_file(root, name):
    portable(name)
    need(root.is_dir() and not root.is_symlink(), "INPUT_ROOT")
    path = root / name
    need(path.is_file() and not path.is_symlink(), "MISSING_OR_SYMLINK")
    # open without following final symlink; bounded read even if size changes.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as f:
        need(stat.S_ISREG(os.fstat(f.fileno()).st_mode), "NOT_REGULAR")
        raw = f.read(LIMIT + 1)
    need(len(raw) <= LIMIT, "INPUT_SIZE")
    return raw

def admit(d):
    if isinstance(d,dict) and d.get("family") == "electrical" and "electrical" not in ADMISSIONS:
        raise Refusal("SOURCE_RECEIPT_PENDING")
    validate(d)
    need(d["family"] in ADMISSIONS, "FAMILY_NOT_ADMITTED")
    trusted = validate(strict(ADMISSIONS[d["family"]].read_bytes()))
    need(canonical(d) == canonical(trusted), "ADMISSION_MISMATCH")
    return d

def verified_inputs(d, root):
    data, pins = {}, []
    for item in d["inputs"]:
        raw = read_file(root, item["filename"])
        actual = digest(raw, item["algorithm"])
        need(actual == item["digest"], "INPUT_DIGEST:" + item["role"])
        data[item["role"]] = raw
        pins.append({**item, "observed_digest": actual, "observed_sha256": sha(raw),
                     "bytes": len(raw)})
    return data, pins

def orient_adapter(d, data):
    # Extract reviewed literal strings, never execute the downloaded Python.
    # The AST and receipt are admitted by independent immutable digest pins.
    r = strict(data["receipt"])
    need(r["schema"] == "vedic.orient-module-receipt.v1" and
         r["dictionary_commit"] == d["edition"] and
         r["module_sha256"] == sha(data["module"]) and
         r["tier"] == d["identity_tier"] and r["identity_complete"] is False and
         r["execution_verified"] is False and
         r["composition"] == "GG2050-VEDIC-000006", "RECEIPT")
    tree = ast.parse(data["prototype"].decode("utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            if node.targets[0].id in ("ADAPTER", "README"):
                values[node.targets[0].id] = ast.literal_eval(node.value)
    runtime = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="runtime")
    scripts = [ast.literal_eval(n.args[0]) for n in ast.walk(runtime)
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
               and n.func.attr=="write_text"]
    need(set(values)=={"ADAPTER","README"} and len(scripts)==1, "ADAPTER_CONTRACT")
    # Candidate version differs, preserve mathematics and exact original adapter.
    readme = values["README"].replace("research package 0.1.0","research package "+d["version"])
    return values["ADAPTER"].encode(), readme.encode(), scripts[0]

def electrical_adapter(d, data):
    # Only a future exact reviewed admission may reach this handler.
    # Receipt schema/contents must be reviewed before lifting this gate.
    need("receipt" in data, "SOURCE_RECEIPT_PENDING")
    raise Refusal("ELECTRICAL_RECEIPT_REVIEW_REQUIRED")

ELECTRICAL_INDEX = b"export {annualLossKwh, dropPercent, lossesWatts, voltageDropVolts} from './adapter.mjs';\n"

def electrical_runtime(d, package, root, test_script, peer_consumer=None):
    """Run pinned peer tests unmodified plus both consumer import surfaces."""
    test_path = package / "factory-peer-test.mjs"
    need(not test_path.exists(), "TEST_PATH_COLLISION")
    test_path.write_text(test_script, encoding="utf-8")
    env = {"PATH":os.environ["PATH"]}
    tap = subprocess.check_output(["node","--no-addons","--test",str(test_path)],
                                  cwd=root,text=True,timeout=25,env=env)
    total = re.search(r"(?m)^# tests (\d+)$",tap)
    passed = re.search(r"(?m)^# pass (\d+)$",tap)
    failed = re.search(r"(?m)^# fail (\d+)$",tap)
    need(total and passed and failed and total.group(1)==passed.group(1)
         and int(total.group(1))>=51 and failed.group(1)=="0", "ELECTRICAL_TEST_COUNT")
    script = """import assert from 'node:assert/strict';
import * as api from '@ventus-internal/vedic-electrical';
import * as direct from './node_modules/@ventus-internal/vedic-electrical/index.mjs';
assert.deepEqual(Object.keys(api).sort(),['annualLossKwh','dropPercent','lossesWatts','voltageDropVolts']);
for(const key of Object.keys(api)) assert.equal(api[key],direct[key]);
const wire={mode:'ac-rms',phases:'three',currentA:100,lengthM:1000,resistanceOhmPerKm:0.2,resistanceBasis:'caller-specified-operating-resistance'};
const drop=api.voltageDropVolts({...wire,reactanceOhmPerKm:0,powerFactor:1,powerFactorBasis:'lagging-or-unity'});
const loss=api.lossesWatts(wire);
const annual=api.annualLossKwh({peakLossWatts:loss.value,lossLoadFactor:0.5,hours:8760,factorBasis:'loss-load-factor'});
const percent=api.dropPercent({mode:'ac-rms',phases:'three',nominalVoltageBasis:'line-to-line',dropVolts:drop.value,nominalVolts:400});
assert.ok(Math.abs(drop.value-34.64101615137755)<1e-10);
assert.equal(loss.value,6000); assert.equal(annual.value,26280);
assert.ok(Math.abs(percent.value-8.660254037844387)<1e-10);
console.log(JSON.stringify({voltage_drop_V:drop.value,loss_W:loss.value,annual_loss_kWh:annual.value,drop_percent:percent.value}));
"""
    (root/"consumer.mjs").write_text(script,encoding="utf-8")
    result = strict(subprocess.check_output(["node","--no-addons","consumer.mjs"],
                    cwd=root,text=True,timeout=20,env=env).encode())
    peer = None
    if peer_consumer is not None:
        (root/"peer-consumer.mjs").write_bytes(peer_consumer)
        peer = strict(subprocess.check_output(["node","--no-addons","peer-consumer.mjs"],cwd=root,text=True,timeout=20,env=env).encode())
        need(peer.get("state")=="PACKAGE_DEVELOPMENT_CHECKS_PASS" and peer.get("invalid_cases")==3,"PEER_CONSUMER")
    return {"state":"PACKAGE_DEVELOPMENT_CHECKS_PASS","peer_consumer":peer,"peer_tests":int(total.group(1)),
            "clean_imports":["direct","package-name"],"known_answer":result}

def pending_electrical_probe(root):
    """Separable development proof, never emits an archive or admission."""
    d = strict(PENDING["electrical"].read_bytes())
    need("electrical" not in ADMISSIONS, "PENDING_ALREADY_ADMITTED")
    try:
        admit(d)
    except Refusal as e:
        need(str(e)=="SOURCE_RECEIPT_PENDING", "WRONG_REFUSAL")
    else:
        raise Refusal("MISSING_RECEIPT_ACCEPTED")
    data,pins=verified_inputs(d,root)
    need(digest(data["module"],"git-blob-sha1")==
         "85f48ecf7effabb47973b0a056f90e82b8196ef2","SOURCE_BLOB")
    with tempfile.TemporaryDirectory(prefix="vedic-electrical-pending-") as tmp:
        clean=Path(tmp)
        package=clean/"node_modules"/d["name"]
        package.mkdir(parents=True)
        for name,raw in {"voltage-drop.mjs":data["module"],"adapter.mjs":data["adapter"],
                         "index.mjs":ELECTRICAL_INDEX,
                         "package.json":canonical({"name":d["name"],"type":"module","private":True,
                                     "exports":{".":"./index.mjs"},"license":"UNLICENSED"})}.items():
            (package/name).write_bytes(raw)
        checks=electrical_runtime(d,package,clean,data["tests"].decode("utf-8"),data["consumer"])
    return {"state":"PRE_ADMISSION_DEVELOPMENT_PROOF_ONLY","archive_produced":False,
            "admission":"SOURCE_RECEIPT_PENDING","independent_acceptance":False,
            "redistribution":"BLOCKED","input_pins":pins,"consumer_checks":checks}

ADAPTERS = {"orient": orient_adapter, "electrical": electrical_adapter}

# No real electrical/nearest receipt pins are yet authorised. A structurally
# valid receipt, even from a peer branch, cannot add itself to this registry.
REVIEWED_RECEIPTS = {}

def review_receipt(family, raw, source_files, closure_raw):
    need(family in REVIEWED_RECEIPTS, "REVIEWED_RECEIPT_NOT_PINNED")
    pin=REVIEWED_RECEIPTS[family]
    need(sha(raw)==pin["receipt_sha256"],"RECEIPT_DIGEST")
    need(sha(closure_raw)==pin["closure_sha256"],"CLOSURE_DIGEST")
    receipt=strict(raw); closure=strict(closure_raw)
    # No guessed general producer schema: exact reviewed schema/validator
    # must be registered together with independent pins.
    need(receipt.get("schema")==pin["schema"],"RECEIPT_SCHEMA")
    need({k:sha(v) for k,v in source_files.items()}==pin["source_sha256"],"RECEIPT_SOURCE")
    need(closure.get("schema")==pin["closure_schema"],"CLOSURE_SCHEMA")
    need(pin["validate"](receipt,closure) is True,"RECEIPT_CONTRACT")
    return receipt

def nearest_adapter(d,data):
    need("receipt" in data and "closure" in data,"NEAREST_RECEIPTS_PENDING")
    review_receipt("nearest-substation",data["receipt"],
                   {"v9-nearest-search.js":data["module"],"v9-geodesy.js":data["local_dependency"]},
                   data["closure"])
    raise Refusal("NEAREST_ADMISSION_REVIEW_REQUIRED")

ADAPTERS["nearest-substation"]=nearest_adapter

def assemble(d, root):
    admit(d)
    data, pins = verified_inputs(d, root)
    adapter, readme, consumer = ADAPTERS[d["family"]](d,data)
    payload = {i["output"]:data[i["role"]] for i in d["inputs"] if i["output"] is not None}
    payload.update({"index.mjs":adapter, "README.md":readme,
                    "package.json":canonical({"name":d["name"],"version":d["version"],
                    "type":"module","private":True,"license":"UNLICENSED",
                    "engines":{"node":">=18"},"exports":{".":"./index.mjs"},"dependencies":{}})})
    roles = {i["output"]:i["role"] for i in d["inputs"] if i["output"] is not None}
    roles.update({"index.mjs":"adapter","README.md":"documentation","package.json":"runtime_manifest"})
    manifest = {"schema":"vedic.package-factory-manifest.v1","descriptor":d,
                "descriptor_sha256":sha(canonical(d)), "input_pins":pins,
                "independent_acceptance":False,"redistribution":"BLOCKED",
                "file_count":len(payload)+1,"public_exports":d["exports"],
                "files":[{"path":k,"role":roles[k],"sha256":sha(v),"bytes":len(v)}
                         for k,v in sorted(payload.items())]}
    payload["manifest.json"] = canonical(manifest)
    return payload, consumer

def archive(payload):
    seen = set()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_STORED) as z:
        for name, raw in sorted(payload.items()):
            folded = portable(name)
            need(folded not in seen, "PATH_COLLISION")
            seen.add(folded)
            need(len(raw)<=LIMIT, "INPUT_SIZE")
            entry=zipfile.ZipInfo(name,(1980,1,1,0,0,0))
            entry.create_system=3
            entry.external_attr=0o100644 << 16
            z.writestr(entry,raw)
    return buf.getvalue()

def verify(raw, expected):
    need(len(raw) <= 32*LIMIT, "ARCHIVE_SIZE")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=z.infolist()
            seen=set()
            for i in infos:
                name=portable(i.filename)
                need(name not in seen,"ARCHIVE_DUPLICATE")
                seen.add(name)
                need(i.create_system==3 and i.external_attr>>16==0o100644 and
                     i.date_time==(1980,1,1,0,0,0) and i.compress_type==zipfile.ZIP_STORED
                     and i.file_size<=LIMIT and not i.flag_bits & 1,"ARCHIVE_METADATA")
            need(z.namelist()==sorted(expected),"ARCHIVE_FILE_SET")
            for name, content in expected.items():
                need(z.read(name)==content,"ARCHIVE_BYTES")
            m=strict(z.read("manifest.json"))
            need(m["file_count"]==len(expected),"MANIFEST_COUNT")
            rows=m["files"]
            need(isinstance(rows,list) and len(rows)==len(expected)-1 and
                 len({r["path"] for r in rows})==len(rows),"MANIFEST_DUPLICATE")
            need({r["path"]:(r["sha256"],r["bytes"]) for r in rows}==
                 {k:(sha(v),len(v)) for k,v in expected.items() if k!="manifest.json"},
                 "MANIFEST_FILES")
    except (zipfile.BadZipFile, KeyError, TypeError) as e:
        raise Refusal("ARCHIVE_INVALID") from e

def run_consumer(d, raw, payload, script):
    verify(raw,payload)
    with tempfile.TemporaryDirectory(prefix="vedic-factory-consumer-") as tmp:
        root=Path(tmp)
        package=root/"node_modules"/d["name"]
        package.mkdir(parents=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for name in payload:
                (package/name).write_bytes(z.read(name))
        if d["family"]=="electrical":
            return electrical_runtime(d,package,root,script)
        expected=json.dumps(sorted(d["exports"]))
        prefix=("import assertFactory from 'node:assert/strict';\n"
                "import * as directFactory from './node_modules/"+d["name"]+"/index.mjs';\n"
                "assertFactory.deepEqual(Object.keys(directFactory).sort(),"+expected+");\n")
        (root/"consumer.mjs").write_text(prefix+script,encoding="utf-8")
        output=subprocess.check_output(["node","--no-addons","consumer.mjs"],cwd=root,
                                       text=True,timeout=20,env={"PATH":os.environ["PATH"]})
        return strict(output.encode())

def publish_local(out, raw):
    # Atomic no-overwrite link; a failed build never creates a final filename.
    need(out.parent.is_dir() and not out.parent.is_symlink(),"OUTPUT_ROOT")
    with tempfile.NamedTemporaryFile(dir=out.parent,delete=False) as f:
        tmp=Path(f.name)
        try:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
            os.link(tmp,out)
        finally:
            tmp.unlink()

def build(d, root, out):
    payload, script=assemble(d,root)
    raw=archive(payload)
    verify(raw,payload)
    checks=run_consumer(d,raw,payload,script)
    second, _=assemble(d,root)
    need(raw==archive(second),"NONREPRODUCIBLE")
    need(checks.get("state")=="PACKAGE_DEVELOPMENT_CHECKS_PASS","RUNTIME_CHECK")
    node_version=subprocess.check_output(["node","--version"],text=True).strip()
    publish_local(out,raw)
    return {"schema":"vedic.package-build-receipt.v1","state":"DEVELOPMENT_CHECKS_PASS",
            "descriptor_sha256":sha(canonical(d)),"archive_sha256":sha(raw),
            "archive_bytes":len(raw),"file_count":len(payload),"reproducible":True,
            "python":os.sys.version.split()[0],"node":node_version,
            "input_pins":strict(payload["manifest.json"])["input_pins"],
            "consumer_checks":checks,"independent_acceptance":False,
            "redistribution":"BLOCKED","obligations":d["obligations"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["validate","build","probe-pending-electrical"])
    p.add_argument("--descriptor",type=Path,required=True)
    p.add_argument("--inputs",type=Path)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    try:
        if a.action=="probe-pending-electrical":
            need(a.inputs is not None and a.out is None,"CLI_ARGUMENTS")
            need(a.descriptor.resolve()==PENDING["electrical"].resolve(),"PENDING_DESCRIPTOR")
            print(canonical(pending_electrical_probe(a.inputs)).decode(),end="")
            return
        d=admit(strict(read_file(a.descriptor.parent,a.descriptor.name)))
        if a.action=="validate":
            result={"state":"ADMITTED","descriptor_sha256":sha(canonical(d))}
        else:
            need(a.inputs is not None and a.out is not None,"CLI_ARGUMENTS")
            result=build(d,a.inputs,a.out)
        print(canonical(result).decode(),end="")
    except (Refusal,OSError,subprocess.SubprocessError,ValueError,KeyError) as e:
        print(json.dumps({"state":"REFUSED","reason":str(e)}),file=os.sys.stderr)
        raise SystemExit(1)

if __name__=="__main__":
    main()

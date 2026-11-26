"""Assemble and verify a clean local browser consumer; never redistribute software."""
import argparse
from functools import partial
import hashlib
import http.server
import io
import json
from pathlib import Path
import tempfile
import threading
import zipfile

PIN="ad4d0daa6cef5b30756184f44726b8a750e6a6d0eb31e2fea7fe6886a6b8669c"
FACTORY_PIN="e83937c040499a7060b03ca2c4969e4414cdca48cb7f28a3ef9039f002486787"
DESCRIPTOR_PIN="b45e61e955e0d0ddde15495f9be7c3fc4943c3193dd8f318a4249524f2fb5f53"
MODULE="af9b5a8796b51a1e4368491b98961a197adec539f2fa0f3ed226552a876864bb"
NAMES={"index.mjs","v9-geodesy.mjs","manifest.json","package.json","README.md","UPSTREAM-LICENSE","source-receipt.json"}
def digest(data): return hashlib.sha256(data).hexdigest()
def encode(obj): return (json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+"\n").encode()
def require(ok,msg):
    if not ok: raise ValueError(msg)
def zip_bytes(files):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_STORED) as z:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0))
            info.create_system=3; info.external_attr=0o100644<<16
            z.writestr(info,raw)
    return out.getvalue()
def verified(raw, factory_evidence=None):
    pin=digest(raw)
    require(pin in (PIN,FACTORY_PIN),"package digest mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        require(len(z.namelist())==len(NAMES) and set(z.namelist())==NAMES,"unexpected package entries")
        files={name:z.read(name) for name in NAMES}
    m=json.loads(files["manifest.json"])
    require(m["public_exports"]==["orient"] and digest(files["v9-geodesy.mjs"])==MODULE,"wrong export or source")
    require(m["redistribution"]=="BLOCKED" and m["independent_acceptance"] is False,"unexpected rights state")
    if pin==PIN:
        require(factory_evidence is None,"wrong receipt edition")
        require(m["files"]=={name:digest(data) for name,data in files.items() if name!="manifest.json"},"file digest mismatch")
        require(m["source_sha256"]==MODULE,"wrong source")
        entry={k:m[k] for k in ("name","version","source","identity_tier","input","outputs","vedic_ids","runtime")}
    else:
        require(factory_evidence is not None,"shared factory evidence required")
        manifest,receipt=factory_evidence
        require(manifest==files["manifest.json"],"factory evidence manifest mismatch")
        r=json.loads(receipt);d=m["descriptor"]
        canonical=(json.dumps(d,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(",",":"))+"\n").encode()
        require(m["schema"]=="vedic.package-factory-manifest.v1" and d["schema"]=="vedic.package-descriptor.v1","factory schema")
        require(digest(canonical)==m["descriptor_sha256"]==DESCRIPTOR_PIN==r["descriptor_sha256"],"descriptor pin")
        require(r["schema"]=="vedic.package-build-receipt.v1" and r["archive_sha256"]==pin and r["archive_bytes"]==len(raw) and r["state"]=="DEVELOPMENT_CHECKS_PASS" and r["reproducible"] is True and r["redistribution"]=="BLOCKED" and r["independent_acceptance"] is False,"factory receipt")
        require(r["input_pins"]==m["input_pins"] and m["file_count"]==r["file_count"]==len(files),"factory input pins/count")
        require(len(m["files"])==len(files)-1 and {x["path"]:(x["sha256"],x["bytes"]) for x in m["files"]}=={k:(digest(v),len(v)) for k,v in files.items() if k!="manifest.json"},"factory file digests")
        source=next(x for x in d["inputs"] if x["role"]=="module")
        require(source["digest"]==MODULE and d["family"]=="orient" and d["version"]=="0.2.0","factory source/version")
        entry={**{k:d[k] for k in ("name","version","identity_tier","runtime","candidate","licence")},"source":source,"input":d["ports"]["input"],"outputs":d["ports"]["output"],"descriptor_sha256":DESCRIPTOR_PIN,"build_receipt_sha256":digest(receipt)}
    entry.update(package_sha256=pin,manifest_sha256=digest(files["manifest.json"]),development_build="verified_exact_archive",browser_acceptance="see separate exact-run receipt",independent_acceptance=False,redistribution="BLOCKED",release_approval=False,public_readback=None)
    return files,entry
def build(raw,app,factory_evidence=None):
    package,entry=verified(raw,factory_evidence)
    catalogue={"schema":"vedic.consumer-catalogue.v2","packages":[entry],"capabilities":[
        {"family":"orient","state":"available_internal","package_sha256":entry["package_sha256"]},
        {"family":"electrical","state":"unavailable","reason":"Awaiting shared-factory admission and exact archive receipt","candidate_contract":"53d893e877b2287dc45faec4db87e30f418c2b5e","package_sha256":None},
        {"family":"nearest-substation","state":"unavailable","reason":"Awaiting admitted package"},
        {"family":"solar-geometry","state":"unavailable","reason":"Awaiting admitted package"}],
        "counts":{"exact_packages":1,"independently_accepted":0,"released":0}}
    files={"index.html":(app/"index.html").read_bytes(),"app.mjs":(app/"app.mjs").read_bytes(),"catalogue.json":encode(catalogue)}
    files.update({"package/"+k:v for k,v in package.items()})
    files["asset-manifest.json"]=encode({"schema":"vedic.consumer-assets.v1","files":{k:digest(v) for k,v in sorted(files.items())}})
    return files
def check_tree(root,expected):
    actual={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob("*") if p.is_file()}
    require(actual==expected,"clean consumer tree mismatch")
def server_for(root,activation=None,port=0):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_POST(self):
            if self.path!="/activate" or activation is None:
                self.send_error(404);return
            if self.headers.get("Origin")!=f"http://127.0.0.1:{self.server.server_port}":
                self.send_error(403);return
            try:
                n=int(self.headers.get("Content-Length","0"))
                require(0<n<=8192,"REQUEST_SIZE")
                require(self.headers.get("Content-Type")=="application/json","REQUEST_TYPE")
                body=activation.resolve(json.loads(self.rfile.read(n)))
            except (ValueError,KeyError,TypeError) as e:
                body={"state":"REFUSED","reason":str(e),"rows":[]}
            raw=encode(body)
            self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    return http.server.ThreadingHTTPServer(("127.0.0.1",port),partial(Handler,directory=str(root)))
def assert_layout(page,stage):
    metrics=page.evaluate("""() => {
        const width=innerWidth, doc=document.documentElement;
        return {width,scrollWidth:doc.scrollWidth,bodyWidth:document.body.scrollWidth,
          offenders:[...document.querySelectorAll('body *')].map(e=>{
            const r=e.getBoundingClientRect();
            return {tag:e.tagName,id:e.id,left:Math.round(r.left),right:Math.round(r.right),scroll:e.scrollWidth,client:e.clientWidth};
          }).filter(r=>r.right>width+1||r.left< -1).slice(0,12)};
    }""")
    require(page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
            f"horizontal overflow at {stage}: {json.dumps(metrics,sort_keys=True)}")
    require(metrics["bodyWidth"]<=metrics["width"],f"body overflow at {stage}: {metrics}")
    return {"stage":stage,"viewport_width":metrics["width"],"document_width":metrics["scrollWidth"]}

def browser_checks(root,expected,activation=None):
    from playwright.sync_api import sync_playwright
    server=server_for(root,activation)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    base=f"http://127.0.0.1:{server.server_port}"
    receipts=[]
    try:
        with sync_playwright() as p:
            for kind in ("chromium","webkit"):
                browser=getattr(p,kind).launch()
                for width,height in [(1280,800),(390,844)]:
                    context=browser.new_context(viewport={"width":width,"height":height},service_workers="block")
                    page=context.new_page(); errors=[]; denied=[]; imports={}
                    def route(r):
                        if r.request.url.startswith(base+"/"): r.continue_()
                        else: denied.append(r.request.url);r.abort()
                    page.route("**/*",route)
                    page.on("pageerror",lambda e:errors.append(str(e)))
                    page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
                    def response(r):
                        name=r.url.removeprefix(base+"/")
                        if name in ("package/index.mjs","package/v9-geodesy.mjs"): imports[name]=r
                    page.on("response",response)
                    page.goto(base+"/")
                    button=page.locator("#calculate"); result=page.locator("#result")
                    from playwright.sync_api import expect
                    expect(button).to_be_enabled()
                    layout=[assert_layout(page,'initial')]
                    expect(page.locator("#electrical-calculate")).to_be_disabled()
                    page.locator("#electrical").evaluate("(f)=>f.dispatchEvent(new Event('submit',{cancelable:true}))")
                    expect(page.locator("#electrical-result")).to_have_text("Unavailable: no admitted electrical package.")
                    expect(page.locator("#evidence")).to_contain_text(json.loads(expected["catalogue.json"])["packages"][0]["version"])
                    button.focus(); button.press("Enter")
                    expect(result).to_have_text("111.319490793 km\n90.000000° initial bearing",use_inner_text=True)
                    page.locator("#a-lon").fill("1");page.locator("#b-lon").fill("0")
                    expect(result).to_have_text("Inputs changed. Calculate again.")
                    button.click();expect(result).to_have_text("111.319490793 km\n270.000000° initial bearing",use_inner_text=True)
                    page.locator("#b-lon").fill("-1");button.click()
                    expect(result).to_have_text("222.638981587 km\n270.000000° initial bearing",use_inner_text=True)
                    for invalid in ("1","181",""):
                        page.locator("#b-lon").fill(invalid);button.click()
                        expect(result).to_contain_text("Cannot calculate:")
                        require(" km" not in result.inner_text(),"stale result")
                    page.locator("#b-lon").fill("0");button.click()
                    expect(result).to_have_text("111.319490793 km\n270.000000° initial bearing",use_inner_text=True)
                    if activation is not None:
                        page.locator("#instruction").fill("Calculate the distance and initial bearing between two points")
                        page.locator("#activate").click()
                        expect(page.locator("#activation-state")).to_contain_text("EXECUTED_INTERNAL")
                        expect(page.locator("#activation-state")).to_contain_text("270.000000°")
                        expect(page.locator("#activation-evidence")).to_contain_text("86415575118")
                        expect(page.locator("#activation-evidence")).to_contain_text("86415575222")
                        layout.append(assert_layout(page,"populated source evidence"))
                        page.locator("#b-lon").fill("-1")
                        expect(page.locator("#activation-state")).to_have_text("Inputs changed. Activate again.")
                        page.locator("#activate").click()
                        expect(page.locator("#activation-state")).to_contain_text("222.638981587 km")
                        layout.append(assert_layout(page,"changed input result"))
                        page.locator("#kuiper-key").fill("86415575118")
                        page.locator("#activate").click()
                        expect(page.locator("#activation-state")).to_contain_text("EXECUTED_INTERNAL")
                        page.locator("#kuiper-key").fill("999")
                        page.locator("#activate").click()
                        expect(page.locator("#activation-state")).to_contain_text("UNKNOWN_KUIPER_KEY")
                        layout.append(assert_layout(page,"unknown key refusal"))
                        page.locator("#kuiper-key").fill("")
                        page.locator("#instruction").fill("Find the nearest candidate substation at or above 132 kV, then calculate geographical distance and initial bearing")
                        page.locator("#activate").click()
                        expect(page.locator("#activation-state")).to_contain_text("UNSUPPORTED_INTENT_OR_UNADMITTED_FAMILY")
                        expect(page.locator("#activation-state")).not_to_contain_text(" km")
                        bad=page.evaluate("""async()=>await (await fetch('/activate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instruction:'Calculate the distance and initial bearing between two points',key:'',inputs:{crs:'WGS84',unit:'radians',point_a:{longitude:0,latitude:0},point_b:{longitude:1,latitude:0}}})})).json()""")
                        require(bad["state"]=="REFUSED" and "unit" in bad["reason"],"incompatible units accepted")
                    layout.append(assert_layout(page,"final state"))
                    require(set(imports)=={"package/index.mjs","package/v9-geodesy.mjs"},"missing actual module request")
                    observed={k:digest(r.body()) for k,r in imports.items()}
                    require(observed=={k:digest(expected[k]) for k in imports},"served import hash mismatch")
                    require(not errors and not denied,f"errors={errors} external_requests={denied}")
                    receipts.append({"browser":kind,"version":browser.version,"viewport":[width,height],"state":"PASS","import_sha256":observed,"known_answers":3,"invalid_cases":3,"electrical_refusal":True,"semantic_activation_tested":activation is not None,"layout_checks":layout})
                    context.close()
                browser.close()
    finally:
        server.shutdown();server.server_close();worker.join()
    return receipts
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--package",type=Path,required=True);p.add_argument("--app",type=Path,required=True);p.add_argument("--evidence",type=Path,required=True)
    p.add_argument("--factory-evidence",type=Path)
    p.add_argument("--activation-input",type=Path)
    p.add_argument("--serve",action="store_true",help="Run the verified app on loopback rather than automated browser tests")
    a=p.parse_args();raw=a.package.read_bytes()
    evidence=None
    if a.factory_evidence:
        blob=a.factory_evidence.read_bytes()
        require(digest(blob)=="c4d8de96f83e431ec1f678581b579a1de24524bb57f29ea019db755860607e2e","factory evidence ZIP digest")
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            evidence=tuple(z.read(name) for name in ("manifest.json","build-receipt.json"))
        for bad in (None,(evidence[0]+b" ",evidence[1]),(evidence[0],b"{}")):
            try: verified(raw,bad)
            except (ValueError,KeyError): pass
            else: raise AssertionError("bad factory receipt accepted")
    files=build(raw,a.app,evidence);artifact=zip_bytes(files)
    require(artifact==zip_bytes(build(raw,a.app,evidence)),"non-reproducible consumer")
    try: verified(raw+b"x")
    except ValueError: pass
    else: raise AssertionError("tampered package accepted")
    with tempfile.TemporaryDirectory(prefix="vedic-clean-browser-") as tmp:
        root=Path(tmp)
        with zipfile.ZipFile(io.BytesIO(artifact)) as z: z.extractall(root)
        check_tree(root,files)
        target=root/"app.mjs";original=target.read_bytes();target.write_bytes(original+b" ")
        try: check_tree(root,files)
        except ValueError: pass
        else: raise AssertionError("tampered app accepted")
        target.write_bytes(original);check_tree(root,files)
        activation=None
        if a.activation_input:
            from tacit5b_activation import Activation
            package,_=verified(raw,evidence)
            try: Activation(a.activation_input,{**package,"v9-geodesy.mjs":b"tampered"})
            except ValueError: pass
            else: raise AssertionError("wrong source digest accepted")
            activation=Activation(a.activation_input,package)
        if a.serve:
            with server_for(root,activation,8765) as server:
                print("Internal application: http://127.0.0.1:8765/ (Ctrl+C to stop)",flush=True)
                try: server.serve_forever()
                except KeyboardInterrupt: pass
            return
        cases=browser_checks(root,files,activation)
    a.evidence.mkdir(parents=True,exist_ok=True)
    (a.evidence/"catalogue.json").write_bytes(files["catalogue.json"])
    (a.evidence/"asset-manifest.json").write_bytes(files["asset-manifest.json"])
    receipt={"state":"BROWSER_DEVELOPMENT_PASS","package_sha256":digest(raw),"consumer_sha256":digest(artifact),"consumer_bytes":len(artifact),"reproducible":True,"browser_cases":cases,"independent_acceptance":False,"redistribution":"BLOCKED"}
    (a.evidence/"consumer-receipt.json").write_bytes(encode(receipt))
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__": main()

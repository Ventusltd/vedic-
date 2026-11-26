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
def verified(raw):
    require(digest(raw)==PIN,"package digest mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        require(len(z.namelist())==len(NAMES) and set(z.namelist())==NAMES,"unexpected package entries")
        files={name:z.read(name) for name in NAMES}
    m=json.loads(files["manifest.json"])
    require(m["files"]=={name:digest(data) for name,data in files.items() if name!="manifest.json"},"file digest mismatch")
    require(m["public_exports"]==["orient"] and m["source_sha256"]==MODULE and digest(files["v9-geodesy.mjs"])==MODULE,"wrong export or source")
    require(m["redistribution"]=="BLOCKED" and m["independent_acceptance"] is False,"unexpected rights state")
    return files,m
def build(raw,app):
    package,m=verified(raw)
    catalogue={"schema":"vedic.consumer-catalogue.provisional.v1","packages":[{
        **{k:m[k] for k in ("name","version","source","identity_tier","input","outputs","vedic_ids","runtime","redistribution","independent_acceptance")},
        "package_sha256":PIN,"manifest_sha256":digest(package["manifest.json"]),
        "development_build":"verified_exact_archive","browser_acceptance":"see separate exact-run receipt",
        "release_approval":False,"public_readback":None}],"counts":{"exact_packages":1,"independently_accepted":0,"released":0}}
    files={"index.html":(app/"index.html").read_bytes(),"app.mjs":(app/"app.mjs").read_bytes(),"catalogue.json":encode(catalogue)}
    files.update({"package/"+k:v for k,v in package.items()})
    files["asset-manifest.json"]=encode({"schema":"vedic.consumer-assets.v1","files":{k:digest(v) for k,v in sorted(files.items())}})
    return files
def check_tree(root,expected):
    actual={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob("*") if p.is_file()}
    require(actual==expected,"clean consumer tree mismatch")
def browser_checks(root,expected):
    from playwright.sync_api import sync_playwright
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),partial(http.server.SimpleHTTPRequestHandler,directory=str(root)))
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
                    button.focus(); button.press("Enter")
                    expect(result).to_have_text("111.319490793 km\n90.000000° initial bearing",use_inner_text=True)
                    page.locator("#a-lon").fill("1");page.locator("#b-lon").fill("0")
                    expect(result).to_have_text("Inputs changed. Calculate again.")
                    button.click();expect(result).to_have_text("111.319490793 km\n270.000000° initial bearing",use_inner_text=True)
                    for invalid in ("1","181",""):
                        page.locator("#b-lon").fill(invalid);button.click()
                        expect(result).to_contain_text("Cannot calculate:")
                        require(" km" not in result.inner_text(),"stale result")
                    page.locator("#b-lon").fill("0");button.click()
                    expect(result).to_have_text("111.319490793 km\n270.000000° initial bearing",use_inner_text=True)
                    require(page.evaluate("document.documentElement.scrollWidth <= innerWidth"),"horizontal overflow")
                    require(set(imports)=={"package/index.mjs","package/v9-geodesy.mjs"},"missing actual module request")
                    observed={k:digest(r.body()) for k,r in imports.items()}
                    require(observed=={k:digest(expected[k]) for k in imports},"served import hash mismatch")
                    require(not errors and not denied,f"errors={errors} external_requests={denied}")
                    receipts.append({"browser":kind,"version":browser.version,"viewport":[width,height],"state":"PASS","import_sha256":observed,"known_answers":2,"invalid_cases":3})
                    context.close()
                browser.close()
    finally:
        server.shutdown();server.server_close();worker.join()
    return receipts
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--package",type=Path,required=True);p.add_argument("--app",type=Path,required=True);p.add_argument("--evidence",type=Path,required=True)
    a=p.parse_args();raw=a.package.read_bytes();files=build(raw,a.app);artifact=zip_bytes(files)
    require(artifact==zip_bytes(build(raw,a.app)),"non-reproducible consumer")
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
        cases=browser_checks(root,files)
    a.evidence.mkdir(parents=True,exist_ok=True)
    (a.evidence/"catalogue.json").write_bytes(files["catalogue.json"])
    (a.evidence/"asset-manifest.json").write_bytes(files["asset-manifest.json"])
    receipt={"state":"BROWSER_DEVELOPMENT_PASS","package_sha256":PIN,"consumer_sha256":digest(artifact),"consumer_bytes":len(artifact),"reproducible":True,"browser_cases":cases,"independent_acceptance":False,"redistribution":"BLOCKED"}
    (a.evidence/"consumer-receipt.json").write_bytes(encode(receipt))
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__": main()

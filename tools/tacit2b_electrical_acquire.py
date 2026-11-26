"""One-off pinned acquisition; never imports or executes remote code."""
import hashlib, json, pathlib, sys, urllib.request
PIN="487ec7bd38dfa5aecb1c75da53b4a866ab2101cb"
BLOB="85f48ecf7effabb47973b0a056f90e82b8196ef2"
PATH="engine/voltage-drop.js"
def git_blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def main():
    out=pathlib.Path(sys.argv[1])
    out.mkdir(parents=True,exist_ok=False)
    url=f"https://raw.githubusercontent.com/Ventusltd/ventus-grid-engine/{PIN}/{PATH}"
    with urllib.request.urlopen(url,timeout=30) as response:
        data=response.read(2*1024*1024+1)
    if len(data)>2*1024*1024 or git_blob(data)!=BLOB:
        raise SystemExit("SOURCE_DIGEST_MISMATCH")
    (out/"voltage-drop.mjs").write_bytes(data)
    receipt={"schema":"tacit2b.provisional-acquisition.v1","repo":"Ventusltd/ventus-grid-engine","commit":PIN,"path":PATH,"git_blob_sha1":BLOB,"sha256":hashlib.sha256(data).hexdigest(),"identity_status":"TACIT10_RECEIPT_PENDING","rights":"BLOCKED_PRIVATE_UNLICENSED","dependencies":[]}
    (out/"acquisition.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":
    main()

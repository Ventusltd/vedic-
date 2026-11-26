"""Local bounded activation bridge to TACIT8, no new semantic compiler."""
import hashlib
import json
from pathlib import Path
import sys

PIN="9330897d89214602077806a3915054b4afc301c5"
MODULE="af9b5a8796b51a1e4368491b98961a197adec539f2fa0f3ed226552a876864bb"
RECEIPT="83147e90c0f0831ee1f82ce5e721a3521dc843421a96ae9cba3425343d0b3c19"
KEYS={"GG2050-VEDIC-000001":"86415575118","GG2050-VEDIC-000005":"86415575222"}
TIER="PINNED_PRODUCER_RECEIPT_MATCH_NOT_WAFER_REPLAY"
BLOBS={"conversational_execution.py":"deea50be1666eda7bddcdc3c789f306c20049018","semantic_retrieval.py":"0c16c18203b59f5d2f0a9f3b27aae965dcd184f9","stars_retrieval.py":"ce8d5855f0dddff59cb343b998d20c0cfaf06499","dictionary.json":"175629827380983e69edcfe1b11e5a1e2a4a7afa","translation-geodesy.json":"707a182be358db746c4b944ee6bea1c87ceb07d6"}
def sha(raw): return hashlib.sha256(raw).hexdigest()
def blob(raw): return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def require(ok,reason):
    if not ok: raise ValueError(reason)
class Activation:
    def __init__(self,root,package):
        root=Path(root)
        for name,pin in BLOBS.items():
            require(blob((root/name).read_bytes())==pin,"COMPILER_PIN_MISMATCH")
        raw=package["v9-geodesy.mjs"]; receipt=package["source-receipt.json"]
        require(sha(raw)==MODULE and sha(receipt)==RECEIPT,"SOURCE_DIGEST_MISMATCH")
        # Use the peer's exact code. The directory contains only hash-checked Python modules.
        sys.path.insert(0,str(root))
        try:
            import conversational_execution as peer
            require(Path(peer.__file__).resolve()==(root/"conversational_execution.py").resolve(),"COMPILER_PATH_MISMATCH")
            self.peer=peer
            cr=peer.curated_records(peer.strict_json((root/"dictionary.json").read_bytes()),peer.strict_json((root/"translation-geodesy.json").read_bytes()))
            pr=peer.load_library((root/"standalone.mjs").read_bytes(),peer.PRODUCER_BLOB,peer.EXPECTED_COUNT)
            self.curated=peer.Index(cr,prefer_coverage=True);self.compiled=peer.Index(pr)
        finally: sys.path.pop(0)
        identity=json.loads(receipt)
        require(identity["schema"]=="vedic.orient-module-receipt.v1" and not identity["identity_complete"],"IDENTITY_SCHEMA")
        self.rows=[]
        # Peer plan source_check uses its earlier receipt layout; validate exact new receipt
        # against the same source pins and span hashes, then pass the actual records to peer.plan.
        parts=raw.split(b"\n"); lines=[part+b"\n" for part in parts[:-1]]+([parts[-1]] if parts[-1] else [])
        for e in sorted(identity["components"],key=lambda x:x["gg_id"]):
            mid=e["gg_id"];name,first,last,output=peer.SPECS[mid]
            s=e["source"];pin={"repo":peer.REPO,"commit":peer.COMMIT,"path":peer.PATH,"blob":peer.BLOB,"first":first,"last":last}
            require(all(s.get(k)==v for k,v in pin.items()) and e["export"]==name and e["span_sha256"]==sha(b"".join(lines[first-1:last])),"SOURCE_SPAN_MISMATCH")
            require(str(e["kuiper"]["key"])==KEYS[mid] and e["kuiper"]["state"]==TIER,"KUIPER_RECEIPT_MISMATCH")
            self.rows.append({"gg_id":mid,"export":name,"output":output,"source":s,"source_sha256":MODULE,"kuiper_reported":e["kuiper"],"stars_reported":e["stars"]})
        require([r["gg_id"] for r in self.rows]==sorted(KEYS),"IDENTITY_COMPONENTS")
    def resolve(self,request):
        require(isinstance(request,dict) and set(request)=={"instruction","inputs","key"},"REQUEST_SCHEMA")
        key=request["key"]
        require(isinstance(key,str) and (not key or key in KEYS.values()),"UNKNOWN_KUIPER_KEY")
        intent=self.peer.propose(request["instruction"],self.curated,self.compiled)
        base={"compiler_commit":PIN,"intent_state":intent["state"],"selected_meaning":intent["candidate_id"],"ranked_ids":intent["curated_ranked_ids"],"rights":"INTERNAL_ONLY_REDISTRIBUTION_BLOCKED","nearest_state":"FAMILY_NOT_ADMITTED"}
        if intent["state"]!="PLAN_PROPOSED":
            return {**base,"state":"REFUSED","reason":"UNSUPPORTED_INTENT_OR_UNADMITTED_FAMILY","rows":[]}
        graph=self.peer.plan(intent,request["inputs"],self.rows)
        return {**base,"state":"PLAN_PROPOSED","rows":self.rows,"graph":graph,"key_tier":TIER,"identity_complete":False,"receipt_sha256":RECEIPT}

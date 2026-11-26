"""A1 turn 14–16: in-process applicability of exact B1/E1 receipts.
No permanent registry, source writer, admission or untrusted HTTP interface.
"""
import argparse, copy, json, subprocess, threading
from pathlib import Path
from tacit_a1_properties import Space, receipt, digest, fields, decimal
from tacit_a1_properties import acquire as acquire_a
from tacit_a_closure import canonical, sha, need
from tacit_a_final import factory_hash
from tacit_a_impact import impact
from tacit_a_index_grain import member
from tacit_a_bonds import download
from tacit_a_recovery import BOND_SHA

B1_HEAD="988e2293fd740ca434a9cf087fa873f841b7dc6f"
B1_ZIP="77561125ed5829483f30f84391c9998a21915654737fbfa34ca336b43686dbe5"
B1_SHA="a5540a0978117750fd54739e423dbd4e7c0150ce1eba81d5139609ed2db7ee97"
E1_HEAD="2211b68b9966b5e22abf80a33e41f8c29f3076ac"
E1_ZIP="ba8d8a88489224062460a1e4e70add3ee67736ab535507b4ffb83256c9e2c0cf"
E1_SHA="dbb2667d82a5033a628950e8c0f9a6bd03d8998ab1faa179de999274efefcbe0"
ARCHIVE="e83937c040499a7060b03ca2c4969e4414cdca48cb7f28a3ef9039f002486787"
OPS=("orient","nearest-orient","electrical")
PAIRS={"orient":set(),"nearest-orient":{("nearestSubstation.id","selected_location.id"),("selected_location.point_a","orient.point_a"),("selected_location.point_b","orient.point_b")},"electrical":{("voltageDropVolts.value","dropPercent.dropVolts"),("lossesWatts.value","annualLossKwh.peakLossWatts")}}

def acquire(root):
    acquire_a(root)
    download(root,"b1",15142906371)
    with (root/"e1.zip").open("xb") as f:
        subprocess.run(["gh","api","repos/Ventusltd/kuiper-belt/actions/artifacts/15141534328/zip"],stdout=f,check=True,timeout=90)

def seal_ok(r):
    return r["receipt_sha256"]==factory_hash({k:v for k,v in r.items() if k!="receipt_sha256"})

class Ledger:
    """Ephemeral, server-owned applicability state; caller cannot supply source authority.

    Only trusted host code may call apply or record_runtime. Events are proposed
    differences against the immutable source snapshot, not claims of a real new
    source revision. Reacquire reviewed pins to enable an invalidated operation.
    """
    def __init__(self,space,root):
        self.space=space
        self._lock=threading.RLock()
        self._epoch={op:0 for op in OPS}
        self._blocked=set()
        self._history={}
        self._events={}
        self._patterns={}
        self.b1=member(root/"b1.zip",B1_ZIP,"tacit-b1-patterns.json",B1_SHA)
        self.e1=member(root/"e1.zip",E1_ZIP,"runtime.json",E1_SHA)
        need(self.b1["archive_sha256"]==ARCHIVE and self.b1["redistribution"]=="BLOCKED","ARCHIVE_AUTHORITY")
        need(len(self.b1["requests"])==len(self.b1["results"])==2,"FRESH_REQUEST_COUNT")
        for q,r in zip(self.b1["requests"],self.b1["results"]):
            self._bind(q,r,"PINNED_B1_PRODUCER",initial=True)
        for op in ("nearest-orient","electrical"):
            q=self.b1["candidate_requests"][op]
            self._bind(q,self.b1["candidates"][op],"PINNED_B1_EXPERIMENT",initial=True)
            self._bind(q,self.b1["refusals"][op],"PINNED_B1_REFUSAL",initial=True)
        need(len(self.e1["fresh_results"])==2 and self.e1["runtime"]=="ACTUAL_B1_PATTERN_BRIDGE","E1_PROOF")
        for envelope in self.e1["fresh_results"]:
            q=envelope["pattern_request"];r=envelope["pattern_receipt"]
            need(envelope["receipt"]==r["legacy_receipt"] and envelope["output"]==r["result"]["output"] and envelope["archive_sha256"]==ARCHIVE,"E1_ENVELOPE")
            self._bind(q,r,"PINNED_E1_HTTP",initial=True)
        need(set(self._patterns)==set(OPS),"PATTERN_COHORT")

    def _validate(self,q,r):
        fields(q,("schema","operation","manifest_sha256","keys","pattern_sha256","inputs"))
        fields(r,("schema","pattern","pattern_sha256","request_sha256","result_sha256","result","legacy_receipt","independent_verification","rights","receipt_sha256"))
        op=q["operation"];need(op in OPS,"OPERATION")
        p=r["pattern"];old=next(x for x in self.space.bound["patterns"] if x["operation"]==op)
        need(q["schema"]=="tacit-b.kuiper-request.v2" and r["schema"]=="tacit-b.kuiper-execution.v2" and p["schema"]=="tacit-b.kuiper-pattern.v2","SCHEMA")
        need(q["manifest_sha256"]==p["manifest_sha256"]==BOND_SHA and p["operation"]==op and q["keys"]==p["keys"]==old["keys"],"SOURCE_KEYS")
        need(p["sources"]==[{"key":k,"meaning_id":self.space.rows[k]["meaning_id"],"source":self.space.rows[k]["source"]} for k in q["keys"]],"EXACT_SOURCE_JOIN")
        graph=p["typed_graph"];expected=[e for e in self.space.b["typed_bonds"] if (e["from"],e["to"]) in PAIRS[op]]
        need(graph["conditional_bonds"]==expected,"TYPED_BOND_JOIN")
        ports=self.space.b["orient"] if op=="orient" else self.space.b["electrical"] if op=="electrical" else {k:self.space.b[k] for k in ("nearest","selected_location","orient")}
        need(graph["ports"]==ports,"TYPED_PORT_JOIN")
        need(p["closure_sha256"]==factory_hash(p["closure"]) and q["pattern_sha256"]==r["pattern_sha256"]==factory_hash(p),"CLOSURE_PATTERN")
        need(r["request_sha256"]==factory_hash(q) and r["result_sha256"]==factory_hash(r["result"]) and seal_ok(r),"V2_RECEIPT")
        legacy=r["legacy_receipt"];x=r["result"]
        q1={k:v for k,v in q.items() if k!="pattern_sha256"};q1["schema"]="tacit-b.kuiper-request.v1"
        need(legacy["request_sha256"]==factory_hash(q1) and seal_ok(legacy),"V1_RECEIPT")
        need(legacy["pattern"]=={"operation":op,"manifest_sha256":BOND_SHA,"keys":q["keys"]} and legacy["pattern_sha256"]==factory_hash(legacy["pattern"]),"V1_PATTERN")
        need(all(x[k]==legacy.get(k) for k in ("state","output","nodes","admission","formal_gate","runtime_receipt_sha256")),"RESULT_JOIN")
        need(r["rights"]==legacy["rights"]=="BLOCKED" and r["independent_verification"]=="PENDING_EXACT_REQUEST_REVIEW","REVIEW_AUTHORITY")
        if op=="orient":
            need(x["state"]=="EXECUTED_INTERNAL" and x["admission"] is True and legacy["archive_sha256"]==p["orient_archive_sha256"]==ARCHIVE and legacy["descriptor_sha256"]==p["descriptor_sha256"],"ORIENT_AUTHORITY")
        else:
            need(x["admission"] is False and x["state"] in ("REFUSED","PRE_ADMISSION_EXECUTED"),"ADMISSION")
            if x["state"]=="REFUSED":need(x["output"] is None and not x["nodes"],"REFUSED_OUTPUT")
        return op

    def _bind(self,q,r,channel,initial=False):
        op=self._validate(q,r)
        if initial and op not in self._patterns:self._patterns[op]=copy.deepcopy(r["pattern"])
        need(self._patterns[op]==r["pattern"],"PINNED_PATTERN")
        h=r["receipt_sha256"]
        prior=self._history.get(h)
        if prior:
            need(prior["request"]==q and prior["receipt"]==r,"RECEIPT_COLLISION")
            if channel not in prior["channels"]:prior["channels"].append(channel)
        else:
            self._history[h]={"operation":op,"request":copy.deepcopy(q),"receipt":copy.deepcopy(r),"channels":[channel],"epoch":self._epoch[op]}
        return h

    def begin(self,op):
        with self._lock:
            need(op in OPS and op not in self._blocked,"DEPENDENCY_STALE")
            return self._epoch[op]

    def assert_current(self,op,epoch):
        with self._lock:
            need(type(epoch) is int and op in OPS and op not in self._blocked and self._epoch[op]==epoch,"DEPENDENCY_STALE")
            return True

    def record_runtime(self,q,r,epoch):
        # Host calls only AFTER its trusted worker has executed and validated the
        # result. Self-hashes alone do not authenticate runtime origin.
        with self._lock:
            self.assert_current(q["operation"],epoch)
            need(r["result"]["state"] in ("EXECUTED_INTERNAL","REFUSED"),"NO_EXPERIMENT_RUNTIME")
            return self._bind(q,r,"TRUSTED_HOST_RUNTIME")

    def snapshot(self):
        with self._lock:
            return {"epochs":dict(self._epoch),"blocked":sorted(self._blocked),"receipts":[
                {"receipt_sha256":h,"operation":x["operation"],"channels":list(x["channels"]),
                 "request_sha256":x["receipt"]["request_sha256"],"pattern_sha256":x["receipt"]["pattern_sha256"],
                 "result_sha256":x["receipt"]["result_sha256"],"state":"STALE" if x["operation"] in self._blocked or x["epoch"]!=self._epoch[x["operation"]] else "CURRENT",
                 "execution_state":x["receipt"]["result"]["state"]} for h,x in sorted(self._history.items())]}

    def apply(self,event):
        # No external event transport or source writer. Atomic process-local
        # state transition on trusted host-supplied evidence only.
        with self._lock:
            event_id=digest(event)
            if event_id in self._events:return copy.deepcopy(self._events[event_id])
            m=copy.deepcopy(self.space.bound)
            for p in m["patterns"]:
                for x in self._history.values():
                    if x["operation"]==p["operation"]:
                        r=x["receipt"];p["receipts"]+= [r[k] for k in ("receipt_sha256","request_sha256","pattern_sha256","result_sha256")]
            result=impact(m,event);affected=result["affected_patterns"]
            before=self.snapshot()
            for op in affected:self._epoch[op]+=1;self._blocked.add(op)
            after=self.snapshot()
            changed=[x["receipt_sha256"] for x in after["receipts"] if x["operation"] in affected]
            out=receipt({"schema":"vedic.tacit-a1.applicability-transition.v1","event":copy.deepcopy(event),"event_sha256":event_id,"b1_sha256":B1_SHA,"e1_sha256":E1_SHA,"impact":result,
                         "affected_receipt_ids":changed,"before":before,"after":after,"authority":"EPHEMERAL_TRUSTED_HOST_ONLY"})
            self._events[event_id]=copy.deepcopy(out)
            return out

def verify(root,out):
    s=Space(root);tests=[]
    def check(n,ok):need(ok,n);tests.append(n)
    def reject(n,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):tests.append(n)
        else:raise AssertionError("EXPECTED_REFUSAL:"+n)
    l=Ledger(s,root);orig=l.snapshot()
    check("eight authentic actual B1/E1 receipts",len(orig["receipts"])==8)
    check("two distinct B1 request and result pairs",len({r["request_sha256"] for r in l.b1["results"]})==2 and len({r["result_sha256"] for r in l.b1["results"]})==2)
    check("E1 two actual HTTP proofs",len({r["pattern_receipt"]["request_sha256"] for r in l.e1["fresh_results"]})==2)
    check("one ORIENT reusable pattern",len({x["pattern_sha256"] for x in orig["receipts"] if x["operation"]=="orient"})==1)
    q=l.b1["requests"][0];r=l.b1["results"][0]
    token=l.begin("orient");check("trusted host receipt replay idempotent",l.record_runtime(q,r,token)==r["receipt_sha256"] and len(l.snapshot()["receipts"])==8)
    bad=copy.deepcopy(r);bad["pattern"]["sources"][0]["source"]["path"]="forged.js"
    bad["pattern_sha256"]=factory_hash(bad["pattern"]);bad["receipt_sha256"]=factory_hash({k:v for k,v in bad.items() if k!="receipt_sha256"})
    reject("forged source rehash",lambda:l.record_runtime({**q,"pattern_sha256":bad["pattern_sha256"]},bad,token))
    reject("stale request",lambda:l.record_runtime(l.b1["requests"][1],r,token))
    nq=l.b1["candidate_requests"]["nearest-orient"]
    reject("no experiment in live runtime",lambda:l.record_runtime(nq,l.b1["candidates"]["nearest-orient"],l.begin("nearest-orient")))
    cases=[]
    for k,row in sorted(s.rows.items(),key=lambda x:int(x[0])):
        module=row["module_classification"]["symbol"];source=row["source"]
        expected={"Vg":["nearest-orient","orient"],"Vn":["nearest-orient"],"Vd":["electrical"]}[module]
        events=[{"kind":"source","source":source,"new_blob":"0"*40}]
        for name in ("producer_needs","producer_standalone","runtime_effects","typed_ports"):
            prop=s.props[k,name]
            events.append({"kind":"property","source":source,"property":name,"old_sha256":digest(prop),"new_sha256":"0"*64})
        for event in events:
            v=Ledger(s,root);old=v.snapshot();tokens={op:v.begin(op) for op in OPS}
            x=v.apply(event)
            check("affected only "+k+" "+event.get("property","source"),x["impact"]["affected_patterns"]==expected)
            check("unaffected and historical "+k+" "+event.get("property","source"),all(y["state"]==("STALE" if y["operation"] in expected else "CURRENT") for y in x["after"]["receipts"]) and {y["receipt_sha256"] for y in old["receipts"]}=={y["receipt_sha256"] for y in x["after"]["receipts"]})
            for op in OPS:
                if op in expected:
                    reject("inflight refused "+k+" "+event.get("property","source")+op,lambda op=op:v.assert_current(op,tokens[op]))
                    reject("no stale restart "+k+" "+event.get("property","source")+op,lambda op=op:v.begin(op))
                else:check("unaffected current "+k+" "+event.get("property","source")+op,v.assert_current(op,tokens[op]))
            check("idempotent event "+k+" "+event.get("property","source"),v.apply(event)==x and v.snapshot()==x["after"])
            if event["kind"]=="source":cases.append(x)
        v=Ledger(s,root)
        for field in ("display_colour","classification_description"):
            x=v.apply({"kind":"presentation","source":source,"field":field})
            check("presentation unchanged "+k+field,x["before"]==x["after"] and not x["impact"]["addresses_changed"])
    for family,review in s.m["family_reviews"].items():
        v=Ledger(s,root);event={"kind":"closure","family":family,"old_sha256":review["closure_sha256"],"new_sha256":"0"*64}
        x=v.apply(event)
        expected={"orient":["nearest-orient","orient"],"nearest":["nearest-orient"],"electrical":["electrical"]}[family]
        check("closure "+family,x["impact"]["affected_patterns"]==expected and x["after"]["blocked"]==expected)
    v=Ledger(s,root);token=v.begin("orient")
    source=next(row["source"] for row in s.rows.values() if row["module_classification"]["symbol"]=="Vg")
    v.apply({"kind":"source","source":source,"new_blob":"0"*40})
    reject("stale inflight commit",lambda:v.record_runtime(q,r,token))
    reject("forged event occurrence",lambda:v.apply({"kind":"source","source":{**source,"path":"forged.js"},"new_blob":"0"*40}))
    check("pinned B1 E1 member unchanged",member(root/"b1.zip",B1_ZIP,"tacit-b1-patterns.json",B1_SHA)==l.b1 and member(root/"e1.zip",E1_ZIP,"runtime.json",E1_SHA)==l.e1)
    check("unchanged permanent identity",len(s.rows)==8 and len(s.props)==32 and len(s.bonds)==5)
    report={"schema":"vedic.tacit-a1.invalidation-proof.v1","pins":{"b1_head":B1_HEAD,"b1_member":B1_SHA,"e1_head":E1_HEAD,"e1_member":E1_SHA,"manifest":BOND_SHA},"initial":orig,"source_transitions":cases,"checks":tests,
            "counts":{"PASS":len(tests),"FAIL":0,"OPEN":3},"open":["E1 live server wiring and authenticated source observation","C1 independent successor acceptance","production identity repair not authorised"],"authority":"EPHEMERAL_CI_ONLY"}
    out.write_bytes(canonical(report)+b"\n")
    print(json.dumps({"counts":report["counts"],"receipts":len(orig["receipts"]),"sha256":sha(out.read_bytes())},sort_keys=True))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify"]);p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    else:verify(a.root,a.out)

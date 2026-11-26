"""Extend the existing standalone consumer only inside its isolated CI checkout."""
from pathlib import Path
import sys

root=Path(sys.argv[1])
def insert(path,old,new):
    p=root/path
    s=p.read_text()
    if s.count(old)!=1:
        raise ValueError("PINNED_APP_ANCHOR:"+path)
    p.write_text(s.replace(old,new),encoding="utf-8")

anchor='<p>Nearest substation → location lookup → ORIENT: unavailable until nearest package and typed bond are admitted.</p>'
insert("apps/orient/index.html",anchor,anchor+
       '<button id="orient-fallback" type="button">Use explicit coordinates instead</button>'
       '<p>Separate ORIENT calculation only. No substation selection and no cable route inference.</p>')
insert("apps/orient/app.mjs","let generation=0;","""let generation=0;
document.querySelector('#orient-fallback').addEventListener('click',()=>{
  document.querySelector('#instruction').value='Calculate the distance and initial bearing between two points';
  document.querySelector('#kuiper-key').value='';
  invalidateActivation();
  document.querySelector('#activate').focus();
});""")
anchor='                        expect(page.locator("#activation-state")).not_to_contain_text(" km")'
insert("tools/tacit5b_consumer.py",anchor,anchor+'''
                        page.locator("#orient-fallback").click()
                        expect(page.locator("#activation-state")).to_have_text("Inputs changed. Activate again.")
                        expect(page.locator("#activate")).to_be_focused()
                        page.locator("#activate").click()
                        expect(page.locator("#activation-state")).to_contain_text("EXECUTED_INTERNAL")
                        expect(page.locator("#activation-state")).to_contain_text("222.638981587 km")
                        layout.append(assert_layout(page,"explicit coordinate fallback"))
''')

# Bind displayed execution evidence to actual immutable imported package and
# current typed request. This is a local observation, not independent acceptance.
insert("apps/orient/app.mjs","const evidence=document.querySelector('#evidence');",
       "const evidence=document.querySelector('#evidence');\nlet packageMeta=null;")
insert("apps/orient/app.mjs","  const {packages:[p]}=await response.json();",
       "  const {packages:[p]}=await response.json();\n  packageMeta=p;")
insert("apps/orient/app.mjs","    const graph=reply.graph;",
       """    const graph=reply.graph;
    if(!packageMeta || packageMeta.package_sha256!=='e83937c040499a7060b03ca2c4969e4414cdca48cb7f28a3ef9039f002486787'||packageMeta.descriptor_sha256!=='b45e61e955e0d0ddde15495f9be7c3fc4943c3193dd8f318a4249524f2fb5f53'||reply.receipt_sha256!=='83147e90c0f0831ee1f82ce5e721a3521dc843421a96ae9cba3425343d0b3c19')throw Error('Package or source receipt mismatch');""")
insert("apps/orient/app.mjs","activationEvidence.textContent=JSON.stringify({meaning:reply.selected_meaning,compiler:reply.compiler_commit,source_records:reply.rows,dependencies:graph.dependencies,ports:graph.outputs,key_tier:reply.key_tier,identity_complete:reply.identity_complete,rights:reply.rights},null,2);",
       """activationEvidence.textContent=JSON.stringify({
      state:'LOCAL_EXECUTION_OBSERVATION',family:'orient',meaning:reply.selected_meaning,
      instruction:document.querySelector('#instruction').value,inputs,result:out,
      package_sha256:packageMeta.package_sha256,descriptor_sha256:packageMeta.descriptor_sha256,
      build_receipt_sha256:packageMeta.build_receipt_sha256,source_receipt_sha256:reply.receipt_sha256,
      compiler:reply.compiler_commit,source_records:reply.rows,dependencies:graph.dependencies,
      ports:graph.outputs,key_tier:reply.key_tier,identity_complete:reply.identity_complete,
      independent_acceptance:false,rights:reply.rights,
      limitations:'Spherical geography, not cable route; nearest/electrical unavailable until admitted.'
    },null,2);""")
insert("apps/orient/index.html","<pre id=\"activation-evidence\" style=\"white-space:pre-wrap;overflow-wrap:anywhere\"></pre>",
       '<p><small>Execution observation: exact internal package, source receipt, input and actual output. Independent acceptance and public distribution are separate.</small></p><pre id="activation-evidence" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>')
insert("tools/tacit5b_consumer.py",'                        layout.append(assert_layout(page,"explicit coordinate fallback"))',
       '''                        observed=json.loads(page.locator("#activation-evidence").inner_text())
                        require(observed["state"]=="LOCAL_EXECUTION_OBSERVATION","execution observation")
                        require(observed["family"]=="orient" and observed["package_sha256"]==FACTORY_PIN,"package observation pin")
                        require(observed["descriptor_sha256"]==DESCRIPTOR_PIN and len(observed["build_receipt_sha256"])==64,"build receipt observation")
                        require(observed["source_receipt_sha256"]=="83147e90c0f0831ee1f82ce5e721a3521dc843421a96ae9cba3425343d0b3c19","source receipt observation")
                        require(observed["inputs"]["point_b"]=={"longitude":-1,"latitude":0},"typed observation input")
                        require(abs(observed["result"]["distance_km"]-222.63898158654712)<=1e-8 and observed["result"]["initial_bearing_deg"]==270,"actual output observation")
                        require(observed["independent_acceptance"] is False and "cable route" in observed["limitations"],"observation limits")
                        page.locator("#b-lon").fill("0")
                        expect(page.locator("#activation-evidence")).to_have_text("")
                        expect(page.locator("#activation-state")).to_have_text("Inputs changed. Activate again.")
                        layout.append(assert_layout(page,"explicit coordinate fallback"))''')

# Reuse the existing activation input and package; selection does not grant authority.
insert("apps/orient/index.html",'<label>Instruction<input id="instruction" value="Calculate the distance and initial bearing between two points"></label>',
       '''<label>Choose operation<select id="operation-choice"><option value="orient">ORIENT — admitted internal</option><option value="nearest">Nearest substation — pre-admission only</option><option value="electrical">Electrical — pre-admission only</option></select></label>
       <p><small>Nearest and electrical have executed in isolated CI, not in this application. No eligible dataset may be inferred from coordinates. No live package admission or engineering certification.</small></p>
       <label>Instruction<input id="instruction" value="Calculate the distance and initial bearing between two points"></label>''')
insert("apps/orient/app.mjs","let generation=0;","""let generation=0;
const choice=document.querySelector('#operation-choice');
const instructions={orient:'Calculate the distance and initial bearing between two points',
 nearest:'Find the nearest candidate substation at or above 132 kV, then calculate geographical distance and initial bearing to that point.',
 electrical:'Calculate voltage drop, resistive power loss and annual energy loss'};
choice.addEventListener('change',()=>{
 document.querySelector('#instruction').value=instructions[choice.value];
 document.querySelector('#kuiper-key').value='';
 invalidateActivation();
 document.querySelector('#activate').focus();
});
document.querySelector('#instruction').addEventListener('input',()=>{const match=Object.keys(instructions).find(k=>instructions[k]===document.querySelector('#instruction').value);choice.value=match||'';});""")
insert("apps/orient/app.mjs","document.querySelector('#instruction').value='Calculate the distance and initial bearing between two points';",
       "document.querySelector('#operation-choice').value='orient';\n  document.querySelector('#instruction').value='Calculate the distance and initial bearing between two points';")
insert("tools/tacit5b_consumer.py",'                        layout.append(assert_layout(page,"explicit coordinate fallback"))',
       '''                        for operation in ("nearest","electrical"):
                            page.locator("#operation-choice").select_option(operation)
                            expect(page.locator("#activate")).to_be_focused()
                            expect(page.locator("#activation-evidence")).to_have_text("")
                            page.locator("#activate").click()
                            expect(page.locator("#activation-state")).to_contain_text("REFUSED")
                            expect(page.locator("#activation-evidence")).to_have_text("")
                            layout.append(assert_layout(page,"unadmitted "+operation))
                        page.locator("#operation-choice").select_option("orient")
                        page.locator("#b-lon").fill("-1")
                        page.locator("#activate").click()
                        expect(page.locator("#activation-state")).to_contain_text("EXECUTED_INTERNAL")
                        expect(page.locator("#activation-evidence")).to_contain_text("LOCAL_EXECUTION_OBSERVATION")
                        layout.append(assert_layout(page,"operation choice restored"))
                        layout.append(assert_layout(page,"explicit coordinate fallback"))''')

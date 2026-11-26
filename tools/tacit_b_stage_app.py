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

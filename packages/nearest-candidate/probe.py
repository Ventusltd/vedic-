"""One-off development harness; not a second package factory. No source artifacts leave runner."""
import hashlib, json, pathlib, shutil, subprocess, tempfile, urllib.request
HERE=pathlib.Path(__file__).resolve().parent
D=json.loads((HERE/'descriptor.json').read_text())
P=D['producer']
def acquire(path, expected):
    url=f"https://raw.githubusercontent.com/{P['repo']}/{P['commit']}/{path}"
    with urllib.request.urlopen(url,timeout=25) as response:
        data=response.read(1_000_001)
    if len(data)>1_000_000: raise ValueError('source too large')
    blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    if blob!=expected: raise ValueError(f'Git blob mismatch: {path}')
    return data,{'git_blob':blob,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
def factory_contract(root, sandbox):
    # Read the reviewed factory, not another builder. Git blob pin checked before execution.
    url='https://raw.githubusercontent.com/Ventusltd/vedic-/050aa53d553eff6a7990fc0ed5f00623788babdd/tools/package_factory.py'
    with urllib.request.urlopen(url,timeout=25) as response:
        raw=response.read(1_000_001)
    assert len(raw)<=1_000_000
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='9512aa3c6db77ea32d54619ed484119d3cb08d7d'
    (root/'factory.py').write_bytes(raw)
    descriptor=HERE/'factory-proposal.json'
    expected=json.loads(descriptor.read_text())
    for item in expected['inputs']:
        if item['repo']=='Ventusltd/vedic-':
            data=(HERE/pathlib.Path(item['path']).name).read_bytes()
            actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            assert actual==item['digest'], item['role']
    # Validate real structural contract, then prove the existing allowlist refuses.
    code="""import importlib.util, json, sys
from pathlib import Path
s=importlib.util.spec_from_file_location('factory',sys.argv[1])
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
d=m.validate(m.strict(Path(sys.argv[2]).read_bytes()))
try: m.admit(d)
except m.Refusal as e:
    assert str(e)=='FAMILY_NOT_ADMITTED', str(e)
else: raise AssertionError('unexpected admission')
print(json.dumps({'structure':'PASS','admission':'REFUSED_FAMILY_NOT_ADMITTED','real_archive':False}))
"""
    (root/'factory-check.py').write_text(code)
    import sys
    result=subprocess.check_output(sandbox+[sys.executable,str(root/'factory-check.py'),str(root/'factory.py'),str(descriptor)],cwd=root,text=True,timeout=30)
    print(result,end='')
    return json.loads(result)

def main():
    receipts={}
    with tempfile.TemporaryDirectory(prefix='tacit3b-') as tmp:
        root=pathlib.Path(tmp)
        package=root/'node_modules/@ventus-internal/vedic-nearest'
        package.mkdir(parents=True)
        for path,blob in P['source_files'].items():
            data,receipt=acquire(path,blob)
            receipts[path]=receipt
            if path.startswith('engine/'):
                dest=package/pathlib.Path(path).name;dest.write_bytes(data)
        (package/'package.json').write_text(json.dumps({'name':D['package_name'],'private':True,'type':'module','exports':'./index.mjs','engines':{'node':'>=18'}},sort_keys=True))
        shutil.copyfile(HERE/'index.mjs',package/'index.mjs')
        (root/'consumer.test.mjs').write_text("import * as direct from './node_modules/@ventus-internal/vedic-nearest/index.mjs';\nimport { deepEqual as directCheck } from 'node:assert/strict';\ndirectCheck(Object.keys(direct),['nearestSubstation']);\n"+(HERE/'consumer.test.mjs').read_text())
        # Isolate execution after acquisition; Node package import resolves from the temp consumer.
        # Run as current runner UID to avoid root execution of producer code.
        import os
        node=shutil.which('node')
        if not node: raise RuntimeError('Node unavailable')
        sandbox=['sudo','unshare','--net','--','setpriv','--reuid',str(os.getuid()),'--regid',str(os.getgid()),'--clear-groups']
        cmd=sandbox+[node,str(root/'consumer.test.mjs')]
        proc=subprocess.run(cmd,cwd=root,check=True,text=True,capture_output=True,timeout=30)
        print(proc.stderr,end='')
        print(proc.stdout)
        result=json.loads(proc.stdout)
        assert result['state']=='PACKAGE_DEVELOPMENT_CHECKS_PASS'
        factory_result=factory_contract(root,sandbox)
        for path, receipt in sorted(receipts.items()): print(path,receipt['sha256'])
    out=pathlib.Path('receipts/tacit3b-nearest.json');out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({'status':'DEVELOPMENT_TESTS_ONLY','source_commit':P['commit'],'source_files':receipts,'layout':'flat portable filenames','observed':result,'network_namespace':'isolated','distribution':'none','shared_factory':factory_result,'independent_acceptance':'pending'},sort_keys=True,indent=2)+'\n')
if __name__=='__main__': main()

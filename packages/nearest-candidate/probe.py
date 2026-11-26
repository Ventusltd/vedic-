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
                dest=package/path;dest.parent.mkdir(exist_ok=True);dest.write_bytes(data)
        (package/'package.json').write_text(json.dumps({'name':D['package_name'],'private':True,'type':'module','exports':'./index.mjs','engines':{'node':'>=18'}},sort_keys=True))
        shutil.copyfile(HERE/'index.mjs',package/'index.mjs')
        shutil.copyfile(HERE/'consumer.test.mjs',root/'consumer.test.mjs')
        # Isolate execution after acquisition; Node package import resolves from the temp consumer.
        # Run as current runner UID to avoid root execution of producer code.
        import os
        node=shutil.which('node')
        if not node: raise RuntimeError('Node unavailable')
        cmd=['sudo','unshare','--net','--','setpriv','--reuid',str(os.getuid()),'--regid',str(os.getgid()),'--clear-groups',node,str(root/'consumer.test.mjs')]
        proc=subprocess.run(cmd,cwd=root,check=True,text=True,capture_output=True,timeout=30)
        print(proc.stdout)
        result=json.loads(proc.stdout.strip().splitlines()[-1])
    out=pathlib.Path('receipts/tacit3b-nearest.json');out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({'status':'DEVELOPMENT_TESTS_ONLY','source_commit':P['commit'],'source_files':receipts,'observed':result,'network_namespace':'isolated','distribution':'none','shared_factory':'pending','independent_acceptance':'pending'},sort_keys=True,indent=2)+'\n')
if __name__=='__main__': main()

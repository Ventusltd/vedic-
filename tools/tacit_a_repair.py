"""Acquire the original producer snapshot and exact Git ancestry. No producer writes."""
import argparse,subprocess
from pathlib import Path
from tacit_a_index_grain import acquire, PARENT
from tacit_a_closure import GRID,COMMIT,need
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True,type=Path);a=p.parse_args()
    acquire(a.root)
    repo=a.root/"git";repo.mkdir()
    subprocess.run(["git","init","-q",str(repo)],check=True,timeout=30)
    subprocess.run(["git","-C",str(repo),"fetch","--depth=2","https://github.com/"+GRID+".git",COMMIT],check=True,timeout=120)
    need(subprocess.check_output(["git","-C",str(repo),"rev-parse","FETCH_HEAD"],text=True).strip()==COMMIT,"FETCH_COMMIT")
    need(subprocess.check_output(["git","-C",str(repo),"rev-parse",COMMIT+"^"],text=True).strip()==PARENT,"PARENT")
if __name__=="__main__":main()

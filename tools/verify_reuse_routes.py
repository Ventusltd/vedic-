"""Read-only CI checks of the existing Modular Star and Kuiper reuse routes."""
import hashlib
from urllib.request import Request, urlopen
from validate_translation import fetch

STARS = ("Ventusltd/stars", "ebf2bf2be0386fcf488735560152d765b046e85e", "code.html", "c27d5d8b6bf533a5e5487a9382e3958d5d9c8df2")
KUIPER = ("Ventusltd/kuiper-belt", "e8b04bea0d369e422cd6313981f1d51cbc4347b9", "see-through/202611020012/README.md", "1d2c8e2e2678f05a0b3f09e79c75d2b9d9011cbb")
KUIPER_APP = ("Ventusltd/kuiper-belt", "e8b04bea0d369e422cd6313981f1d51cbc4347b9", "see-through/202611020012/index.html", "b069ce1d879eec5c8f0c8bc4fe12e10a3dadd1c1")

def pinned(record):
    repo, commit, path, blob = record
    raw = fetch(repo, commit, path)
    assert len(raw) <= 1_000_000
    assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob, path
    return raw

def public(url):
    with urlopen(Request(url, headers={"User-Agent":"VEDIC-code-reuse-verifier","Cache-Control":"no-cache"}),timeout=30) as r:
        assert r.status == 200, url
        body = r.read(1_000_001)
        assert 0 < len(body) <= 1_000_000
        return body

def main():
    public_stars = public("https://ventusltd.github.io/stars/code.html")
    stars=pinned(STARS)
    readme=pinned(KUIPER)
    kuiper=pinned(KUIPER_APP)
    for marker in (b"Copy the code", b"Copy an import line", b"?family=", b"function search(q)"):
        assert marker in stars, marker
        assert marker in public_stars, marker
    assert b"#repo=gridatlas" in readme
    assert b'descent.js' in kuiper
    assert b'descent.js' in public("https://ventusltd.github.io/kuiper-belt/see-through/202611020012/")
    print("PASS: pinned producer contracts and public Modular Star/Kuiper reuse routes; no family or standalone claim")

if __name__ == "__main__":
    main()

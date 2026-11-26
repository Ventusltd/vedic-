"""Verify public Pages files match exact staged bytes; fail if unavailable."""
import hashlib
import os
import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

base = os.environ["PAGE_URL"].rstrip("/") + "/"
if not base.startswith("https://"):
    raise SystemExit("Missing HTTPS Pages URL")
files = sorted(p for p in Path("_site").rglob("*") if p.is_file() and p.name != ".nojekyll")
if not files:
    raise SystemExit("No staged files")
for attempt in range(12):
    try:
        for p in files:
            url = urljoin(base, p.relative_to("_site").as_posix())
            req = Request(url, headers={"Cache-Control": "no-cache"})
            with urlopen(req, timeout=15) as response:
                served = response.read()
            expected = p.read_bytes()
            if served != expected:
                raise ValueError("Served bytes differ: " + url)
            print(url, hashlib.sha256(served).hexdigest(), flush=True)
        print("Public byte verification passed")
        break
    except Exception as err:
        print(f"Attempt {attempt + 1}: {err}", flush=True)
        if attempt == 11:
            raise
        time.sleep(10)

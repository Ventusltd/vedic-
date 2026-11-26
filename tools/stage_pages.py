"""Stage the explicit VEDIC Pages payload and print its byte digests."""
import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = (
    "index.html",
    "data/anatomy.json",
    "data/translation-geodesy.json",
    "data/nearest-spider.json",
    "data/dictionary.json",
)


def stage(destination):
    payload = {name: (ROOT / name).read_bytes() for name in PUBLIC_FILES}
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in payload.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"{hashlib.sha256(data).hexdigest()}  {name}", flush=True)
    (destination / ".nojekyll").touch()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    stage(parser.parse_args().destination)

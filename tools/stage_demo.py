"""Stage byte-exact upstream maths for VEDIC demos, never rewrite the engine."""
import hashlib
from pathlib import Path
from validate_translation import fetch
ROOT = Path(__file__).resolve().parents[1]
PIN = "487ec7bd38dfa5aecb1c75da53b4a866ab2101cb"
FILES = {
    "engine/v9-geodesy.js": ("14023f06d4ef2ea806437863bd35dee954c46b11", "geodesy.mjs"),
    "LICENSE": ("d645695673349e3947e8e5ae42332d0ac3164cd7", "LICENSE"),
    "NOTICE": ("fc080f562deed00d61e2b3e0fe39346cc6c2987e", "NOTICE"),
}
def main():
    target = ROOT / "demo-engine"
    target.mkdir(exist_ok=True)
    for source, (expected, output) in FILES.items():
        data = fetch("Ventusltd/ventus-grid-engine", PIN, source)
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual != expected:
            raise ValueError("Upstream Git blob mismatch: " + source)
        (target / output).write_bytes(data)
        print("Verified and staged", source, actual)
if __name__ == "__main__":
    main()

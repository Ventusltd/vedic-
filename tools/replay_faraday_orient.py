"""Run the VEDIC ORIENT apparatus using the existing Faraday experiment runner."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from semantic_compiler import ROOT, Refusal, need, pinned_git_file, strict_json

FARADAY = "e439b450f37a8c124fa4a0cb38159ae0dc337062"
EXPERIMENT = 101
FILES = {
    "run.mjs": "b0d63f8350f081079f0df7508a120f512ff845c143585c758ae42fb1d1db5be3",
    "INDEX.tsv": "25bd06cc1a904df3dcd4c63d9e7a43f86558b5b7920989cb46f34ddf4e0fd0d2",
}
CANDIDATE_ROW = (
    "101\tVEDIC packaged geodesy\tDo the known spherical outputs and bounded refusals follow through ORIENT?"
    "\tExact private package via the VEDIC compiler\tAny mismatched output, scope or refusal"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("faraday", "factory-repo", "private-package", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        source = {name: pinned_git_file(args.faraday, FARADAY, f"experiments/{name}", digest)
                  for name, digest in FILES.items()}
        index = source["INDEX.tsv"].decode("utf-8").rstrip("\r\n")
        numbers = [int(line.split("\t", 1)[0]) for line in index.splitlines()[1:]]
        need(numbers == list(range(1, EXPERIMENT)), "FARADAY_INDEX_CHANGED")
        args.out.mkdir()
        for name, raw in source.items():
            (args.out / name).write_bytes(raw)
        (args.out / "INDEX.tsv").write_bytes((index + "\n" + CANDIDATE_ROW + "\n").encode("utf-8"))
        (args.out / f"e{EXPERIMENT:03}.mjs").write_bytes(
            (ROOT / "tools/faraday_orient_experiment.mjs").read_bytes())
        package = args.private_package.resolve()
        env = {**os.environ, "VEDIC_PYTHON": sys.executable,
               "VEDIC_COMPILER": str(ROOT / "tools/semantic_compiler.py"),
               "VEDIC_FACTORY_REPO": str(args.factory_repo.resolve()),
               "VEDIC_ORIENT_ARCHIVE": str(package / "orient.zip"),
               "VEDIC_ORIENT_BUILD_RECEIPT": str(package / "build-receipt.json")}
        outcome = subprocess.run(["node", "--no-addons", "run.mjs", str(EXPERIMENT)],
                                 cwd=args.out, env=env, check=False, timeout=120)
        receipt = strict_json((args.out / f"results/e{EXPERIMENT:03}.json").read_bytes())
        need(outcome.returncode == 0 and receipt["result"] == "CONFIRMED", "FARADAY_NOT_CONFIRMED")
    except (Refusal, OSError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Confirmed staged Faraday candidate {EXPERIMENT} from {FARADAY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

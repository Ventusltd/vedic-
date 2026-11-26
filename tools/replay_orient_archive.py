"""Recover the exact private ORIENT archive from its existing build evidence."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch
import zipfile

from semantic_compiler import (BINDINGS, Refusal, need, pinned_git_file, sha256,
                               small_read, stage_factory, strict_json)

SOURCE_MEMBERS = {
    "module.mjs": "source-receipt/v9-geodesy.mjs",
    "receipt.json": "source-receipt/receipt.json",
}
MANIFEST_SHA256 = "67b6f9f39e30449e1a965d1e06334925ee002a5fd3b4429f892fe61f83a3af78"


def member(archive, name):
    matches = [entry for entry in archive.infolist() if entry.filename == name]
    need(len(matches) == 1 and matches[0].file_size <= 2 * 1024 * 1024,
         "ARTIFACT_MEMBER_MISMATCH", member=name)
    return archive.read(matches[0])


def reassemble(vedic, engine, source_artifact, build_artifact):
    binding = strict_json(small_read(BINDINGS))["bindings"]["GG2050-VEDIC-000006"]
    package = binding["package"]
    with zipfile.ZipFile(source_artifact) as source:
        inputs = {name: member(source, path) for name, path in SOURCE_MEMBERS.items()}
    with zipfile.ZipFile(build_artifact) as build:
        manifest = member(build, "manifest.json")
        receipt = member(build, "build-receipt.json")
    need(sha256(manifest) == MANIFEST_SHA256
         and sha256(receipt) == package["build_receipt_sha256"], "BUILD_EVIDENCE_MISMATCH")
    need(inputs["module.mjs"] == pinned_git_file(
        engine, "487ec7bd38dfa5aecb1c75da53b4a866ab2101cb", "engine/v9-geodesy.js"),
        "SOURCE_ARTIFACT_GIT_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="vedic-package-recovery-") as tmp:
        root = Path(tmp)
        stage_factory(vedic, root, package)
        spec = importlib.util.spec_from_file_location("pinned_factory", root / "tools/package_factory.py")
        factory = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(factory)
        descriptor = strict_json(small_read(root / "packages/factory/admissions/orient.json"))
        repos = {"Ventusltd/vedic-": vedic, "Ventusltd/ventus-grid-engine": engine}
        for item in descriptor["inputs"]:
            if item["filename"] not in inputs:
                inputs[item["filename"]] = pinned_git_file(
                    repos[item["repo"]], item["commit"], item["path"])
        # The published build opens files using Linux-only flags. Supply immutable
        # in-memory bytes while retaining the original Factory digest checks.
        with patch.object(factory, "read_file", side_effect=lambda _, name: inputs[name]):
            payload, _ = factory.assemble(descriptor, None)
        raw = factory.archive(payload)
        factory.verify(raw, payload)
    need(payload["manifest.json"] == manifest and sha256(raw) == package["archive_sha256"],
         "REASSEMBLED_ARCHIVE_MISMATCH")
    return raw, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("vedic", "engine", "source-artifact", "build-artifact", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        need(not args.out.exists(), "OUTPUT_EXISTS")
        archive, receipt = reassemble(args.vedic, args.engine, args.source_artifact, args.build_artifact)
        staging = Path(tempfile.mkdtemp(prefix=".vedic-orient-", dir=args.out.parent))
        try:
            (staging / "orient.zip").write_bytes(archive)
            (staging / "build-receipt.json").write_bytes(receipt)
            staging.rename(args.out)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"state": "REFUSED", "reason": str(exc)}))
        return 2
    print(json.dumps({"state": "EXACT_ARCHIVE_RECOVERED", "archive_bytes": len(archive),
                      "archive_sha256": sha256(archive), "build_receipt_sha256": sha256(receipt)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

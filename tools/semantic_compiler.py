"""Resolve the existing VEDIC dictionary and invoke reviewed package bindings."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY = ROOT / "data" / "dictionary.json"
BINDINGS = ROOT / "data" / "command-execution-bindings.json"
RECEIPT_SCHEMA = "vedic.command-execution.v1"
PHRASE = re.compile(r"[a-z]+(?: [a-z]+){0,4}")


class Refusal(ValueError):
    def __init__(self, code, **details):
        super().__init__(code)
        self.details = details


def need(condition, code, **details):
    if not condition:
        raise Refusal(code, **details)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def unique(pairs):
        fields = {}
        for key, value in pairs:
            need(key not in fields, "DUPLICATE_JSON_KEY")
            fields[key] = value
        return fields

    def finite_number(literal):
        value = float(literal)
        need(math.isfinite(value), "NONFINITE_INPUT")
        return value

    def nonfinite(_literal):
        raise Refusal("NONFINITE_INPUT")

    try:
        return json.loads(raw, object_pairs_hook=unique, parse_float=finite_number,
                          parse_constant=nonfinite)
    except Refusal:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Refusal("INVALID_JSON") from exc


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def small_read(path, limit=2 * 1024 * 1024):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, "PAYLOAD_TOO_LARGE")
    return raw


def phrase_key(phrase):
    key = " ".join(phrase.strip().lower().split())
    need(phrase.isascii() and PHRASE.fullmatch(key), "COMMAND_SYNTAX")
    return key


def resolve(phrase, dictionary, registry, sense_id=None):
    key = phrase_key(phrase)
    entries = dictionary["entries"]
    bindings = registry["bindings"]
    matching = []
    for entry in entries:
        binding = bindings.get(entry["gg_id"], {})
        names = [entry["word"], *entry.get("aliases", []), *binding.get("aliases", [])]
        if any(" ".join(name.lower().split()) == key for name in names):
            if sense_id is None or sense_id == entry["gg_id"]:
                matching.append(entry)
    need(matching, "UNKNOWN_COMMAND")
    need(len(matching) == 1, "AMBIGUOUS_COMMAND",
         candidates=[entry["gg_id"] for entry in matching])
    command = matching[0]
    command_id = command["gg_id"]
    plan = {
        "command_id": command_id,
        "canonical": command["word"],
        "intent": command.get("purpose"),
        "dictionary_status": command["state"],
        "inputs": command["inputs"],
        "output": command["output"],
        "execution_readiness": "NO_REVIEWED_PACKAGE_BINDING",
    }
    binding = bindings.get(command_id)
    if binding:
        need(binding["sense_key"] == command["sense_key"]
             and binding["components"] == command["components"]
             and command["composition_mode"] == "shared_inputs", "DICTIONARY_BINDING_DRIFT")
        plan["execution_readiness"] = "PRIVATE_FACTORY_PACKAGE"
        for field in ("aliases", "components", "operations", "ports", "refusals",
                      "scope", "package", "source_receipt_sha256", "independent_package_acceptance"):
            plan[field] = binding[field]
    return plan


def pinned_git_file(repo, commit, path, expected_sha256=None):
    environment = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1"}
    try:
        result = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"],
                                check=True, capture_output=True, timeout=15, env=environment)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refusal("PINNED_GIT_OBJECT_UNAVAILABLE", path=path) from exc
    raw = result.stdout
    if expected_sha256 is not None:
        need(sha256(raw) == expected_sha256, "GIT_BYTES_MISMATCH", path=path)
    return raw


def stage_factory(repo, factory, package):
    for relative, digest in package["factory_files"].items():
        path = factory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pinned_git_file(repo, package["factory_commit"], relative, digest))


def execute(plan, values, repo, archive, build_receipt):
    need(plan["execution_readiness"] == "PRIVATE_FACTORY_PACKAGE", "PACKAGE_NOT_ADMITTED")
    package = plan["package"]
    evidence = {field: small_read(path) for path, field in
                ((archive, "archive_sha256"), (build_receipt, "build_receipt_sha256"))}
    for field, raw in evidence.items():
        need(sha256(raw) == package[field], "PACKAGE_EVIDENCE_MISMATCH", evidence=field)
    request = {
        "schema": "vedic.typed-package-request.v1",
        "family": package["family"],
        "export": package["export"],
        "archive_sha256": package["archive_sha256"],
        "descriptor_sha256": package["descriptor_sha256"],
        "ports": plan["ports"],
        "input": values,
    }
    with tempfile.TemporaryDirectory(prefix="vedic-command-") as tmp:
        factory = Path(tmp)
        stage_factory(repo, factory, package)
        runner = factory / "tools/typed_package_execution.py"
        runner_bytes = runner.read_bytes()
        runtime_compatibility = "PINNED_FACTORY_RUNNER"
        if os.name == "nt":
            # Windows Node's system crypto initialization requires SYSTEMROOT.
            # Preserve the Factory's minimal environment and its exact checks.
            original = b'env={"PATH":os.environ["PATH"]}'
            replacement = b'env={k:os.environ[k] for k in ("PATH","SYSTEMROOT")}'
            need(runner_bytes.count(original) == 1 and "SYSTEMROOT" in os.environ,
                 "WINDOWS_RUNNER_SHAPE")
            runner_bytes = runner_bytes.replace(original, replacement)
            runner.write_bytes(runner_bytes)
            runtime_compatibility = "WINDOWS_SYSTEMROOT_ONLY"
        request_path = factory / "request.json"
        request_path.write_bytes(json_bytes(request))
        archive_path = factory / "orient.zip"
        archive_path.write_bytes(evidence["archive_sha256"])
        receipt_path = factory / "build-receipt.json"
        receipt_path.write_bytes(evidence["build_receipt_sha256"])
        command = [sys.executable, "-E", "-s", str(runner), "--request", str(request_path),
                   "--archive", str(archive_path), "--receipt", str(receipt_path)]
        try:
            result = subprocess.run(command, capture_output=True, timeout=30, cwd=factory)
        except (OSError, subprocess.SubprocessError) as exc:
            raise Refusal("PACKAGE_RUN_ERROR") from exc
    outcome = strict_json(result.stdout) if result.stdout.strip() else {}
    if result.returncode != 0:
        raise Refusal("PACKAGE_REFUSED", package_reason=outcome.get("reason", "PACKAGE_RUN_ERROR"))
    need(outcome.get("state") == "EXECUTED_ADMITTED_ORIENT_ONLY", "PACKAGE_RESULT_MISMATCH")
    pattern = outcome.get("pattern", {})
    need(pattern.get("request") == request
         and pattern.get("source_receipt_sha256") == plan["source_receipt_sha256"]
         and pattern.get("independent_acceptance") is False, "PACKAGE_RESULT_MISMATCH")
    return {
        "schema": RECEIPT_SCHEMA,
        "state": "EXECUTED_PRIVATE_PACKAGE",
        "plan": plan,
        "plan_sha256": sha256(json_bytes(plan)),
        "runtime_compatibility": runtime_compatibility,
        "runner_sha256": sha256(runner_bytes),
        "package_execution": outcome,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command")
    parser.add_argument("--sense-id", help="Select an existing ID for a command with several meanings")
    parser.add_argument("--input", type=Path, help="Execute with this exact JSON input")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--build-receipt", type=Path)
    parser.add_argument("--factory-repo", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        registry = strict_json(small_read(BINDINGS))
        need(registry.get("schema") == "vedic.execution-bindings.v1", "BINDINGS_SCHEMA")
        plan = resolve(args.command, strict_json(DICTIONARY.read_bytes()), registry, args.sense_id)
        if args.input:
            need(plan["execution_readiness"] == "PRIVATE_FACTORY_PACKAGE", "PACKAGE_NOT_ADMITTED")
            need(args.archive and args.build_receipt, "PACKAGE_EVIDENCE_REQUIRED")
            result = execute(plan, strict_json(small_read(args.input)), args.factory_repo,
                             args.archive, args.build_receipt)
        else:
            need(not (args.archive or args.build_receipt), "INPUT_REQUIRED")
            result = {"state": "RESOLVED", "plan": plan, "plan_sha256": sha256(json_bytes(plan))}
    except Refusal as exc:
        result = {"schema": RECEIPT_SCHEMA, "state": "REFUSED", "reason": str(exc), **exc.details}
        print(json_bytes(result).decode(), end="")
        return 2
    except OSError:
        print(json_bytes({"schema": RECEIPT_SCHEMA, "state": "REFUSED",
                          "reason": "EVIDENCE_IO_ERROR"}).decode(), end="")
        return 2
    print(json_bytes(result).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

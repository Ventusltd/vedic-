"""Retain scheduled family progress and prepare reviewable VEDIC Git bundles."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_REF = "refs/heads/automation/vedic-daily-state"
STATE_SCHEMA = "vedic.daily-state.v1"
FAMILY_SCHEMA = "vedic.daily-family-pulse.v2"
BUNDLE_REF = "refs/heads/automation/vedic-daily-proposal-bundle"
PROPOSAL_PREFIX = "automation/vedic-daily-proposal-"
PROPOSAL_SCHEMA = "vedic.daily-proposal.v1"
QUEUE = "data/source-command-candidates.json"
DICTIONARY = "data/dictionary.json"
ARCHIVE = "data/admitted-queue-archive.json"
MAX_BATCH = 20
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
IDENTITY = {
    "GIT_AUTHOR_NAME": "VEDIC daily automation",
    "GIT_AUTHOR_EMAIL": "vedic-daily@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "VEDIC daily automation",
    "GIT_COMMITTER_EMAIL": "vedic-daily@users.noreply.github.com",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(root, *args, data=None, env=None):
    return subprocess.run(args, cwd=root, input=data, stdout=subprocess.PIPE, check=True,
                          timeout=200, env={**os.environ, **(env or {})}).stdout


def git(root, *args, **kwargs):
    return run(root, "git", *args, **kwargs)


def gh_json(root, *args):
    return json.loads(run(root, "gh", *args))


def read_json(path):
    return json.loads(path.read_bytes())


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def oid(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value), "invalid Git commit")
    return value


def command(root, *args):
    return run(root, sys.executable, *args)


def remote_oid(root, ref):
    lines = git(root, "ls-remote", "--refs", "origin", ref).decode().splitlines()
    if not lines:
        return None
    require(len(lines) == 1 and lines[0].endswith("\t" + ref), "ambiguous remote ref")
    return oid(lines[0].split("\t")[0])


def family_receipt(receipt):
    require(receipt.get("schema") == FAMILY_SCHEMA, "unsupported family checkpoint schema")
    old, new, count = (receipt.get(key) for key in ("previous_cursor", "next_cursor", "scanned_families"))
    require(all(type(value) is int for value in (old, new, count)) and 0 <= old <= new and
            0 <= count <= 100 and (new > old) == (count > 0), "invalid family progress")
    family_hash = receipt.get("cursor_family_hash")
    require((new == 0 and family_hash is None) or
            (isinstance(family_hash, str) and re.fullmatch(r"[0-9a-f]{40,64}", family_hash)),
            "invalid checkpoint identity")
    require(receipt.get("status") == ("research_candidates" if count else "no_change"),
            "invalid family receipt status")
    return receipt


def state_receipt(state):
    require(state.get("schema") == STATE_SCHEMA, "unsupported durable checkpoint schema")
    oid(state["source_commit"])
    require(type(state.get("run_id")) is int and state["run_id"] > 0, "invalid checkpoint run ID")
    family_receipt(state["family"])
    return state


def load_state(root):
    existing = remote_oid(root, STATE_REF)
    if existing is None:
        return None, None
    git(root, "fetch", "--no-tags", "--depth=1", "origin", STATE_REF)
    fetched = oid(git(root, "rev-parse", "FETCH_HEAD").decode().strip())
    return fetched, state_receipt(json.loads(git(root, "show", f"{fetched}:checkpoint.json")))


def legacy_checkpoint(root, run_id, scratch):
    current = gh_json(root, "run", "view", str(run_id), "--json", "createdAt")
    created = current["createdAt"]
    date = created.split("T", 1)[0]
    if date < "2026-11-27":
        return None
    runs = gh_json(root, "run", "list", "--workflow", "modular-consumer.yml", "--event", "schedule",
                   "--branch", "main", "--status", "success", "--created", f"2026-11-27..{date}",
                   "--limit", "100", "--json", "databaseId,createdAt")
    prior = max((item for item in runs if item["createdAt"] < created),
                key=lambda item: item["createdAt"], default=None)
    if prior is None:
        return None
    previous = str(prior["databaseId"])
    artifacts = gh_json(root, "api", f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{previous}/artifacts")
    available = {record["name"] for record in artifacts["artifacts"] if not record["expired"]}
    name = f"vedic-research-{previous}"
    if name not in available:
        attempt = gh_json(root, "run", "view", previous, "--json", "attempt")["attempt"]
        name = f"vedic-research-{previous}-{attempt}"
    require(name in available, "earlier family receipt expired; restore a known durable checkpoint")
    run(root, "gh", "run", "download", previous, "--name", name,
        "--dir", str(scratch))
    receipts = list(scratch.rglob("family-research.json"))
    require(len(receipts) == 1, "expected one earlier family receipt; restore a known durable checkpoint")
    return family_receipt(read_json(receipts[0]))


def research(root, output, source_commit, run_id):
    output.mkdir(parents=True, exist_ok=True)
    base, state = load_state(root) if run_id else (None, None)
    if state and state["run_id"] == run_id:
        write_json(output / "family-research.json", state["family"])
        write_json(output / "state-update.json", {"base": base, "checkpoint": state})
        print("Family progress was already recorded for this run.")
        return
    require(not state or state["run_id"] < run_id, "a later scheduled run already recorded progress")
    with tempfile.TemporaryDirectory(prefix="vedic-daily-state-") as path:
        scratch = Path(path)
        checkpoint = state["family"] if state else legacy_checkpoint(root, run_id, scratch) if run_id else None
        args = ["tools/family_pulse.py", "--output", str(output)]
        if checkpoint:
            checkpoint_path = scratch / "checkpoint.json"
            write_json(checkpoint_path, checkpoint)
            args.extend(("--checkpoint", str(checkpoint_path)))
        print(command(root, *args).decode())
    receipt = family_receipt(read_json(output / "family-research.json"))
    require(receipt["previous_cursor"] == (checkpoint["next_cursor"] if checkpoint else 0),
            "family output does not advance the input cursor")
    if run_id:
        result = {"schema": STATE_SCHEMA, "source_commit": oid(source_commit), "run_id": run_id, "family": receipt}
        write_json(output / "state-update.json", {"base": base, "checkpoint": result})


def persist(root, update, source_commit, run_id):
    checkpoint = state_receipt(update["checkpoint"])
    require(checkpoint["source_commit"] == oid(source_commit) and checkpoint["run_id"] == run_id,
            "checkpoint does not belong to this scheduled run")
    base, previous = load_state(root)
    if previous == checkpoint:
        print("Family progress was already recorded for this run.")
        return
    require(base == update["base"], "durable checkpoint changed while processing; retry from its latest state")
    require(not previous or previous["run_id"] < run_id, "scheduled run would replace newer family progress")
    require(not previous or checkpoint["family"]["previous_cursor"] == previous["family"]["next_cursor"],
            "checkpoint does not continue durable family progress")
    blob = git(root, "hash-object", "-w", "--stdin", data=json_bytes(checkpoint)).decode().strip()
    tree = git(root, "mktree", data=f"100644 blob {blob}\tcheckpoint.json\n".encode()).decode().strip()
    parent = ("-p", base) if base else ()
    commit = git(root, "commit-tree", tree, *parent, "-m", f"Record VEDIC daily family progress ({run_id})",
                 env=IDENTITY).decode().strip()
    git(root, "push", "--porcelain", "origin", f"{oid(commit)}:{STATE_REF}")
    print(f"Stored family cursor {checkpoint['family']['next_cursor']} at {commit}.")


def merge_candidates(queue, discovered):
    from source_admissions import candidate_id

    require(queue.get("schema") == discovered.get("schema") == "vedic.source-candidates.v1", "candidate schema")
    require(isinstance(discovered.get("records"), list) and len(discovered["records"]) <= MAX_BATCH,
            "policy candidate budget")
    known = {candidate_id(candidate): candidate for candidate in queue["records"]}
    for candidate in discovered["records"]:
        key = candidate_id(candidate)
        if key in known:
            require(candidate == known[key], "reviewed candidate identity conflicts with existing queue record")
            continue
        known[key] = candidate
        queue["records"].append(candidate)
    return queue


def proposal(root, output, created_at=None):
    require(not git(root, "branch", "--show-current"), "proposal requires an isolated detached checkout")
    require(not git(root, "status", "--porcelain", "--untracked-files=no"), "proposal requires a clean checkout")
    head = oid(git(root, "rev-parse", "HEAD").decode().strip())
    date = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    identity = {**IDENTITY, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    output.mkdir(parents=True, exist_ok=True)
    discovery_path = output / "policy-candidates.json"
    print(command(root, "tools/daily_source_policy.py", "--output", str(discovery_path)).decode())
    queue_path = root / QUEUE
    queue = read_json(queue_path)
    discovery = read_json(discovery_path)
    initial_count = len(queue["records"])
    combined = merge_candidates(queue, discovery)
    if len(combined["records"]) > initial_count:
        write_json(queue_path, combined)
        git(root, "add", "--", QUEUE)
        git(root, "-c", "commit.gpgSign=false", "commit", "-m", "Queue VEDIC source policy candidates", env=identity)
    manifest = oid(git(root, "log", "-1", "--format=%H", "--", QUEUE).decode().strip())
    with tempfile.TemporaryDirectory(prefix="vedic-daily-proposal-") as folder:
        staged = Path(folder) / "staged"
        result = json.loads(command(root, "tools/source_admissions.py", "--prepare", "--limit", str(MAX_BATCH),
                                    "--output-dir", str(staged)))
        receipt = {"schema": PROPOSAL_SCHEMA, "base": head, "manifest_commit": manifest,
                   "added": result["added"], "held": result["held"], "dictionary_count": result["count"]}
        if result["added"]:
            for relative in (DICTIONARY, ARCHIVE):
                (root / relative).write_bytes((staged / relative).read_bytes())
            git(root, "add", "--", DICTIONARY, ARCHIVE)
            git(root, "-c", "commit.gpgSign=false", "commit", "-m", "Apply reviewed VEDIC source admissions", env=identity)
            print(command(root, "tools/allocate_commands.py", "--check").decode())
            print(command(root, "tools/source_admissions.py", "--check", "--online").decode())
            candidate = oid(git(root, "rev-parse", "HEAD").decode().strip())
            git(root, "update-ref", BUNDLE_REF, candidate)
            bundle = output / "proposal.bundle"
            git(root, "bundle", "create", str(bundle), BUNDLE_REF, "^" + head)
            require(bundle.stat().st_size <= MAX_BUNDLE_BYTES, "proposal bundle exceeds its byte budget")
            receipt.update(status="ready_for_review", head=candidate, bundle_ref=BUNDLE_REF,
                           bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest())
        else:
            receipt["status"] = "no_change"
    write_json(output / "proposal.json", receipt)
    print(json_bytes(receipt).decode())


def review_pr(root, output, repository):
    receipt = read_json(output / "proposal.json")
    require(receipt["schema"] == PROPOSAL_SCHEMA and receipt["status"] == "ready_for_review", "proposal is not ready")
    base, candidate = oid(receipt["base"]), oid(receipt["head"])
    bundle = output / "proposal.bundle"
    require(bundle.stat().st_size <= MAX_BUNDLE_BYTES and
            hashlib.sha256(bundle.read_bytes()).hexdigest() == receipt["bundle_sha256"], "proposal bundle integrity")
    if remote_oid(root, "refs/heads/main") != base:
        print("Main advanced before PR opening. The proposal remains available for review in the run artifact.")
        return
    open_prs = gh_json(root, "pr", "list", "--repo", repository, "--base", "main", "--state", "open",
                       "--limit", "100", "--json", "headRefName,url")
    for record in open_prs:
        if record["headRefName"].startswith(PROPOSAL_PREFIX):
            print(f"A daily review PR is already open: {record['url']}")
            return
    git(root, "bundle", "verify", str(bundle))
    local_ref = "refs/vedic-daily/review"
    git(root, "fetch", str(bundle), f"{BUNDLE_REF}:{local_ref}")
    require(git(root, "rev-parse", local_ref).decode().strip() == candidate, "bundle head differs from receipt")
    changed = set(git(root, "diff", "--name-only", base, candidate).decode().splitlines())
    require({DICTIONARY, ARCHIVE} <= changed <= {QUEUE, DICTIONARY, ARCHIVE}, "unexpected proposal paths")
    branch = PROPOSAL_PREFIX + candidate[:20]
    git(root, "push", "--porcelain", "origin", f"{candidate}:refs/heads/{branch}")
    message = (f"Proposed {len(receipt['added'])} source-reviewed meanings.\n\n"
               f"Pinned reviewed manifest: `{receipt['manifest_commit']}`.\n\n"
               "Review evidence and wait for CI. Use a merge commit to retain the pinned manifest commit.")
    with tempfile.TemporaryDirectory(prefix="vedic-daily-review-") as folder:
        body = Path(folder) / "body.md"
        body.write_text(message, encoding="utf-8")
        print(run(root, "gh", "pr", "create", "--repo", repository, "--base", "main", "--head", branch,
                  "--title", "VEDIC: apply bounded daily source admissions", "--body-file", str(body)).decode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("research", "persist", "proposal", "review-pr"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--created-at")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == "research":
        research(ROOT, output, args.commit, args.run_id)
    elif args.stage == "persist":
        require(args.run_id is not None, "missing scheduled run ID")
        persist(ROOT, read_json(output / "state-update.json"), args.commit, args.run_id)
    elif args.stage == "proposal":
        proposal(ROOT, output, args.created_at)
    else:
        require(args.repository == "Ventusltd/vedic-", "unexpected repository for review PR")
        review_pr(ROOT, output, args.repository)


if __name__ == "__main__":
    main()

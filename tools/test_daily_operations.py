import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import daily_operations as operations


def family(previous, current):
    return {"schema": operations.FAMILY_SCHEMA, "previous_cursor": previous, "next_cursor": current,
            "scanned_families": 1 if current > previous else 0,
            "cursor_family_hash": "a" * 40 if current else None,
            "status": "research_candidates" if current > previous else "no_change"}


def candidate(first):
    return {"source": {"path": "test.py", "first": first, "last": first + 1}, "word": "MEASURE TEST"}


def queue(*records):
    return {"schema": "vedic.source-candidates.v1", "records": list(records)}


class DailyOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.remote = self.directory / "remote.git"
        self.repo = self.directory / "producer"
        self.repo.mkdir()
        operations.git(self.directory, "init", "--bare", str(self.remote))
        operations.git(self.repo, "init", "-b", "main")
        operations.git(self.repo, "config", "core.autocrlf", "false")
        operations.git(self.repo, "remote", "add", "origin", str(self.remote))
        operations.write_json(self.repo / operations.QUEUE, queue(candidate(10)))
        operations.write_json(self.repo / operations.DICTIONARY, {"entries": ["prior"]})
        operations.write_json(self.repo / operations.ARCHIVE, {"records": []})
        operations.git(self.repo, "add", "data")
        operations.git(self.repo, "-c", "commit.gpgSign=false", "commit", "-m", "Baseline", env=operations.IDENTITY)
        self.base = operations.git(self.repo, "rev-parse", "HEAD").decode().strip()
        operations.git(self.repo, "push", "origin", "main")

    def fixture_update(self, number, base, previous_cursor, next_cursor):
        return {"base": base, "checkpoint": {"schema": operations.STATE_SCHEMA, "source_commit": self.base,
                                             "run_id": number, "family": family(previous_cursor, next_cursor)}}

    def test_durable_state_bootstrap_and_retry(self):
        self.assertEqual(operations.load_state(self.repo), (None, None))
        initial = self.fixture_update(10, None, 0, 100)
        operations.persist(self.repo, initial, self.base, 10)
        state_commit, state = operations.load_state(self.repo)
        self.assertEqual(state, initial["checkpoint"])
        operations.persist(self.repo, initial, self.base, 10)
        self.assertEqual(operations.load_state(self.repo)[0], state_commit)
        output = self.directory / "retry"
        with patch.object(operations, "command") as command:
            operations.research(self.repo, output, self.base, 10)
            command.assert_not_called()
        self.assertEqual(operations.read_json(output / "family-research.json"), initial["checkpoint"]["family"])

    def test_accelerator_checkpoint_is_coupled_to_family_persistence(self):
        initial = self.fixture_update(10, None, 0, 100)
        operations.persist(self.repo, initial, self.base, 10)
        base, _ = operations.load_state(self.repo)
        progress = {"schema": operations.daily_accelerator.SCHEMA, "database_sha256": "a" * 64,
                    "method_sha256": "b" * 64, "completed_rounds": 1,
                    "probe_coverage": {"FIND EXAMPLE": {"tested": 16, "total": 20}}}
        output = self.directory / "accelerated"

        def mocked_family(root, *args):
            operations.write_json(output / "family-research.json", family(100, 200))
            return b""

        with patch.object(operations, "command", side_effect=mocked_family), \
                patch.object(operations.daily_accelerator, "research", return_value=progress) as accelerator:
            operations.research(self.repo, output, self.base, 11, accelerator=True)
            accelerator.assert_called_once_with(self.repo, output, None)
        update = operations.read_json(output / "state-update.json")
        self.assertEqual(update["base"], base)
        operations.persist(self.repo, update, self.base, 11)
        state_commit, state = operations.load_state(self.repo)
        self.assertEqual(state["accelerator"], progress)
        with patch.object(operations.daily_accelerator, "research") as accelerator:
            operations.research(self.repo, self.directory / "retry", self.base, 11, accelerator=True)
            accelerator.assert_not_called()
        with self.assertRaisesRegex(ValueError, "Missing existing accelerator progress"):
            operations.persist(self.repo, self.fixture_update(12, state_commit, 200, 300), self.base, 12)

    def test_stale_and_discontinuous_progress_is_refused(self):
        initial = self.fixture_update(10, None, 0, 100)
        operations.persist(self.repo, initial, self.base, 10)
        state_commit = operations.load_state(self.repo)[0]
        with self.assertRaisesRegex(ValueError, "changed while processing"):
            operations.persist(self.repo, self.fixture_update(11, None, 0, 101), self.base, 11)
        with self.assertRaisesRegex(ValueError, "does not continue"):
            operations.persist(self.repo, self.fixture_update(11, state_commit, 2, 101), self.base, 11)
        valid = self.fixture_update(11, state_commit, 100, 200)
        operations.persist(self.repo, valid, self.base, 11)
        self.assertEqual(operations.load_state(self.repo)[1], valid["checkpoint"])
        with self.assertRaisesRegex(ValueError, "later scheduled run"):
            operations.research(self.repo, self.directory / "old", self.base, 10)
        self.assertEqual(operations.remote_oid(self.repo, "refs/heads/main"), self.base)

    def test_migration_advances_legacy_receipt(self):
        output = self.directory / "migration"
        legacy = family(0, 100)

        def mocked_family(root, *args):
            checkpoint_path = Path(args[args.index("--checkpoint") + 1])
            self.assertEqual(operations.read_json(checkpoint_path), legacy)
            operations.write_json(output / "family-research.json", family(100, 200))
            return b""

        with patch.object(operations, "legacy_checkpoint", return_value=legacy), \
                patch.object(operations, "command", side_effect=mocked_family):
            operations.research(self.repo, output, self.base, 10)
        update = operations.read_json(output / "state-update.json")
        operations.persist(self.repo, update, self.base, 10)
        self.assertEqual(operations.load_state(self.repo)[1]["family"], family(100, 200))

    def test_unavailable_legacy_artifact_stops_without_state_update(self):
        output = self.directory / "unavailable"
        history = [{"databaseId": 9, "createdAt": "2026-11-27T03:37:00Z"}]
        responses = [{"createdAt": "2026-11-28T03:37:00Z"}, history, {"artifacts": []}, {"attempt": 1}]
        with patch.object(operations, "gh_json", side_effect=responses), \
                patch.dict(operations.os.environ, {"GITHUB_REPOSITORY": "Ventusltd/vedic-"}):
            with self.assertRaisesRegex(ValueError, "earlier family receipt expired"):
                operations.legacy_checkpoint(self.repo, 10, output)
        self.assertFalse((output / "family-research.json").exists())

    def test_malformed_remote_state_stops_instead_of_bootstrapping(self):
        operations.git(self.repo, "push", "origin", f"{self.base}:{operations.STATE_REF}")
        with self.assertRaises(operations.subprocess.CalledProcessError):
            operations.load_state(self.repo)

    def test_conflicting_candidate_is_refused_and_exact_retry_is_idempotent(self):
        current = queue(candidate(10))
        self.assertEqual(operations.merge_candidates(current, queue(candidate(10))), current)
        changed = {**candidate(10), "word": "DIFFERENT TEST"}
        with self.assertRaisesRegex(ValueError, "conflicts"):
            operations.merge_candidates(current, queue(changed))

    def test_proposal_bundle_replays_exact_manifest_commit(self):
        output = self.directory / "proposal"
        operations.git(self.repo, "checkout", "--detach", self.base)

        def mock_cli(root, tool, *args):
            if tool.endswith("daily_source_policy.py"):
                operations.write_json(Path(args[-1]), queue(candidate(20)))
            elif "--prepare" in args:
                staged = Path(args[-1])
                operations.write_json(staged / operations.DICTIONARY, {"entries": ["prior", "new"]})
                operations.write_json(staged / operations.ARCHIVE, {"records": ["new"]})
                return operations.json_bytes({"added": ["new"], "held": [], "count": 2})
            return b""

        with patch.object(operations, "command", side_effect=mock_cli):
            operations.proposal(self.repo, output)
        receipt = operations.read_json(output / "proposal.json")
        self.assertEqual(receipt["status"], "ready_for_review")
        self.assertEqual(receipt["base"], self.base)
        self.assertEqual(operations.remote_oid(self.repo, "refs/heads/main"), self.base)
        fresh = self.directory / "review"
        operations.git(self.directory, "clone", "--branch", "main", str(self.remote), str(fresh))
        ref = "refs/heads/review"
        operations.git(fresh, "fetch", str(output / "proposal.bundle"), f"{operations.BUNDLE_REF}:{ref}")
        self.assertEqual(operations.git(fresh, "rev-parse", ref).decode().strip(), receipt["head"])
        content = operations.git(fresh, "show", f"{receipt['manifest_commit']}:{operations.QUEUE}")
        self.assertEqual(json.loads(content), queue(candidate(10), candidate(20)))

    def test_empty_proposal_writes_receipt_without_bundle(self):
        output = self.directory / "no-change"
        operations.git(self.repo, "checkout", "--detach", self.base)

        def mock_cli(root, tool, *args):
            if tool.endswith("daily_source_policy.py"):
                operations.write_json(Path(args[-1]), queue())
                return b""
            return operations.json_bytes({"added": [], "held": [], "count": 1})

        with patch.object(operations, "command", side_effect=mock_cli):
            operations.proposal(self.repo, output)
        self.assertEqual(operations.read_json(output / "proposal.json")["status"], "no_change")
        self.assertFalse((output / "proposal.bundle").exists())

    def test_proposal_refuses_existing_local_branch(self):
        with self.assertRaisesRegex(ValueError, "detached checkout"):
            operations.proposal(self.repo, self.directory / "attached")


if __name__ == "__main__":
    unittest.main()

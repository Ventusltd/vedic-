# VEDIC daily operations

The single scheduled workflow runs at 03:37 UTC. It records up to 100 Modular Star family observations and separately prepares up to 20 reviewed source admissions. Family observations and source-admission bundles have separate jobs and receipts. A failure in one does not block the other. Manual dispatch and pull-request checks produce previews.

## Family checkpoint

Successful scheduled observations advance `checkpoint.json` on the dedicated `automation/vedic-daily-state` branch. The write job runs only on scheduled `main` in `Ventusltd/vedic-`. It uses a fast-forward push and compares the previous checkpoint revision and cursor before recording progress. A retry of the recorded workflow run reuses the same cursor. The branch stores the family receipt and exact source commit.

The first scheduled run migrates the latest applicable successful legacy receipt if one exists. A missing or invalid known predecessor fails closed. If checkpoint history becomes unavailable, recover the last known verified checkpoint commit from a Git mirror or authenticated workflow receipt before resuming. Keep the state branch when replacing or cleaning up workflow artifacts. Research artifacts expire after 14 days. The state remains in Git.

## Review a proposal

The `vedic-proposal-<run_id>` artifact contains `proposal.json` and the bounded policy candidate manifest. A `ready_for_review` receipt includes `proposal.bundle`, its SHA-256, the proposal tip, and the pinned queue commit. A `no_change` receipt has no bundle. Inspect any held candidates before changing the reviewed source policy.

Verify the recorded SHA-256, then import the bundle into an existing VEDIC Git checkout that contains its stated base commit.

```bash
git bundle verify /path/to/proposal.bundle
git fetch /path/to/proposal.bundle refs/heads/automation/vedic-daily-proposal-bundle:refs/heads/review/vedic-daily-proposal
git log --oneline --stat origin/main..review/vedic-daily-proposal
```

If the proposal is still current, push it to a review branch and open a pull request. The existing VEDIC gates replay admission evidence and validate the Pages candidate. Use a merge commit so the archive's pinned manifest commit remains reachable. Keep a pending PR stable until review has finished. Merging into `main` triggers the existing publishing workflow.

The standard repository token records family progress. Review PR creation is optional and uses an existing, separately approved GitHub App installation when `VEDIC_REVIEW_APP_CLIENT_ID` and `VEDIC_REVIEW_APP_PRIVATE_KEY` are available. The App token is scoped to this repository and requests Contents and Pull requests write access. The PR uses normal repository checks and review. Without an App configuration, the artifact is the handoff. The workflow does not enable auto-merge or change repository permissions.

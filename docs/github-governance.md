# GitHub Governance for Detection as Code

## Branch model

The repository uses two permanent branches:

| Branch | Purpose | Who can push directly |
|---|---|---|
| `dev` | Staging — analysts submit detections here | Nobody |
| `main` | Production — only promoted from `dev` | Nobody |

All changes to either branch must go through a pull request.

### Analyst workflow

```
git checkout dev && git pull origin dev
git checkout -b dev/<your-name>/<detection-name>

# write and validate your detection
git push origin dev/<your-name>/<detection-name>
# open PR → target: dev
```

After review and merge to `dev`, a separate PR promotes the changes to `main`:

```
PR: dev → main
  CI validates again
  Approving review required
  Merge → deploy to Splunk
```

### Branch naming convention

```
dev/<analyst-name>/<change-summary>
```

Examples:
```
dev/alice/brute-force-rdp
dev/bob/powershell-encoding-tuning
dev/security-team/lateral-movement-coverage
```

Avoid a shared `dev` branch per analyst (e.g. `dev/alice`). Short-lived, scoped branches keep each change isolated and make PR ownership unambiguous.

---

## Pull request flow

1. Analyst creates a branch from `dev` following the naming convention above
2. Analyst writes or updates detection YAML files under `detections/`
3. Analyst validates locally: `python3 scripts/validate.py --no-splunk <file>`
4. Analyst opens a PR into `dev`
5. CI runs `Validate Changed Detections` — schema + SPL syntax check
6. At least one reviewer approves the detection logic
7. Merge to `dev`
8. A promotion PR (`dev → main`) is opened (manually or via automation)
9. CI validates again
10. Merge to `main`
11. `Deploy Detections to Splunk` runs automatically

The deploy workflow verifies that every push to `main` originated from a merged PR. This is a soft guard against accidental direct pushes.

---

## Protected branch settings

Apply these settings to both `dev` and `main`:

| Setting | Value |
|---|---|
| Require pull request before merging | Enabled |
| Required approving reviews | `1` |
| Dismiss stale approvals after new commits | Enabled |
| Require approval of the most recent push | Enabled |
| Require status checks before merging | Enabled |
| Required status check | `Validate Changed Detections` |
| Require branches to be up to date before merging | Enabled |
| Require conversation resolution before merging | Enabled |
| Allow force pushes | Disabled |
| Allow deletions | Disabled |
| Include administrators | Enabled |

> **GitHub plan requirement:** Branch protection rules on private repositories require GitHub Pro or GitHub Enterprise. On the free plan, these settings cannot be enforced via the API.
>
> If branch protection is unavailable, the deploy workflow partially compensates — it blocks deployments that did not originate from a merged PR. However, this does not prevent direct pushes to `dev` or `main` by users with write access.
>
> **Mitigations for free plan:**
> - Grant analysts `read` access only; submit changes via forks
> - Move the repository to a GitHub organization on a paid plan
> - Enable repository rulesets (available on some org plans at no extra cost)

---

## Detection deletion policy

Detection files must not be deleted from the repository. The CI pipeline blocks PRs that contain deleted detection files.

To retire a detection:
1. Set `status: deprecated` in the YAML file
2. Merge the change — the detection is updated to disabled in Splunk
3. Handle Splunk removal through a deliberate decommission step (manual or a separate workflow)

Deleting a YAML file leaves no record of what the detection was, making it impossible to automate safe Splunk cleanup.

---

## Branch cleanup

| Mechanism | Trigger | Scope |
|---|---|---|
| GitHub "delete branch on merge" | Automatic after PR merge | The merged PR branch only |
| `Cleanup Merged Branches` workflow | Weekly (Sunday 03:17 UTC) or manual | All merged analyst branches older than 14 days |

The cleanup workflow only removes branches that:
- Are already merged into `main`
- Have a last commit older than 14 days
- Match a managed prefix (`dev/`, `feature/`, `fix/`, `detection/`, `hotfix/`)

`main` and `dev` are never deleted by the workflow.

---

## Operating guidelines

- Keep PRs focused on one detection or one tightly related set of detections
- Validate locally before opening a PR — catches schema errors without spending CI time
- Increment `version` when modifying an existing detection
- Keep detection `id` values stable — they are the stable identifier for the saved search across environments
- Treat YAML `status` as lifecycle metadata, not the only source of deployment state
- Let the deploy workflow set the effective Splunk state with `DEPLOY_STATUS`; merges to `main` deploy with `DEPLOY_STATUS=production`
- Use `status: draft` for detections that are not ready to be enabled
- Use `status: deprecated` to retire detections; draft and deprecated detections are always deployed disabled

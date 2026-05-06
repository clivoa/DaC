# GitHub Governance for Detection as Code

This repository models an enterprise Detection as Code workflow where detection content is reviewed, validated, merged, and deployed through GitHub.

## Branch model

`main` is the production branch. A change merged into `main` is eligible for deployment to Splunk.

Analysts work in short-lived branches using this naming pattern:

```text
dev/<analyst>/<change-summary>
```

Examples:

```text
dev/alice/brute-force-login
dev/bruno/powershell-encoded-command
dev/security-team/internal-port-scan-tuning
```

Avoid a single shared `dev` branch. With multiple analysts, shared development branches become hard to review, hard to clean up, and easy to break accidentally. Short-lived analyst branches keep each change isolated and make PR ownership clear.

## Pull request flow

1. An analyst creates or updates detection YAML files under `detections/`.
2. The analyst opens a PR into `main`.
3. GitHub Actions runs `Validate Changed Detections`.
4. The PR must pass validation and receive approval.
5. The PR is merged into `main`.
6. The deploy workflow runs from `main` and creates or updates Splunk saved searches.

The deploy workflow should not run from analyst branches. This keeps Splunk deployment tied to reviewed code only.

## Protected branch policy

`main` should be protected with these controls:

| Setting | Value |
|---|---|
| Require a pull request before merging | Enabled |
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

These settings block direct changes to `main`, including accidental pushes from repository administrators during the simulation.

## Detection deletion policy

Detection files should not be deleted as part of the normal analyst workflow. Set `status: deprecated` instead and handle Splunk removal through a deliberate decommission process.

The validation and deployment workflows block deleted detection files because a deleted YAML file does not contain enough information to safely remove or disable the matching Splunk saved search.

## Branch cleanup

Two cleanup mechanisms are used:

| Mechanism | Purpose |
|---|---|
| GitHub delete branch on merge | Deletes PR branches immediately after merge |
| `Cleanup Merged Branches` workflow | Removes stale merged branches that were not auto-deleted |

The cleanup workflow runs weekly and can also be started manually from **Actions → Cleanup Merged Branches**.

By default, it deletes only merged branches older than 14 days and only when they match one of these prefixes:

```text
dev/
feature/
fix/
detection/
hotfix/
```

Unmerged branches are never deleted by the workflow.

## Operating notes

- Keep PRs focused on one detection or one related detection set.
- Validate locally before pushing when possible.
- Keep detection IDs stable after creation.
- Increment `version` when changing an existing detection.
- Use `production` only when a detection is ready to be enabled in Splunk.
- Use `draft` or `testing` for detections that should be deployed as disabled saved searches.

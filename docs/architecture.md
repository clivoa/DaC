# Detection as Code — Architecture

## What is Detection as Code?

Detection as Code (DaC) applies software engineering practices to security detection engineering. Instead of managing Splunk saved searches manually through the web UI, detections are authored as version-controlled YAML files, reviewed through pull requests, validated automatically by a CI/CD pipeline, and deployed to Splunk through an automated process.

This gives security teams:

- **Version control** — full history of every detection change, who changed it, and why
- **Peer review** — detections are reviewed before they reach production
- **Automated validation** — syntax errors and schema violations are caught before deployment
- **Reproducibility** — any Splunk environment can be populated from the repository
- **Auditability** — every deployed detection traces back to an approved pull request

---

## Repository model

### This repository (simulation / getting started)

This repository combines everything in one place for ease of setup:

```
DaC/
├── detections/        ← detection content (would be its own repo in production)
├── scripts/           ← validation and deployment scripts
├── schemas/           ← detection YAML schema
├── .github/workflows/ ← CI/CD pipeline
├── runner/            ← self-hosted runner container (infrastructure)
├── docs/              ← documentation
└── docker-compose.yml ← runner orchestration (infrastructure)
```

### Production split (recommended)

In a production environment, split the repository into two:

| Repository | Contents | Audience |
|---|---|---|
| `dac-detections` | `detections/`, `scripts/`, `schemas/`, `.github/workflows/`, `docs/authoring.md` | All analysts and engineers |
| `dac-infrastructure` | `runner/`, `docker-compose.yml`, `docs/runner-setup.md`, `docs/splunk-setup.md` | Platform / SecOps infra team only |

The detection repository contains everything an analyst needs to write, validate, and submit detections. The infrastructure repository is managed by the team responsible for the runner and Splunk environment.

---

## Branch strategy

```
  analyst branch
  dev/alice/brute-force-login
          │
          │  Pull Request
          ▼
    ┌─────────────────────────────────────┐
    │           dev branch                │
    │                                     │
    │  CI: Validate Changed Detections    │
    │  ├── YAML syntax                    │
    │  ├── JSON Schema                    │
    │  └── SPL syntax (Splunk REST API)   │
    │                                     │
    │  Required: 1 approving review       │
    └─────────────────────────────────────┘
          │
          │  Merge to dev (staging)
          ▼
    ┌─────────────────────────────────────┐
    │           main branch               │
    │                                     │
    │  PR: dev → main (production)        │
    │  CI: Validate again (belt+suspenders│
    │  Required: 1 approving review       │
    └─────────────────────────────────────┘
          │
          │  Merge to main
          ▼
    ┌─────────────────────────────────────┐
    │  Deploy to Splunk                   │
    │  ├── Verify: must be from merged PR │
    │  ├── Dry-run (preview)              │
    │  └── Create/update saved searches  │
    └─────────────────────────────────────┘
```

### Branch naming

Analysts work in short-lived branches following this convention:

```
dev/<analyst-name>/<change-summary>
```

Examples:
```
dev/alice/brute-force-rdp-login
dev/bob/update-powershell-thresholds
dev/security-team/mitre-t1059-coverage
```

### Protected branches

| Branch | Who can push directly | Who can merge |
|---|---|---|
| `main` | Nobody | Via approved PR from `dev` only |
| `dev` | Nobody | Via approved PR from analyst branch |

> Branch protection requires GitHub Pro or GitHub Enterprise for private repositories.
> See [github-governance.md](github-governance.md) for the full policy and a workaround for repositories on the free plan.

---

## CI/CD pipeline

### `validate-pr.yml` — Pull Request validation

Triggered on every PR targeting `dev` or `main`.

```
PR opened or updated
        │
        ▼
Identify changed detection files
        │
        ├── Any files deleted? → BLOCK (set status: deprecated instead)
        │
        ▼
For each changed .yml file:
  1. Parse YAML (syntax check)
  2. Validate against JSON Schema
      ├── required fields present?
      ├── status in allowed enum?
      ├── id matches UUID v4 format?
      └── MITRE tags match T####(.###) format?
  3. POST to /services/search/parser (live SPL check)
      └── Splunk parses the query and returns errors or warnings
        │
        ├── Any errors? → FAIL (PR blocked)
        └── All pass?   → PASS (PR unblocked)
```

The `--github-annotations` flag makes errors appear inline in the PR diff view.

### `deploy.yml` — Production deployment

Triggered on every push to `main` (i.e. after a PR is merged).

```
Push to main
        │
        ▼
Verify: was this push from a merged PR?
        │ (guards against accidental direct pushes)
        │
        ▼
Identify changed detection files (vs previous commit)
        │
        ├── workflow_dispatch with deploy_all=true → deploy all files
        │
        ▼
Dry-run: show what would be created/updated
        │
        ▼
Deploy: POST to Splunk REST API
  ├── saved search exists? → update
  └── saved search missing? → create
```

Detection `status` controls whether the saved search is enabled in Splunk:

| Detection `status` | Splunk saved search |
|---|---|
| `production` | created/updated **enabled** |
| `draft`, `testing`, `deprecated` | created/updated **disabled** |

### `cleanup-branches.yml` — Branch housekeeping

Runs weekly (Sunday 03:17 UTC) and on manual trigger.

Deletes merged branches older than 14 days that match the analyst branch prefixes (`dev/`, `feature/`, `fix/`, `detection/`, `hotfix/`). Never deletes `main` or `dev`.

---

## Detection validation in depth

### Validation layers

| Layer | Where | What is checked | Requires Splunk? |
|---|---|---|---|
| Pre-commit hook | Local (analyst machine) | YAML syntax + JSON Schema | No |
| CI — PR to `dev` | GitHub Actions runner | YAML + Schema + SPL syntax | Yes |
| CI — PR to `main` | GitHub Actions runner | YAML + Schema + SPL syntax | Yes |
| Human review | GitHub PR | Logic, thresholds, MITRE mapping | N/A |

### Schema validation

Every detection file is validated against `schemas/detection.schema.json` using JSON Schema Draft-7. The schema enforces:

- Required fields: `name`, `id`, `version`, `status`, `author`, `description`, `type`, `search`, `tags.category`
- `id` must be a valid UUID v4
- `status` must be one of `draft`, `testing`, `production`, `deprecated`
- `type` must be one of `alert`, `report`, `scheduled_report`
- MITRE ATT&CK technique IDs must match `T####` or `T####.###`
- `alert.severity` must be one of `informational`, `low`, `medium`, `high`, `critical`

Schema errors fail the PR check. Warnings (e.g. missing MITRE tags, `status: draft`) are reported but do not block the PR.

### SPL syntax check

The validation script POSTs the SPL query to Splunk's `/services/search/parser` endpoint. This uses the actual Splunk parser to check the query, which catches:

- Unclosed parentheses or brackets
- Invalid command names
- Malformed `eval` expressions
- Invalid `stats` aggregation syntax

The check requires a live Splunk instance reachable by the runner. If Splunk is unreachable, the check is skipped with a warning (not a failure) to avoid blocking PRs during infrastructure downtime.

---

## Infrastructure components

### Self-hosted GitHub Actions runner

The runner is an Ubuntu 24.04 container managed with Docker Compose. It must run on the same machine as Splunk (or have network access to it) because GitHub-hosted runners cannot reach a local Splunk instance.

See [runner-setup.md](runner-setup.md) for setup instructions.

```
macOS host (Orbstack)
├── splunk container        (dac_default network, port 8089)
└── dac-gh-runner container (dac_default network)
        │
        └── registers with GitHub → receives and executes workflow jobs
```

The runner connects to Splunk using the container hostname `splunk` over the shared `dac_default` Docker network.

### Network connectivity

| Source | Destination | Protocol | Purpose |
|---|---|---|---|
| `dac-gh-runner` | `splunk:8089` | HTTPS | SPL validation and deployment |
| GitHub Actions | `dac-gh-runner` | WebSocket | Job dispatch |
| Browser (analyst) | `localhost:8000` | HTTP | Splunk web UI |

---

## Detection lifecycle (step by step)

1. **Identify** a threat technique to detect (reference MITRE ATT&CK)
2. **Create a branch** from `dev`:
   ```bash
   git checkout dev && git pull origin dev
   git checkout -b dev/<your-name>/<detection-name>
   ```
3. **Write the detection** YAML file under `detections/<category>/`
4. **Generate a UUID** for the `id` field:
   ```bash
   python3 -c "import uuid; print(uuid.uuid4())"
   ```
5. **Validate locally** (no Splunk required):
   ```bash
   python3 scripts/validate.py --no-splunk detections/<category>/<file>.yml
   ```
6. **Commit and push** — pre-commit hooks run automatically
7. **Open a PR** targeting `dev`
8. **CI validates** — schema and SPL syntax check against Splunk
9. **Peer review** — a colleague reviews the detection logic
10. **Merge to `dev`** — detection is staged
11. **Open PR** `dev → main` for production promotion
12. **Merge to `main`** — deploy workflow runs automatically
13. **Verify in Splunk** — confirm the saved search was created/updated

---

## Adding new validation checks

The validation pipeline is designed to be extended. Add new checks to `scripts/validate.py` in the `validate_file()` function or as new functions called from `main()`.

Ideas for additional checks:
- Sigma rule compatibility (convert detection to Sigma format)
- MITRE ATT&CK coverage gap analysis
- Duplicate detection name check (query Splunk for existing saved searches)
- Performance estimation (flag searches scanning without index/sourcetype constraints)
- Required `schedule` field when `type` is `alert`

---

## Extending to multiple environments

For teams with separate development and production Splunk instances:

1. Add a second set of GitHub secrets (`SPLUNK_DEV_URL`, `SPLUNK_PROD_URL`, etc.)
2. Modify `deploy.yml` to deploy to the dev Splunk on merge to `dev` and to the prod Splunk on merge to `main`
3. Update the runner setup to have access to both Splunk instances, or use separate runners per environment with different labels

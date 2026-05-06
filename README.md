# Detection as Code — Splunk

A complete Detection as Code (DaC) pipeline for managing Splunk detections as version-controlled YAML files, with automated validation and deployment through GitHub Actions.

[![Validate Detection PR](https://github.com/clivoa/DaC/actions/workflows/validate-pr.yml/badge.svg)](https://github.com/clivoa/DaC/actions/workflows/validate-pr.yml)

---

## How it works

```
Analyst creates or edits a detection YAML file
              │
              ▼
  git push → Pull Request → dev branch
              │
              ▼
  GitHub Actions (self-hosted runner)
  ┌────────────────────────────────────────┐
  │  1. YAML syntax check                  │
  │  2. JSON Schema validation             │
  │  3. SPL syntax check (Splunk REST API) │
  │  → PR blocked if any check fails       │
  └────────────────────────────────────────┘
              │
              ▼
  Code review + approval → merge to dev
              │
              ▼
  PR: dev → main (production promotion)
              │
              ▼
  GitHub Actions deploy
  ┌────────────────────────────────────────┐
  │  1. Verify: came from a merged PR      │
  │  2. Dry-run preview                    │
  │  3. Create/update Splunk saved search  │
  └────────────────────────────────────────┘
```

For the full architecture and design rationale, see [docs/architecture.md](docs/architecture.md).

---

## Repository structure

```
.
├── detections/
│   ├── endpoint/          # Endpoint detections (Windows, Linux, macOS)
│   ├── network/           # Network-based detections
│   ├── identity/          # Identity and access detections
│   ├── cloud/             # Cloud provider detections
│   └── application/       # Application-layer detections
├── docs/
│   ├── architecture.md    # Full DaC design, pipeline, and concepts
│   ├── github-governance.md # Branch model and protection policy
│   ├── splunk-setup.md    # Splunk local setup with Orbstack/Docker
│   └── runner-setup.md    # Self-hosted runner container setup
├── runner/
│   ├── Dockerfile         # Ubuntu 24.04 image with GitHub Actions runner
│   └── entrypoint.sh      # Runner registration and graceful deregistration
├── schemas/
│   └── detection.schema.json  # JSON Schema for detection YAML files
├── scripts/
│   ├── validate.py        # Schema + SPL syntax validation
│   ├── deploy.py          # Deploy detections via Splunk REST API
│   └── splunk_client.py   # Splunk REST API client
├── .github/
│   ├── workflows/
│   │   ├── validate-pr.yml       # Required check on PRs to dev and main
│   │   ├── deploy.yml            # Deploy on merge to main
│   │   └── cleanup-branches.yml # Weekly stale branch cleanup
│   └── PULL_REQUEST_TEMPLATE.md
├── docker-compose.yml     # Orchestrates the self-hosted runner container
├── .env.example           # Environment variable reference (no real values)
├── CONTRIBUTING.md        # How to write and submit detections
└── SECURITY.md            # Security policy and sensitive data guidelines
```

---

## Detection file format

```yaml
name: "Detect <Threat Name>"
id: "<uuid-v4>"           # python3 -c "import uuid; print(uuid.uuid4())"
version: 1                # increment on every change
status: draft             # draft | testing | production | deprecated
author: "<your-team>"
date: "YYYY-MM-DD"
modified: "YYYY-MM-DD"
description: "What this detects and why it matters"
type: alert               # alert | report | scheduled_report

search: |
  index=<index> EventCode=<code>
  | stats count by ComputerName, User
  | where count > 0

schedule:
  cron: "*/15 * * * *"
  earliest: "-15m"
  latest: "now"

alert:
  condition: "search count > 0"
  severity: high          # informational | low | medium | high | critical
  suppress: false

tags:
  mitre_attack:
    - T1059.001           # T#### or T####.###
  platform:
    - Windows             # Windows | Linux | macOS | AWS | Azure | GCP | Network
  category: endpoint      # endpoint | network | identity | cloud | application

splunk_app: "search"
```

> **`status` → Splunk state:** `production` = enabled. All other values = created as disabled.

---

## Infrastructure setup

This pipeline requires two local components running on Orbstack. Set them up once:

| Component | Guide |
|---|---|
| Splunk (Docker) | [docs/splunk-setup.md](docs/splunk-setup.md) |
| GitHub Actions runner (Docker) | [docs/runner-setup.md](docs/runner-setup.md) |

### Required GitHub secrets

Go to **Settings → Secrets and variables → Actions**:

| Type | Name | Value |
|---|---|---|
| Secret | `SPLUNK_URL` | `https://splunk:8089` |
| Secret | `SPLUNK_TOKEN` | token from Splunk → Settings → Tokens |
| Variable | `SPLUNK_APP` | `search` (or your custom app name) |

---

## Local development

### Setup

```bash
# Install Python dependencies and pre-commit hooks
make setup

# Required environment variables for local SPL validation
export SPLUNK_URL="https://splunk:8089"   # or https://localhost:8089 if port 8089 is published
export SPLUNK_TOKEN="<your-token>"
```

### Validate detections

```bash
# Schema validation only (no Splunk required)
make validate

# Schema + live SPL syntax check
make validate-splunk

# Single file
python3 scripts/validate.py detections/endpoint/detect_new_local_admin.yml
```

### Deploy manually

```bash
make deploy-dry   # preview without making changes
make deploy       # deploy all production-status detections
```

---

## Analyst workflow

```bash
# 1. Create a branch from dev
git checkout dev && git pull origin dev
git checkout -b dev/<your-name>/<detection-name>

# 2. Write the detection file
# (generate a fresh UUID for the id field)
python3 -c "import uuid; print(uuid.uuid4())"

# 3. Validate locally before committing
python3 scripts/validate.py --no-splunk detections/<category>/<file>.yml

# 4. Commit and push
git add detections/<category>/<file>.yml
git commit -m "feat: describe the detection"
git push origin dev/<your-name>/<detection-name>

# 5. Open a PR into dev → CI validates automatically
# 6. After review and merge → promote via PR: dev → main → auto-deploy
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete authoring guide and detection quality guidelines.

---

## Validated fields

| Field | Required | Rule |
|---|---|---|
| `name` | Yes | min 5 characters |
| `id` | Yes | UUID v4 format |
| `version` | Yes | integer ≥ 1 |
| `status` | Yes | `draft` \| `testing` \| `production` \| `deprecated` |
| `author` | Yes | string |
| `description` | Yes | min 10 characters |
| `type` | Yes | `alert` \| `report` \| `scheduled_report` |
| `search` | Yes | valid SPL (checked live via Splunk REST API) |
| `tags.category` | Yes | enum |
| `tags.mitre_attack` | No | `T####` or `T####.###` format — warning if absent |

---

## GitHub governance

`main` and `dev` are protected branches. All changes must be submitted through a pull request. See [docs/github-governance.md](docs/github-governance.md) for the full policy, branch protection settings, and notes on GitHub plan requirements.

---

## License

[MIT](LICENSE)

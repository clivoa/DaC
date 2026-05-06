# Detection as Code — Splunk

Manage Splunk detections as versioned YAML files with a full CI/CD pipeline powered by GitHub Actions and a self-hosted runner running in Orbstack.

## How it works

```
Analyst creates or edits a detection YAML file
              │
              ▼
     git push → open Pull Request
              │
              ▼
  GitHub Actions  (self-hosted runner on Orbstack)
  ┌────────────────────────────────────────┐
  │  1. YAML syntax check                  │
  │  2. JSON Schema validation             │
  │  3. SPL syntax check (Splunk REST API) │
  │  → PR blocked if any check fails       │
  └────────────────────────────────────────┘
              │
              ▼
     Code review + approval
              │
              ▼
        Merge to main
              │
              ▼
  GitHub Actions deploy
  ┌────────────────────────────────────────┐
  │  1. Dry-run (preview changes)          │
  │  2. Create or update saved search      │
  │     via Splunk REST API                │
  └────────────────────────────────────────┘
```

## Repository structure

```
.
├── detections/
│   ├── endpoint/          # Endpoint detections (Windows, Linux)
│   ├── network/           # Network detections
│   └── identity/          # Identity and access detections
├── docs/
│   ├── splunk-setup.md    # How to run Splunk locally with Orbstack
│   └── runner-setup.md    # How to set up the self-hosted runner container
├── runner/
│   ├── Dockerfile         # Ubuntu 24.04 image with GitHub Actions runner
│   └── entrypoint.sh      # Registers runner on start, deregisters on stop
├── schemas/
│   └── detection.schema.json  # JSON Schema — validated on every PR
├── scripts/
│   ├── validate.py        # Schema + SPL syntax validation
│   ├── deploy.py          # Deploy detections via Splunk REST API
│   └── splunk_client.py   # Splunk REST API client
├── .github/workflows/
│   ├── validate-pr.yml    # Triggered on every PR touching detections/
│   └── deploy.yml         # Triggered on every merge to main
├── docker-compose.yml     # Starts the self-hosted runner container
├── .env.example           # Environment variable template
└── .pre-commit-config.yaml
```

## Detection file format

```yaml
name: "Descriptive detection name"
id: "uuid-v4"             # generate: python3 -c "import uuid; print(uuid.uuid4())"
version: 1                # increment on every change
status: draft             # draft | testing | production | deprecated
author: "your-name"
date: "2026-05-06"
modified: "2026-05-06"
description: "What this detects and why (min 10 characters)"
type: alert               # alert | report | scheduled_report

search: |
  index=windows EventCode=4732
  | where Group_Name="Administrators"
  | table _time, ComputerName, Member_Name

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
    - T1098               # required format: T####(.###)
  platform:
    - Windows             # Windows | Linux | macOS | AWS | Azure | GCP | Network
  category: identity      # endpoint | network | identity | cloud | application

splunk_app: "search"      # target Splunk app (defaults to search)
```

> **Status → Splunk state mapping:**
> `production` → enabled | all other statuses → created as disabled

## Validated fields

| Field | Required | Validation |
|---|---|---|
| `name` | Yes | min 5 characters |
| `id` | Yes | UUID v4 format |
| `version` | Yes | integer ≥ 1 |
| `status` | Yes | enum |
| `author` | Yes | string |
| `description` | Yes | min 10 characters |
| `type` | Yes | enum |
| `search` | Yes | string + live SPL check via Splunk API |
| `tags.category` | Yes | enum |
| `tags.mitre_attack` | No | format `T####(.###)` — warning if missing |

## Local setup

### 1. Install Python dependencies and pre-commit hooks

```bash
make setup
```

### 2. Set environment variables

```bash
export SPLUNK_URL="https://localhost:8089"
export SPLUNK_TOKEN="your-token"
```

### 3. Validate detections locally

```bash
# Schema only (no Splunk connection needed)
make validate

# Schema + live SPL syntax check
make validate-splunk

# Single file
python3 scripts/validate.py detections/endpoint/detect_new_local_admin.yml
```

### 4. Deploy manually

```bash
make deploy-dry    # preview without changes
make deploy        # deploy all detections
```

## Infrastructure setup

Before the CI/CD pipeline works, you need two things running locally:

| Component | Guide |
|---|---|
| Splunk (Docker/Orbstack) | [docs/splunk-setup.md](docs/splunk-setup.md) |
| GitHub Actions runner (Docker/Orbstack) | [docs/runner-setup.md](docs/runner-setup.md) |

## GitHub secrets and variables

Go to **Settings → Secrets and variables → Actions** and add:

| Type | Name | Value |
|---|---|---|
| Secret | `SPLUNK_URL` | `https://host.internal:8089` |
| Secret | `SPLUNK_TOKEN` | token from Splunk Settings → Tokens |
| Variable | `SPLUNK_APP` | `search` (or your custom app) |

> `host.internal` resolves to the macOS host from inside the Orbstack runner container.
> Use `localhost:8089` only when running scripts directly on the Mac.

## Analyst workflow

```bash
# 1. Create a branch for the new detection
git checkout -b detection/brute-force-login

# 2. Write the detection file
vim detections/identity/detect_brute_force_login.yml

# 3. Validate locally before committing
python3 scripts/validate.py --no-splunk detections/identity/detect_brute_force_login.yml

# 4. Commit and push — pre-commit hooks run automatically
git add detections/identity/detect_brute_force_login.yml
git commit -m "feat: add brute force login detection"
git push origin detection/brute-force-login

# 5. Open PR → CI validates automatically
# 6. After approval and merge → CI deploys automatically
```

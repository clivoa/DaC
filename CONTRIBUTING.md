# Contributing Detections

This guide covers how to write, validate, and submit a detection through the DaC pipeline.

## Prerequisites

- Python 3.10+ and `pip3`
- Git
- (Optional) A local Splunk instance for live SPL validation — see [docs/splunk-setup.md](docs/splunk-setup.md)

```bash
# Install dependencies and pre-commit hooks
make setup
```

---

## Step-by-step: adding a detection

### 1. Create a branch from `dev`

```bash
git checkout dev && git pull origin dev
git checkout -b dev/<your-name>/<detection-summary>
```

Use the naming pattern `dev/<your-name>/<change>`. Examples:
```
dev/alice/detect-rdp-brute-force
dev/bob/update-powershell-baseline
```

### 2. Create the detection file

Place the file under `detections/<category>/` where `<category>` is one of:
`endpoint`, `network`, `identity`, `cloud`, `application`.

Generate a UUID for the `id` field:
```bash
python3 -c "import uuid; print(uuid.uuid4())"
```

Use this template:

```yaml
name: "Detect <Threat Name>"
id: "<uuid-v4>"
version: 1
status: draft        # start as draft; set to testing/production when ready
author: "<your-team>"
date: "<YYYY-MM-DD>"
modified: "<YYYY-MM-DD>"
description: "<What this detects and why it matters>"
type: alert

search: |
  index=<index> <sourcetype or filters>
  | <transformations>
  | stats count by <key_fields>
  | where count > 0

schedule:
  cron: "*/15 * * * *"
  earliest: "-15m"
  latest: "now"

alert:
  condition: "search count > 0"
  severity: medium    # informational | low | medium | high | critical
  suppress: false

tags:
  mitre_attack:
    - T1234.001       # format: T#### or T####.###
  platform:
    - Windows         # Windows | Linux | macOS | AWS | Azure | GCP | Network
  category: endpoint  # endpoint | network | identity | cloud | application

splunk_app: "search"
```

### 3. Validate locally

```bash
# Schema only (no Splunk required)
python3 scripts/validate.py --no-splunk detections/<category>/<file>.yml

# Schema + live SPL check (requires SPLUNK_URL and SPLUNK_TOKEN env vars)
python3 scripts/validate.py detections/<category>/<file>.yml
```

Fix any errors before committing. The pre-commit hook runs schema validation automatically on `git commit`.

### 4. Commit and push

```bash
git add detections/<category>/<file>.yml
git commit -m "feat: <short description of detection>"
git push origin dev/<your-name>/<detection-summary>
```

### 5. Open a pull request

Open a PR from your branch into **`dev`** (not `main`).

The CI pipeline will run automatically and check:
- YAML syntax
- Schema validation (required fields, valid enums, UUID format)
- SPL syntax via the Splunk REST API

Errors appear inline in the PR diff. Fix them and push a new commit — CI re-runs automatically.

### 6. Address review feedback

A reviewer will check the detection logic, thresholds, and MITRE mapping. Update the detection based on feedback and push additional commits to the same branch.

### 7. Promote to production

After your PR is merged into `dev`, a senior analyst or platform engineer will open a PR from `dev` to `main`. On merge to `main`, the detection is deployed to Splunk automatically.

Change `status` from `draft`/`testing` to `production` when the detection is validated and ready to be enabled in Splunk.

---

## Updating an existing detection

1. Create a branch from `dev`
2. Edit the detection file
3. Increment the `version` field
4. Update the `modified` date
5. Follow steps 3–7 above

---

## Detection quality guidelines

### SPL

- Always filter by `index` and, where possible, `sourcetype` or `source` — avoid unbounded searches
- Use `stats` or `tstats` rather than raw search when aggregating large volumes
- Avoid `| head` or `| tail` in production detections — use `| where count > <threshold>` instead
- Test thresholds against real data before setting `status: production`

### Metadata

- `description` should explain *what* the detection looks for and *why* it matters — not just repeat the name
- MITRE ATT&CK tags should reflect the actual technique, not just the tactic
- Use `status: testing` for detections deployed as disabled — they can be enabled in Splunk for tuning without being "production"

### IDs

- The `id` field is permanent. Never change a detection's `id` after it has been merged
- The `id` is used to correlate the YAML file with the Splunk saved search across environments

---

## Running all detections locally

```bash
# Validate all detections (schema only)
make validate

# Validate all detections with live SPL check
make validate-splunk

# Preview deployment (dry run)
make deploy-dry
```

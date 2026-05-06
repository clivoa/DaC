# GitHub Actions Self-Hosted Runner (Orbstack / Docker)

The DaC CI/CD workflows run on a **self-hosted runner** because the Splunk instance is local (Orbstack). GitHub-hosted runners cannot reach `localhost`.

The runner is an Ubuntu 24.04 container built with Docker and managed via `docker compose`.

---

## Architecture

```
macOS host (Orbstack)
├── splunk container        ← port 8089 exposed on localhost
└── dac-gh-runner container ← reaches Splunk via host.internal:8089
        │
        └── connects to GitHub → executes workflow jobs
```

The runner container uses `host.internal` (mapped to the Orbstack host via `extra_hosts`) to reach the Splunk REST API at `https://host.internal:8089`.

---

## Prerequisites

- Orbstack running with the Splunk container healthy (see [splunk-setup.md](splunk-setup.md))
- Docker Compose v2 (`docker compose` command available)
- A GitHub Personal Access Token (PAT) with **`repo`** scope

---

## 1. Create the PAT

1. Go to https://github.com/settings/tokens → **Generate new token (classic)**
2. Grant the **`repo`** scope (full control of private repos)
3. Copy the token

---

## 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values. There are two authentication modes:

**Option A — One-time registration token** (from GitHub UI, expires ~1 hour)
```dotenv
GITHUB_OWNER=your-github-username
GITHUB_REPO=your-repo-name
RUNNER_TOKEN=AAW7OBMxxxxxxxxxxxxxxx   # Settings → Actions → Runners → New runner
SPLUNK_URL=https://host.internal:8089
SPLUNK_USERNAME=admin
SPLUNK_PASSWORD=your-password
```

The registration config is persisted in a Docker volume (`runner_config`).
On subsequent container restarts, the token is not needed again.

**Option B — Personal Access Token** (recommended for production, never expires)
```dotenv
GITHUB_OWNER=your-github-username
GITHUB_REPO=your-repo-name
GITHUB_PAT=ghp_xxxxxxxxxxxxxxxxxxxx   # Settings → Tokens → repo scope
SPLUNK_URL=https://host.internal:8089
SPLUNK_TOKEN=your-splunk-api-token
```

The PAT fetches a fresh registration token on every container start and enables
graceful deregistration when the container stops.

---

## 3. Build and start the runner

```bash
# Build the image (only needed on first run or after runner/Dockerfile changes)
make runner-build

# Start the runner in the background
make runner-up

# Confirm it registered successfully
docker compose logs -f gh-runner
```

Expected log output:
```
==> Fetching registration token...
==> Configuring runner 'dac-runner' → https://github.com/owner/repo
    Labels: self-hosted,linux,dac
√ Connected to GitHub
√ Runner successfully added
√ Settings Saved.
==> Runner ready. Waiting for jobs...
Current runner version: '2.334.0'
Listening for Jobs
```

---

## 4. Verify on GitHub

Go to your repository → **Settings → Actions → Runners**.

The `dac-runner` should appear with status **Idle**.

---

## 5. How workflows target this runner

The workflows use:

```yaml
runs-on: [self-hosted, linux, dac]
```

All three labels must match what the runner was registered with (`RUNNER_LABELS=self-hosted,linux,dac`).

---

## 6. Updating the runner version

Check the latest version at https://github.com/actions/runner/releases, then update `docker-compose.yml`:

```yaml
args:
  RUNNER_VERSION: "2.335.0"  # update here
```

Rebuild and restart:

```bash
docker compose build && docker compose up -d
```

---

## 7. Day-to-day management

```bash
# Stop runner (auto-deregisters from GitHub)
docker compose down

# View logs
docker compose logs -f gh-runner

# Restart
docker compose restart gh-runner
```

---

## 8. Troubleshooting

**Runner shows as offline on GitHub:**
Check that the container is still running and that the PAT hasn't expired.
```bash
docker compose ps
docker compose logs gh-runner --tail 50
```

**Cannot reach Splunk (`host.internal` not resolving):**
Verify the `extra_hosts` entry in `docker-compose.yml` and that Splunk is actually healthy:
```bash
docker compose exec gh-runner curl -sk https://host.internal:8089/services/server/info \
  -H "Authorization: Bearer ${SPLUNK_TOKEN}" -o /dev/null -w "%{http_code}\n"
```

**Runner token expired before startup:**
PAT-based registration fetches a fresh token each time the container starts — no manual rotation needed.

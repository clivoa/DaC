# GitHub Actions Self-Hosted Runner (Orbstack / Docker)

The DaC CI/CD workflows run on a **self-hosted runner** because the Splunk instance is local (Orbstack). GitHub-hosted runners cannot reach `localhost`.

The runner is an Ubuntu 24.04 container built with Docker and managed via `docker compose`.

---

## Architecture

```
macOS host (Orbstack)
├── splunk container        (dac_default network, port 8089)
└── dac-gh-runner container (dac_default network)
        │
        └── connects to GitHub → executes workflow jobs
```

Both containers share the `dac_default` Docker network. The runner reaches Splunk at `https://splunk:8089` using the container hostname directly — no host port mapping required.

---

## Prerequisites

- Orbstack running with the Splunk container healthy (see [splunk-setup.md](splunk-setup.md))
- Docker Compose v2 (`docker compose` command available)
- A GitHub account with write access to the repository

---

## 1. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values. There are two authentication modes:

**Option A — One-time registration token** (from GitHub UI, expires ~1 hour)
```dotenv
GITHUB_OWNER=your-github-username
GITHUB_REPO=DaC
RUNNER_TOKEN=<token-from-github-ui>   # Settings → Actions → Runners → New runner
SPLUNK_URL=https://splunk:8089
SPLUNK_TOKEN=<your-splunk-api-token>
```

The registration config is persisted in a Docker volume (`runner_config`).
On subsequent container restarts, the token is not needed again — the runner reuses its saved credentials.

**Option B — Personal Access Token** (recommended, auto-refreshes on each start)
```dotenv
GITHUB_OWNER=your-github-username
GITHUB_REPO=DaC
GITHUB_PAT=<pat-with-repo-scope>   # github.com/settings/tokens
SPLUNK_URL=https://splunk:8089
SPLUNK_TOKEN=<your-splunk-api-token>
```

The PAT fetches a fresh registration token on every container start and enables graceful deregistration on stop.

---

## 2. Connect Splunk to the shared network

The runner and Splunk must share the `dac_default` Docker network. Run once after the Splunk container is started:

```bash
docker network connect dac_default splunk
```

> Repeat this step any time the Splunk container is recreated.

---

## 3. Build and start the runner

```bash
make runner-build   # build the image (first run or after Dockerfile changes)
make runner-up      # start the runner container

# Verify registration succeeded
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

```yaml
runs-on: [self-hosted, linux, dac]
```

All three labels must match `RUNNER_LABELS` in your `.env`.

---

## 6. Updating the runner version

Check the latest version at https://github.com/actions/runner/releases, then update `docker-compose.yml`:

```yaml
args:
  RUNNER_VERSION: "2.335.0"
```

Rebuild and restart:

```bash
docker compose build && docker compose up -d
```

---

## 7. Day-to-day management

```bash
docker compose down               # Stop and deregister runner
docker compose logs -f gh-runner  # View logs
docker compose restart gh-runner  # Restart
```

---

## 8. Troubleshooting

**Runner shows as offline on GitHub**

```bash
docker compose ps
docker compose logs gh-runner --tail 50
```

**Runner stuck with "A session for this runner already exists"**

The previous session did not deregister cleanly. Force a fresh registration:

```bash
# 1. Delete the runner from GitHub
gh api repos/<owner>/<repo>/actions/runners \
  --jq '.runners[] | select(.name=="dac-runner") | .id' \
  | xargs -I{} gh api repos/<owner>/<repo>/actions/runners/{} -X DELETE

# 2. Clear saved credentials from the volume
docker compose stop gh-runner
docker run --rm -v dac_runner_config:/config ubuntu:24.04 \
  sh -c "rm -f /config/.runner /config/.credentials /config/.credentials_rsaparams"

# 3. Set a fresh RUNNER_TOKEN in .env and restart
docker compose up -d
```

**Cannot reach Splunk from the runner**

```bash
# Verify the containers share the dac_default network
docker network inspect dac_default --format '{{range .Containers}}{{.Name}} {{end}}'
# Expected: dac-gh-runner splunk

# If splunk is missing, reconnect it
docker network connect dac_default splunk

# Test connectivity
docker exec dac-gh-runner curl -sk https://splunk:8089/services/server/info \
  -H "Authorization: Bearer <your-token>" -o /dev/null -w "%{http_code}\n"
# Expected: 200
```

**`_work` directory permission denied**

Occurs when the volume was written by root. Fix with:

```bash
docker exec -u root dac-gh-runner chown -R runner:runner /home/runner/actions-runner/_work
```

# Splunk Local Setup (Orbstack / Docker)

Splunk Enterprise running in Docker via Orbstack on macOS (Apple Silicon).

## Requirements

- macOS with [Orbstack](https://orbstack.dev) installed and running
- `docker` available in the terminal

> **Apple Silicon note:** The official Splunk image is `linux/amd64` only.
> Orbstack runs it transparently via Rosetta 2 — no extra configuration needed.

---

## 1. Create persistent volumes

```bash
docker volume create splunk-etc
docker volume create splunk-data
```

| Volume | Mount inside container | Purpose |
|---|---|---|
| `splunk-etc` | `/opt/splunk/etc` | Configuration, apps, saved searches |
| `splunk-data` | `/opt/splunk/var` | Indexed data, logs |

---

## 2. Run the Splunk container

```bash
docker run -d \
  --platform linux/amd64 \
  --name splunk \
  --hostname splunk \
  -p 8000:8000 \
  -p 8088:8088 \
  -p 8089:8089 \
  -p 9997:9997 \
  -e SPLUNK_START_ARGS="--accept-license" \
  -e SPLUNK_GENERAL_TERMS="--accept-sgt-current-at-splunk-com" \
  -e SPLUNK_PASSWORD="<your-password>" \
  -v splunk-etc:/opt/splunk/etc \
  -v splunk-data:/opt/splunk/var \
  --restart unless-stopped \
  splunk/splunk:latest
```

| Port | Purpose |
|---|---|
| `8000` | Web UI |
| `8088` | HTTP Event Collector (HEC) |
| `8089` | REST API / Management — **required for DaC workflows** |
| `9997` | Universal Forwarder receiver |

> **Password rules:** minimum 8 characters, must contain at least one uppercase letter and one digit.

---

## 3. Wait for Splunk to be healthy

Splunk takes 1–2 minutes on first start.

```bash
until [ "$(docker inspect --format='{{.State.Health.Status}}' splunk)" = "healthy" ]; do
  echo "Waiting for Splunk..."; sleep 5
done
echo "Splunk is ready"
```

---

## 4. Access

| | Value |
|---|---|
| Web UI | http://localhost:8000 |
| REST API | https://localhost:8089 |
| Username | `admin` |
| Password | the value you set in `SPLUNK_PASSWORD` above |

> Change the password after first login: **Settings → Users → admin → Edit**.

---

## 5. Generate an API token for DaC workflows

The CI/CD pipeline authenticates to Splunk using a Bearer token (safer than a password).

1. Log in to the web UI
2. Go to **Settings → Tokens**
3. Click **New Token**
4. Set **User**: `admin`, **Expiration**: your preference
5. Copy the token — you will not see it again

Use this token as `SPLUNK_TOKEN` in your `.env` file and as the `SPLUNK_TOKEN` GitHub secret.

---

## 6. Connect Splunk to the DaC network

The GitHub Actions runner and Splunk must be on the same Docker network so the runner can reach the Splunk REST API by container name.

```bash
# Run once after starting or recreating the Splunk container
docker network connect dac_default splunk
```

The runner will then reach Splunk at `https://splunk:8089`.

> Run this command again any time the Splunk container is recreated (e.g. after an update).

---

## 7. Day-to-day management

```bash
docker start splunk    # Start
docker stop splunk     # Stop
docker logs -f splunk  # Tail logs
docker ps --filter name=splunk  # Check status
```

---

## 8. Verify REST API is reachable from the runner

```bash
docker exec dac-gh-runner curl -sk https://splunk:8089/services/server/info \
  -H "Authorization: Bearer <your-token>" \
  -o /dev/null -w "%{http_code}\n"
# Expected: 200
```

---

## 9. Remove Splunk completely

```bash
docker rm -f splunk
docker volume rm splunk-etc splunk-data
```

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

---

## 3. Wait for Splunk to be healthy

Splunk takes 1–2 minutes on first start.

```bash
# Poll until healthy
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
| Password | `<your-password>` |

> Change the password after first login: **Settings → Users → admin → Edit**.

---

## 5. Generate an API token for DaC workflows

The CI/CD pipeline authenticates to Splunk using a Bearer token (safer than a password).

1. Log in to the web UI
2. Go to **Settings → Tokens**
3. Click **New Token**
4. Set **User**: `admin`, **Expiration**: your preference
5. Copy the token — you won't see it again

Use this token as `SPLUNK_TOKEN` in your `.env` file and as the `SPLUNK_TOKEN` GitHub secret.

---

## 6. Day-to-day management

```bash
# Start
docker start splunk

# Stop
docker stop splunk

# Tail logs
docker logs -f splunk

# Check status
docker ps --filter name=splunk
```

---

## 7. Verify REST API is reachable

```bash
curl -sk https://localhost:8089/services/server/info \
  -H "Authorization: Bearer <your-token>" \
  -o /dev/null -w "%{http_code}\n"
# Expected: 200
```

---

## 8. Remove Splunk completely

```bash
docker rm -f splunk
docker volume rm splunk-etc splunk-data
```

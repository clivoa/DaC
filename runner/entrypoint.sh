#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Fetch a one-time registration token from the GitHub API.
# Requires GITHUB_PAT (Personal Access Token with repo scope) +
# GITHUB_OWNER + GITHUB_REPO to be set in the container environment.
# ---------------------------------------------------------------------------
get_registration_token() {
    curl -sfX POST \
        -H "Authorization: token ${GITHUB_PAT}" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runners/registration-token" \
        | jq -r .token
}

get_removal_token() {
    curl -sfX POST \
        -H "Authorization: token ${GITHUB_PAT}" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runners/remove-token" \
        | jq -r .token
}

# ---------------------------------------------------------------------------
# Validate required environment variables
# ---------------------------------------------------------------------------
: "${GITHUB_OWNER:?'GITHUB_OWNER is required'}"
: "${GITHUB_REPO:?'GITHUB_REPO is required'}"
: "${GITHUB_PAT:?'GITHUB_PAT is required'}"

RUNNER_NAME_RESOLVED="${RUNNER_NAME:-dac-runner-$(hostname)}"
RUNNER_LABELS_RESOLVED="${RUNNER_LABELS:-self-hosted,linux,dac}"
REPO_URL="https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}"

echo "==> Fetching registration token..."
REG_TOKEN=$(get_registration_token)

echo "==> Configuring runner '${RUNNER_NAME_RESOLVED}' for ${REPO_URL}"
echo "    Labels: ${RUNNER_LABELS_RESOLVED}"

./config.sh \
    --url "${REPO_URL}" \
    --token "${REG_TOKEN}" \
    --name "${RUNNER_NAME_RESOLVED}" \
    --labels "${RUNNER_LABELS_RESOLVED}" \
    --work "_work" \
    --unattended \
    --replace

# ---------------------------------------------------------------------------
# Graceful shutdown: deregister runner when the container stops
# ---------------------------------------------------------------------------
cleanup() {
    echo "==> Deregistering runner from GitHub..."
    REMOVE_TOKEN=$(get_removal_token)
    ./config.sh remove --unattended --token "${REMOVE_TOKEN}" || true
}
trap cleanup EXIT SIGTERM SIGINT

echo "==> Runner is ready. Waiting for jobs..."
./run.sh

#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Two authentication modes:
#
#   RUNNER_TOKEN  — one-time registration token from GitHub UI (expires ~1h).
#                   Runner config is persisted in the volume; subsequent
#                   container restarts reuse it without re-registering.
#
#   GITHUB_PAT    — Personal Access Token (repo scope). Fetches a fresh
#                   registration token on every start and enables graceful
#                   deregistration on stop. Recommended for production.
# ---------------------------------------------------------------------------

get_registration_token() {
    if [[ -n "${RUNNER_TOKEN:-}" ]]; then
        echo "${RUNNER_TOKEN}"
    elif [[ -n "${GITHUB_PAT:-}" ]]; then
        curl -sfX POST \
            -H "Authorization: token ${GITHUB_PAT}" \
            -H "Accept: application/vnd.github.v3+json" \
            "https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runners/registration-token" \
            | jq -r .token
    else
        echo "ERROR: set RUNNER_TOKEN (one-time) or GITHUB_PAT (persistent)" >&2
        exit 1
    fi
}

get_removal_token() {
    [[ -z "${GITHUB_PAT:-}" ]] && return 0
    curl -sfX POST \
        -H "Authorization: token ${GITHUB_PAT}" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runners/remove-token" \
        | jq -r .token
}

# ---------------------------------------------------------------------------
# Validate required variables
# ---------------------------------------------------------------------------
: "${GITHUB_OWNER:?'GITHUB_OWNER is required'}"
: "${GITHUB_REPO:?'GITHUB_REPO is required'}"

if [[ -z "${RUNNER_TOKEN:-}" && -z "${GITHUB_PAT:-}" ]]; then
    echo "ERROR: set RUNNER_TOKEN or GITHUB_PAT" >&2
    exit 1
fi

RUNNER_NAME_RESOLVED="${RUNNER_NAME:-dac-runner-$(hostname)}"
RUNNER_LABELS_RESOLVED="${RUNNER_LABELS:-self-hosted,linux,dac}"
REPO_URL="https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}"

# ---------------------------------------------------------------------------
# Register only if not already configured (supports volume-persisted config)
# ---------------------------------------------------------------------------
if [[ ! -f ".runner" ]]; then
    echo "==> Fetching registration token..."
    REG_TOKEN=$(get_registration_token)

    echo "==> Configuring runner '${RUNNER_NAME_RESOLVED}' → ${REPO_URL}"
    echo "    Labels: ${RUNNER_LABELS_RESOLVED}"

    ./config.sh \
        --url "${REPO_URL}" \
        --token "${REG_TOKEN}" \
        --name "${RUNNER_NAME_RESOLVED}" \
        --labels "${RUNNER_LABELS_RESOLVED}" \
        --work "_work" \
        --unattended \
        --replace
else
    echo "==> Runner already configured (using persisted config)"
fi

# ---------------------------------------------------------------------------
# Graceful shutdown: deregister when the container stops (requires PAT)
# ---------------------------------------------------------------------------
cleanup() {
    echo "==> Container stopping..."
    REMOVE_TOKEN=$(get_removal_token)
    if [[ -n "${REMOVE_TOKEN}" ]]; then
        echo "==> Deregistering runner from GitHub..."
        ./config.sh remove --unattended --token "${REMOVE_TOKEN}" || true
    else
        echo "==> No PAT set — skipping deregistration (runner will show offline until next start)"
    fi
}
trap cleanup EXIT SIGTERM SIGINT

echo "==> Runner ready. Waiting for jobs..."
./run.sh

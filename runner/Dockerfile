FROM ubuntu:24.04

# Check for latest version at: https://github.com/actions/runner/releases
ARG RUNNER_VERSION=2.334.0
ARG TARGETARCH=arm64

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl \
    git \
    jq \
    python3 \
    python3-pip \
    python3-venv \
    libssl-dev \
    libffi-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# GitHub runner uses 'x64' instead of 'amd64'
RUN ARCH=$([ "${TARGETARCH}" = "amd64" ] && echo "x64" || echo "${TARGETARCH}") && \
    curl -Lo /tmp/runner.tar.gz \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${ARCH}-${RUNNER_VERSION}.tar.gz" && \
    mkdir -p /home/runner/actions-runner && \
    tar xzf /tmp/runner.tar.gz -C /home/runner/actions-runner && \
    rm /tmp/runner.tar.gz && \
    /home/runner/actions-runner/bin/installdependencies.sh

RUN useradd -m -s /bin/bash runner && \
    chown -R runner:runner /home/runner && \
    echo "runner ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Pre-install Python dependencies used by detection scripts
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages -r /tmp/requirements.txt

COPY runner/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /home/runner/actions-runner
USER runner

ENTRYPOINT ["/entrypoint.sh"]

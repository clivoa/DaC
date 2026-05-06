# Security Policy

## Scope

This repository contains:

- Example Splunk detection rules in YAML format
- Scripts for validating and deploying detections
- CI/CD pipeline configuration for GitHub Actions
- Infrastructure configuration for a self-hosted runner

## Reporting a vulnerability

If you discover a security vulnerability in this project — for example, a flaw in the validation logic, the deployment script, or the runner configuration — please report it by opening a GitHub Issue with the label `security`.

For sensitive disclosures that should not be public, email the repository maintainer directly.

## Sensitive data guidelines

Do not commit the following to this repository:

| What | Why |
|---|---|
| Splunk API tokens | Live credentials — rotate immediately if exposed |
| Splunk passwords | Same as above |
| GitHub PATs or runner tokens | Grant repository access |
| Internal hostnames or IP addresses | Exposes network topology |
| Real threat intelligence indicators | May tip off adversaries or violate TLP |
| SIEM index names or sourcetype names | Exposes data architecture |

All runtime secrets belong in:
- `.env` (local, git-ignored)
- GitHub Actions secrets (`Settings → Secrets and variables → Actions`)

The `.env.example` file documents which variables are required using placeholder values. Never put real values in `.env.example`.

## Detection content

Detections in this repository are examples intended for educational and demonstration purposes. Thresholds, index names, and field names in the example files may not match your environment and must be tuned before use in production.

Do not publish detections that contain classified threat intelligence or information covered by a non-disclosure agreement.

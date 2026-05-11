#!/usr/bin/env python3
"""Deploy Splunk detections from YAML files via REST API."""
import sys
import os
import yaml
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

REPO_ROOT = Path(__file__).parent.parent
DEPLOY_STATUSES = ("draft", "testing", "production", "deprecated")

SEVERITY_MAP = {
    "informational": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "critical": 5,
}


def effective_deploy_status(detection: dict, deploy_status: Optional[str] = None) -> str:
    """Return the deployment status, falling back to the detection lifecycle status."""
    status = deploy_status or detection.get("status", "testing")
    if status not in DEPLOY_STATUSES:
        expected = ", ".join(DEPLOY_STATUSES)
        raise ValueError(f"Invalid deploy status '{status}'. Expected one of: {expected}")
    return status


def should_disable_saved_search(detection: dict, deploy_status: Optional[str] = None) -> bool:
    """Decide whether the Splunk saved search should be disabled."""
    if detection.get("status") in ("draft", "deprecated"):
        return True
    return effective_deploy_status(detection, deploy_status) != "production"


def to_splunk_params(detection: dict, deploy_status: Optional[str] = None) -> Dict[str, Any]:
    """Map detection YAML fields to Splunk saved search POST parameters."""
    params: Dict[str, Any] = {
        "description": detection.get("description", ""),
        "disabled": "1" if should_disable_saved_search(detection, deploy_status) else "0",
        "is_scheduled": "0",
    }

    if schedule := detection.get("schedule"):
        params["is_scheduled"] = "1"
        params["cron_schedule"] = schedule.get("cron", "*/15 * * * *")
        params["dispatch.earliest_time"] = schedule.get("earliest", "-15m")
        params["dispatch.latest_time"] = schedule.get("latest", "now")

    if alert := detection.get("alert"):
        params["alert_condition"] = alert.get("condition", "")
        params["alert.severity"] = SEVERITY_MAP.get(alert.get("severity", "medium"), 3)
        params["alert.suppress"] = "1" if alert.get("suppress") else "0"
        if period := alert.get("suppress_period"):
            params["alert.suppress.period"] = period

    return params


def deploy_file(
    file_path: str,
    client,
    app: str,
    dry_run: bool,
    deploy_status: Optional[str] = None,
) -> dict:
    with open(file_path) as f:
        detection = yaml.safe_load(f)

    name = detection["name"]
    search = detection["search"].strip()
    params = to_splunk_params(detection, deploy_status)
    lifecycle_status = detection.get("status", "unknown")
    resolved_status = effective_deploy_status(detection, deploy_status)
    splunk_state = "enabled" if params["disabled"] == "0" else "disabled"

    existing = client.get_saved_search(name, app=app)
    action = "create" if existing is None else "update"

    if dry_run:
        return {
            "file": file_path,
            "name": name,
            "action": f"would-{action}",
            "ok": True,
            "lifecycle_status": lifecycle_status,
            "deploy_status": resolved_status,
            "splunk_state": splunk_state,
        }

    try:
        if action == "create":
            client.create_saved_search(name, search, params, app=app)
        else:
            client.update_saved_search(name, search, params, app=app)
        return {
            "file": file_path,
            "name": name,
            "action": action,
            "ok": True,
            "lifecycle_status": lifecycle_status,
            "deploy_status": resolved_status,
            "splunk_state": splunk_state,
        }
    except Exception as e:
        return {
            "file": file_path,
            "name": name,
            "action": action,
            "ok": False,
            "error": str(e),
            "lifecycle_status": lifecycle_status,
            "deploy_status": resolved_status,
            "splunk_state": splunk_state,
        }


def print_summary(results: List[dict], dry_run: bool) -> bool:
    all_ok = True
    for r in results:
        icon = "✓" if r["ok"] else "✗"
        dry = " (dry-run)" if dry_run else ""
        state = (
            f" [{r['splunk_state']}, lifecycle_status={r['lifecycle_status']}, "
            f"deploy_status={r['deploy_status']}]"
        )
        print(f"{icon} [{r['action']}{dry}] {r['name']}{state}")
        if not r["ok"]:
            print(f"  ERROR: {r.get('error', 'unknown')}")
            all_ok = False
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Deploy Splunk detections to a Splunk instance")
    parser.add_argument("files", nargs="*", help="Detection YAML files to deploy")
    parser.add_argument("--all", action="store_true", help="Deploy all detections in repo")
    parser.add_argument("--splunk-url", default=os.getenv("SPLUNK_URL"))
    parser.add_argument("--splunk-token", default=os.getenv("SPLUNK_TOKEN"))
    parser.add_argument("--splunk-username", default=os.getenv("SPLUNK_USERNAME"))
    parser.add_argument("--splunk-password", default=os.getenv("SPLUNK_PASSWORD"))
    parser.add_argument("--app", default=os.getenv("SPLUNK_APP", "search"))
    parser.add_argument(
        "--deploy-status",
        default=os.getenv("DEPLOY_STATUS"),
        choices=DEPLOY_STATUSES,
        help="Override YAML lifecycle status when deciding whether saved searches are enabled",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deployed without making changes",
    )
    args = parser.parse_args()

    if not args.splunk_url:
        print("ERROR: SPLUNK_URL is required (env var or --splunk-url)")
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).parent))
    from splunk_client import SplunkClient

    client = SplunkClient(
        args.splunk_url,
        token=args.splunk_token,
        username=args.splunk_username,
        password=args.splunk_password,
    )

    if not client.health_check():
        print(f"ERROR: Cannot reach Splunk at {args.splunk_url}")
        sys.exit(1)

    files: List[str] = list(args.files)
    if args.all:
        files = [str(p) for p in (REPO_ROOT / "detections").rglob("*.yml")]

    if not files:
        print("No files to deploy.")
        sys.exit(0)

    print(f"Deploying {len(files)} detection(s) to {args.splunk_url} (app={args.app})")
    if args.deploy_status:
        print(f"Deployment status override: {args.deploy_status}")
    else:
        print("Deployment status override: not set (using each detection's YAML status)")
    if args.dry_run:
        print("--- DRY RUN ---")

    results = [
        deploy_file(f, client, args.app, args.dry_run, args.deploy_status)
        for f in files
    ]
    ok = print_summary(results, args.dry_run)

    deployed = sum(1 for r in results if r["ok"])
    print(f"\n{deployed}/{len(results)} detections deployed successfully")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

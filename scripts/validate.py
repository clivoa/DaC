#!/usr/bin/env python3
"""Validate Splunk detection YAML files against schema and optionally Splunk's SPL parser."""
import sys
import os
import yaml
import json
import argparse
import jsonschema
from pathlib import Path
from typing import List, Dict, Tuple, Optional

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "detection.schema.json"


def _annotation(level: str, file: str, msg: str) -> str:
    return f"::{level} file={file}::{msg}"


def load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def check_yaml_syntax(file_path: str) -> Tuple[bool, str]:
    try:
        with open(file_path) as f:
            yaml.safe_load(f)
        return True, ""
    except yaml.YAMLError as e:
        return False, str(e)


def check_schema(detection: dict, schema: dict) -> List[str]:
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or 'root'}: {e.message}"
        for e in sorted(validator.iter_errors(detection), key=lambda e: e.path)
    ]


def check_spl_syntax(search: str, client) -> Tuple[bool, str]:
    try:
        result = client.validate_spl(search)
        messages = result.get("messages", [])
        errors = [m for m in messages if m.get("type") == "FATAL"]
        if errors:
            return False, errors[0].get("text", "SPL syntax error")
        return True, ""
    except Exception as e:
        return False, f"Could not reach Splunk for syntax check: {e}"


def warnings_for(detection: dict) -> List[str]:
    warns = []
    if detection.get("status") == "draft":
        warns.append("Detection is still in 'draft' status — not yet ready for review")
    if not detection.get("tags", {}).get("mitre_attack"):
        warns.append("No MITRE ATT&CK tags defined")
    if not detection.get("schedule") and detection.get("type") in ("alert", "scheduled_report"):
        warns.append("No schedule defined for an alert-type detection")
    return warns


def validate_file(file_path: str, schema: dict, client=None) -> dict:
    result = {"file": file_path, "passed": True, "errors": [], "warnings": []}

    ok, msg = check_yaml_syntax(file_path)
    if not ok:
        result["passed"] = False
        result["errors"].append(f"YAML syntax: {msg}")
        return result

    with open(file_path) as f:
        detection = yaml.safe_load(f)

    schema_errors = check_schema(detection, schema)
    if schema_errors:
        result["passed"] = False
        result["errors"].extend([f"Schema: {e}" for e in schema_errors])

    if client and "search" in detection:
        ok, msg = check_spl_syntax(detection["search"].strip(), client)
        if not ok:
            result["passed"] = False
            result["errors"].append(f"SPL: {msg}")

    result["warnings"].extend(warnings_for(detection))
    return result


def print_results(results: List[dict], github_annotations: bool = False) -> bool:
    all_passed = True
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        status = "PASS" if r["passed"] else "FAIL"
        print(f"\n{icon} [{status}] {r['file']}")

        for err in r["errors"]:
            print(f"  ERROR: {err}")
            if github_annotations:
                print(_annotation("error", r["file"], err))
        for warn in r["warnings"]:
            print(f"  WARN:  {warn}")
            if github_annotations:
                print(_annotation("warning", r["file"], warn))

        if not r["passed"]:
            all_passed = False

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Validate Splunk detection YAML files")
    parser.add_argument("files", nargs="*", help="Detection files to validate")
    parser.add_argument("--all", action="store_true", help="Validate all detections in repo")
    parser.add_argument("--splunk-url", default=os.getenv("SPLUNK_URL"))
    parser.add_argument("--splunk-token", default=os.getenv("SPLUNK_TOKEN"))
    parser.add_argument("--splunk-username", default=os.getenv("SPLUNK_USERNAME"))
    parser.add_argument("--splunk-password", default=os.getenv("SPLUNK_PASSWORD"))
    parser.add_argument("--no-splunk", action="store_true", help="Skip live SPL syntax check")
    parser.add_argument("--github-annotations", action="store_true", help="Emit GitHub Actions annotations")
    args = parser.parse_args()

    schema = load_schema()

    client = None
    if not args.no_splunk and args.splunk_url:
        sys.path.insert(0, str(Path(__file__).parent))
        from splunk_client import SplunkClient

        client = SplunkClient(
            args.splunk_url,
            token=args.splunk_token,
            username=args.splunk_username,
            password=args.splunk_password,
        )
        if not client.health_check():
            print("WARNING: Cannot reach Splunk — skipping live SPL validation")
            client = None
    elif not args.no_splunk and not args.splunk_url:
        print("INFO: SPLUNK_URL not set — skipping live SPL validation")

    files: List[str] = list(args.files)
    if args.all:
        files = [str(p) for p in (REPO_ROOT / "detections").rglob("*.yml")]

    if not files:
        print("No detection files to validate.")
        sys.exit(0)

    results = [validate_file(f, schema, client) for f in files]
    passed = print_results(results, github_annotations=args.github_annotations)

    total = len(results)
    ok_count = sum(1 for r in results if r["passed"])
    print(f"\n{'='*50}")
    print(f"Result: {ok_count}/{total} detections passed")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

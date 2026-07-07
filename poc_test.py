#!/usr/bin/env python3
"""AutoPoC Test Script for komi-learn

This script validates komi-learn running in OpenShift containers.
Since komi-learn is a CLI tool (Job workload), tests are run via kubectl
against pre-deployed Job manifests rather than HTTP endpoints.

Test scenarios:
1. cli-help: Verify CLI is installed and responds to --help
2. demo-loop: Run the full learning pipeline demo (offline, no API key)
3. test-suite: Run pytest test suite inside the container
"""
import json
import os
import subprocess
import sys
import time

NAMESPACE = os.environ.get("NAMESPACE", "autopoc-test-builds")
results = []


def run_kubectl(args: list[str], timeout: int = 120) -> tuple[int, str]:
    """Run a kubectl command and return (returncode, output)."""
    cmd = ["kubectl"] + args + ["-n", NAMESPACE]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {timeout}s"


def check_job(job_name: str, scenario_name: str, description: str,
              expected_in_output: str | None = None, timeout: int = 120):
    """Check if a Job completed successfully and validate its output."""
    start = time.time()

    # Check job status
    rc, status_out = run_kubectl(
        ["get", "job", job_name, "-o", "jsonpath={.status.succeeded}"]
    )
    succeeded = status_out.strip() == "1"

    # Get job logs
    rc_logs, logs = run_kubectl(["logs", f"job/{job_name}"], timeout=30)

    duration = round(time.time() - start, 2)

    if not succeeded:
        results.append({
            "scenario_name": scenario_name,
            "status": "fail",
            "output": logs[:2000],
            "error_message": "Job did not complete successfully",
            "duration_seconds": duration,
        })
        return

    if expected_in_output and expected_in_output not in logs:
        results.append({
            "scenario_name": scenario_name,
            "status": "fail",
            "output": logs[:2000],
            "error_message": f"Expected '{expected_in_output}' not in output",
            "duration_seconds": duration,
        })
        return

    results.append({
        "scenario_name": scenario_name,
        "status": "pass",
        "output": logs[:2000],
        "error_message": None,
        "duration_seconds": duration,
    })


# === SCENARIOS ===

# Scenario 1: CLI Help
check_job("komi-learn-cli-help", "cli-help",
          "Verify komi-learn CLI responds to --help",
          expected_in_output="komi-learn")

# Scenario 2: Demo Loop
check_job("komi-learn-demo-loop", "demo-loop",
          "Run full learning pipeline demo",
          expected_in_output="SESSION 2")

# Scenario 3: Test Suite (may fail due to pre-existing test bugs)
check_job("komi-learn-test-suite", "test-suite",
          "Run pytest test suite",
          expected_in_output="passed")

# === END SCENARIOS ===

print(json.dumps({"results": results}, indent=2))
sys.exit(1 if any(r["status"] in ("fail", "error") for r in results) else 0)

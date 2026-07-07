# PoC Plan: komi-learn

## Project Classification
- **Type:** infrastructure
- **Key Technologies:** Python 3.10+, stdlib-only core, optional sentence-transformers/blake3/pynacl
- **ODH Relevance:** Agent memory and continuous learning infrastructure for AI coding assistants. Validates whether CLI-based agent tooling can be containerized and tested on OpenShift as a repeatable CI/CD pattern.

## PoC Objectives
1. Containerize the komi-learn CLI tool in a UBI-based image and verify it runs on OpenShift
2. Validate the full learning loop (distill, recall, curate) executes correctly in a containerized environment
3. Run the project's test suite inside the container to confirm compatibility with OpenShift's security constraints (random UID, read-only root filesystem)
4. Demonstrate that Python stdlib-only agent tooling can be packaged and validated as a Job workload on OpenShift

## Infrastructure Requirements
- **Resource Profile:** small (256Mi RAM, 250m CPU)
- **GPU Required:** No
- **Persistent Storage:** None (all operations use temp directories)
- **Sidecar Containers:** None
- **Deployment Model:** Job (CLI tool that runs and exits)
- **Listens on Port:** No
- **Long Running:** No
- **Needs LLM API:** No (demo_loop.py uses a scripted model, no real LLM needed)

## Test Scenarios

### Scenario 1: cli-help
- **Description:** Verify the komi-learn CLI is installed and responds to --help
- **Type:** cli
- **Input:** `komi-learn --help`
- **Expected:** Exits 0, shows usage information with subcommands (install, doctor, status, config, sync, etc.)
- **Timeout:** 15 seconds

### Scenario 2: demo-loop
- **Description:** Run the built-in demo_loop.py which exercises the full learning pipeline (distill, recall, curate, pool) with a scripted model -- no API key needed
- **Type:** cli
- **Input:** `python examples/demo_loop.py`
- **Expected:** Exits 0, outputs SESSION 1, DISTILL, SESSION 2, RESULT sections showing the learning loop working end-to-end
- **Timeout:** 60 seconds

### Scenario 3: test-suite
- **Description:** Run the project's pytest test suite inside the container
- **Type:** cli
- **Input:** `python -m pytest tests/ -x -q --tb=short`
- **Expected:** Exits 0, all tests pass (or the vast majority pass)
- **Timeout:** 120 seconds

## Dockerfile Considerations
- Use `registry.access.redhat.com/ubi9/python-312` as base image
- Install with `pip install -e .[dev]` to include pytest for testing
- No EXPOSE needed (no server port)
- Use Job deployment model with ENTRYPOINT for the CLI
- Ensure git is available (pool module uses git subprocess calls)

## Deployment Considerations
- Deploy as Kubernetes Jobs (one per test scenario)
- No Service or Route needed
- No secrets required (demo runs offline with scripted model)
- Jobs should have `backoffLimit: 1` and `activeDeadlineSeconds: 120`

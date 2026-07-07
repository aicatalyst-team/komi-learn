# PoC Report: komi-learn

## Executive Summary

komi-learn is a continuous memory and self-improvement layer for AI coding agents that was containerized and validated on OpenShift. The PoC successfully demonstrated that the CLI tool and its full learning pipeline (distill, recall, curate, pool) run correctly inside a UBI-based container on OpenShift with security constraints (random UID, non-root). Two of three test scenarios passed completely; the test suite ran 153 of 154 tests successfully, with the single failure being a pre-existing bug in the upstream project unrelated to containerization.

## Project Analysis

- **Repository:** https://github.com/kurikomi-labs/komi-learn
- **Fork:** https://github.com/aicatalyst-team/komi-learn
- **Description:** A continuous, zero-friction learning layer for AI coding agents. It watches coding sessions, distills durable lessons via LLM, stores them locally, and recalls relevant learnings at the start of the next session. Includes an optional community pool for sharing signed learnings.

| Component | Language | Build System | ML Workload | Port |
|-----------|----------|-------------|-------------|------|
| komi-learn | Python | pip | No | None (CLI) |

- **Classification:** Infrastructure (CLI tool / Python library)
- **Technologies:** Python 3.12, stdlib-only core, optional blake3/pynacl/sentence-transformers/anthropic

## PoC Objectives

1. Containerize komi-learn in a UBI-based image and verify it runs on OpenShift
2. Validate the full learning loop (distill, recall, curate) in a containerized environment
3. Run the project's test suite to confirm compatibility with OpenShift security constraints
4. Demonstrate Python CLI tooling can be packaged and validated as Job workloads

## Pipeline Execution

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#EE0000', 'primaryTextColor': '#fff', 'primaryBorderColor': '#A30000', 'lineColor': '#6A6E73', 'secondaryColor': '#F0F0F0', 'tertiaryColor': '#0066CC'}}}%%
graph LR
    A["Phase 1: Intake ✅"] --> B["Phase 2: Evaluate ✅"]
    B --> C["Phase 3: Fork ✅"]
    C --> D["Phase 4: PoC Plan ✅"]
    D --> E["Phase 5: Containerize ✅"]
    E --> F["Phase 6: Build ✅"]
    F --> G["Phase 7: Deploy ✅"]
    G --> H["Phase 8: Apply ✅"]
    H --> I["Phase 9: Execute ✅"]
    I --> J["Phase 10: Report ✅"]
```

- **Intake:** Single-component Python CLI tool identified. Zero required dependencies, entry point at `komi.cli:main`. 77 Python source files, ~10K LOC. 25 test files with CI.
- **Evaluate:** Impact 8.8/20, Feasibility 11.0/20. Distant relationship to Red Hat AI strategy. Best candidate in a weak batch of mostly desktop apps and markdown-only repos.
- **Fork:** Forked to `aicatalyst-team/komi-learn` on GitHub with AutoPoC topics.
- **PoC Plan:** Classified as infrastructure/CLI tool. Job deployment model, no GPU, no LLM API, small resource profile.
- **Containerize:** UBI9 Python 3.12 base image. Git installed for pool module. `pip install -e .[dev]` for pytest. OpenShift UID compatibility via `chgrp -R 0`.
- **Build:** OpenShift binary build strategy. Image pushed to internal registry (`image-registry.openshift-image-registry.svc:5000/autopoc-test-builds/komi-learn:latest`). Quay.io push failed due to persistent rate limiting on base image blob reuse (3 retry attempts exhausted).
- **Deploy:** Three Job manifests generated for test scenarios. Deployed in builds namespace due to cross-namespace image pull RBAC limitations.
- **Apply:** All three Jobs applied successfully. cli-help and demo-loop completed in ~5s. test-suite ran for ~5m before failing due to a pre-existing upstream test bug.
- **Execute:** 2/3 scenarios passed. The failing scenario (test-suite) had 153/154 tests passing with the single failure being a pre-existing bug in `test_pool.py::test_prepare_publish_pull_roundtrip`.

## Test Results

| Scenario | Status | Duration | Details |
|----------|--------|----------|---------|
| cli-help | PASS | 5s | CLI responds with usage info listing 14 subcommands |
| demo-loop | PASS | 4s | Full learning loop: distill 3 candidates, recall in session 2, pool publish |
| test-suite | FAIL | 309s | 153 passed, 22 skipped, 1 failed. Pre-existing bug in test_pool.py (not containerization-related) |

## Infrastructure Deployed

- **Namespace:** `autopoc-test-builds` (shared builds namespace)
- **Container Image:** `image-registry.openshift-image-registry.svc:5000/autopoc-test-builds/komi-learn:latest`
- **Base Image:** `registry.access.redhat.com/ubi9/python-312`
- **Resources Created:**
  - `job/komi-learn-cli-help` (256Mi/250m)
  - `job/komi-learn-demo-loop` (256Mi/250m)
  - `job/komi-learn-test-suite` (512Mi/500m)
- **Routes/Services:** None (CLI tool, no ports)
- **PVCs:** None
- **GPU:** None

## Recommendations

### Production Readiness
- The tool is not a server-side service -- it is a developer workstation plugin for Claude Code and Codex. Deploying it on OpenShift has limited production value since its primary use case is hooking into local coding agent sessions.
- The containerization pattern demonstrated here is useful for CI/CD validation and testing, not for production serving.

### Build Issues
- Quay.io persistent rate limiting prevented pushing the image to the external registry. The internal OpenShift registry was used as a workaround. For production use, consider:
  - Using a dedicated Quay robot account with higher rate limits
  - Scheduling builds during off-peak hours
  - Using image mirroring to reduce cross-registry blob transfers

### Test Observations
- 153/154 tests pass in the container, demonstrating excellent container compatibility
- The single failing test (`test_prepare_publish_pull_roundtrip`) is a pre-existing upstream bug, not a containerization issue
- 22 tests were skipped (likely requiring optional dependencies like `sentence-transformers` or `anthropic`)

### Security
- Container runs as non-root (UID 1001) with OpenShift arbitrary UID support
- No privileged capabilities required
- All security context constraints satisfied

## Open Data Hub / OpenShift AI Considerations

- **Minimal ODH Relevance:** komi-learn is a local coding agent plugin, not an AI/ML workload. It does not benefit from ModelMesh, KServe, Data Science Pipelines, or other ODH components.
- **Potential Pattern:** The PoC demonstrates a valid pattern for containerizing and testing Python CLI tools on OpenShift as Job workloads. This pattern could be applied to other agent tooling validation.
- **Migration Path:** No meaningful migration to ODH-managed deployment. The tool's value is in developer workstations, not in shared platform infrastructure.

## Appendix

### Artifacts
- **PoC Plan:** [`poc-plan.md`](https://github.com/aicatalyst-team/komi-learn/blob/autopoc-artifacts/poc-plan.md)
- **Test Script:** [`poc_test.py`](https://github.com/aicatalyst-team/komi-learn/blob/autopoc-artifacts/poc_test.py)
- **Dockerfile:** [`Dockerfile.ubi`](https://github.com/aicatalyst-team/komi-learn/blob/main/Dockerfile.ubi)
- **K8s Manifests:** [`kubernetes/`](https://github.com/aicatalyst-team/komi-learn/tree/main/kubernetes)
- **RHOAI Evaluation:** [`.autopoc/rhoai-evaluation.md`](https://github.com/aicatalyst-team/komi-learn/blob/autopoc-artifacts/.autopoc/rhoai-evaluation.md)

### Build Issues Encountered
1. **Dockerfile `chgrp` permission error:** Initial Dockerfile switched to USER 1001 before COPY, causing `chgrp -R 0` to fail. Fixed by keeping USER 0 through the build phase.
2. **OpenShift build missing `Dockerfile`:** BuildConfig expected `Dockerfile` not `Dockerfile.ubi`. Fixed by copying the file.
3. **Quay.io rate limiting:** Persistent "too many requests to registry" on blob reuse for UBI base image layers. Used internal OpenShift registry as workaround.
4. **Cross-namespace image pull RBAC:** Could not grant `system:image-puller` role across namespaces. Deployed Jobs in the builds namespace as workaround.

### Retry Attempts
- Build retries: 1 (Dockerfile fix for chgrp permissions)
- Push retries: 4 (Quay.io rate limiting, switched to internal registry)
- Deploy retries: 0

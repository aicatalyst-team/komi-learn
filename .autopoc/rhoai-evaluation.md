# RHOAI Evaluation: komi-learn

## Strategy: Red Hat AI 2026

### Impact Dimensions

| Dimension | Score (0-20) | Rationale |
|-----------|-------------|-----------|
| audience_value | 12 | Developer-focused tool for AI coding agents. Relevant audience but niche (coding agent power users). Growing category but narrow reach. |
| strategic_alignment | 10 | Adjacent to agentic AI strategy area. Provides agent memory/learning but is a local plugin, not a platform service. Does not integrate with Llama Stack, MCP, AI Hub, or other Red Hat AI stack components. |
| strategy_fit | 8 | Tangentially fits "agentic-ai" category as agent memory infrastructure. However, it is a local-first tool with no server component - matches the "duplicate_if" pattern: "another local-first agent framework with no durable platform angle." |
| platform_leverage | 6 | CLI tool with zero required dependencies and no network service. Containerizing it adds minimal OpenShift platform value. No meaningful use of Kubernetes features (services, scaling, PVCs for models). |
| demo_potential | 8 | Demo would show a CLI tool running in a container executing its learning pipeline. Not visually compelling. No web UI, no API endpoints to interact with. |

**Impact Score: 8.8/20**

### Feasibility Dimensions

| Dimension | Score (0-20) | Rationale |
|-----------|-------------|-----------|
| container_readiness | 6 | Python stdlib-only, pip-installable. No Dockerfile exists. Single entry point (CLI). Easy to containerize as a Job workload. |
| dependency_profile | 16 | Zero required dependencies (stdlib only). Optional extras well-defined but not needed for core functionality. Clean dependency profile. |
| reproduction_confidence | 12 | Clear install instructions, 25 test files, CI pipeline. Well-structured codebase. However, testing a CLI tool in containers requires wrapping in Job manifests. |
| complexity_sweet_spot | 10 | Simple enough to containerize quickly, but provides limited platform value. The PoC would validate basic containerization rather than interesting platform interactions. |

**Feasibility Score: 11.0/20**

### Overall Assessment

- **Relationship to Red Hat AI:** distant - A local-first coding agent plugin that does not integrate with or validate any Red Hat AI platform capability.
- **Strategy Areas:** agentic-ai (tangential)
- **Capability Labels:** agent-runtime (loose fit)

### Strengths
- Zero-dependency Python package makes containerization trivial
- Well-tested codebase with 25 test files and CI
- MIT licensed, active development
- Interesting concept (persistent agent memory)

### Risks
- No server component - containerization adds minimal value
- Desktop-oriented tool (hooks into Claude Code/Codex local sessions)
- No GPU, no ML inference, no model serving - limited RHOAI relevance
- PoC would prove "Python CLI runs in container" rather than platform capability

### Recommendation
The project has low strategic alignment but is the most containerization-friendly candidate in the current batch. The PoC will demonstrate basic Python CLI containerization on OpenShift as a Job workload, running the built-in demo and test suite.

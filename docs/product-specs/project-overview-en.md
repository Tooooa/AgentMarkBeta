# project-overview.en

## One-line purpose
This document gives agents a fast, code-free understanding of AgentMark goals, boundaries, and expected workflows.

## Core content
### Mission
- AgentMark focuses on behavioral watermarking for LLM agents.
- It aims to preserve downstream utility while enabling provenance verification.
- The repository combines algorithm implementation, integration, visualization, and evaluation.

### Value proposition
- Researchers get reproducible benchmark pipelines.
- Engineers get low-intrusion integration paths.
- Platform teams get behavior-level ownership signals.

### Scope
- ToolBench tool-use experiments.
- ALFWorld embodied tasks.
- Oasis social simulation experiments.
- RLNC and semantic rewriting robustness evaluations.

### Out-of-scope
- It is not a replacement for every text watermark method.
- It is not a hosted production SaaS.
- Isolated vendor trees are not enforced by main repository guardrails.

### Building blocks
- `agentmark/core`: sampler, codec, parser, simulation helpers.
- `agentmark/sdk`: integration wrappers and prompt adapters.
- `agentmark/proxy`: OpenAI Chat Completions compatible gateway.
- `dashboard/server`: API and session orchestration.
- `dashboard/src`: user interaction and visualization.
- `experiments/*`: scenario-driven pipelines and evaluation scripts.

### Typical workflow
1. Prepare runtime environment and credentials.
2. Start backend/frontend or proxy mode.
3. Run experiment scripts with selected configs.
4. Inspect logs and behavior traces.
5. Run robustness and false-positive analyses.

### Inputs and outputs
- Inputs: task configs, model endpoints, datasets, payload bits.
- Outputs: trajectories, action weights, evaluation metrics, visual artifacts.

### Runtime prerequisites
- Python 3.9+ for main stack.
- Separate Python 3.10+ environment for Oasis subproject.
- ToolBench retriever cache and data folder must be prepared.

### Maintenance policy
- docs directory is the source of truth for engineering conventions.
- README files remain external onboarding entry points.
- Boundary changes must update dependency rules and CI policy.

## Agent behavior guidance
- Read this file and `environments-matrix.md` before touching code.
- Classify changes by layer before implementation.
- Update architecture docs when dependency boundaries change.
- If a decision affects reliability or risk, update observability and quality docs.
- Escalate unresolved architecture intent with `NEEDS_HUMAN_REVIEW`.

## Related files
- [../../README_en.md](../../README_en.md)
- [./environments-matrix.md](./environments-matrix.md)
- [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
- [../operations/runbook-local-dev.md](../operations/runbook-local-dev.md)

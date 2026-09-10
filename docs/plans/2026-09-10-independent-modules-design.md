# Independent video-pipeline modules

## Decision

Keep one public repository, but make each production capability independently runnable and testable. The shared package owns only local job storage, media utilities, status, reporting, feedback and notification primitives. A module owns its workflow, prompts, rules, agent configuration and tests.

An editor's choice of Codex, Claude Code, GLM or another agent is an execution choice, not a product dependency.

## Public modules

- `draft-review`: checks an editor's first draft against the approved script and editing rules.
- `conformer`: will combine host conforming and screen matching into a Final Cut rough-cut workflow. The existing A-roll and screen-retrieval work are internal conformer components, not separate user-facing products.

Both modules get their own command-line entry point and can be installed from the same repository. The umbrella `video-pipeline` command remains for compatibility and module discovery.

## Agent boundary

Modules exchange a versioned JSON task bundle with an optional agent adapter. The task contains the module/task name, prompt, response schema and a manifest of permitted evidence. The result contains structured output, adapter/model labels and usage.

Supported execution shapes are optional adapters rather than requirements:

- a generic command configured as an argument array, suitable for an agent CLI or local wrapper;
- an OpenAI-compatible endpoint;
- Claude Code as a convenience adapter that may itself route to any configured model;
- no-agent mode, which completes deterministic preparation and clearly reports that semantic analysis remains pending.

Provider secrets and model choices remain in private per-module configuration. Shared core configuration contains no GLM-, Claude- or Codex-specific fields. Legacy review environment variables remain temporary aliases so existing editor setups continue to work.

## Dependency and failure rules

- Importing or testing one module must not import another production module.
- A missing optional agent cannot prevent local media analysis or evidence preparation.
- No module may silently label an agent-free partial run as a complete semantic review.
- Agent failures are module-local and become actionable `needs_attention` results.
- Production media, transcripts, screenshots, reports and credentials remain outside Git.

## Test and benchmark policy

Each module owns unit tests and sanitized fixtures. A benchmark records which adapter, if any, produced semantic inputs; it is not globally forced online or offline. The September SSL/domain run is stored as evidence of the current conformer components, with its failed GLM attempt clearly separated from the deterministic retrieval results.

## Compatibility

`video-pipeline review`, `video-pipeline batch`, existing private configuration and report fields continue to work. New names use `agent` rather than `GLM` or `provider` where the concept is generic. Deprecated names are accepted at the boundary and translated inside `draft-review`; they are not part of the shared-core contract.

# Modules

One repository contains a small shared core and independently runnable modules. The core supplies local storage, media utilities, reports, statuses, feedback and notification primitives. It does not choose a model.

## `draft-review`

Status: `production_mvp`

Command: `video-draft-review`

Checks an edited tutorial against the approved script and editing standards. It owns its rules, prompts, agent adapters, module configuration and tests. It can use any configured agent or stop after deterministic evidence preparation.

The compatible umbrella commands remain:

```bash
video-pipeline review ...
video-pipeline batch ...
```

## `conformer`

Status: `benchmark_components`

Command: `video-conformer`

The production objective is to select complete host takes against the canonical script, derive visual beats, retrieve screen footage, distinguish outcome states, and generate a prepared Final Cut timeline.

`aroll` and `screen-matcher` are internal components of the conformer. They are not separate editor-facing workflows. Their existing benchmarks should be preserved, but the repository must not claim the full conformer is built until real inputs run end to end.

The conformer can define its own optional agent adapters when semantic stages are implemented. It must not inherit the review module's agent choice.

## Module rules

- A module can be invoked and tested without importing another production module.
- Each module owns its configuration, prompts, rules, schemas and fixtures.
- Shared job IDs and artifact metadata remain compatible across modules.
- Agent/model choice is private, optional and module-scoped.
- A local deterministic stage can run without an agent.
- A missing semantic stage must be reported as pending or blocked, never as a successful clean result.
- Production evidence stays outside this public repository.

List the installed boundaries with:

```bash
video-pipeline modules
```

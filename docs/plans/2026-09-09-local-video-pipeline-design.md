# Local-first video pipeline design

## Goal

Give a small editing team a reviewer they can run on their own Macs before they hand final videos to the configured final reviewer. Reduce review time, video uploads, repeated media processing, and unnecessary model calls.

## Approved workflow

1. An editor selects local videos and their approved scripts.
2. The Mac extracts transcripts, frames, screen text, and technical measurements.
3. Deterministic checks and GLM produce a timestamped local report with evidence and suggested fixes.
4. The editor makes the changes.
5. The editor confirms the batch is ready for the final reviewer. Version 0.1 does not recheck revisions.
6. A private relay can post accurate batch counts to Google Chat and mention the final reviewer and the responsible editor.
7. The final reviewer performs final approval.

## Architecture

One public repository contains a shared core and independent modules. The core owns job identity, caching, status, model adapters, reports, and notifications. Modules own their prompts, rules, tests, and results.

The draft-review module is the first production module. A-roll conforming and screen matching remain independent modules that can reuse the core.

Raw media and reports stay outside the repository. The optional relay receives metadata only. Model adapters support an OpenAI-compatible GLM endpoint and a safe command invocation. A cloud model sees only the evidence included in its requests; a local command can keep all evidence local.

## Status model

- `running`: local checks are in progress.
- `review_complete`: the report exists and the editor is making changes.
- `needs_attention`: one or more jobs could not be checked.
- `ready_for_reviewer`: the editor confirms the requested changes were made.
- `approved`: reserved for the final reviewer's later approval action.

`review_complete` never means `ready_for_reviewer`.

## Improvement model

Every issue records its source, rule version, model, and confidence. Feedback is scoped to a single video, a module, or the shared pipeline. Shared changes are proposed as versioned rule or code changes and tested against sanitized fixtures before merge. Production evidence never enters the public repository.

## First release acceptance

- A five-video batch can finish or resume after interruption.
- Reports contain timestamps, problem statements, fixes, confidence, and local evidence.
- Repeated runs reuse cached work for unchanged files.
- Ready status requires editor confirmation.
- Notifications use accurate totals and real configured Chat user IDs.
- Notification retries cannot create duplicate batch events.
- No production media or secrets are written inside the repository.

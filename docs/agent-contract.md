# Agent task contract

Modules use `video-pipeline-agent-task/1` when they need judgment from an external agent. The contract keeps the module independent from the program or model that handles the task.

## Request

The module writes a JSON request containing:

- `contract_version`;
- `module` and `task`;
- `system_prompt` and `prompt`;
- the required `response_schema`;
- an allowlist of local `evidence_files`.

The configured command receives the request path through `{request_file}`. `{evidence_manifest}` contains the same explicit evidence allowlist.

## Response

The command writes JSON to `{response_file}` or standard output. Its contents must match the schema in the request. The module records the adapter/model label, call usage when available, and a content-based cache signature.

The command is an argument array and never runs through a shell. Credentials belong to the command's private environment or the editor's agent configuration, not the request or repository.

## No-agent mode

`none` is a valid adapter. The module saves the request bundle and deterministic artifacts, then reports that semantic work remains pending. It must not turn the absence of an agent into a clean-review claim.

## Example wrapper shape

```text
my-agent-wrapper REQUEST_JSON RESPONSE_JSON
```

The wrapper may use Codex, Claude Code, GLM, a local model or another system. That choice does not change the module contract.

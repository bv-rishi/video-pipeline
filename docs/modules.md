# Modules

## `draft-review`

Production MVP. Checks an edited tutorial against the approved script and the channel's editing standards. Produces timestamped findings for the editor.

## `aroll`

Planned promotion of the host-conformer benchmark. It will align the host recording to exact script lines and identify likely usable takes. It does not decide screen footage.

## `screen-matcher`

Planned promotion of the screen-retrieval benchmark. It will find candidate screen states, distinguish exact evidence from substitutes or missing footage, and retain attempt/outcome metadata.

All modules use the same job identity, storage, status, and version fields. A module can change independently as long as it preserves the shared job contract.

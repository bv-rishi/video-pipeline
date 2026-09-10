# Video Pipeline

Video Pipeline is a public, local-first toolkit for producing and checking tutorial videos. Editors choose only the module they need. Raw videos stay on their Macs.

The repository does not require GLM, Codex, Claude Code, or any other specific model. A module can use the agent already available on that computer, connect through a compatible API, invoke a configured local command, or prepare evidence without an agent.

## Independent modules

### `draft-review`

This is the first production module. It checks an edited tutorial against its approved script and the channel's editing standards. It:

- extracts media facts, audio, transcript and screen text locally;
- runs deterministic checks;
- prepares compact, timestamped evidence for an optional agent;
- writes local JSON, Markdown and HTML reports;
- resumes completed work instead of repeating it;
- handles several videos as a batch;
- lets the editor confirm the requested changes are complete.

Run it directly with `video-draft-review`, or keep using the compatible `video-pipeline review` and `video-pipeline batch` commands.

### `conformer`

This module will select host takes against the exact script, retrieve the corresponding screen footage, and generate a prepared Final Cut timeline. A-roll alignment and screen matching are components of this one module.

The current repository contains the module boundary and sanitized benchmark results. It does not yet claim to contain the production conformer.

Inspect available modules:

```bash
video-pipeline modules
video-conformer status
```

See [docs/modules.md](docs/modules.md) for the boundaries and current status.

## Install on macOS

Requirements:

- Python 3.11 or newer
- FFmpeg and ffprobe
- whisper.cpp's `whisper-cli`
- a whisper.cpp model file
- Xcode command-line tools for Apple Vision OCR

Install:

```bash
brew install ffmpeg whisper-cpp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install -e .
video-pipeline doctor
```

Editors can also double-click `scripts/install-macos.command`. The installer creates a private configuration at `~/.config/video-pipeline/config.toml`.

Point the local media layer at an existing Whisper model:

```bash
export VIDEO_PIPELINE_WHISPER_MODEL="/absolute/path/to/ggml-base.en.bin"
```

## Choose an agent per module

Agent configuration belongs to a module, not the shared pipeline. `draft-review` currently supports:

- `auto`: use the module's private preference, then a configured command, Claude Code, a compatible API, or evidence-only mode;
- `command`: invoke any argument-array wrapper that follows the [agent task contract](docs/agent-contract.md);
- `claude-code`: use the model route in the editor's private Claude Code settings;
- `openai-compatible`: call a privately configured compatible endpoint;
- `none`: finish local analysis, save agent task bundles, and mark semantic review as pending.

Examples:

```bash
video-draft-review review \
  --video "/absolute/path/to/draft.mp4" \
  --script "/absolute/path/to/script.txt" \
  --editor editor-one \
  --title "Tutorial title" \
  --agent auto

video-draft-review review \
  --video "/absolute/path/to/draft.mp4" \
  --script "/absolute/path/to/script.txt" \
  --editor editor-one \
  --agent none
```

The second command still creates transcripts, OCR, deterministic findings and versioned agent request bundles. Its status is `needs_attention`, because no semantic reviewer ran.

### Generic command adapter

Configure an argument list as JSON. No shell is invoked:

```bash
export VIDEO_PIPELINE_DRAFT_REVIEW_AGENT_COMMAND_JSON='["my-agent-wrapper", "{request_file}", "{response_file}"]'
video-draft-review review ... --agent command
```

The wrapper can use Codex, Claude Code, GLM, a local model, or another agent. The module only cares that the wrapper reads the request and writes schema-valid JSON.

### Compatible API adapter

```bash
export VIDEO_PIPELINE_DRAFT_REVIEW_API_KEY="your-key"
export VIDEO_PIPELINE_DRAFT_REVIEW_API_BASE_URL="https://provider.example/v1"
export VIDEO_PIPELINE_DRAFT_REVIEW_API_MODEL="configured-model"
video-draft-review review ... --agent openai-compatible
```

Legacy `VIDEO_PIPELINE_GLM_*` and `VIDEO_PIPELINE_CLAUDE_*` review settings remain accepted during the 0.2 transition. New installations should use the module-scoped names in `config.example.toml`.

## Run a batch

Copy `examples/batch.example.json` outside the repository, replace the example paths, and run:

```bash
video-draft-review batch /absolute/path/to/editor-one-batch.json --agent auto
```

The runner records progress after every video. Running the same command again resumes the batch and reuses unchanged local analysis and agent responses.

After the editor makes the requested changes:

```bash
video-pipeline ready --batch-id editor-one-2026-09-09-01
```

Version 0.2 still trusts the editor's confirmation and does not automatically recheck the revised video.

## Record improvements privately

Corrections can apply to one video, one module, or the shared pipeline:

```bash
video-pipeline feedback \
  --job-id JOB_ID \
  --kind incorrect \
  --issue-id ISSUE-003 \
  --scope draft-review \
  --note "The control was visible but covered by the presenter; classify it as obscured, not missing."
```

Production feedback stays in the private local work directory. Shared behavior changes require a sanitized fixture and pull request.

## Notification relay

The optional relay is separate from every media module. It receives batch ID, editor, counts, state, event time and delivery result. It never receives videos, scripts, transcripts, screenshots or reports.

See [docs/relay.md](docs/relay.md).

## Privacy

A cloud agent sees only the prompt and evidence included in its task. Use `--text-only` to exclude screenshots, a local command to keep evidence on the Mac, or `--agent none` to create the evidence bundle without contacting an agent.

Do not use GitHub Issues to track real production videos. Never commit media, transcripts, screenshots, reports, private paths or credentials.

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
video-conformer validate-benchmark benchmarks/conformer/ssl-domain-2026-09-10/summary.json
```

Contributions should arrive through a branch or fork and a pull request. Each module owns its prompts, tests and sanitized fixtures. Importing one production module must not import another.

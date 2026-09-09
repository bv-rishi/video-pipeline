# Video Pipeline

Video Pipeline is a local-first quality-control system for tutorial videos. Editors run it on their Macs, review timestamped findings, make the changes, and mark the batch ready for the final reviewer.

Raw videos stay on the editor's Mac. A small optional relay receives counts and status only so it can notify a private Google Chat space.

## Current module

The first working module is `draft-review`. It:

- reads an approved script and local video;
- extracts media facts, audio, transcript, and screen text locally;
- sends compact evidence to a configured GLM endpoint or command;
- writes local JSON, Markdown, and HTML reports;
- resumes completed analysis instead of repeating it;
- runs several videos as one batch;
- lets the editor confirm that requested changes are complete;
- sends metadata-only batch notifications through an optional private relay.

The A-roll conformer and screen-matching modules are represented in the shared architecture and will be promoted from the existing benchmarks after this workflow is stable.

## Quick start on macOS

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

Editors can also double-click `scripts/install-macos.command`, then use `scripts/run-batch.command` and drag a private batch JSON file into the Terminal window. The installer creates a private configuration at `~/.config/video-pipeline/config.toml`.

Point the reviewer at an existing Whisper model:

```bash
export VIDEO_PIPELINE_WHISPER_MODEL="/absolute/path/to/ggml-base.en.bin"
```

Configure GLM using its OpenAI-compatible API:

```bash
export VIDEO_PIPELINE_GLM_API_KEY="your-key"
export VIDEO_PIPELINE_GLM_BASE_URL="https://api.z.ai/api/paas/v4"
export VIDEO_PIPELINE_GLM_MODEL="glm-4.6v"
```

The base URL and model are configurable because normal GLM and GLM Coding plans can use different endpoints and image support. Never add the key to this repository. The default ceiling is six GLM calls per video; change it with `VIDEO_PIPELINE_MAX_GLM_CALLS` only after checking the expected cost and video length.

Run one review:

```bash
video-pipeline review \
  --video "/absolute/path/to/draft.mp4" \
  --script "/absolute/path/to/script.txt" \
  --editor editor-one \
  --title "Tutorial title"
```

Reports are written under `~/Library/Application Support/Video Pipeline/jobs/` by default. Open `report.html` in a browser.

## Run a batch

Copy `examples/batch.example.json` outside the repository, replace the example paths, and run:

```bash
video-pipeline batch /absolute/path/to/editor-one-batch.json
```

The runner records progress after every video. Running the same command again resumes the batch and reuses cached media analysis and GLM responses.

After the editor has made the requested changes:

```bash
video-pipeline ready --batch-id editor-one-2026-09-09-01
```

This is an editor confirmation. Version 0.1 does not automatically recheck the revised video.

Check the local counts at any time:

```bash
video-pipeline status --batch-id editor-one-2026-09-09-01
```

## GLM command adapter

If GLM is available through a local command rather than an API, configure an argument list as JSON. No shell is invoked.

```bash
export VIDEO_PIPELINE_GLM_COMMAND_JSON='["glm", "review", "--prompt", "{prompt_file}", "--output", "{output_file}"]'
video-pipeline review ... --provider command
```

The command must write the documented issue JSON to `{output_file}`, or print it to stdout. It can read the image manifest from `{images_manifest}`.

## Notification relay

The relay is deliberately separate from video processing. See [docs/relay.md](docs/relay.md). It stores only batch ID, editor, counts, state, event time, and delivery result. It never receives videos, scripts, transcripts, screenshots, or reports.

## Privacy

With a cloud GLM endpoint, the raw video remains local but the prepared prompt and selected screenshots are sent to that model provider. Use `--text-only` to send text evidence without screenshots, or use the command adapter with a local model to keep all evidence on the Mac.

Do not use GitHub Issues to track real production videos in this public repository.

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Contributions should arrive through a branch or fork and a pull request. Shared behaviour changes must include tests. Editorial rules should be scoped to one video, one module, or the shared pipeline instead of being silently applied everywhere.

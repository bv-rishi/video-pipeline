#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
cd "$project_dir"

if ! command -v brew >/dev/null 2>&1; then
  print "Homebrew is required. Install it from https://brew.sh and run this installer again."
  exit 1
fi

brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list whisper-cpp >/dev/null 2>&1 || brew install whisper-cpp

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools
.venv/bin/python -m pip install -e .

config_dir="$HOME/.config/video-pipeline"
mkdir -p "$config_dir"
if [[ ! -f "$config_dir/config.toml" ]]; then
  cp config.example.toml "$config_dir/config.toml"
fi

print ""
print "Video Pipeline is installed."
print "Edit $config_dir/config.toml with the local Whisper model path."
print "If Claude Code already uses GLM, the reviewer will reuse that setup automatically."
print "Then run scripts/run-batch.command and drag a private batch JSON file into the window."
read "?Press Return to close."

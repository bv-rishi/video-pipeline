#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
runner="$project_dir/.venv/bin/video-pipeline"
if [[ ! -x "$runner" ]]; then
  print "Video Pipeline is not installed. Run scripts/install-macos.command first."
  read "?Press Return to close."
  exit 1
fi

print "Drag the private batch JSON file here, then press Return:"
read -r "manifest_path?"
manifest_path="${(Q)manifest_path}"

"$runner" batch "$manifest_path"
print ""
read "?The batch has finished. Press Return to close."

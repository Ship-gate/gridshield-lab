#!/bin/zsh
set -eu
GRIDSHIELD_APP="${0:A:h}"
GRIDSHIELD_ENV="$GRIDSHIELD_APP/../../work/gridshield-venv"
GRIDSHIELD_UV="$(command -v uv || true)"
if [[ -z "$GRIDSHIELD_UV" && -x "$HOME/.local/bin/uv" ]]; then
  GRIDSHIELD_UV="$HOME/.local/bin/uv"
fi
if [[ ! -x "$GRIDSHIELD_UV" ]]; then
  print 'Install uv from https://docs.astral.sh/uv/ then run this setup again.'
  exit 1
fi
cd "$GRIDSHIELD_APP"
"$GRIDSHIELD_UV" venv "$GRIDSHIELD_ENV" --python 3.11 --allow-existing
"$GRIDSHIELD_UV" pip sync requirements.lock --python "$GRIDSHIELD_ENV/bin/python"
"$GRIDSHIELD_ENV/bin/python" launch.py

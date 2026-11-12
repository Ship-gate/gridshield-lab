#!/bin/zsh
set -eu
GRIDSHIELD_APP="${0:A:h}"
GRIDSHIELD_PYTHON="$GRIDSHIELD_APP/../../work/gridshield-venv/bin/python"
if [[ ! -x "$GRIDSHIELD_PYTHON" ]]; then
  print 'GridShield needs its local Python environment. Run Setup GridShield.command first.'
  read -r '?Press Return to close.'
  exit 1
fi
cd "$GRIDSHIELD_APP"
"$GRIDSHIELD_PYTHON" launch.py

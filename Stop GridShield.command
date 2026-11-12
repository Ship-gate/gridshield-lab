#!/bin/zsh
set -eu
GRIDSHIELD_APP="${0:A:h}"
"$GRIDSHIELD_APP/../../work/gridshield-venv/bin/python" "$GRIDSHIELD_APP/stop.py"

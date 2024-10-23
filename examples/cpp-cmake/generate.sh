#!/bin/bash

##set -eu
set -e

## works both under bash and sh
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")


GEN_SCRIPT_PATH="$SCRIPT_DIR/generate-graph.sh"


if [[ $* == *--venv* ]]; then
	## run under venv
	VENV_DIR="$SCRIPT_DIR/../../venv"
	"$VENV_DIR"/activatevenv.sh "$GEN_SCRIPT_PATH --venv; exit"
else
	$GEN_SCRIPT_PATH
fi

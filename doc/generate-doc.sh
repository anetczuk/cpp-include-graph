#!/bin/bash

set -eu


## works both under bash and sh
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")


CPPIG_SRC_DIR="$SCRIPT_DIR/../src"

"$CPPIG_SRC_DIR"/cppincludegraphgen --help > "$SCRIPT_DIR"/cmd_args.txt

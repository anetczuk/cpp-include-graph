#!/bin/bash

##set -eu
set -e

## works both under bash and sh
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")


BUILD_LOG_FILE="$SCRIPT_DIR/build/build_log.txt"
UNZIP_DIR="$SCRIPT_DIR/build"


compile_code() {
    CODE_FILE="$SCRIPT_DIR/cpp_makefile_template.zip"
    SRC_DIR="$UNZIP_DIR/cpp_makefile_template"
    
    
    rm -rf "$UNZIP_DIR"
    
    mkdir -p "$UNZIP_DIR"
    cd "$UNZIP_DIR"
    
    unzip -o "$CODE_FILE"
    
    cd "$SRC_DIR"
    
    
    ##
    ## build project and collect info
    ##
    
    make CXX="g++" CXXFLAGS="-H" -j1 2>&1 | tee "$BUILD_LOG_FILE"
}

compile_code


GEN_CMD="cppincludegraphgen"
if [[ $* == *--venv* ]]; then
	## do nothing - use standard executable (installed)
	:
else
	## set path to local executable
	CPPIG_SRC_DIR="$SCRIPT_DIR/../../src"
	GEN_CMD="$CPPIG_SRC_DIR/cppincludegraphgen"
fi


##
## generate include graph
##

OBJ_REGEX="^g\+\+.*-o (\S*)$"

# OUT_DIR="$SCRIPT_DIR/include_graph_full"
# rm -rf "$OUT_DIR"
# mkdir -p "$OUT_DIR"
# $GEN_CMD -lf "$BUILD_LOG_FILE" --build_regex "$OBJ_REGEX" --rel_names "$UNZIP_DIR" --outdir "$OUT_DIR"

OUT_DIR="$SCRIPT_DIR/include_graph_reduced"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
$GEN_CMD -lf "$BUILD_LOG_FILE" --build_regex "$OBJ_REGEX" --rel_names "$UNZIP_DIR" --reduce_dirs "/opt" "/usr" --outdir "$OUT_DIR"

BROKEN_LINKS=0
result=$(checklink -r -q "$OUT_DIR/index.html" 2> /dev/null) || BROKEN_LINKS=1
if [[ "$result" != "" || $BROKEN_LINKS -ne 0 ]]; then
	echo "broken links found:"
	echo "$result"
	exit 1
fi
# else: # empty string - no errors
echo "no broken links found"

#!/bin/bash

##set -eu
set -e

## works both under bash and sh
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")


BUILD_LOG_FILE="$SCRIPT_DIR/build/build_log.txt"


compile_code() {
    CODE_FILE="$SCRIPT_DIR/cpp_makefile_template.zip"
    UNZIP_DIR="$SCRIPT_DIR/build"
    SRC_DIR="$UNZIP_DIR/cpp_makefile_template"
    
    
    rm -rf "$UNZIP_DIR"
    
    mkdir -p "$UNZIP_DIR"
    cd $UNZIP_DIR
    
    unzip -o $CODE_FILE
    
    cd "$SRC_DIR"
    
    
    ##
    ## build project and collect info
    ##
    
    make CXX="g++" CXXFLAGS="-H" -j1 2>&1 | tee "$BUILD_LOG_FILE"
}

compile_code


##
## generate include graph
##

OBJ_REGEX="^g\+\+.*-o (\S*)$"

GRAPH_DIR="$SCRIPT_DIR/include_graph_full"
rm -rf "$GRAPH_DIR"
mkdir -p "$GRAPH_DIR"
cppincludegraphgen -lf "$BUILD_LOG_FILE" --build_regex "$OBJ_REGEX" --outdir "$GRAPH_DIR"

GRAPH_DIR="$SCRIPT_DIR/include_graph_reduced"
rm -rf "$GRAPH_DIR"
mkdir -p "$GRAPH_DIR"
cppincludegraphgen -lf "$BUILD_LOG_FILE" --build_regex "$OBJ_REGEX" --reduce_dirs "/opt" "/usr" --outdir "$GRAPH_DIR"

#!/bin/bash

##set -eu
set -e

## works both under bash and sh
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")


BUILD_LOG_FILE="$SCRIPT_DIR/build/build_log.txt"
UNZIP_DIR="$SCRIPT_DIR/build"


compile_code() {
    CODE_FILE="$SCRIPT_DIR/cmake-3.26.1-tutorial-source.zip"
    SRC_DIR="$UNZIP_DIR/cmake-3.26.1-tutorial-source/Complete"
    BUILD_DIR="$UNZIP_DIR/build"
    
    
    rm -rf "$UNZIP_DIR"
    
    mkdir -p "$UNZIP_DIR"
    cd $UNZIP_DIR
    
    unzip -o $CODE_FILE
    
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"
    
    
    ##
    ## build project and collect info
    ##
    
    cmake -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
          -DCMAKE_C_FLAGS="-H" \
          -DCMAKE_CXX_FLAGS="-H" \
          "$SRC_DIR"
    
    cmake --build . -- -j 1 2>&1 | tee "$BUILD_LOG_FILE"
}

compile_code


##
## generate include graph
##

# intentionally change directory from build dir to check relative paths
cd "$SCRIPT_DIR"

echo "generating full graph"
GRAPH_DIR="$SCRIPT_DIR/include_graph_full"
rm -rf "$GRAPH_DIR"
mkdir -p "$GRAPH_DIR"
cppincludegraphgen -lf "$BUILD_LOG_FILE" --build_dir "$UNZIP_DIR/build" --rel_names "$UNZIP_DIR" --outdir "$GRAPH_DIR"

echo "generating reduced graph"
GRAPH_DIR="$SCRIPT_DIR/include_graph_reduced"
rm -rf "$GRAPH_DIR"
mkdir -p "$GRAPH_DIR"
cppincludegraphgen -lf "$BUILD_LOG_FILE" --build_dir "$UNZIP_DIR/build" --rel_names "$UNZIP_DIR" --reduce_dirs "/opt" "/usr" --outdir "$GRAPH_DIR"

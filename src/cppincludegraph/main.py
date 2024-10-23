# Copyright (c) 2022, Arkadiusz Netczuk <dev.arnet@gmail.com>
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause license found in the
# LICENSE file in the root directory of this source tree.
#

import os
import logging
from typing import List
import argparse

from cppincludegraph import logger
from cppincludegraph.includegraph import GraphNode, IncludeGraph
from cppincludegraph.logparser import find_build_logs, read_files_info, read_build_logs
from cppincludegraph.generator import generate_pages


_LOGGER = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


## ===================================================================


def main():
    parser = argparse.ArgumentParser(description="generate headers include graph based on compiler output")
    parser.add_argument("-la", "--logall", action="store_true", help="Log all messages")

    ## =================================================

    parser.add_argument(
        "-lf",
        "--log_files",
        nargs="+",
        action="store",
        required=False,
        default="",
        help="List of build log files." " Providing multiple log files is suitable in case of catkin build tool.",
    )
    parser.add_argument(
        "--build_dir",
        action="store",
        required=False,
        default=".",
        help="Build root directory (if other than current work dir)",
    )
    parser.add_argument(
        "--log_dir", action="store", required=False, default="", help="Root for search for build log files"
    )
    parser.add_argument(
        "--log_name", action="store", required=False, default="", help="Name of build log file to search for"
    )
    parser.add_argument(
        "--build_regex",
        action="store",
        required=False,
        default="",
        help=r"Build object regex. If not given then '.*Building \S* object (.*)$' is used.",
    )
    parser.add_argument(
        "-rd",
        "--reduce_dirs",
        nargs="+",
        action="store",
        required=False,
        default="",
        help="List of headers directories to reduce",
    )
    parser.add_argument("--rel_names", action="store", required=False, default="", help="Reduce prefix of all names")
    parser.add_argument(
        "--files_info",
        action="store",
        required=False,
        default="",
        help="Files information (file can be generated using 'cppincludegraphdump' script)",
    )
    parser.add_argument("--outdir", action="store", required=False, default="", help="Output directory")

    args = parser.parse_args()

    if args.logall is True:
        logger.configure(logLevel=logging.DEBUG)
    else:
        logger.configure(logLevel=logging.INFO)

    log_dir = args.log_dir
    log_name = args.log_name

    if len(log_dir) == 0:
        log_dir = None
    if len(log_name) == 0:
        log_name = None

    found_logs = find_build_logs(log_dir, log_name)
    if len(args.log_files) > 0:
        found_logs.extend(args.log_files)

    build_dir = args.build_dir
    if not os.path.isdir(build_dir):
        _LOGGER.error("given build directory does not exist: %s", build_dir)
        return 1
    build_dir = os.path.realpath(build_dir)

    _LOGGER.info("reading build logs: %s", found_logs)
    files_info_dict = read_files_info(args.files_info)
    graph_list: List[GraphNode] = read_build_logs(
        found_logs, build_dir, files_info_dict, args.reduce_dirs, args.build_regex
    )

    _LOGGER.info("building include graph")
    IncludeGraph.subdir_mode = False
    build_tree: IncludeGraph = IncludeGraph(graph_list, args.rel_names)
    build_tree.setRootDir(args.outdir)

    #     ## pprint.pprint( build_tree )
    #     print_graph( build_tree.root.children )

    #     out_stats = os.path.join( args.outdir, "most_common.txt" )
    #     print_stats( build_tree, out_stats )

    ##
    ## generate HTML data
    ##
    if len(args.outdir) > 0:
        _LOGGER.info("generating HTML graph")
        generate_pages(build_tree, args.outdir, files_info_dict)

    _LOGGER.info("--- completed ---")
    return 0

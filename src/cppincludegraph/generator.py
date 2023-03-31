# Copyright (c) 2022, Arkadiusz Netczuk <dev.arnet@gmail.com>
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause license found in the
# LICENSE file in the root directory of this source tree.
#

import os
import logging
import argparse
from typing import List, Set, Dict, Any, Tuple
import collections

from showgraph.io import read_file
from showgraph.graphviz import Graph, set_node_style

from cppincludegraph import texttemplate
from cppincludegraph.includegraph import GraphNode, IncludeGraph, get_names
from cppincludegraph.logparser import find_build_logs, read_files_info, read_build_logs


_LOGGER = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname( os.path.abspath(__file__) )


## ===================================================================


def generate_pages( build_tree: IncludeGraph, out_dir, files_info_dict=None, config_params_dict=None ):
    if files_info_dict is None:
        files_info_dict = {}
    if config_params_dict is None:
        config_params_dict = {}

    params_dict: Dict[ str, Any ] = {}
    generate_graph_pages( build_tree, params_dict, out_dir )


##
def generate_graph_pages( build_tree: IncludeGraph, item_config_dict, output_dir ):
    main_page_link = os.path.join( output_dir, "item.html" )

    all_nodes: List[ GraphNode ] = build_tree.getFlatList()

#     graph_generator = GraphFactory( build_tree, output_dir )

    package_nodes = build_tree.getPackageNodes()

    object_files_names = set()
    for package_node in package_nodes:
        object_files_names.update( [ child.data.name for child in package_node.children ] )

    child_counter = 0
    child_size    = len( all_nodes )

    handled_nodes: Set[str] = set()
    ## child_node: GraphNode
    for child_node in all_nodes:
        child_counter += 1

        child_name = child_node.data.name
        if child_name in handled_nodes:
            continue

        _LOGGER.info( "%s/%s: generating data for child %s", child_counter, child_size, child_name )
        handled_nodes.add( child_name )

        _LOGGER.info( "generating dot graph" )
        child_dir = os.path.join( output_dir, child_node.data.subdir )
        child_graph: Graph = generate_dot_graph2( build_tree, [ child_node ], child_dir )
        os.makedirs( child_dir, exist_ok=True )

        _LOGGER.info( "storing dot graph" )
        store_dot_graph( child_graph, child_dir )

        if child_node in package_nodes:
            ## package
            include_counter = count_packages_includes( [child_node] )
            included_list = get_includes_list( build_tree, object_files_names, include_counter )
        else:
            ## header
            included_list = get_includes_list( build_tree, object_files_names, child_node.data.include_counter )

        page_params = item_config_dict.copy()
        page_params.update( { "root_dir":       output_dir,
                              "main_page_link": main_page_link,
                              "item_data":      child_node.data,
                              "children_list":  child_node.children,
                              "included_list":  included_list
                              } )
        generate_html_page( child_dir, page_params )

    ## generate main page
    _LOGGER.info( "generating main page" )
    graph: Graph = generate_dot_graph2( build_tree, package_nodes, output_dir )
    store_dot_graph( graph, output_dir )

    out_png = os.path.join( output_dir, "include_tree.gv.png" )
    graph.writePNG( out_png )

    include_counter = count_packages_includes( package_nodes )
    included_list   = get_includes_list( build_tree, object_files_names, include_counter )

    page_params = item_config_dict.copy()
    page_params.update( { "root_dir": output_dir,
                          "children_list":  package_nodes,
                          "included_list":  included_list
                          } )
    generate_html_page( output_dir, page_params )


def get_includes_list( build_tree, object_files_names, include_counter ):
    included_list = []
    for node_name, count in include_counter.items():
        if node_name in object_files_names:
            ## skip object file
            continue
        node = build_tree.getNode( node_name )
        rounded_total = round( count * node.data.fsize / 1024, 2)
        included_list.append( (node.data, count, rounded_total) )
    return included_list


def count_packages_includes( package_nodes_list: List[GraphNode] ):
    include_counter: collections.Counter = collections.Counter()
    for package_node in package_nodes_list:
        for obj_node in package_node.children:
            names = get_names( obj_node.data.all_children )
            include_counter.update( names )
    return include_counter


##
def generate_html_page( page_dir, page_params ):
    svg_path    = os.path.join( page_dir, "include_tree.gv.svg" )
    svg_content = read_file( svg_path )
    os.remove( svg_path )                   ## remove file -- content embedded into HTML

    ## prepare input for template
    page_params.update( { "page_dir":          page_dir,
                          "body_color":        "#bbbbbb",
                          "svg_name":          "include_tree.gv.svg",
                          "svg_embed_content": svg_content
                          } )

    template_path = os.path.join( SCRIPT_DIR, "template", "include_tree_page.html.tmpl" )
    html_out_path = os.path.join( page_dir, "item.html" )

    _LOGGER.info( "writing page: file://%s", html_out_path )
    texttemplate.generate( template_path, html_out_path, INPUT_DICT=page_params )


def generate_dot_graph2( build_tree: IncludeGraph, nodes_list: List[ GraphNode ], base_dir ) -> Graph:
    active_nodes = build_tree.getConnectedNodes( nodes_list )
    graph: Graph = generate_base_graph( active_nodes, base_dir )

    include_nodes = build_tree.findMaxIncludeNodes( nodes_list )

    ## tree_node: GraphNode
    for tree_node in include_nodes:
        item_label = tree_node.data.label
        graph_node = graph.getNode( item_label )
        if not graph_node:
            continue

        if tree_node not in include_nodes:
            continue
        style = { "style": "filled",
                  "fillcolor": "hotpink1"
                  }
        set_node_style( graph_node, style )

    top_nodes = graph.getNodesTop()
    graph.setNodesRank( top_nodes, "min" )
    for graph_node in top_nodes:
        style = { "style": "filled",
                  "fillcolor": "yellow"
                  }
        set_node_style( graph_node, style )

    ## tree_node: GraphNode
    for tree_node in nodes_list:
        item_label = tree_node.data.label
        graph_node = graph.getNode( item_label )
        if not graph_node:
            continue
        style = { "style": "filled",
                  "fillcolor": "red"
                  }
        set_node_style( graph_node, style )

    return graph


##TODO: remove root_dir
def generate_base_graph( all_nodes, base_dir ) -> Graph:
    graph: Graph = Graph()
    base_graph = graph.base_graph
    base_graph.set_name( "include_graph" )
    base_graph.set_type( 'digraph' )
    base_graph.set_rankdir( 'LR' )

    ## add nodes

#     added_nodes = set()
    for item_node in all_nodes:
        item_name  = item_node.data.name
        item_label = item_node.data.label
#         if item_name in added_nodes:
#             continue
#         added_nodes.add( item_name )

        base_name  = os.path.basename( item_name )
        new_node   = graph.addNode( item_label, shape="box", label=base_name )
        if new_node:
            new_node.set( "tooltip", item_label )
            rel_link = os.path.relpath( item_node.data.href, base_dir )
            new_node.set( "href", rel_link )

    added_edges: Set[ Tuple[str, str] ] = set()
    for child in all_nodes:
        parents = child.parents
        if parents is None:
            continue
        for parent in parents:
            if parent not in all_nodes:
                continue
            new_dege = ( parent.data.label, child.data.label )
            if new_dege in added_edges:
                ## skip edge
                continue
            added_edges.add( new_dege )
            graph.addEdge( *new_dege )

    return graph


def store_dot_graph( graph: Graph, page_dir ):
#     out_raw = os.path.join( page_dir, "include_tree.gv.txt" )
#     graph.writeRAW( out_raw )
#
#     out_png = os.path.join( page_dir, "include_tree.gv.png" )
#     graph.writePNG( out_png )

    out_svg = os.path.join( page_dir, "include_tree.gv.svg" )
    graph.write( out_svg, file_format='svg')


## ============================================================================
## ============================================================================
## ============================================================================


def main():
    parser = argparse.ArgumentParser(description='generate headers include graph based on compiler output')
    parser.add_argument( '-la', '--logall', action='store_true', help='Log all messages' )

    ## =================================================

    parser.add_argument( '-lf', '--log_files', nargs='+', action='store', required=False, default="",
                         help="List of build log files" )
    parser.add_argument( '--log_dir', action='store', required=False, default="",
                         help="Root for search for build log files" )
    parser.add_argument( '--log_name', action='store', required=False, default="",
                         help="Name of build log file to search for" )
    parser.add_argument( '--build_regex', action='store', required=False, default="",
                         help=r"Build object regex. If not given then '.*Building \S* object (.*)$' is used." )
    parser.add_argument( '-rd', '--reduce_dirs', nargs='+', action='store', required=False, default="",
                         help="List of headers directories to reduce" )
    parser.add_argument( '--rel_names', action='store', required=False, default="",
                         help="Reduce prefix of all names" )
    parser.add_argument( '--files_info', action='store', required=False, default="",
                         help="Files information (file can be generated using 'cppincludegraphdump' script)" )
    parser.add_argument( '--outdir', action='store', required=False, default="", help="Output directory" )

    args = parser.parse_args()

    logging.basicConfig()
    if args.logall is True:
        logging.getLogger().setLevel( logging.DEBUG )
    else:
        logging.getLogger().setLevel( logging.INFO )

    log_dir  = args.log_dir
    log_name = args.log_name

    if len(log_dir) == 0:
        log_dir = None
    if len(log_name) == 0:
        log_name = None

    found_logs = find_build_logs( log_dir, log_name )
    if len(args.log_files) > 0:
        found_logs.extend( args.log_files )

    _LOGGER.info( "reading build logs: %s", found_logs )
    files_info_dict = read_files_info( args.files_info )
    graph_list: List[ GraphNode ] = read_build_logs( found_logs, files_info_dict, args.reduce_dirs, args.build_regex )

    _LOGGER.info( "building include graph" )
    build_tree: IncludeGraph = IncludeGraph( graph_list, args.rel_names )
    build_tree.setRootDir( args.outdir )

#     ## pprint.pprint( build_tree )
#     print_graph( build_tree.root.children )

#     out_stats = os.path.join( args.outdir, "most_common.txt" )
#     print_stats( build_tree, out_stats )

    ##
    ## generate HTML data
    ##
    if len( args.outdir ) > 0:
        _LOGGER.info( "generating HTML graph" )
        generate_pages( build_tree, args.outdir, files_info_dict )

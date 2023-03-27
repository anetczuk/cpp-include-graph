# Copyright (c) 2022, Arkadiusz Netczuk <dev.arnet@gmail.com>
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause license found in the
# LICENSE file in the root directory of this source tree.
#

import os
import logging
import argparse
import re
from typing import List, Set, Dict, Any, Iterable, Tuple
from enum import Enum, unique
import collections

from showgraph.io import read_file, prepare_filesystem_name, read_list
from showgraph.graphviz import Graph, set_node_style

from cppincludegraph import texttemplate


_LOGGER = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname( os.path.abspath(__file__) )


## ===================================================================


# @dataclass
class NodeData():

    @unique
    class NodeType(Enum):
        PACKAGE  = "PACKAGE"
        OBJ_FILE = "OBJ_FILE"
        HEADER   = "HEADER"

    def __init__(self):
        self.name: str       = None
        self.type: NodeData.NodeType = None
        self.fsize: int      = 0            ## file size
        self.dc_size: int    = 0            ## size of direct children
        self.ai_size: int    = 0            ## size with all includes
        self.subdir: str     = None
        self.href: str       = None
        self.include_counter = None
        self.all_children: Set[ 'GraphNode' ] = None
        self.all_obj_files: Set[ 'GraphNode' ] = None

    def getTypeName(self):
        if self.type is None:
            return ""
        return self.type.name

    def calculateIncludeSize(self):
        include_size = self.fsize
        for child in self.all_children:
            include_size += child.data.fsize
        return include_size


##
class GraphNode():

    def __init__(self):
        self.data: NodeData                = NodeData()
        self.parents: Set[ 'GraphNode' ]   = set()
        self.children: List[ 'GraphNode' ] = []

    def addChild(self, child: 'GraphNode' ):
        self.children.append( child )
        child.parents.add( self )

    def addChildren(self, children ):
        for child in children:
            self.addChild( child )

    def removeChild(self, child):
        try:
            self.children.remove( child )
        except Exception:
            pass

    def removeParent(self, parent):
        self.parents.remove( parent )

    def removeFromTree(self):
        for parent in self.parents:
            parent.removeChild( self )
        for child in self.children:
            child.removeParent( self )

    def getFlatList(self, include_self=True) -> List[ 'GraphNode' ]:
        if include_self:
            return get_flat_list_breadth( [self] )
        return get_flat_list_breadth( self.children )

    def chopChildren(self, node_prefix):
        name = self.data.name
        if name.startswith( node_prefix ):
            self.children = []
            return
        for child in self.children:
            child.chopNodes( node_prefix )

    def chopNodes(self, node_prefix):
        all_children = self.getFlatList( False )
        for child in all_children:
            name = child.data.name
            if name.startswith( node_prefix ) is False:
                continue
            for child_parent in child.parents:
                child_parent.removeChild( child )

    def printTree(self, indent=0):
        name = self.data.name
        print( " " * indent + name )
        for child in self.children:
            child.printTree( indent + 2 )


# ##
# class IncludeItem():
#
#     def __init__( self, node: GraphNode=None ):
#         self.parents: Set[ str ]  = set()
#         self.children: Set[ str ] = set()
#         self.data: NodeData       = NodeData()
#         if node:
#             self.parents  = get_names( node.parents )
#             self.children = get_names( node.children )
#             self.data     = copy.copy( node.data )
#             self.data.all_children.clear()
#
#
# ##
# class IncludeGraphState():
#
#     def __init__(self, root_list: List[ GraphNode ]=[]):
# #         self.all_items: List[ IncludeItem ]  = []
#         self.root_items: List[ IncludeItem ] = []
#         self.items_dict = {}
#
#         all_nodes = get_flat_list_breadth( root_list )
#         for node in all_nodes:
#             node_item = IncludeItem(node)
# #             self.all_items.append( node_item )
#             if len(node_item.parents) < 1:
#                 self.root_items.append( node_item )
#             self.items_dict[ node_item.data.name ] = node_item
#
#     def generateGraph(self) -> 'IncludeGraph':
#         nodes_tree = self.generateTree()
#         return IncludeGraph( nodes_tree )
#
#     def generateTree(self):
#         item_names = [ item.data.name for item in self.root_items ]
#         nodes_dict = {}
#         return self.generateNodesTreeFromList( item_names, nodes_dict )
#
#     def generateNodesTreeFromList(self, items_list: List[str], nodes_dict) -> List[ GraphNode ]:
#         ret_list = []
#         for item_name in items_list:
#             item: IncludeItem = self.items_dict.get( item_name, None )
#             node = self.generateNodeTreeFromItem( item, nodes_dict )
#             ret_list.append( node )
#         return ret_list
#
#     def generateNodeTreeFromItem(self, item: IncludeItem, nodes_dict) -> GraphNode:
#         item_name = item.data.name
#         node = nodes_dict.get( item_name, None )
#         if node:
#             return node
#         node          = GraphNode()
#         node.data     = copy.copy( item.data )
#         nodes_dict[ item_name ] = node
#         node.parents  = self.generateNodesTreeFromList( item.parents, nodes_dict )
#         node.children = self.generateNodesTreeFromList( item.children, nodes_dict )
#         return node


##
class IncludeGraph():

    def __init__(self, packages_list: List[ GraphNode ] = None):
        if packages_list is None:
            packages_list = []
        self.root: GraphNode = GraphNode()
        self.root.data.name = "root"
        self.root.addChildren( packages_list )

        self.nodes_dict = {}

#         self._updateNames()
        self._calculateDirs()
        self._calculateChildren()
        self._calculateObjFiles()
        self._countIncludes()

        for child in self.root.data.all_children:
            self.nodes_dict[ child.data.name ] = child

#     def _updateNames(self):
#         ## package: GraphNode
#         for package in self.root.children:
#             package_name = package.data.name
#             ## child: GraphNode
#             for child in package.children:
#                 child.data.name = package_name + "/" + child.data.name

    def _calculateDirs(self):
        for package in self.root.children:
            pkg_subdir          = prepare_filesystem_name( package.data.name )
            package.data.subdir = pkg_subdir
            package.data.href   = os.path.join( pkg_subdir, "item.html" )

            all_children = package.getFlatList( False )
            for child in all_children:
                child_subdir = prepare_filesystem_name( child.data.name )
                if not child.data.name.startswith("/"):
                    child_subdir = os.path.join( pkg_subdir, child_subdir )
                child.data.subdir = child_subdir
                child.data.href   = os.path.join( child_subdir, "item.html" )

    def _calculateChildren( self ):
        calculate_all_children( self.root )

        for node in self.root.data.all_children:
            children_size = 0
            for child in node.children:
                children_size += child.data.fsize
            node.data.dc_size = children_size

        for node in self.root.data.all_children:
            node.data.ai_size = node.data.calculateIncludeSize()

    def _calculateObjFiles( self ):
        all_nodes: List[ GraphNode ] = get_flat_list_breadth( self.root.children )
        for node in all_nodes:
            node.data.all_obj_files = get_parent_obj_files( node )

    def _countIncludes(self):
        for node in self.root.data.all_children:
            counted_items = count_includes( node.data.all_children )
            node.data.include_counter = counted_items
        self.root.data.include_counter = count_includes( self.root.children )

#     def getState(self) -> IncludeGraphState:
#         return IncludeGraphState( self.root.children )

    def setRootDir(self, root_dir):
        nodes = self.getFlatList()
        for node in nodes:
            node.data.href = os.path.join( root_dir, node.data.href )

    def getNode(self, name):
        node = self.nodes_dict.get(name, None)
        if node is None:
            _LOGGER.warning( "missing node: %s", name )
        return node

    def getNodes(self, names_list: List[ str ]):
        ret_list = []
        for node in self.root.data.all_children:
            if node.data.name in names_list:
                ret_list.append( node )
        return ret_list

    def getPackageNodes(self):
        return self.root.children

    def getFlatList(self) -> List[ GraphNode ]:
        return get_flat_list_breadth( self.root.children )

    def getConnectedNodesByName( self, names_list: List[ str ] ) -> Set[ GraphNode ]:
        nodes_list = self.getNodes( names_list )
        return self.getConnectedNodes( nodes_list )

    def getConnectedNodes(self, nodes_list: List[ GraphNode ]) -> Set[ GraphNode ]:
        ret_list: Set[ GraphNode ] = set()
        for node in nodes_list:
            ret_list.add( node )
            children = calculate_children( node )
            parents  = calculate_parents( node )
            ret_list.update( children )
            ret_list.update( parents )
        ret_list.remove( self.root )
        return ret_list

    def findMaxIncludeNodes(self, start_nodes_list: List[ GraphNode ]) -> Set[ GraphNode ]:
        ret_list = set()
        ret_list.update( self.findMaxIncludeChildrenPath(start_nodes_list) )
        ret_list.update( self.findMaxIncludeParentsPath(start_nodes_list) )
        return ret_list

    def findMaxIncludeChildrenPath(self, start_nodes_list: List[ GraphNode ]) -> Set[ GraphNode ]:
        ret_list: List[GraphNode] = []
        ret_list.extend( start_nodes_list )
        i = 0
        while i < len(ret_list):
            node: GraphNode = ret_list[i]
            i += 1
            next_node: GraphNode = max_include_node_from_list( node.children )
            if next_node in ret_list:
                continue
            if next_node:
                ret_list.append( next_node )
        return set( ret_list )

    def findMaxIncludeParentsPath(self, start_nodes_list: List[ GraphNode ]) -> Set[ GraphNode ]:
        ret_list = []
        ret_list.extend( start_nodes_list )
        i = 0
        while i < len(ret_list):
            node = ret_list[i]
            i += 1
            next_node = max_include_node_from_list( node.parents )
            if next_node in ret_list:
                continue
            if next_node:
                ret_list.append( next_node )
        return set( ret_list )

#     def calculateSubGraph(self, nodes_list: List[ GraphNode ]) -> 'IncludeGraph':
# #         names_list = get_names( nodes_list )
# #         nodes_list = self.getNodes( names_list )
#         connected = self.getConnectedNodes( nodes_list )
#
#         for child in self.root.data.all_children:
#             if child in connected:
#                 continue
#             child.removeFromTree()
#         for item in self.root.children.copy():
#             if item in connected:
#                 continue
#             self.root.children.remove( item )
#
# #         names_list = get_names( nodes_list )
# #         build_tree.preserveNodesByName( names_list )
# #         build_tree = IncludeGraph( build_tree.nodes )
#
#         return None


def get_parent_obj_files( node: GraphNode ):
    if node.data.all_obj_files:
        return node.data.all_obj_files
    ret_set: Set[GraphNode] = set()
    watch_list: List[GraphNode] = []
    watch_list.extend( node.parents )
    i = 0
    while i < len(watch_list):
        parent: GraphNode = watch_list[i]
        i += 1
        if parent.data.all_obj_files:
            ret_set.update( parent.data.all_obj_files )
            continue
        if parent.data.type is NodeData.NodeType.OBJ_FILE:
            ret_set.add( parent )
            continue
        for item in parent.parents:
            if item not in watch_list:
                watch_list.append( item )
    return ret_set


def max_include_node_from_list( nodes_list: Iterable[GraphNode] ) -> GraphNode:
    max_value = -1
    max_node  = None
    for node in nodes_list:
        if node.data.ai_size > max_value:
            max_node  = node
            max_value = node.data.ai_size
    return max_node


def get_names( nodes_list: Iterable[ GraphNode ] ):
    return [ item.data.name for item in nodes_list ]


##
def get_flat_list_breadth( nodes_list: List['GraphNode'], ignore_nodes: List[str] = None,
                           ignore_children: List[str] = None ) -> List[ 'GraphNode' ]:
    ## breadth first order
    ret_list = []
    ret_list.extend( nodes_list )
    i = 0
    while i < len(ret_list):
        node = ret_list[i]
        i += 1

        if ignore_children:
            node_name = node.data.name
            if starts_with( node_name, ignore_children ):
                ## add node without children -- node already added, so continue
                continue

        if ignore_nodes:
            for child in node.children:
                if child in ret_list:
                    continue
                child_name = child.data.name
                if starts_with( child_name, ignore_nodes ):
                    ## skip node
                    continue
                ret_list.append( child )
        else:
            for child in node.children:
                if child in ret_list:
                    continue
                ret_list.append( child )

    return ret_list


def starts_with( name, prefix_list ):
    for prefix in prefix_list:
        if name.startswith( prefix ):
            return True
    return False


##
def get_flat_list_depth(nodes_list: List[ GraphNode ]) -> List[ GraphNode ]:
    ## depth first order
    ret_list = []
    ret_list.extend( nodes_list )
    i = 0
    while i < len(ret_list):
        node = ret_list[i]
        if node.children:
            ret_list = ret_list[ :i ] + node.children + ret_list[ i: ]
        i += 1
    return ret_list


def calculate_children( node: GraphNode ) -> List[ GraphNode ]:
    ret_list = []
    ret_list.extend( node.children )
    i = 0
    while i < len(ret_list):
        item = ret_list[i]
        i   += 1
        for elem in item.children:
            if elem not in ret_list:
                ret_list.append( elem )
    return ret_list


def calculate_parents( node: GraphNode ) -> List[ GraphNode ]:
    ret_list: List[GraphNode] = []
    ret_list.extend( node.parents )
    i = 0
    while i < len(ret_list):
        item = ret_list[i]
        i   += 1
        for elem in item.parents:
            if elem not in ret_list:
                ret_list.append( elem )
    return ret_list


def calculate_all_children( node: GraphNode ):
    ## depth first order
    ret_list: Set[GraphNode] = set()
    ## child: GraphNode
    for child in node.children:
        child_data = child.data
        if child_data.all_children is None:
            child_data.all_children = set()            ## mark as under calculation
            calculate_all_children( child )
        ret_list.update( child_data.all_children )
        ret_list.add( child )
    node.data.all_children = ret_list


def count_includes( children_list: List[ GraphNode ] ):
    ## depth first order
    ret_count: collections.Counter = collections.Counter()
    for child in children_list:
        names = get_names( child.data.all_children )
        ret_count.update( names )
        ret_count.update( [child.data.name] )
    return ret_count


def print_graph( nodes_list: List[ GraphNode ], indent=0 ):
    progres_list = []
    ## item: GraphNode
    for item in nodes_list:
        progres_list.append( (item, indent) )
    progres_list.reverse()
    visited_set: Set[GraphNode] = set()
    while len( progres_list ) > 0:
        data = progres_list.pop(-1)
        node: GraphNode = data[0]

        if node in visited_set:
            print( " " * data[1], node.data.name, "(recurrent)", "parents:",
                   len(node.parents), "children:", len(node.children) )
            continue

        visited_set.add( node )
        print( " " * data[1], node.data.name, "parents:", len(node.parents), "children:", len(node.children) )
        children = []
        for child in node.children:
            children.append( (child, data[1] + 2) )
        children.reverse()
        progres_list.extend( children )
#     print( "Total number of items:", len(visited_set) )


def print_stats( build_tree: IncludeGraph, out_path ):
    include_counter: collections.Counter = collections.Counter()

    ## tree_item: GraphNode
    for tree_item in build_tree.root.children:
#         tree_item.chopNodes( "/usr" )
#         tree_item.chopNodes( "/opt" )

        all_children = tree_item.getFlatList()
        for tree_node in all_children:
            name = tree_node.data.name
            include_counter[ name ] += 1

    print( "Total headers found:", len(include_counter) )
    common = include_counter.most_common(50)

    # pprint.pprint( common )

    with open( out_path, 'w', encoding='utf-8' ) as out_file:
        for item, count in common:
            out_file.write( f"{count} {item}\n" )
        # pprint.pprint( common, out_file )


## ===================================================================


class GraphBuilder():

    def __init__(self, files_info_dict=None):
        self.files_info_dict = files_info_dict
        if self.files_info_dict is None:
            self.files_info_dict = {}
        self.nodes_dict      = {}
        self.build_list      = []

    def getNode(self, node: GraphNode) -> Tuple[GraphNode, bool]:
        file_info = self.getInfo( node.data )
        item_name = file_info[0]
        file_size = file_info[1]
        new_node_data = self._getNodeFromDict( item_name )
        new_node: GraphNode = new_node_data[0]
        new_node.data.type  = node.data.type
        new_node.data.fsize = file_size
        #print( "xxxx:", item_name, file_size )
        return new_node_data

    def getInfo(self, node_data):
        item_name = node_data.name
        if node_data.type is NodeData.NodeType.PACKAGE:
            return (item_name, 0)

        file_info = self.files_info_dict.get( item_name, None )
        if file_info:
            return file_info

        for key in self.files_info_dict.keys():
            if not key.endswith(item_name):
                continue
            file_info = self.files_info_dict.get( key, None )
            if file_info:
                return file_info

        _LOGGER.warning( "unable to get data for file: %s", item_name )
        return (item_name, 0)

    def _getNodeFromDict(self, node_name) -> Tuple[GraphNode, bool]:
        found_node = self.nodes_dict.get( node_name, None )
        if found_node:
            return (found_node, False)
        found_node = GraphNode()
        found_node.data.name = node_name
        self.nodes_dict[ node_name ] = found_node
        return (found_node, True)

    def addTree(self, package_node: GraphNode):
        _LOGGER.info( "getting children list from %s", package_node.data.name )

        ignore_list = None
#         ignore_list = [ "/usr", "/opt" ]
        raw_children = get_flat_list_breadth( [package_node], ignore_children=ignore_list )

        _LOGGER.info( "processing children list %s", len(raw_children) )
        for child in raw_children:
            new_node_data = self.getNode( child )
            new_node: GraphNode = new_node_data[0]

            if len(child.parents) < 1:
                ## no parents, children will be added later
    #             print( "adding package:", new_node.data.name )
                self.build_list.append( new_node )
                continue

            for child_parent in child.parents:
                existing_parent_data = self.getNode( child_parent )
                if existing_parent_data[1] is True:
                    raise Exception( "parent should already exist" )
                existing_parent = existing_parent_data[0]
                if new_node in existing_parent.children:
    #                 print( f"..... {new_node.data.name} already added to {existing_parent.data.name}" )
                    continue
    #             print( f"adding: {existing_parent.data.name} -> {new_node.data.name}" )
                existing_parent.addChild( new_node )


def read_build_dir( log_dir, files_info_dict=None ) -> List[ GraphNode ]:
    if files_info_dict is None:
        files_info_dict = {}
    log_files_list = []
    for root, dirs, fnames in os.walk( log_dir ):
        for fname in fnames:
            if fname != "build.make.log":
                continue
            log_path = os.path.join( root, fname )
            log_files_list.append( log_path )
    return read_build_logs( log_files_list, files_info_dict )


def read_build_logs( log_files_list, files_info_dict=None ) -> List[ GraphNode ]:
    if files_info_dict is None:
        files_info_dict = {}
#     raw_tree: List[ GraphNode ] = []
    graph_builder = GraphBuilder( files_info_dict )

    read_counter = 0
    read_size    = len( log_files_list )
    for log_path in log_files_list:
        read_counter += 1
        _LOGGER.info( "%s/%s: reading log file: %s", read_counter, read_size, log_path )
        module_tree_list = read_build_log_file( log_path )
        if not module_tree_list:
            continue
        package_node = GraphNode()
        log_dir = os.path.dirname( log_path )
        package_node.data.name = os.path.basename( log_dir )
        package_node.data.type = NodeData.NodeType.PACKAGE
        package_node.addChildren( module_tree_list )
#         raw_tree.append( package_node )

        graph_builder.addTree( package_node )

    return graph_builder.build_list


def read_build_log_file( log_path ) -> List[ GraphNode ]:
    content = read_file( log_path )

    module_tree_list = []
    level_node_dict: Dict[ int, GraphNode ] = None

    line_num = 0
    for line in content.splitlines():
        line_num += 1
        line = line.strip()
        line = escape_ansi( line )

        ## print( "line:", line )

        recent_obj_file = get_after( line, "Building CXX object " )
        if recent_obj_file:
            ## new object file -- expecting include tree
            ## print( f"xxx: >{recent_obj_file}<" )

            #recent_obj_file = os.path.realpath( recent_obj_file )
            item_node = GraphNode()
            item_node.data.name = recent_obj_file
            item_node.data.type = NodeData.NodeType.OBJ_FILE
            level_node_dict    = {}
            level_node_dict[0] = item_node
            continue

        if line.startswith("."):
            ## content of include tree
            if level_node_dict is None:
                ## invalid case -- happens in case of interweaved logs
                _LOGGER.error( "invalid (interweaved) file %s:%s", log_path, line_num )
                return None
                # raise Exception( f"invalid (interweaved) file {log_path}:{line_num}" )

            space_pos = line.find(" ")
            if space_pos < 0:
                ## invalid case -- happens in case of interweaved logs
                level_node_dict = None
                _LOGGER.error( "invalid case - no space found: %s in %s", line, log_path )
                _LOGGER.error( "invalid (interweaved) file %s:%s", log_path, line_num )
                return None
                # raise Exception( f"invalid (interweaved) file {log_path}:{line_num}" )

            parent_index = space_pos - 1
            if parent_index not in level_node_dict:
                ## invalid case -- happens in case of interweaved logs
                level_node_dict = None
                _LOGGER.error( "invalid (interweaved) file %s:%s", log_path, line_num )
                return None
                # raise Exception( f"invalid (interweaved) file {log_path}:{line_num}" )

            dots_text = line[ :space_pos ]
            dots_set = set( dots_text )
            if len(dots_set) > 1:
                ## invalid case -- happens in case of interweaved logs
                level_node_dict = None
                _LOGGER.error( "invalid case - invalid chars found: >%s< %s in %s", dots_text, space_pos, log_path )
                _LOGGER.error( "invalid (interweaved) file %s:%s", log_path, line_num )
                return None
                # raise Exception( f"invalid (interweaved) file {log_path}:{line_num}" )

            ## adding header node
            item = line[ space_pos + 1: ]
            item = os.path.realpath( item )
            graph_node = GraphNode()
            graph_node.data.name = item
            graph_node.data.type = NodeData.NodeType.HEADER
            parent_node = level_node_dict[ parent_index ]
            parent_node.addChild( graph_node )
            level_node_dict[ space_pos ] = graph_node
            continue

        ## other case
        if level_node_dict is not None:
            root_node = level_node_dict[0]
            module_tree_list.append( root_node )
        level_node_dict = None

    return module_tree_list


def get_after( content, start ):
    try:
        pos = content.index( start )
        return content[ pos + len(start): ]
    except ValueError:
        pass
    return None


def escape_ansi(line):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', line)


##
def read_files_info( files_info_path ):
    ret_data = {}
    content = read_list( files_info_path )
    for line in content:
        times_list = re.findall( r"\"(.*)\" \"(.*)\" (\d+)", line )
        if len(times_list) != 1:
            continue
        data_tuple = times_list[0]
        if len(data_tuple) != 3:
            continue
        in_file = data_tuple[0]
        real_name = data_tuple[1]
        ret_data[ in_file ]   = [ real_name, int(data_tuple[2]) ]
        ## sometimes compiler prints real path (resolves links)
        ret_data[ real_name ] = [ real_name, int(data_tuple[2]) ]
    return ret_data


## ===================================================================


def generate_pages( build_tree: IncludeGraph, out_dir, files_info_dict=None, config_params_dict=None ):
    if files_info_dict is None:
        files_info_dict = {}
    if config_params_dict is None:
        config_params_dict = {}

    params_dict: Dict[ str, Any ] = {}
    generate_main_page( build_tree, params_dict, out_dir )


##
def generate_main_page( build_tree: IncludeGraph, item_config_dict, output_dir ):
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
        child_graph: Graph = generate_dot_graph2( build_tree, [ child_node ], output_dir )
        child_dir = os.path.join( output_dir, child_node.data.subdir )
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
        page_params.update( { "root_dir": output_dir,
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
def generate_html_page( output_dir, page_params ):
    svg_path    = os.path.join( output_dir, "include_tree.gv.svg" )
    svg_content = read_file( svg_path )
    os.remove( svg_path )                   ## remove file -- content embedded into HTML

    ## prepare input for template
    page_params.update( { "body_color":   "#bbbbbb",
                          "svg_name":     "include_tree.gv.svg",
                          "svg_embed_content":  svg_content
                          } )

    template_path = os.path.join( SCRIPT_DIR, "template", "include_tree_page.html.tmpl" )
    main_out_path = os.path.join( output_dir, "item.html" )

    _LOGGER.info( "writing page: file://%s", main_out_path )
    texttemplate.generate( template_path, main_out_path, INPUT_DICT=page_params )


def generate_dot_graph2( build_tree: IncludeGraph, nodes_list: List[ GraphNode ], root_dir ) -> Graph:
    active_nodes = build_tree.getConnectedNodes( nodes_list )
    graph: Graph = generate_base_graph( active_nodes, root_dir )

    include_nodes = build_tree.findMaxIncludeNodes( nodes_list )

    ## tree_node: GraphNode
    for tree_node in include_nodes:
        item_name = tree_node.data.name
        graph_node = graph.getNode( item_name )
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
        graph_node.set( "tooltip", item_name )
        style = { "style": "filled",
                  "fillcolor": "yellow"
                  }
        set_node_style( graph_node, style )

    ## tree_node: GraphNode
    for tree_node in nodes_list:
        item_name = tree_node.data.name
        graph_node = graph.getNode( item_name )
        if not graph_node:
            continue

        graph_node.set( "tooltip", item_name )
        style = { "style": "filled",
                  "fillcolor": "red"
                  }
        set_node_style( graph_node, style )

        #TODO: is this required?
        graph_node.set( "href", tree_node.data.href )

    return graph


##TODO: remove root_dir
def generate_base_graph( all_nodes, root_dir ) -> Graph:
    graph: Graph = Graph()
    base_graph = graph.base_graph
    base_graph.set_name( "include_graph" )
    base_graph.set_type( 'digraph' )
    base_graph.set_rankdir( 'LR' )

    ## add nodes

#     added_nodes = set()
    for child_node in all_nodes:
        child_name = child_node.data.name
#         if child_name in added_nodes:
#             continue
#         added_nodes.add( child_name )

        item_name  = os.path.basename( child_name )
        new_node   = graph.addNode( child_name, shape="box", label=item_name )
        if new_node:
            new_node.set( "tooltip", child_name )
            new_node.set( "href", child_node.data.href )

    added_edges: Set[ Tuple[str, str] ] = set()
    for child in all_nodes:
        parents = child.parents
        if parents is None:
            continue
        for parent in parents:
            if parent not in all_nodes:
                continue
            new_dege = ( parent.data.name, child.data.name )
            if new_dege in added_edges:
                ## skip edge
                continue
            added_edges.add( new_dege )
            graph.addEdge( *new_dege )

    return graph


def store_dot_graph( graph: Graph, root_dir ):
#     out_raw = os.path.join( root_dir, "include_tree.gv.txt" )
#     graph.writeRAW( out_raw )
#
#     out_png = os.path.join( root_dir, "include_tree.gv.png" )
#     graph.writePNG( out_png )

    out_svg = os.path.join( root_dir, "include_tree.gv.svg" )
    graph.write( out_svg, file_format='svg')


## ===================================================================


def main():
    parser = argparse.ArgumentParser(description='cpp include graph')
    parser.add_argument( '-la', '--logall', action='store_true', help='Log all messages' )

#     subparsers = parser.add_subparsers( help='commands', description="select one of subcommands", dest='subcommand', required=True )

    ## =================================================

#     subparser = subparsers.add_parser('all_current', help='Store data from almost all providers using current data if required')
#     subparser.set_defaults( func=grab_all )
#     subparser.add_argument( '-f', '--force', action='store_true', help="Force refresh data" )
#     subparser.add_argument( '-of', '--out_format', action='store', required=True, default="", help="Output format, one of: csv, xls, pickle. If none given, then will be deduced based on extension of output path." )
#     subparser.add_argument( '-od', '--out_dir', action='store', default="", help="Output directory" )

    ## =================================================

    parser.add_argument( '-lf', '--log_files', nargs='+', action='store', required=False, default="",
                         help="List of build log files" )
#     parser.add_argument( '-d', '--dir', action='store', required=False, default="",
#                          help="Directory to search for 'build.make.log' files" )
    parser.add_argument( '--file_info', action='store', required=False, default="",
                         help="Files information" )
    parser.add_argument( '--outdir', action='store', required=False, default="", help="Output HTML" )

    args = parser.parse_args()

    logging.basicConfig()
    if args.logall is True:
        logging.getLogger().setLevel( logging.DEBUG )
    else:
        logging.getLogger().setLevel( logging.INFO )

    _LOGGER.info( "reading build logs: %s", args.log_files )
    files_info_dict = read_files_info( args.file_info )
    graph_list: List[ GraphNode ] = read_build_logs( args.log_files, files_info_dict )

    _LOGGER.info( "building include graph" )
    build_tree: IncludeGraph = IncludeGraph( graph_list )
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

# Copyright (c) 2022, Arkadiusz Netczuk <dev.arnet@gmail.com>
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause license found in the
# LICENSE file in the root directory of this source tree.
#

import os
import logging
from enum import Enum, unique
import collections

from typing import List, Set, Iterable

from showgraph.io import prepare_filesystem_name


_LOGGER = logging.getLogger(__name__)


# @dataclass
class NodeData:

    @unique
    class NodeType(Enum):
        """Node type."""

        PACKAGE = "PACKAGE"
        OBJ_FILE = "OBJ_FILE"
        HEADER = "HEADER"

    def __init__(self):
        self.name: str = None
        self.label: str = None
        self.type: NodeData.NodeType = None
        self.fsize: int = 0  ## file size
        self.dc_size: int = 0  ## size of direct children
        self.ai_size: int = 0  ## size with all includes
        self.subdir: str = None
        self.href: str = None
        self.include_counter = None
        self.all_children: Set["GraphNode"] = set()
        self.all_children = None  ## workaround for pylint
        self.all_obj_files: Set["GraphNode"] = None

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
class GraphNode:

    def __init__(self):
        self.data: NodeData = NodeData()
        self.parents: Set["GraphNode"] = set()
        self.children: List["GraphNode"] = []

    def addChild(self, child: "GraphNode"):
        self.children.append(child)
        child.parents.add(self)

    def addChildren(self, children):
        for child in children:
            self.addChild(child)

    def removeChild(self, child):
        try:
            self.children.remove(child)
        except ValueError:
            pass

    def removeParent(self, parent):
        self.parents.remove(parent)

    def removeFromTree(self):
        for parent in self.parents:
            parent.removeChild(self)
        for child in self.children:
            child.removeParent(self)

    def getFlatList(self, include_self=True) -> List["GraphNode"]:
        if include_self:
            return get_flat_list_breadth([self])
        return get_flat_list_breadth(self.children)

    def chopChildren(self, node_prefix):
        name = self.data.name
        if name.startswith(node_prefix):
            self.children = []
            return
        for child in self.children:
            child.chopNodes(node_prefix)

    def chopNodes(self, node_prefix):
        all_children = self.getFlatList(False)
        for child in all_children:
            name = child.data.name
            if name.startswith(node_prefix) is False:
                continue
            for child_parent in child.parents:
                child_parent.removeChild(child)

    def printTree(self, indent=0):
        name = self.data.name
        print(" " * indent + name)
        for child in self.children:
            child.printTree(indent + 2)


##
class IncludeGraph:

    def __init__(self, packages_list: List[GraphNode] = None, names_base_dir=None):
        if packages_list is None:
            packages_list = []
        self.root: GraphNode = GraphNode()
        self.root.data.name = "root"
        self.root.addChildren(packages_list)

        self.nodes_dict = {}

        all_nodes = self.getFlatList()
        if names_base_dir:
            names_base_dir_len = len(names_base_dir)
            for node in all_nodes:
                if node.data.name.startswith(names_base_dir):
                    node.data.label = node.data.name[names_base_dir_len:]
                    if node.data.label[0] == "/":
                        node.data.label = node.data.label[1:]
                else:
                    node.data.label = node.data.name
        else:
            for node in all_nodes:
                node.data.label = node.data.name

        #         self._updateNames()
        self._calculateDirs()
        self._calculateChildren()
        self._calculateObjFiles()
        self._countIncludes()

        for child in self.root.data.all_children:
            self.nodes_dict[child.data.name] = child

    #     def _updateNames(self):
    #         ## package: GraphNode
    #         for package in self.root.children:
    #             package_name = package.data.name
    #             ## child: GraphNode
    #             for child in package.children:
    #                 child.data.name = package_name + "/" + child.data.name

    def _calculateDirs(self):
        for package in self.root.children:
            pkg_subdir = prepare_filesystem_name(package.data.label)
            package.data.subdir = pkg_subdir
            package.data.href = os.path.join(pkg_subdir, "item.html")

            all_children = package.getFlatList(False)
            for child in all_children:
                child_subdir = prepare_filesystem_name(child.data.label)
                if not child.data.name.startswith("/"):
                    child_subdir = os.path.join(pkg_subdir, child_subdir)
                child.data.subdir = child_subdir
                child.data.href = os.path.join(child_subdir, "item.html")

    def _calculateChildren(self):
        calculate_all_children(self.root)

        for node in self.root.data.all_children:
            children_size = 0
            for child in node.children:
                children_size += child.data.fsize
            node.data.dc_size = children_size

        for node in self.root.data.all_children:
            node.data.ai_size = node.data.calculateIncludeSize()

    def _calculateObjFiles(self):
        all_nodes: List[GraphNode] = get_flat_list_breadth(self.root.children)
        for node in all_nodes:
            node.data.all_obj_files = get_parent_obj_files(node)

    def _countIncludes(self):
        for node in self.root.data.all_children:
            counted_items = count_includes(node.data.all_children)
            node.data.include_counter = counted_items
        self.root.data.include_counter = count_includes(self.root.children)

    #     def getState(self) -> IncludeGraphState:
    #         return IncludeGraphState( self.root.children )

    def setRootDir(self, root_dir):
        nodes = self.getFlatList()
        for node in nodes:
            node.data.href = os.path.join(root_dir, node.data.href)

    def getNode(self, name):
        node = self.nodes_dict.get(name, None)
        if node is None:
            _LOGGER.warning("missing node: %s", name)
        return node

    def getNodes(self, names_list: List[str]):
        ret_list = []
        for node in self.root.data.all_children:
            if node.data.name in names_list:
                ret_list.append(node)
        return ret_list

    def getPackageNodes(self):
        return self.root.children

    def getFlatList(self) -> List[GraphNode]:
        return get_flat_list_breadth(self.root.children)

    def getConnectedNodesByName(self, names_list: List[str]) -> Set[GraphNode]:
        nodes_list = self.getNodes(names_list)
        return self.getConnectedNodes(nodes_list)

    def getConnectedNodes(self, nodes_list: List[GraphNode]) -> Set[GraphNode]:
        ret_list: Set[GraphNode] = set()
        for node in nodes_list:
            ret_list.add(node)
            children = calculate_children(node)
            parents = calculate_parents(node)
            ret_list.update(children)
            ret_list.update(parents)
        if ret_list:
            ret_list.remove(self.root)
        return ret_list

    def findMaxIncludeNodes(self, start_nodes_list: List[GraphNode]) -> Set[GraphNode]:
        ret_list = set()
        ret_list.update(self.findMaxIncludeChildrenPath(start_nodes_list))
        ret_list.update(self.findMaxIncludeParentsPath(start_nodes_list))
        return ret_list

    def findMaxIncludeChildrenPath(self, start_nodes_list: List[GraphNode]) -> Set[GraphNode]:
        ret_list: List[GraphNode] = []
        ret_list.extend(start_nodes_list)
        i = 0
        while i < len(ret_list):
            node: GraphNode = ret_list[i]
            i += 1
            next_node: GraphNode = max_include_node_from_list(node.children)
            if next_node in ret_list:
                continue
            if next_node:
                ret_list.append(next_node)
        return set(ret_list)

    def findMaxIncludeParentsPath(self, start_nodes_list: List[GraphNode]) -> Set[GraphNode]:
        ret_list = []
        ret_list.extend(start_nodes_list)
        i = 0
        while i < len(ret_list):
            node = ret_list[i]
            i += 1
            next_node = max_include_node_from_list(node.parents)
            if next_node in ret_list:
                continue
            if next_node:
                ret_list.append(next_node)
        return set(ret_list)


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


def get_parent_obj_files(node: GraphNode):
    if node.data.all_obj_files:
        return node.data.all_obj_files
    ret_set: Set[GraphNode] = set()
    watch_list: List[GraphNode] = []
    watch_list.extend(node.parents)
    i = 0
    while i < len(watch_list):
        parent: GraphNode = watch_list[i]
        i += 1
        if parent.data.all_obj_files:
            ret_set.update(parent.data.all_obj_files)
            continue
        if parent.data.type is NodeData.NodeType.OBJ_FILE:
            ret_set.add(parent)
            continue
        for item in parent.parents:
            if item not in watch_list:
                watch_list.append(item)
    return ret_set


def max_include_node_from_list(nodes_list: Iterable[GraphNode]) -> GraphNode:
    max_value = -1
    max_node = None
    for node in nodes_list:
        if node.data.ai_size > max_value:
            max_node = node
            max_value = node.data.ai_size
    return max_node


def get_names(nodes_list: Iterable[GraphNode]):
    return [item.data.name for item in nodes_list]


##
def get_flat_list_breadth(
    nodes_list: List["GraphNode"], ignore_nodes: List[str] = None, ignore_children: List[str] = None
) -> List["GraphNode"]:
    ## breadth first order
    ret_list = []
    ret_list.extend(nodes_list)
    i = 0
    while i < len(ret_list):
        node = ret_list[i]
        i += 1

        if ignore_children:
            node_name = node.data.name
            if starts_with(node_name, ignore_children):
                ## add node without children -- node already added, so continue
                continue

        if ignore_nodes:
            for child in node.children:
                if child in ret_list:
                    continue
                child_name = child.data.name
                if starts_with(child_name, ignore_nodes):
                    ## skip node
                    continue
                ret_list.append(child)
        else:
            for child in node.children:
                if child in ret_list:
                    continue
                ret_list.append(child)

    return ret_list


def starts_with(name, prefix_list):
    for prefix in prefix_list:
        if name.startswith(prefix):
            return True
    return False


##
def get_flat_list_depth(nodes_list: List[GraphNode]) -> List[GraphNode]:
    ## depth first order
    ret_list = []
    ret_list.extend(nodes_list)
    i = 0
    while i < len(ret_list):
        node = ret_list[i]
        if node.children:
            ret_list = ret_list[:i] + node.children + ret_list[i:]
        i += 1
    return ret_list


def calculate_children(node: GraphNode) -> List[GraphNode]:
    ret_list = []
    ret_list.extend(node.children)
    i = 0
    while i < len(ret_list):
        item = ret_list[i]
        i += 1
        for elem in item.children:
            if elem not in ret_list:
                ret_list.append(elem)
    return ret_list


def calculate_parents(node: GraphNode) -> List[GraphNode]:
    ret_list: List[GraphNode] = []
    ret_list.extend(node.parents)
    i = 0
    while i < len(ret_list):
        item = ret_list[i]
        i += 1
        for elem in item.parents:
            if elem not in ret_list:
                ret_list.append(elem)
    return ret_list


def calculate_all_children(node: GraphNode):
    ## depth first order
    ret_list: Set[GraphNode] = set()
    ## child: GraphNode
    for child in node.children:
        child_data = child.data
        if child_data.all_children is None:
            child_data.all_children = set()  ## mark as under calculation
            calculate_all_children(child)
        ret_list.update(child_data.all_children)
        ret_list.add(child)
    node.data.all_children = ret_list


def count_includes(children_list: List[GraphNode]):
    ## depth first order
    ret_count: collections.Counter = collections.Counter()
    for child in children_list:
        names = get_names(child.data.all_children)
        ret_count.update(names)
        ret_count.update([child.data.name])
    return ret_count


def print_graph(nodes_list: List[GraphNode], indent=0):
    progres_list = []
    ## item: GraphNode
    for item in nodes_list:
        progres_list.append((item, indent))
    progres_list.reverse()
    visited_set: Set[GraphNode] = set()
    while len(progres_list) > 0:
        data = progres_list.pop(-1)
        node: GraphNode = data[0]

        if node in visited_set:
            print(
                " " * data[1],
                node.data.name,
                "(recurrent)",
                "parents:",
                len(node.parents),
                "children:",
                len(node.children),
            )
            continue

        visited_set.add(node)
        print(" " * data[1], node.data.name, "parents:", len(node.parents), "children:", len(node.children))
        children = []
        for child in node.children:
            children.append((child, data[1] + 2))
        children.reverse()
        progres_list.extend(children)


#     print( "Total number of items:", len(visited_set) )


def print_stats(build_tree: IncludeGraph, out_path):
    include_counter: collections.Counter = collections.Counter()

    ## tree_item: GraphNode
    for tree_item in build_tree.root.children:
        #         tree_item.chopNodes( "/usr" )
        #         tree_item.chopNodes( "/opt" )

        all_children = tree_item.getFlatList()
        for tree_node in all_children:
            name = tree_node.data.name
            include_counter[name] += 1

    print("Total headers found:", len(include_counter))
    common = include_counter.most_common(50)

    # pprint.pprint( common )

    with open(out_path, "w", encoding="utf-8") as out_file:
        for item, count in common:
            out_file.write(f"{count} {item}\n")
        # pprint.pprint( common, out_file )

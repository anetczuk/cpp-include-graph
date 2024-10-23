# Copyright (c) 2022, Arkadiusz Netczuk <dev.arnet@gmail.com>
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause license found in the
# LICENSE file in the root directory of this source tree.
#

import os
import logging
import re

from typing import Tuple, List, Dict

from showgraph.io import read_file, read_list

from cppincludegraph.includegraph import GraphNode, NodeData, get_flat_list_breadth


_LOGGER = logging.getLogger(__name__)


class GraphBuilder:

    def __init__(self, files_info_dict=None):
        self.files_info_dict = files_info_dict  ## fname -> (fname, fsize)
        self.load_from_disk = files_info_dict is None or len(files_info_dict) < 1
        if self.files_info_dict is None:
            self.files_info_dict = {}
        self.nodes_dict = {}
        self.build_list = []

    def getNode(self, node: GraphNode) -> Tuple[GraphNode, bool]:
        file_info = self.getInfo(node.data)
        item_name = file_info[0]
        file_size = file_info[1]
        new_node_data = self._getNodeFromDict(item_name)
        new_node: GraphNode = new_node_data[0]
        new_node.data.type = node.data.type
        new_node.data.fsize = file_size
        # print( "xxxx:", item_name, file_size )
        return new_node_data

    def getInfo(self, node_data):
        """Return pair (file name, file size)."""
        item_name = node_data.name
        if node_data.type is NodeData.NodeType.PACKAGE:
            return (item_name, 0)

        ## get data from info file
        file_info = self.files_info_dict.get(item_name, None)
        if file_info:
            return file_info

        for key in self.files_info_dict.keys():
            if not key.endswith(item_name):
                continue
            file_info = self.files_info_dict.get(key, None)
            if file_info:
                return file_info

        ## could not find data in dict

        if self.load_from_disk:
            ## read data from disk
            real_path = os.path.realpath(item_name)
            file_stats = os.stat(real_path)
            file_size = file_stats.st_size
            file_data = (real_path, file_size)
            self.files_info_dict[item_name] = file_data
            self.files_info_dict[real_path] = file_data
            return file_data

        _LOGGER.warning("unable to get data for file: %s", item_name)
        return (item_name, 0)

    def _getNodeFromDict(self, node_name) -> Tuple[GraphNode, bool]:
        found_node = self.nodes_dict.get(node_name, None)
        if found_node:
            return (found_node, False)
        found_node = GraphNode()
        found_node.data.name = node_name
        self.nodes_dict[node_name] = found_node
        return (found_node, True)

    def addTree(self, package_node: GraphNode, reduce_dirs=None):
        _LOGGER.info("getting children list from %s", package_node.data.name)

        ignore_list = reduce_dirs
        #         ignore_list = [ "/usr", "/opt" ]
        raw_children = get_flat_list_breadth([package_node], ignore_children=ignore_list)

        _LOGGER.info("processing children list %s", len(raw_children))
        for child in raw_children:
            new_node_data = self.getNode(child)
            new_node: GraphNode = new_node_data[0]

            if len(child.parents) < 1:
                ## no parents, children will be added later
                #             print( "adding package:", new_node.data.name )
                self.build_list.append(new_node)
                continue

            for child_parent in child.parents:
                existing_parent_data = self.getNode(child_parent)
                if existing_parent_data[1] is True:
                    raise RuntimeError("parent should already exist")
                existing_parent = existing_parent_data[0]
                if new_node in existing_parent.children:
                    continue
                existing_parent.addChild(new_node)


def find_build_logs(log_dir, log_name):
    if log_dir is None:
        return []
    if log_name is None:
        log_name = "build.make.log"
    log_files_list = []
    for root, _, fnames in os.walk(log_dir):
        for fname in fnames:
            if fname != log_name:
                continue
            log_path = os.path.join(root, fname)
            log_files_list.append(log_path)
    return log_files_list


def read_build_logs(
    log_files_list, build_dir, files_info_dict=None, reduce_dirs=None, build_regex=None, name_from_log_file=False
) -> List[GraphNode]:
    if files_info_dict is None:
        files_info_dict = {}

    #     raw_tree: List[ GraphNode ] = []
    graph_builder = GraphBuilder(files_info_dict)

    read_counter = 0
    read_size = len(log_files_list)
    for log_path in log_files_list:
        read_counter += 1
        _LOGGER.info("%s/%s: reading log file: %s", read_counter, read_size, log_path)
        module_tree_list = read_build_log_file(log_path, build_dir, build_regex)
        if not module_tree_list:
            continue
        package_node = GraphNode()
        if name_from_log_file:
            log_base = os.path.basename(log_path)
            log_base = os.path.splitext(log_base)[0]
            package_node.data.name = log_base
        else:
            if len(log_files_list) > 1:
                log_dir = os.path.dirname(log_path)
                package_node.data.name = os.path.basename(log_dir)
            else:
                package_node.data.name = os.path.basename(build_dir)
        package_node.data.type = NodeData.NodeType.PACKAGE
        package_node.addChildren(module_tree_list)
        #         raw_tree.append( package_node )

        graph_builder.addTree(package_node, reduce_dirs)

    return graph_builder.build_list


def read_build_log_file(log_path, build_dir, build_regex=None) -> List[GraphNode]:
    content = read_file(log_path)
    if not content:
        _LOGGER.warning("unable to read file: %s", log_path)
        return None

    if not build_regex:
        ## defaulting to make output
        build_regex = r".*Building \S* object (.*)$"

    cxx_object_node_list = []
    level_node_dict: Dict[int, GraphNode] = None

    line_num = 0
    for line in content.splitlines():
        line_num += 1
        line = line.strip()
        line = escape_ansi(line)

        ## print( "line:", line )

        recent_obj_file = None
        found_obj_file = re.findall(build_regex, line)
        if len(found_obj_file) == 1:
            recent_obj_file = found_obj_file[0]

        if recent_obj_file:
            ## new object file -- expecting include tree
            ## print( f"xxx: >{recent_obj_file}<" )

            # recent_obj_file = os.path.realpath( recent_obj_file )
            item_node = GraphNode()
            item_node.data.name = os.path.join(build_dir, recent_obj_file)
            item_node.data.type = NodeData.NodeType.OBJ_FILE
            level_node_dict = {}
            level_node_dict[0] = item_node
            continue

        if line.startswith("."):
            ## content of include tree
            if level_node_dict is None:
                ## invalid case -- happens in case of interweaved logs
                _LOGGER.error("invalid (interweaved) file %s:%s", log_path, line_num)
                return None
                # raise Exception( f"invalid (interweaved) file {log_path}:{line_num}" )

            space_pos = line.find(" ")
            if space_pos < 0:
                ## invalid case -- happens in case of interweaved logs
                level_node_dict = None
                _LOGGER.error("invalid case - no space found: %s in %s", line, log_path)
                _LOGGER.error("invalid (interweaved) file %s:%s", log_path, line_num)
                return None
                # raise Exception( f"invalid (interweaved) file {log_path}:{line_num}" )

            parent_index = space_pos - 1
            if parent_index not in level_node_dict:
                ## invalid case -- happens in case of interweaved logs
                level_node_dict = None
                _LOGGER.error("invalid (interweaved) file %s:%s", log_path, line_num)
                return None
                # raise Exception( f"invalid (interweaved) file {log_path}:{line_num}" )

            dots_text = line[:space_pos]
            dots_set = set(dots_text)
            if len(dots_set) > 1:
                ## invalid case -- happens in case of interweaved logs
                level_node_dict = None
                _LOGGER.error("invalid case - invalid chars found: >%s< %s in %s", dots_text, space_pos, log_path)
                _LOGGER.error("invalid (interweaved) file %s:%s", log_path, line_num)
                return None
                # raise Exception( f"invalid (interweaved) file {log_path}:{line_num}" )

            ## adding header node
            item = line[space_pos + 1 :]
            item = os.path.realpath(item)
            graph_node = GraphNode()
            graph_node.data.name = item
            graph_node.data.type = NodeData.NodeType.HEADER
            parent_node = level_node_dict[parent_index]
            parent_node.addChild(graph_node)
            level_node_dict[space_pos] = graph_node
            continue

        ## other case
        if level_node_dict is not None:
            root_node = level_node_dict[0]
            cxx_object_node_list.append(root_node)
        level_node_dict = None

    return cxx_object_node_list


# def get_after( content, start ):
#     try:
#         pos = content.index( start )
#         return content[ pos + len(start): ]
#     except ValueError:
#         pass
#     return None


def escape_ansi(line):
    ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", line)


##
def read_files_info(files_info_path):
    ret_data = {}
    content = read_list(files_info_path)
    for line in content:
        times_list = re.findall(r"\"(.*)\" \"(.*)\" (\d+)", line)
        if len(times_list) != 1:
            continue
        data_tuple = times_list[0]
        if len(data_tuple) != 3:
            continue
        in_file = data_tuple[0]
        real_name = data_tuple[1]
        ret_data[in_file] = [real_name, int(data_tuple[2])]
        ## sometimes compiler prints real path (resolves links)
        ret_data[real_name] = [real_name, int(data_tuple[2])]
    return ret_data

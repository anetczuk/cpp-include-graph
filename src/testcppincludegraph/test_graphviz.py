# Copyright (c) 2022, Arkadiusz Netczuk <dev.arnet@gmail.com>
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause license found in the
# LICENSE file in the root directory of this source tree.
#

import unittest

from showgraph.graphviz import Graph, EDGE_COLORS_PATH, EDGE_COLORS_LIST

import sys
import pydotplus


class GraphTest(unittest.TestCase):
    def setUp(self):
        ## Called before testfunction is executed
        pass

    def tearDown(self):
        ## Called after testfunction was executed
        pass

    def test_addNodeObject(self):
        print( "aaaa1", sys.prefix )
        print( "aaaa2", EDGE_COLORS_PATH )
        self.assertEqual( "aaa", EDGE_COLORS_LIST )

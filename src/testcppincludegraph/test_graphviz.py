# Copyright (c) 2022, Arkadiusz Netczuk <dev.arnet@gmail.com>
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause license found in the
# LICENSE file in the root directory of this source tree.
#

import unittest

from showgraph.graphviz import EDGE_COLORS_LIST


class GraphTest(unittest.TestCase):
    def setUp(self):
        ## Called before testfunction is executed
        pass

    def tearDown(self):
        ## Called after testfunction was executed
        pass

    def test_edge_colors_list(self):
        """Test is dependency project is installed successfully with data."""
        self.assertGreater(len(EDGE_COLORS_LIST), 0)

# Copyright (c) 2022, Arkadiusz Netczuk <dev.arnet@gmail.com>
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause license found in the
# LICENSE file in the root directory of this source tree.
#

import sys
import os


MODULE_DIR = os.path.dirname( os.path.abspath(__file__) )

#### append source root
sys.path.append(os.path.abspath( os.path.join( MODULE_DIR, ".." ) ))


DATA_DIR = os.path.join( MODULE_DIR, "data" )


def get_data_path( file_path ):
    return os.path.join( DATA_DIR, file_path )

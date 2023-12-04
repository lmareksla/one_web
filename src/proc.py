import os
import sys
import logging
import binascii
import csv
import datetime

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *
from log import *

sys.path.append("src")

from utils import *
from data_file import *
from data_info_file import *
from gps_file import *
from data_linker import *
from mask import *
from clusterer import *
from dpe import *


if __name__ == '__main__':
    
    print("main processing script")


    # find directories

    # load dirs

    # iterate over dirs

        # load gps
        # load info
        # load data

        # data linker

        # masking of frames

        # running clusterer
            # clusterization
            # export of clists



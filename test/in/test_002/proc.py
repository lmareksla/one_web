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
from decoder import *
from log import *

sys.path.append("src")

from utils import *
from data_info_file import *


if __name__ == '__main__':

    data_info_file_path_name = "devel/data/dosimeter_measure_info.csv" 
    data_info_file = DataInfoFile(data_info_file_path_name, "./test/out/test_002/")
    data_info_file.do_print = False
    data_info_file.load()
    data_info_file.print()

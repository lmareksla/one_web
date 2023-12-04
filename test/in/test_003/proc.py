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
from gps_file import *


if __name__ == '__main__':

    gps_file_path_name = "devel/data/dosimeter_gps_info.csv" 
    gps_file = GpsFile(gps_file_path_name, "./test/out/test_003/")
    gps_file.do_print = False
    gps_file.load()
    gps_file.print(do_full_data_print=True)

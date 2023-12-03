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
from data_file import *


if __name__ == '__main__':

	file_in_path_name = "./test/in/test_001/dosimeter_image_packets.csv"
	data_file = DataFile(file_in_path_name, "./test/out/test_001/")
	data_file.do_print = False
	data_file.load()
	data_file.log_stat()
	data_file.log_frames()
import os
import sys
import logging
import binascii
import csv
import datetime
import matplotlib.colors as mcolors

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from decoder import *
from log import *

sys.path.append("src")

from data_file import *
from gps_file import *
from data_info_file import *
from gps_spice import *
from utils import *
from data_linker import *



if __name__ == '__main__':

    dir_data = "./devel/data/"

    gps_file =  GpsFile(dir_data + "dosimeter_gps_info.csv", log_path="./test/out/test_004/", log_name="log_data.txt")
    data_file = DataFile(dir_data + "dosimeter_image_packets.csv", log_path="./test/out/test_004/", log_name="log_gps.txt")
    info_file = DataInfoFile(dir_data + "dosimeter_measure_info.csv", log_path="./test/out/test_004/", log_name="log_infp.txt")                

    gps_file.do_print = False
    data_file.do_print = False
    info_file.do_print = False

    gps_file.load()
    data_file.load()
    info_file.load()

    frames_ext = []

    data_linker = DataLinker(log_path="./test/out/test_004/", log_name="log_data_linker.txt")
    data_linker.do_print = False
    data_linker.link_data_info_gps(data_file, info_file, gps_file, frames_ext, do_print_info=True)

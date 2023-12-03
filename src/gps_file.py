import os
import sys
import logging
import binascii
import csv
import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import math
from mpl_toolkits.mplot3d import Axes3D

import spiceypy as spice

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from log import *


class GpsFile(object):
    """docstring for GpsFile"""
    def __init__(self, file_in_path_name):
        super(GpsFile, self).__init__()

        self.file_in_path_name = file_in_path_name

        self.data = pd.DataFrame()

    def load(self):
        if not self.file_in_path_name:
            raise_runtime_error(f"GpsFile.load - fail to load file: {self.file_in_path_name}.")

        try:
            self.data = pd.read_csv(self.file_in_path_name, sep=",")   
        except Exception as e:
            raise_runtime_error(f"FileMeasInfoload - fail to load data from: {self.file_in_path_name}. {e}")


if __name__ == '__main__':
    
    case = 4

    if case == 1:

        file_in_path_name = "./devel/data_file/dosimeter_gps_info.csv"

        gps_file = GpsFile(file_in_path_name)

        gps_file.load()


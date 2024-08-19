import os
import sys
import logging
import binascii
import csv
import datetime
import multiprocessing
import shutil
import json
import time
from matplotlib.colors import LogNorm
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import copy
from datetime import datetime

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *
from log import *

sys.path.append("src")

from dir import *
from utils import *
from data_file import *
from data_info_file import *
from gps_file import *
from data_linker import *
from mask import *
from clusterer import *
from dpe import *
from clist_h5 import *
from plot import *
from analysis import *

sys.path.append("src/pydpe/src")

from clist import *
from cluster import *

def json_dump_endl(file_out_path_name, data_json, file_mode):
    """introduces endl after each item, but not in dictionaries - stays as one liner"""

    file_out_path_name_adj = file_out_path_name + ".adj" 

    with open(file_out_path_name_adj, "w") as file_json:
        json.dump(data_json, file_json)

    line_adjust = ""
    with open(file_out_path_name_adj, "r") as file_json:
        for line in file_json:
            line = line.replace("{", "{\n ")
            line = line.replace("],", "],\n")
            # line = line.replace("\",", "\",\n")            
            line = line.replace("}", "\n}")
            line_adjust += line

    with open(file_out_path_name, file_mode) as file_json:
        file_json.write(line_adjust)


    delete_file(file_out_path_name_adj)


def export_graph(file_out_path_name, data_x, data_y, key_x, key_y, label_x="", label_y="", title="", file_format="json", file_mode="w"):
    
    if file_format == "json":

        data_json = {}

        data_json[key_x] = data_x
        data_json[key_y] = data_y
        data_json["title"] = title
        data_json["label_x"] = label_x
        data_json["label_y"] = label_y

        # with open(file_out_path_name, file_mode) as file_json:
        #     json.dump(data_json, file_json,  indent=1)
        json_dump_endl(file_out_path_name, data_json, file_mode)

def export_graphs(file_out_path_name, data_and_keys, label_x="", label_y="", title="", file_format="json", file_mode="w"):
    
    if file_format == "json":

        data_json = {}


        for data_and_keys_list in data_and_keys:
            key_x = data_and_keys_list[2]
            key_y = data_and_keys_list[3]
            data_json[key_x] = data_and_keys_list[0]
            data_json[key_y] = data_and_keys_list[1]

        data_json["title"] = title
        data_json["label_x"] = label_x
        data_json["label_y"] = label_y

        # with open(file_out_path_name, file_mode) as file_json:
        #     json.dump(data_json, file_json,  indent=2)
        json_dump_endl(file_out_path_name, data_json, file_mode)


def export_map(file_out_path_name, data_z_2d, data_x, data_y, key_z, key_x, key_y, 
                label_z="", label_x="", label_y="", title="", file_format="json", file_mode="w"):

    if file_format == "json":

        data_json = {}

        data_json[key_x] = data_x
        data_json[key_y] = data_y
        data_json[key_z] = data_z_2d        
        data_json["title"] = title
        data_json["label_x"] = label_x
        data_json["label_y"] = label_y
        data_json["label_z"] = label_y

        # with open(file_out_path_name, file_mode) as file_json:
        #     json.dump(data_json, file_json,  indent=1)
        json_dump_endl(file_out_path_name, data_json, file_mode)

if __name__ == "__main__":
    
    case = 1

    if case == 1:

        file_out_path = "devel/export_phys"
        file_out_name = "graph.json"

        data_x = [1,2,3,4,5]
        data_y = [1.23124, 23.4124, 12, 2, 5]

        key_x = "key_x"
        key_y = "key_y"


        export_graph(file_out_path + os.sep + file_out_name, data_x, data_y, key_x, key_y) 

    if case == 2:

        file_out_path = "devel/export_phys"
        file_out_name = "graphs.json"

        data_x = [1,2,3,4,5]
        data_y = [1.23124, 23.4124, 12, 2, 5]

        key_x = "key_x"
        key_y = "key_y"


        data_and_keys = [   [data_x, data_y, key_x + "1", key_y + "1"],
                            [data_x, data_y, key_x + "2", key_y + "2"],
                            [data_x, data_y, key_x + "3", key_y + "3"]
                         ]

        export_graphs(file_out_path + os.sep + file_out_name, data_and_keys) 

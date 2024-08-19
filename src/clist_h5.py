import sys
import math
import os
import time

import pandas as pd
import h5py
import json
import numpy as np
import matplotlib.pyplot as plt

sys.path.append("src")
from dir import *

sys.path.append("src/pydpe/src")
from clist import *
from cluster import *


def convert_clist_to_h5(clist, column_names, column_units, h5_out_path_name = ""):
    print(f"info - exporting clist into h5 file {h5_out_path_name}")
    with h5py.File(h5_out_path_name, 'w') as h5_file:
        for column_name, column_unit in zip(column_names, column_units):
            print(f"\tinfo - converting column {column_name}")
            h5_file.create_dataset(column_name, data=clist[column_name].values)
        

def load_column_names_units(clist_path_name):
    with open(clist_path_name, 'r') as file:
        column_names = file.readline().strip().split('\t')
        column_units = file.readline().strip().split('\t')
    return column_names, column_units

def load_clist_from_h5(h5_file_path_name):

    # Open the HDF5 file for reading
    with h5py.File(h5_file_path_name, 'r') as h5_file:
        # Initialize an empty dictionary to store column data
        column_data = {}

        # Iterate over the keys in the HDF5 file
        for key in h5_file.keys():
            # Read the data from each dataset
            column_data[key] = h5_file[key][:]

    # Construct the DataFrame from the column data
    df = pd.DataFrame(column_data)

    # Display the resulting DataFrame
    print(df)

if __name__ == "__main__":

    dir_data_proc =     "/home/lukas/file/analysis/one_web/data/proc"
    dir_proc_dpe_name = "04_dpe"
    h5_out_path_name =  os.path.join(dir_data_proc, "clist_total.h5")

    dirs_proc_data_name = sorted(list_dirs_of_dir(dir_data_proc))
    
    clist_total = None
    column_names = []
    column_units = []

    for idx, dir_proc_data_name in enumerate(dirs_proc_data_name):

        print(f"info - processing {dir_proc_data_name}")

        dir_proc_dpe_data = os.path.join(dir_data_proc, dir_proc_data_name, dir_proc_dpe_name)
        clist_path_name = os.path.join(dir_proc_dpe_data, "File", "data_ext.clist")

        clist = pd.read_csv(clist_path_name, sep='\t', header=None, skiprows=2)

        if not column_names:
            column_names, column_units = load_column_names_units(clist_path_name)

        clist.columns = column_names

        if clist_total is None:
            clist_total = clist
        else:
            clist_total = pd.concat([clist_total, clist], ignore_index=True) 

    clist_total["ClusterPixels"] = clist_total["ClusterPixels"].astype(str)

    if clist_total is not None and not clist_total.empty:
        convert_clist_to_h5(clist_total, column_names, column_units, h5_out_path_name)
    else:
        print(f"error - failed to convert clist to h5 file")

    start = time.time()


    # load_clist_from_h5(h5_out_path_name)

    # print(f"time need to load h5 df: {time.time() - start}")

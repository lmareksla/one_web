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

sys.path.append("src")

from dir import *
from utils import *
from data_file import *
from data_info_file import *
from gps_file import *
from data_linker import *
from mask import *
from clusterer import *

from clist_h5 import *
from report import *
from analysis import *

sys.path.append("src/pydpe/src")

from clist import *
from cluster import *


def files_in_dir(directory, base_name):
    file_list = []
    for filename in os.listdir(directory):
        if base_name in filename:
            full_path = os.path.join(directory, filename)
            if os.path.isfile(full_path):
                file_list.append(full_path)
    return file_list


def analyse_frames_from_dir(dir_path_name, frame_base_name, count_frame_max=None):

    if not os.path.exists(dir_path_name):
        raise RuntimeError(f"dirctory does not exist {dir_path_name}")

    frame_files = files_in_dir(dir_path_name, frame_base_name)  

    frame_count = len(frame_files)
    if count_frame_max is not None:
        frame_count = count_frame_max
    
    frac_more_to_alls = np.zeros(frame_count)

    for idx, frame_file in enumerate(frame_files):

        if count_frame_max is not None and idx >= count_frame_max:
            break 

        if "json" in frame_files:
            continue 

        frame_file_json = frame_file.replace(frame_base_name + ".txt", "info.json")

        frame = FrameExtInfo()
        frame.load(frame_file, frame_file_json)

        frame_matrix = frame.get_matrix()

        count_sum = frame_matrix.sum()
        count_one = np.sum(np.isin(frame_matrix, [1]))
        count_more = np.sum(frame_matrix > 1)
        count_hit_pix = np.count_nonzero(frame_matrix)

        # print(f"count_hit_pix  {count_hit_pix}")
        # print(f"count_sum      {count_sum}")
        # print(f"count_one      {count_one}")
        # print(f"count_more     {count_more}")
        # print(f"frac_more_to_all    {100*frac_more_to_all:.2f}")
        
        if count_hit_pix > 0:
            frac_more_to_all = count_more/float(count_hit_pix)
            frac_more_to_alls[idx] = frac_more_to_all

    frac_more_to_all_mean = frac_more_to_alls.mean()
    frac_more_to_all_std = frac_more_to_alls.std()

    return frac_more_to_all_mean, frac_more_to_all_std


def analyse_clists(dir_path_name):

    clist_name = "data_ext.clist"
    clist_path_name = os.path.join(dir_path_name, clist_name)

    clist = Clist(clist_path_name)

    frame_count_pileups = 0
    frame_unix_time_curr = 0
    frame_unix_time_prev = clist.data.at[0,"T"]

    frames_count_pileups = []
    frames_unix_time = []
    frames_long = []
    frames_lat = []

    row = None

    for idx, row in clist.data.iterrows():

        frame_unix_time_curr = row["T"]


        if frame_unix_time_curr != frame_unix_time_prev:  
            frame_unix_time_prev = frame_unix_time_curr

            frames_unix_time.append(frame_unix_time_curr)
            frames_count_pileups.append(frame_count_pileups)
            frames_long.append(row["GpsLong"]*0.5)
            frames_lat.append(row["GpsLat"]*0.5)

            frame_count_pileups = 0


        # load cluster
        cluster = cl.Cluster()
        cluster_str = row["ClusterPixels"]
        try:
            cluster.load_from_string(cluster_str)
        except:
            print(f"error - failed to load cluster {idx} from row")
            continue

        # iterating trough list of pixels
        for pix in cluster.pixels:
            if pix.toa > 1:
                frame_count_pileups += 1
                break

    frames_unix_time.append(frame_unix_time_curr)
    frames_count_pileups.append(frame_count_pileups)
    frames_long.append(row["GpsLong"]*0.5)
    frames_lat.append(row["GpsLat"]*0.5)


    # fig,axs = plt.subplots(3,1, figsize=(9,20))
    # axs[0].scatter(frames_long, frames_lat, s=5)
    # axs[1].scatter(frames_long, frames_count_pileups, s=5)
    # axs[2].scatter(frames_lat, frames_count_pileups, s=5)    
    # plt.show()

    return frames_long, frames_lat, frames_count_pileups


def hitogram_normalized_to_occurance(list_x, list_y, vals, bins=None, ranges=None):
    hist_bin_vals_occ, x_edges, y_edges = numpy.histogram2d(list_x, list_y, bins=bins, range=ranges)    
    hist_bin_vals, x_edges, y_edges = numpy.histogram2d(list_x, list_y, bins=bins, range=ranges, weights=vals)    

    # to avoid division with zeros, only division with ge 2 is valid (0 and 1 has same effect)
    hist_bin_vals_occ[hist_bin_vals_occ == 0] = 1  

    # avarage over all frames - counts of frames in given bin of long & lat
    hist_bin_vals = hist_bin_vals / hist_bin_vals_occ

    return x_edges, y_edges, hist_bin_vals

if __name__ == '__main__':

    dir_data_proc =     "/home/lukas/file/analysis/one_web/data/pile_up/proc"
    dir_out_figs =      "/home/lukas/file/analysis/one_web/data/pile_up/results"

    dir_proc_mask_name =        "02_mask"
    dir_proc_clusterer_name =   "03_clusterer"

    legend_labels = ["1500", "1000", "750"]

    dirs_proc_data_name = sorted(list_dirs_of_dir(dir_data_proc))

    roi = [[62, 192], [62, 192]]    

    bins = [10,5]

    datetime_batch_start_list = []

    list_frames_count_pileups = []
    list_frames_unix_time = []
    list_frames_long = []
    list_frames_lat = []

    for idx, dir_proc_data_name in enumerate(dirs_proc_data_name):

        if dir_proc_data_name == "1st":
            continue 

        datetime_batch_start_list.append(idx)

        dir_proc_data = os.path.join(dir_data_proc, dir_proc_data_name, dir_proc_clusterer_name)
        frames_long, frames_lat, frames_count_pileups = analyse_clists(dir_proc_data)

        list_frames_count_pileups.append(frames_count_pileups)
        list_frames_long.append(frames_long)
        list_frames_lat.append(frames_lat)           


    for idx in range(len(list_frames_count_pileups)):    

        sum_frames_count_pileups = np.sum(list_frames_count_pileups[idx])

        print(f"{legend_labels[idx]}\t{sum_frames_count_pileups}\t{sum_frames_count_pileups/len(list_frames_count_pileups[idx]):.2f}\t{np.max(list_frames_count_pileups[idx])}")



    fig,axs = plt.subplots(1,3, figsize=(20,8))
    for idx in range(len(list_frames_count_pileups)):

        frames_long = list_frames_long[idx]
        frames_lat = list_frames_lat[idx]
        frames_count_pileups = list_frames_count_pileups[idx]

        x_edges, y_edges, hist_bin_vals = hitogram_normalized_to_occurance(frames_long, frames_lat, frames_count_pileups, bins=bins)
        hist_bin_vals, x_edges, y_edges = convert_np_to_plt_hist2d(hist_bin_vals, x_edges, y_edges)
        plot_longlatvar(x_edges, y_edges, hist_bin_vals, ax=axs[idx], fig=fig, bins=bins, do_log_z=False, cmap="viridis")

    plt.show()        

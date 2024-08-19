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
from report import *

sys.path.append("src/pydpe/src")

from clist import *
from cluster import *

def unzip_mask_directory(dir_mask_path_name):
    unzip_directory(dir_mask_path_name + ".zip", dir_mask_path_name)

def analyse_frames_pile_up(dir_path_name, frame_base_name, count_frame_max=None):

    if not os.path.exists(dir_path_name):
        raise RuntimeError(f"directory does not exist {dir_path_name}")

    frame_files = files_in_dir(dir_path_name, frame_base_name)  

    frame_count = len(frame_files)
    if count_frame_max is not None:
        frame_count = count_frame_max
    

    frac_more_to_alls = np.zeros(frame_count)


    for idx,frame_file in enumerate(frame_files):

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

def plot_pile_up(dir_out_figs, datetime_batch_start_list, frac_more_to_all_means, frac_more_to_all_stds):

    fig, ax = plt.subplots(2,1, figsize=(15,12))
    ax[0].errorbar(datetime_batch_start_list, 100*np.array(frac_more_to_all_means), yerr=100*np.array(frac_more_to_all_stds), 
                fmt='o', capsize=2,markersize=3, elinewidth=0.5 )    
    ax[0].set_xlabel("start of data batch")
    ax[0].set_ylabel("frac of more count pix to all hit pix [%]")

    ax[1].scatter(datetime_batch_start_list, 100*np.array(frac_more_to_all_means), color="C0", s=10)
    ax[1].set_xlabel("start of data batch")
    ax[1].set_ylabel("frac of more count pix to all hit pix [%]")      
    ax[1].set_title(f"fraction of more count pixels to count of all hit pixels - mean: {np.mean(100*np.array(frac_more_to_all_means)):.2f} +- {np.mean(100*np.array(frac_more_to_all_stds)):.2f}")

    plt.savefig(dir_out_figs + os.path.sep + "frac_more_hit_pix_all.png")
    plt.close()  


def evaluate_saturates_frame(count_pix_hit, count_par ,frame_id, dir_mask_path_name, gps, clist_rows):

    if count_pix_hit < 200:
        return

    frame_base_name = f"{str(int(frame_id)).zfill(7)}"
    data_in_path_names = [  os.path.join(dir_mask_path_name, f"{frame_base_name}_Count.txt"), 
                            os.path.join(dir_mask_path_name, f"{frame_base_name}_iToT.txt")] 
    info_in_path_name = os.path.join(dir_mask_path_name, f"{frame_base_name}_info.json") 

    print(info_in_path_name)

    frame = Frame()
    frame.load(data_in_path_names, info_in_path_name)    

    fig, axs = plt.subplots(2,3, figsize=(18,12))

    frame.plot_matrix(mode=Tpx3Mode.TOT ,do_log_z = True, fig=fig, ax=axs[0,0], label_z="energy [keV]")
    frame.plot_matrix(mode=Tpx3Mode.COUNT ,do_log_z = True, fig=fig, ax=axs[0,1], label_z="count [-]")    
    axs[0,2].axis('off')
    axs[0,2].set_xticks([])
    axs[0,2].set_yticks([])            
    axs[0,2].text(0.3, 0.8, f"longitude [deg]:     {gps[0]:.1f}", fontsize=12, ha='left', va='center')
    axs[0,2].text(0.3, 0.7, f"latitude [deg]:     {gps[1]:.1f}", fontsize=12, ha='left', va='center')
    axs[0,2].text(0.3, 0.6, f"count pixels:     {count_pix_hit}", fontsize=12, ha='left', va='center')
    axs[0,2].text(0.3, 0.5, f"count particles:   {count_par}", fontsize=12, ha='left', va='center')

    # axs[2].text(0.3, 0.7, f"dir:   {dir_mask_path_name}", fontsize=12, ha='center', va='center')8

    hist_el = None; cbar_el = None
    hist_prot = None; cbar_prot = None
    hist_ion = None; cbar_ion = None

    for row in clist_rows:

        cluster = Cluster()
        cluster.load_from_clist_row(row)

        if row["PIDClass"] == 0: 
            hist_prot, cbar_prot = cluster.plot(fig=fig, ax=axs[1,0], show_plot=False)
            cbar_prot.remove()
        elif row["PIDClass"] == 2: 
            hist_ion, cbar_ion = cluster.plot(fig=fig, ax=axs[1,1], show_plot=False)
            cbar_ion.remove()
        else:
            hist_el, cbar_el = cluster.plot(fig=fig, ax=axs[1,2], show_plot=False)
            cbar_el.remove()            

    axs[1,0].set_title("protons")
    axs[1,0].set_xlim(0,256)
    axs[1,0].set_ylim(0,256)
    if hist_prot is not None:
        cbar_prot = plt.colorbar(hist_prot[3], ax=axs[1,0])

    axs[1,1].set_title("ions")
    axs[1,1].set_xlim(0,256)
    axs[1,1].set_ylim(0,256)
    if hist_ion is not None:
        cbar_ion = plt.colorbar(hist_ion[3], ax=axs[1,1])

    axs[1,2].set_title("electrons and photons")
    axs[1,2].set_xlim(0,256)
    axs[1,2].set_ylim(0,256)
    if hist_el is not None:
        cbar_el = plt.colorbar(hist_el[3], ax=axs[1,2])

    datetime = dir_mask_path_name.split("/")[-2]

    plt.savefig("/home/lukas/file/analysis/one_web/data/devel/saturation/frames_weird/" + datetime + "_" + frame_base_name + ".png")
    plt.close()

def analyse_frames_saturation(dir_proc_path_name, dir_mask_name, dir_dpe_name):

    dir_mask_path_name = os.path.join(dir_proc_path_name, dir_mask_name)  
    dir_dpe_path_name = os.path.join(dir_proc_path_name, dir_dpe_name)  

    clist_path_name = os.path.join(dir_dpe_path_name, "File", "data_ext.clist")



    clist = Clist(clist_path_name)

    frame_par_counts = [0]
    frame_pix_hit_counts = [0] 
    frame_times = [0]
    frame_id_prev = -1
    gps_prev = []
    clist_rows = []

    for idx, row in clist.data.iterrows():
        progress_bar(len(clist.data), idx+1)


        t_curr = row["T"]
        frame_id_curr = row["Flags"]
        pix_hit_count = row["Size"]
        gps = [row["GpsLong"], row["GpsLat"]]

        if frame_id_prev != -1  and frame_id_curr != frame_id_prev:
            if frame_times[-1] != 0:

                # evaluate saturation
                evaluate_saturates_frame(frame_pix_hit_counts[-1], frame_par_counts[-1],
                                         frame_id_prev, dir_mask_path_name, gps_prev, clist_rows)

                frame_pix_hit_counts.append(0)
                frame_par_counts.append(0)
                frame_times.append(0)
            else:
                frame_par_counts[-1] = 0
                frame_pix_hit_counts[-1] = 0

            clist_rows.clear()

        frame_par_counts[-1] += 1
        frame_pix_hit_counts[-1] += pix_hit_count
        frame_times[-1] = t_curr
        clist_rows.append(row)

        frame_id_prev = frame_id_curr
        gps_prev = gps


    return frame_par_counts, frame_times, frame_pix_hit_counts



def plot_saturation():
    pass


if __name__ == '__main__':

    dir_data_proc =     "/home/lukas/file/analysis/one_web/data/proc"
    dir_phys =          "/home/lukas/file/analysis/one_web/data/phys"
    dir_out_figs =      "/home/lukas/file/analysis/one_web/data/stat"

    dir_proc_mask_name =    "02_mask"
    dir_dpe_name =          "04_dpe"

    dirs_proc_data_name = sorted(list_dirs_of_dir(dir_data_proc))
    
    roi = [[62, 192], [62, 192]]    

    do_pile_up =         False
    do_saturation =      True



    datetime_batch_start_list = []


    # pile-up
    if do_pile_up:

        count_frame_max =           None
        frac_more_to_all_means =    []
        frac_more_to_all_stds =     []

        for idx, dir_proc_data_name in enumerate(dirs_proc_data_name):
            progress_bar(len(dirs_proc_data_name), idx+1)

            datetime_batch_start = extract_1st_datetime_from_dir_name(dir_proc_data_name)
            datetime_batch_start_list.append(datetime_batch_start)

            dir_proc_dpe_data = os.path.join(dir_data_proc, dir_proc_data_name, dir_proc_mask_name)

            # unzip_mask_directory(dir_proc_dpe_data)

            # analysis
            frac_more_to_all_mean, frac_more_to_all_std = analyse_frames_pile_up(dir_proc_dpe_data, "count", count_frame_max)
            frac_more_to_all_stds.append(frac_more_to_all_std)
            frac_more_to_all_means.append(frac_more_to_all_mean)


        # plot
        plot_pile_up(dir_out_figs, datetime_batch_start_list, frac_more_to_all_means, frac_more_to_all_stds)


    # saturation
    if do_saturation:

        frame_par_counts = []
        frame_times = []
        frame_pix_hit_counts = []

        dir_res_path = "/home/lukas/file/analysis/one_web/data/devel/frame_counts/"
        file_res_path_name = os.path.join(dir_res_path, "data.json")

        do_create_data = True

        if do_create_data:
            for idx, dir_proc_data_name in enumerate(dirs_proc_data_name):
                progress_bar(len(dirs_proc_data_name), idx+1)

                dir_proc_dpe_data = os.path.join(dir_data_proc, dir_proc_data_name)

                unzip_mask_directory(os.path.join(dir_data_proc, dir_proc_data_name, dir_proc_mask_name))

                frame_par_counts_curr, frame_times_curr, frame_pix_hit_counts_curr = analyse_frames_saturation(dir_proc_dpe_data, dir_proc_mask_name, dir_dpe_name)
                
                if len(frame_par_counts_curr) != 0:
                    frame_par_counts.extend(frame_par_counts_curr)
                    frame_times.extend(frame_times_curr)
                    frame_pix_hit_counts.extend(frame_pix_hit_counts_curr)


            with open(file_res_path_name, "w") as file_json:
                data = {}
                data["frame_par_counts"] = frame_par_counts
                data["frame_times"] = frame_times
                data["frame_pix_hit_counts"] = frame_pix_hit_counts

                json.dump(data, file_json)

        else:
            with open(file_res_path_name, "r") as file_json:
                data = json.load(file_json)

            frame_par_counts = data["frame_par_counts"]       
            frame_times = data["frame_times"]       
            frame_pix_hit_counts = data["frame_pix_hit_counts"]       

        fig, axs = plt.subplots(2,2, figsize=(15,15))

        bin_max=np.max(frame_par_counts)
        axs[0,0].hist(frame_par_counts, bins=bin_max, range=[0,bin_max])

        bin_max=np.max(frame_pix_hit_counts)
        axs[0,1].hist(frame_pix_hit_counts, bins=bin_max, range=[0,bin_max])
        
        bin_max=np.max(frame_pix_hit_counts)
        hist2d_res = axs[2].hist2d(frame_pix_hit_counts, frame_par_counts, 
                        bins=[np.max(frame_pix_hit_counts), np.max(frame_par_counts)], 
                        range=[[0,np.max(frame_pix_hit_counts)],[0,np.max(frame_par_counts)]],
                        norm = LogNorm())        
        cbar = fig.colorbar(hist2d_res[3], ax=axs[2])  # hist[3] returns the QuadMesh
        cbar.set_label('Counts')        

        plt.show()

        # plot
        # fig, axs = plt.subplots(2,1, figsize=(15,15))

        # for idx in range(len(frame_times)):
        #     if frame_times[idx] == 0:
        #         print(idx, len(frame_par_counts))

        # axs[0].scatter(list(range(len(frame_par_counts))), frame_par_counts, s=0.5)
        # axs[1].scatter(frame_times, frame_par_counts, s=0.5)

        # plt.show()
import os
import sys
import logging
import binascii
import csv
import datetime
import matplotlib.colors as mcolors
import re
import json

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *
from log import *

sys.path.append("src")

from data_file import *
from gps_file import *
from data_info_file import *
from gps_spice import *
from utils import *
from data_linker import *

def get_directories(root_path):
    entries = os.listdir(root_path)
    directories = [entry for entry in entries if os.path.isdir(os.path.join(root_path, entry))]
    return directories

def extract_1st_datetime_from_dir_name(dir_name):
    dir_name = os.path.basename(os.path.normpath(dir_name))

    # Use regular expression to find the datetime
    datetime_match = re.search(r'_(\d{4}-\d{2}-\d{2}_\d{2}_\d{2}_\d{2}_\d{3})-', dir_name)

    if datetime_match:
        extracted_datetime_str = datetime_match.group(1)

        # Convert the string to a datetime object
        extracted_datetime = datetime.datetime.strptime(extracted_datetime_str, "%Y-%m-%d_%H_%M_%S_%f")

    return extracted_datetime

def check_list_str_in_str(list_str, str_main):
    for str_item in list_str:
        if str_item in str_main:
            return True
    return False

def get_frame_id_mode_from_file_name(file_in_name):
    file_in_path_name_no_suffix =  file_in_name[:file_in_name.find(".")]
    frame_id_mode = file_in_path_name_no_suffix.split("_")
    
    if len(frame_id_mode) < 2:
        return None, None

    frame_id = int(frame_id_mode[0])
    frame_mode = frame_id_mode[1]

    return frame_id, frame_mode

def load_frames(dir_in_path):
    frames = []

    file_names = os.listdir(dir_in_path)
    file_names = sorted(file_names)

    file_ignore_patterns = ["sum", "json", "mask"]

    frame_id_prev = -1
    data_in_path_names = []

    for file_name in file_names: 
        if check_list_str_in_str(file_ignore_patterns, file_name):
            continue

        frame_id, frame_mode = get_frame_id_mode_from_file_name(file_name)

        if data_in_path_names and frame_id_prev != frame_id:
            data_in_name = os.path.basename(data_in_path_names[0])
            info_in_name = data_in_name[: data_in_name.find("_")] + "_info.json"
            info_in_path_name = os.path.join(dir_in_path, info_in_name)
            frame = FrameExtInfo()
            frame.load(data_in_path_names, info_in_path_name)
            frames.append(frame) 
            data_in_path_names.clear()

        frame_id_prev = frame_id
        data_in_path_names.append(os.path.join(dir_in_path, file_name) )

    return frames

if __name__ == '__main__':
    
    dir_proc = "/home/lukas/file/analysis/one_web/data/proc/"
    dir_out_figs = "//home/lukas/file/analysis/one_web/data/stat/"

    data_file_json_name =   "data_file.json"
    info_file_json_name =   "data_info_file.json"
    gps_file_json_name =    "gps_file.json"
    data_linker_json_name = "data_linker.json"

    dirs_proc_data = get_directories(dir_proc)
    dirs_proc_data = sorted(dirs_proc_data) 


    datetime_batch_start_list = []
    count_in_data_info_list = np.zeros((len(dirs_proc_data)))
    count_linked_data_info_list = np.zeros((len(dirs_proc_data)))
    count_linked_data_gps_list = np.zeros((len(dirs_proc_data)))
    t_acq_total_data_info_list = np.zeros((len(dirs_proc_data)))
    t_acq_mean_data_info_list = np.zeros((len(dirs_proc_data)))
    t_duration_data_info_list = np.zeros((len(dirs_proc_data)))
    count_in_frames_decode = np.zeros((len(dirs_proc_data)))    
    count_ok_frames_decode = np.zeros((len(dirs_proc_data)))        
    count_error_frames_decode = np.zeros((len(dirs_proc_data)))
    count_error_frames_decode_miss = np.zeros((len(dirs_proc_data)))
    count_error_frames_decode_zero = np.zeros((len(dirs_proc_data)))
    count_error_frames_decode_term = np.zeros((len(dirs_proc_data)))
    temp_mean_list = np.zeros((len(dirs_proc_data)))
    temp_std_list = np.zeros((len(dirs_proc_data)))

    for idx, dir_proc_data in enumerate(dirs_proc_data):
        datetime_batch_start = extract_1st_datetime_from_dir_name(dir_proc_data)
        dir_proc_data_path = os.path.join(dir_proc, dir_proc_data)

        info_json_path_name = os.path.join(dir_proc_data_path, "data_info_file.json")
        linker_json_path_name = os.path.join(dir_proc_data_path, "data_linker.json")
        data_json_path_name = os.path.join(dir_proc_data_path, "data_file.json")
        gps_json_path_name = os.path.join(dir_proc_data_path, "gps_file.json")

        datetime_batch_start_list.append(datetime_batch_start)

        try:
            with open(info_json_path_name, "r") as info_json:
                info_data = json.load(info_json)
            with open(linker_json_path_name, "r") as linker_json:
                linker_data = json.load(linker_json)
            with open(gps_json_path_name, "r") as gps_json:
                gps_data = json.load(gps_json)
            with open(data_json_path_name, "r") as data_json:
                data_data = json.load(data_json)     
        except:
            print(f"failed to read data batch {dir_proc_data} - skipping")
            continue       

        count_linked_data_gps_list[idx] = linker_data["count_linked_data_gps"]
        count_linked_data_info_list[idx] = linker_data["count_linked_data_info"]
        count_in_data_info_list[idx] = linker_data["count_in_data_info"]        
        t_acq_total_data_info_list[idx] = info_data["time_acq_total"]
        t_acq_mean_data_info_list[idx] = info_data["time_acq_mean"]
        t_duration_data_info_list[idx] = info_data["duration_sec"]

        count_in_frames_decode[idx] = data_data["count_all_frames"]
        count_ok_frames_decode[idx] = data_data["count_ok_frames"]
        count_error_frames_decode[idx] = data_data["count_err_integrity_check_frames"]
        count_error_frames_decode_miss[idx] = data_data["count_err_integrity_check_frames_miss"]
        count_error_frames_decode_zero[idx] = data_data["count_err_integrity_check_frames_zero"]
        count_error_frames_decode_term[idx] = data_data["count_err_integrity_check_frames_term"]

        temp_mean_list[idx] = info_data["temperature_mean"]
        temp_std_list[idx] = info_data["temperature_std"]


    
    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, count_in_frames_decode, color="C0",label="in", marker="v", s=10)
    ax.scatter(datetime_batch_start_list, count_linked_data_gps_list, color="C1",label="out", marker="^", s=10)    
    ax.set_xlabel("start of data batch")
    ax.set_ylabel("count of frames [-]")
    ax.set_title("Count of all frames measured (in) and frames which passed thourhg whole processing (out)")      
    ax.legend()
    plt.savefig(dir_out_figs + "count_frames_in_out.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, count_in_frames_decode - count_linked_data_gps_list, color="C0",label="in", marker="v", s=10)
    ax.set_xlabel("start of data batch")
    ax.set_ylabel("count of error frames [-]")
    ax.set_title("Count of all error or lost frames")      
    ax.legend()
    plt.savefig(dir_out_figs + "count_error_frames.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, 100*(count_in_frames_decode - count_linked_data_gps_list)/count_in_frames_decode, color="C0",label="all", marker="v", s=10)
    ax.scatter(datetime_batch_start_list, 100*(count_in_frames_decode - count_ok_frames_decode)/count_in_frames_decode, color="C1", s=10, label="decode", marker="^")
    ax.scatter(datetime_batch_start_list, 100*(count_ok_frames_decode - count_linked_data_info_list)/count_in_frames_decode, color="C2", s=10, label="link info", marker=8)
    ax.scatter(datetime_batch_start_list, 100*(count_linked_data_info_list - count_linked_data_gps_list)/count_in_frames_decode, color="C3", s=10, label="link gps", marker=9)    
    # ax.scatter(datetime_batch_start_list, 100*(count_linked_data_info_list - count_linked_data_gps_list + count_ok_frames_decode - count_linked_data_info_list + count_in_frames_decode - count_ok_frames_decode)/count_in_frames_decode, color="C4", s=10, label="term", marker=9)            
    ax.set_xlabel("start of data batch")
    ax.set_ylabel("Fraction of error frames [%]")
    ax.set_title("Fraction of all error or lost frames to all input frames.")      
    ax.legend()
    plt.savefig(dir_out_figs + "frac_error_frames.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, 100*(count_in_frames_decode - count_linked_data_gps_list)/count_in_frames_decode, color="C0",label="in", marker="v", s=10)
    ax.set_xlabel("start of data batch")
    ax.set_ylabel("Fraction of error frames [%]")
    ax.set_title("Fraction of all error or lost frames to all input frames.")      
    ax.legend()
    plt.savefig(dir_out_figs + "frac_error_frames_all.png")
    plt.close()        


    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, count_in_data_info_list, color="C0",label="in", marker="v", s=10)
    ax.scatter(datetime_batch_start_list, count_linked_data_info_list, color="C1",label="out info link", marker="^", s=10)       
    ax.set_xlabel("start of data batch")
    ax.set_ylabel("count of frames [-]")
    ax.set_title("count of input and output frames from linking processes: info and gps metadata")      
    ax.legend()
    plt.savefig(dir_out_figs + "count_frames_linking.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, 100.*(count_in_data_info_list - count_linked_data_gps_list)/count_in_data_info_list, color="C0", s=10, marker="v", label="lost all")
    ax.scatter(datetime_batch_start_list, 100.*(count_in_data_info_list - count_linked_data_info_list)/count_in_data_info_list, color="C1", s=10, marker="^", label="lost info")
    ax.scatter(datetime_batch_start_list, 100.*(count_linked_data_info_list - count_linked_data_gps_list)/count_in_data_info_list, color="C2", s=10, marker=8, label="lost gps")        
    ax.set_xlabel("start of data batch")
    ax.set_ylabel("fraction of lost frames [%]")  
    ax.set_title("Fraction of lost frames due to linking processes: info and gps metadata.")
    ax.legend()                  
    plt.savefig(dir_out_figs + "frac_frame_linking_lost.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.errorbar(datetime_batch_start_list, temp_mean_list, yerr=temp_std_list, fmt='o', capsize=2,markersize=3, elinewidth=0.5 )    
    ax.set_xlabel("start of data batch")
    ax.set_ylabel("mean temperature [s]")    
    ax.set_title("Mean value of temperature with std as error bars over day of measurement.")      
    plt.savefig(dir_out_figs + "temperature_mean.png")
    plt.close()     

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, t_acq_total_data_info_list/3600., color="C0", s=10)
    ax.set_xlabel("start of data batch")
    ax.set_ylabel("total acq time [h]")      
    ax.set_title("Total acquisition time in one day.")
    plt.savefig(dir_out_figs + "time_acq_total.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, t_acq_mean_data_info_list, color="C0", s=10)
    ax.set_xlabel("start of data batch")
    ax.set_ylabel("mean acq time [s]")    
    ax.set_title("Mean value of acquisition time over day of measurement.")      
    plt.savefig(dir_out_figs + "time_acq_mean.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, 100.*(t_acq_total_data_info_list)/t_duration_data_info_list, color="C0", s=10)
    ax.set_xlabel("start of data batch")
    ax.set_ylabel("fraction acq time to live time [%]")   
    ax.set_title("Fraction of acquisition time in live time of detector.")             
    plt.savefig(dir_out_figs + "frac_acq_live_time.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, count_in_frames_decode, color="C0", s=10, label="all", marker="v")
    ax.scatter(datetime_batch_start_list, count_error_frames_decode, color="C1", s=10, label="error", marker="^")
    ax.scatter(datetime_batch_start_list, count_ok_frames_decode, color="C2", s=10, label="ok", marker=8)
    ax.set_xlabel("start of data batch")      
    ax.set_ylabel("count of frames")
    ax.set_title("Count of frames in decode - all in, error frames and ok out frames.")                 
    plt.savefig(dir_out_figs + "count_frames_decode.png")
    plt.close()      

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, count_error_frames_decode, color="C0", s=10)
    ax.set_xlabel("start of data batch")      
    ax.set_ylabel("count error frames from decoding")
    ax.set_title("Fraction of acquisition time in live time of detector.")                 
    plt.savefig(dir_out_figs + "error_frames_decode.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, (100*count_error_frames_decode)/count_in_data_info_list, color="C0", s=10)
    ax.set_xlabel("start of data batch")      
    ax.set_ylabel("fraction of error frames from decoding to input frames [%]")
    ax.set_title("Fraction of error frames from decoding to input frames.")                     
    plt.savefig(dir_out_figs + "frac_error_frames_decode.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, count_error_frames_decode, color="C0", s=10, label="all", marker="v")
    ax.scatter(datetime_batch_start_list, count_error_frames_decode_miss, color="C1", s=10, label="miss", marker="^")
    ax.scatter(datetime_batch_start_list, count_error_frames_decode_zero, color="C2", s=10, label="zero", marker=8)
    ax.scatter(datetime_batch_start_list, count_error_frames_decode_term, color="C3", s=10, label="term", marker=9)    
    ax.legend()    
    ax.set_xlabel("start of data batch")      
    ax.set_ylabel("count error frames from decoding")
    ax.set_title("Count of error frames from decoding.")                         
    plt.savefig(dir_out_figs + "error_frames_decode_all.png")
    plt.close()        

    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(datetime_batch_start_list, (100*count_error_frames_decode)/count_in_data_info_list, color="C0", s=10, label="all", marker="v")
    ax.scatter(datetime_batch_start_list, (100*count_error_frames_decode_miss)/count_in_data_info_list, color="C1", s=10, label="miss", marker="^")
    ax.scatter(datetime_batch_start_list, (100*count_error_frames_decode_zero)/count_in_data_info_list, color="C2", s=10, label="zero", marker=8)
    ax.scatter(datetime_batch_start_list, (100*count_error_frames_decode_term)/count_in_data_info_list, color="C3", s=10, label="term", marker=9)   
    ax.legend()     
    ax.set_xlabel("start of data batch")      
    ax.set_ylabel("fraction of error frames from decoding to all input frames")
    ax.set_title("Fraction of error frames from decoding to all input frames.")                             
    plt.savefig(dir_out_figs + "frac_error_frames_decode_all.png")
    plt.close()      



    print(f"count of all in frames:                 {count_in_data_info_list.sum()}")
    print(f"count of lost frame:                    {count_in_data_info_list.sum()-count_linked_data_gps_list.sum()}")
    print(f"fraciton of lost frame:                 {100*(count_in_data_info_list.sum() - count_linked_data_gps_list.sum())/count_in_data_info_list.sum():.2f}")
    print(f"total acq time:                         {t_acq_total_data_info_list.sum():.2f} s")
    print(f"total acq time:                         {t_acq_total_data_info_list.sum()/(24.*3600.):.2f} d")    
    print(f"total live time:                        {t_duration_data_info_list.sum():.2f} s")  
    print(f"total live time:                        {t_duration_data_info_list.sum()/(24.*3600.):.2f} d")          
    print(f"mean acq time:                          {t_acq_mean_data_info_list.mean():.2f} s")
    print(f"fraciton of total acq and duration:     {100*(t_acq_total_data_info_list.sum())/t_duration_data_info_list.sum():.2f}")

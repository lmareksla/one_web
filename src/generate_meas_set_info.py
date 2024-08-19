import sys
import os
from datetime import datetime

import json

sys.path.append("src")
from dir import *



def get_directories(root_path):
    entries = os.listdir(root_path)
    directories = [entry for entry in entries if os.path.isdir(os.path.join(root_path, entry))]
    return directories


def create_json_with_settings(file_out_path_name, data):
    with open(file_out_path_name, "w") as file_json:
        json.dump(data, file_json, indent=2)


if __name__ == '__main__':

    args = sys.argv

    dir_raw = "/home/lukas/file/analysis/one_web/data/new/raw/"
    
    if len(args) > 1:
        dir_raw = args[1]    
    

    dirs_raw_data = sorted(get_directories(dir_raw))

    meas_info_name = "meas_settings.json"

    datetime_start = []
    datetime_end =  []
    settings = []

    # original
    datetime_start.append(datetime.datetime(2000, 1, 1, 0, 0, 0))
    datetime_end.append(datetime.datetime(2024, 1, 13, 0, 0, 0))
    settings.append({
        "long_acquisition_time" :       1000,
        "short_acquisition_time" :      10,
        "desired_occupancy" :           1500,
        "default_acquisition_time" :    1000,
        "max_acq_time" :                10000,
        "min_acq_time" :                10,
        "meas_mode"    :                2        
        })

    # duty cycle incerease
    datetime_start.append(datetime.datetime(2024, 1, 13, 0, 0, 0))
    datetime_end.append(datetime.datetime(2024, 4, 4, 0, 0, 0))    
    settings.append({
        "long_acquisition_time" : 1000,
        "short_acquisition_time" : 10,
        "desired_occupancy" : 1500,
        "default_acquisition_time" : 1000,
        "max_acq_time" : 25000,
        "min_acq_time" : 0.5,
        "meas_mode"    : 2
        })

    # # switch to tot toa
    # datetime_start.append(datetime.datetime(2024, 3, 9, 0, 0, 0))
    # datetime_end.append(datetime.datetime(2024, 4, 4, 0, 0, 0))     
    # settings.append({
    #     "long_acquisition_time" : 1000,
    #     "short_acquisition_time" : 10,
    #     "desired_occupancy" : 1500,
    #     "default_acquisition_time" : 1000,
    #     "max_acq_time" : 25000,
    #     "min_acq_time" : 0.5,
    #     "meas_mode"    : 2
    #     })

    # switch to 1000 occ
    datetime_start.append(datetime.datetime(2024, 4, 4, 0, 0, 0))
    datetime_end.append(datetime.datetime(2024, 4, 20, 0, 0, 0))     
    settings.append({
        "long_acquisition_time" : 1000,
        "short_acquisition_time" : 10,
        "desired_occupancy" : 1000,
        "default_acquisition_time" : 1000,
        "max_acq_time" : 25000,
        "min_acq_time" : 0.5,
        "meas_mode"    : 2        
        })

    # switch to 750 occ
    datetime_start.append(datetime.datetime(2024, 4, 20, 0, 0, 0))
    datetime_end.append(datetime.datetime(3000, 1, 1, 0, 0, 0))     
    settings.append({
        "long_acquisition_time" : 1000,
        "short_acquisition_time" : 10,
        "desired_occupancy" : 750,
        "default_acquisition_time" : 1000,
        "max_acq_time" : 25000,
        "min_acq_time" : 0.5,
        "meas_mode"    : 2        
        })

    idx_settings = 0

    for idx, dir_raw_data in enumerate(dirs_raw_data):

        start_date_str, end_date_str = dir_raw_data.split('-_')[0:2]
        start_date = datetime.datetime.strptime(start_date_str, '_%Y-%m-%d_%H_%M_%S_%f')
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d_%H_%M_%S_%f')

        while start_date > datetime_end[idx_settings]:
            idx_settings += 1

        if end_date < datetime_start[idx_settings]:
            raise RuntimeError(f"fail in the settings assigment for {idx} {dir_raw_data}")

        meas_info_path_name = os.path.join(dir_raw, dir_raw_data, meas_info_name)

        create_json_with_settings(meas_info_path_name, settings[idx_settings])

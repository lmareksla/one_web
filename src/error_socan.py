import sys
from datetime import datetime
import math

import pandas as pd
import matplotlib.pyplot as plt


sys.path.append("src")
from utils import *
from gps_spice import *
from phys import *


def evaluate_stat(data_socan):
    count_err = 0

    count_err_check_sum = 0
    count_err_frame = 0

    count_err_check_sum_or_frame = 0

    count_err_no_check_sum_and_frame = 0
    count_err_check_sum_and_no_frame = 0
    count_err_check_sum_and_frame = 0
    count_err_no_check_sum_and_no_frame = 0

    key_errors = []
    for key in data_socan.keys():
        if "Error" in key:
            key_errors.append(key)


    for idx, row in data_socan.iterrows():

        if row["Error Checksum"] == "ERROR_DETECTED":
            count_err_check_sum += 1

        if row["Error Frame"] == "ERROR_DETECTED":
            count_err_frame += 1


        if row["Error Checksum"] == "ERROR_DETECTED" or row["Error Frame"] == "ERROR_DETECTED":
            count_err_check_sum_or_frame += 1

        if not row["Error Checksum"] == "ERROR_DETECTED" and row["Error Frame"] == "ERROR_DETECTED":
            count_err_no_check_sum_and_frame += 1

        if row["Error Checksum"] == "ERROR_DETECTED" and not row["Error Frame"] == "ERROR_DETECTED":
            count_err_check_sum_and_no_frame += 1

        if row["Error Checksum"] == "ERROR_DETECTED" and row["Error Frame"] == "ERROR_DETECTED":
            count_err_check_sum_and_frame += 1

        if not row["Error Checksum"] == "ERROR_DETECTED" and not row["Error Frame"] == "ERROR_DETECTED":
            count_err_no_check_sum_and_no_frame += 1 

        for key in key_errors:
            if row[key] == "ERROR_DETECTED":
                count_err += 1
                break


    print(f"count_err                {count_err}")
    print("")
    print(f"count_err_check_sum      {count_err_check_sum}")
    print(f"count_err_frame          {count_err_frame}")    
    print("")
    print(f"count_err_check_sum_or_frame              {count_err_check_sum_or_frame}")        
    print(f"count_err_no_check_sum_and_frame          {count_err_no_check_sum_and_frame}")    
    print(f"count_err_check_sum_and_no_frame          {count_err_check_sum_and_no_frame}")    
    print(f"count_err_check_sum_and_frame             {count_err_check_sum_and_frame}")    
    print(f"count_err_no_check_sum_and_no_frame       {count_err_no_check_sum_and_no_frame}")                    

def extend_gps_wtih_longlatalt(gps_data):
    longitude_key = "longitude_deg"
    latitude_key = "latitude_deg"
    altitude_key =  "altitude_km"

    # extend data with new columns
    long_lat_alt_keys = [longitude_key, latitude_key, altitude_key]

    for key in long_lat_alt_keys:
        if key not in data_gps:
            data_gps[key] = 0.0

    # calculate lat, long and alt
    for idx, row in data_gps.iterrows():
        vec_J2000 = np.array([row["HkaNavPospropJ0 (m)"], row["HkaNavPospropJ1 (m)"], row["HkaNavPospropJ2 (m)"]])
        vec_altlonglat = transform_J2000_to_ITRF93_altlonglat(vec_J2000, row["Time"])  # spice
        # vec_altlonglat = transform_J2000_to_altlonglat_astropy(vec_J2000, row["Time"].strip())   # astropy - 4x longer calc

        data_gps.at[idx, altitude_key] = vec_altlonglat[0]
        data_gps.at[idx, longitude_key] = vec_altlonglat[1]
        data_gps.at[idx, latitude_key] = vec_altlonglat[2]    

def export_gps_data_extended(gsp_data, file_out_paht_name):
    data_gps.to_csv(file_out_paht_name, index=False)  


def link_gps_socan(data_gps, data_socan, socan_error_gps_csv_path_name):


    time_window_sec = 120

    data_socan_gps = data_socan

    longitude_key = "longitude_deg"
    latitude_key = "latitude_deg"
    altitude_key =  "altitude_km"

    # extend data with new columns
    long_lat_alt_keys = [longitude_key, latitude_key, altitude_key]

    for key in long_lat_alt_keys:
        if key not in data_socan_gps:
            data_socan_gps[key] = 0.0    

    idx_gps = 0
    prev_time_diff = -1
    time_gps =   datetime.datetime.strptime(data_gps.loc[idx_gps, "Time"].strip(), '%Y-%m-%d %H:%M:%S.%f') 
    fail_to_link = False

    for idx, row in data_socan.iterrows():

        time_socan = datetime.datetime.strptime(row["Time"].strip(), '%Y-%m-%d %H:%M:%S.%f') 

        idx_gps_orig = idx_gps
        prev_time_diff = -1

        # print(time_socan, time_gps, abs((time_socan - time_gps).total_seconds()))


        while abs((time_socan - time_gps).total_seconds()) > time_window_sec:
            # print("b", time_socan, time_gps, abs((time_socan - time_gps).total_seconds()), prev_time_diff)

            if prev_time_diff != -1 and prev_time_diff < abs((time_socan - time_gps).total_seconds()):
                # print("fail to lonk", time_socan, time_gps, abs((time_socan - time_gps).total_seconds()), prev_time_diff)
                idx_gps = idx_gps_orig
                time_gps =   datetime.datetime.strptime(data_gps.loc[idx_gps, "Time"].strip(), '%Y-%m-%d %H:%M:%S.%f') 
                prev_time_diff = -1
                fail_to_link = True
                break

            prev_time_diff = abs((time_socan - time_gps).total_seconds())
            idx_gps += 1
            time_gps =   datetime.datetime.strptime(data_gps.loc[idx_gps, "Time"].strip(), '%Y-%m-%d %H:%M:%S.%f') 

        if not fail_to_link:
            # print("done", time_socan, time_gps, abs((time_socan - time_gps).total_seconds()))
            data_socan_gps.loc[idx, longitude_key] = data_gps.loc[idx_gps, longitude_key]
            data_socan_gps.loc[idx, latitude_key] = data_gps.loc[idx_gps, latitude_key]
            data_socan_gps.loc[idx, altitude_key] = data_gps.loc[idx_gps, altitude_key]
        else:
            # print("fail to link", time_socan, time_gps, abs((time_socan - time_gps).total_seconds()))
            fail_to_link = False

        # print("------")

    data_socan_gps = data_socan_gps[(data_socan_gps[longitude_key] != 0) & (data_socan_gps[latitude_key] != 0) & (data_socan_gps[altitude_key] != 0)]
    data_socan_gps.to_csv(socan_error_gps_csv_path_name, index=False)

    return data_socan_gps

        
if __name__ == "__main__":


    do_gps_ext =    False
    do_link =       False

    socan_error_csv_path_name = "./devel/socan_error/socan_report.csv"
    gps_csv_path_name = "./devel/socan_error/gps.csv"
    gps_ext_csv_path_name = "./devel/socan_error/gps_ext.csv"
    socan_error_gps_csv_path_name = "./devel/socan_error/socan_gps_ext.csv"

    data_socan = pd.read_csv(socan_error_csv_path_name, delimiter=",")
    data_gps = pd.read_csv(gps_csv_path_name, delimiter=",")


    if do_gps_ext:
        extend_gps_wtih_longlatalt(data_gps)
        export_gps_data_extended(data_gps, gps_ext_csv_path_name)
    else:
        data_gps = pd.read_csv(gps_ext_csv_path_name, delimiter=",")

    data_socan_gps = None
    if do_link:
        data_socan_gps =  link_gps_socan(data_gps, data_socan, socan_error_gps_csv_path_name)
    else:
        data_socan_gps = pd.read_csv(socan_error_gps_csv_path_name, delimiter=",")


    data_check_sum_long = []
    data_check_sum_lat = []

    data_err_frame_long = []
    data_err_frame_lat = []


    data_err_long = []
    data_err_lat = []


    key_errors = []
    for key in data_socan.keys():
        if "Error" in key:
            key_errors.append(key)

    for idx, row in data_socan_gps.iterrows():
        if row["Error Checksum"] == "ERROR_DETECTED" and row["Error Frame"] == "ERROR_DETECTED":
            data_err_frame_long.append(row["longitude_deg"])
            data_err_frame_lat.append(row["latitude_deg"])

        if row["Error Checksum"] == "ERROR_DETECTED":
            data_check_sum_long.append(row["longitude_deg"])
            data_check_sum_lat.append(row["latitude_deg"])

        for key in key_errors:
            if row[key] == "ERROR_DETECTED":
                data_err_long.append(row["longitude_deg"])
                data_err_lat.append(row["latitude_deg"])

                break

    fig, axes = plt.subplots(2,2,figsize=(20,12))


    plot_longlatvar(data_err_frame_long, data_err_frame_lat, [1]*len(data_err_frame_lat), ax=axes[0,0], fig=fig)
    plot_longlatvar(data_check_sum_long, data_check_sum_lat, [1]*len(data_check_sum_lat), ax=axes[0,1], fig=fig)
    plot_longlatvar(data_err_long, data_err_lat, [1]*len(data_err_lat), ax=axes[1,1], fig=fig)


    plt.show()

    evaluate_stat(data_socan)
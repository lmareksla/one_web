import sys
import os
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import math
from matplotlib.colors import LogNorm
import numpy as np
import json
import copy

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *
from log import *

sys.path.append("src")

from utils import *
from gps_spice import *

class GpsFile(object):
    """docstring for GpsFile"""
    def __init__(self, file_in_path_name, log_path="", log_name="log.txt"):
        self.file_in_path_name = file_in_path_name
        
        self.data = pd.DataFrame()

        self._done_load = False            # check whether load was done and successful

        # stat
        self.frame_count = 0

        self.timestamp_first = None
        self.timestamp_last = None

        self.duration_sec = None
        self.duration_hours = None

        self.count_err_duplicities = 0     # count of duplicities in the file   
        self.count_err_time_jumps = 0      # count of time jumps in the data -> more that 5s diff   
        self.count_err_wrong_val = 0

        # log and print
        self.do_log = True
        self.do_print = True
        self.log_file_path = log_path
        self.log_file_name = log_name
        self.log_file = None

        try:
            self._open_log()
        except Exception as e:
            log_warning(f"failed to open log {os.path.join(self.log_file_path, self.log_file_name)}: {e}",
                        self.log_file, self.do_print, self.do_log)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.log_file:
            self.log_file.close()        

    def _open_log(self):
        self.log_file = open(os.path.join(self.log_file_path, self.log_file_name), "w")

    def load(self):
        log_info(f"loading file: {self.file_in_path_name}", self.log_file, self.do_print, self.do_log)

        if not self.file_in_path_name:
            raise_runtime_error(f"GpsFile.load - fail to load file: {self.file_in_path_name}.", self.log_file, self.do_print, self.do_log)

        try:
            self.data = pd.read_csv(self.file_in_path_name, sep=",")             
            self._correct_data_for_anomalies()     
            self._extend_data_with_lat_long_alt()
            self.statistics()
        except Exception as e:
            raise_runtime_error(f"GpsFile.load - fail to load data from: {self.file_in_path_name}. {e}", self.log_file, self.do_print, self.do_log)

        self._done_load = True


    """correct data for anomalies:
        * duplicities
    """
    def _correct_data_for_anomalies(self):
        if self.data.empty:
            raise_runtime_error(f"GpsFile._correct_data_for_anomalies - failed to correct for anomalies, because data is empty.",
                                self.log_file, self.do_print, self.do_log)
        try:
            row_prev = None
            idx_bad_rows = []
            for idx, row in self.data.iterrows():
                timestamp = row["TIME"]
                dt_timestamp = convert_str_timestapmp_to_datetime(timestamp)
                if row_prev is not None:
                    dt_timestamp_prev = convert_str_timestapmp_to_datetime(row_prev["TIME"])

                # duplicity
                if row_prev is not None and row_prev["TIME"] == timestamp:
                    log_error(f"{timestamp} duplicate frame info" ,self.log_file, self.do_print, self.do_log)
                    
                    self.count_err_duplicities += 1
                    idx_bad_rows.append(idx)

                # jumps in time
                if row_prev is not None and (datetime_diff_seconds(dt_timestamp,dt_timestamp_prev) > 10 or \
                   datetime_diff_seconds(dt_timestamp,dt_timestamp_prev) < 0):
                    log_error(f"{timestamp} time jump in gps info {datetime_diff_seconds(dt_timestamp,dt_timestamp_prev)} s" ,self.log_file, self.do_print, self.do_log)

                    self.count_err_time_jumps += 1

                # wrong values
                if not row["TIME"] or pd.isna(row["J2000_X (m)"]) or pd.isna(row["J2000_Y (m)"]) or pd.isna(row["J2000_Z (m)"]):
                    log_error(f"{timestamp} wrong values {row}" ,self.log_file, self.do_print, self.do_log)

                    self.count_err_wrong_val += 1
                    idx_bad_rows.append(idx)

                row_prev = row

            if idx_bad_rows:
                self.data = self.data.drop(idx_bad_rows)
                self.data = self.data.reset_index(drop=True)

        except Exception as e:
            raise_runtime_error(f"GpsFile._correct_data_for_anomalies - failed to correct for anomalies. {e}",
                                self.log_file, self.do_print, self.do_log)

    def extract_acq_time(self, frame_order_id):

        acq_time = -1

        try:
            timestamp, temperature, pix_count_short, pix_count_long, pix_count_saved, pix_count_unsaved, error_id = self.get_frame_meas_info(frame_order_id)
        except Exception as e:
            raise_runtime_error(f"Fail to extract acq time: {frame_order_id}. {e}", self.log_file, self.do_print, self.do_log)

        pixels_per_ms = float(pix_count_long - pix_count_short) / float(self.long_acquisition_time - self.short_acquisition_time)

        if pixels_per_ms > 0:
            pixels_0_ms = pix_count_long - int(pixels_per_ms * float(self.long_acquisition_time))
            desired_ms = int(float(self.desired_occupancy - pixels_0_ms) / float(pixels_per_ms))
                
            if desired_ms <= 0:
                desired_ms = self.default_acquisition_time
        else:
            desired_ms = self.default_acquisition_time

        if desired_ms > self.max_acq_time:
            desired_ms = self.max_acq_time
        elif desired_ms < self.min_acq_time:
            desired_ms = self.min_acq_time

        return desired_ms/1000.0

    """extension of data with converted J2000 into latitude longitude and altitude based on spice"""
    def _extend_data_with_lat_long_alt(self):
        if self.data.empty:
            raise_runtime_error(f"GpsFile._extend_data_with_lat_long_alt - failed because data was not loaded", self.log_file, self.do_print, self.do_log)
        
        log_info("Extending data with lat long alt",self.log_file, self.do_print, self.do_log)

 
        longitude_key = "longitude_deg"
        latitude_key = "latitude_deg"
        altitude_key =  "altitude_km"

        # extend data with new columns
        long_lat_alt_keys = [longitude_key, latitude_key, altitude_key]

        for key in long_lat_alt_keys:
            if key not in self.data:
                self.data[key] = 0.0

        # calculate lat, long and alt
        for idx, row in self.data.iterrows():
            progress_bar(len(self.data), idx)
            
            vec_J2000 = np.array([row["J2000_X (m)"], row["J2000_Y (m)"], row["J2000_Z (m)"]])
            vec_altlonglat = transform_J2000_to_ITRF93_altlonglat(vec_J2000, row["TIME"])  # spice
            # vec_altlonglat = transform_J2000_to_altlonglat_astropy(vec_J2000, row["TIME"].strip())   # astropy - 4x longer calc

            self.data.at[idx, altitude_key] = vec_altlonglat[0]
            self.data.at[idx, longitude_key] = vec_altlonglat[1]
            self.data.at[idx, latitude_key] = vec_altlonglat[2]


    def statistics(self):
        if self.data.empty:
            raise_runtime_error("statistics : No data loaded.", self.log_file, self.do_print, self.do_log)

        self.frame_count = len(self.data)
           
        self.timestamp_first = convert_str_timestapmp_to_datetime(self.data.iloc[0]["TIME"])
        self.timestamp_last = convert_str_timestapmp_to_datetime(self.data.iloc[-1]["TIME"])

        self.duration_sec = datetime_diff_seconds(self.timestamp_last,self.timestamp_first)
        self.duration_hours = self.duration_sec/3600.

    def print(self, do_print_data=True, do_full_data_print=False):
        
        msg =  "\n"
        msg += "===============================================================\n"
        msg += "DATA\n"
        msg += "\n"
        if not self.data.empty and do_print_data:
            if do_full_data_print:
                msg += f"{self.data.to_string()}\n"
            else:
                msg += f"{self.data}\n"
        msg += "\n"
        msg += "INFO\n"
        msg += "\n"
        msg += f"timestamp_first:            {self.timestamp_first}\n"
        msg += f"timestamp_last:             {self.timestamp_last}\n"
        msg += f"duration_sec:               {self.duration_sec} s\n"    
        msg += f"duration_hours:             {self.duration_hours:.2f} h\n"  
        msg += "\n"        
        msg += f"count_err_duplicities:      {self.count_err_duplicities}\n"
        msg += f"count_err_wrong_val:        {self.count_err_wrong_val}\n"        
        msg += f"count_err_time_jumps:       {self.count_err_time_jumps}\n"        
        msg += "===============================================================\n"

        log_info(msg,self.log_file, self.do_print, self.do_log)
        return msg

    def get_done_load(self):
        return self._done_load

    def export_stat(self, file_out_path_name):
        data_out = self.create_meta_data_dict()

        with open(file_out_path_name, "w") as json_file:
            json.dump(data_out, json_file, indent=4)

    def create_meta_data_dict(self):
        members_dict = {}
        
        # remove some unwanted
        keys_skip = ["log_file", "data"]

        # convert specail objects formats to standard python formats
        for key, value in self.__dict__.items():

            if key in keys_skip:
                continue

            if isinstance(value, np.int64):
                members_dict[key] = int(value)
            elif isinstance(value, datetime.datetime):
                members_dict[key] =  value.isoformat() 
            else:
                members_dict[key] = value

        return members_dict

if __name__ == '__main__':

    case = 1

    # basic test of file info 
    if case == 1:

        gps_file_path_name = "devel/data/dosimeter_gps_info.csv" 
        file_out_path_name = "./devel/export/gps_file.json"

        gps_file = GpsFile(gps_file_path_name)
        gps_file.load()
        gps_file.print(do_full_data_print = True)

        gps_file.export_stat(file_out_path_name)

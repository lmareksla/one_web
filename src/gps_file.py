import sys
import os
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import math
from matplotlib.colors import LogNorm
import numpy as np

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *
from log import *

sys.path.append("src/pxdata/src")

from utils import *

class GpsFile(object):
    """docstring for GpsFile"""
    def __init__(self, file_in_path_name, log_path="", log_name="log.txt"):
        self.file_in_path_name = file_in_path_name
        
        self.data = pd.DataFrame()

        # stat
        self.frame_count = 0

        self.timestamp_first = None
        self.timestamp_last = None

        self.duration_sec = None
        self.duration_hours = None

        self.count_err_duplicities = 0     # count of duplicities in the file   
        self.count_err_time_jumps = 0      # count of time jumps in the data -> more that 5s diff   

        # log and print
        self.do_log = True
        self.do_print = True
        self.log_file_path = log_path
        self.log_file_name = log_name
        self.log_file = None

        try:
            self._open_log()
        except Exception as e:
            log_warning(f"failed to open log {os.path.join(self.log_file_path, self.log_file_name)}: {e}")

    def __exit__(self, exc_type, exc_value, traceback):
        if self.log_file:
            self.log_file.close()        

    def _open_log(self):
        self.log_file = open(os.path.join(self.log_file_path, self.log_file_name), "w")

    def load(self):
        log_info(f"loading file: {self.file_in_path_name}", self.log_file, self.do_print, self.do_log)

        if not self.file_in_path_name:
            raise_runtime_error(f"GpsFile.load - fail to load file: {self.file_in_path_name}.")

        try:
            self.data = pd.read_csv(self.file_in_path_name, sep=",")             
            self._correct_data_for_anomalies()     
            self.statistics()
        except Exception as e:
            raise_runtime_error(f"GpsFile.load - fail to load data from: {self.file_in_path_name}. {e}")

    """correct data for anomalies:
        * duplicities
    """
    def _correct_data_for_anomalies(self):
        if self.data.empty:
            raise_runtime_error(f"GpsFile._correct_data_for_anomalies - failed to correct for anomalies, because data is empty.")
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

                row_prev = row

            if idx_bad_rows:
                self.data = self.data.drop(idx_bad_rows)
                self.data = self.data.reset_index(drop=True)

        except Exception as e:
            raise_runtime_error(f"GpsFile._correct_data_for_anomalies - failed to correct for anomalies. {e}")

    def extract_acq_time(self, frame_order_id):

        acq_time = -1

        try:
            timestamp, temperature, pix_count_short, pix_count_long, pix_count_saved, pix_count_unsaved, error_id = self.get_frame_meas_info(frame_order_id)
        except Exception as e:
            raise_runtime_error(f"Fail to extract acq time: {frame_order_id}. {e}")

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

    def get_frame_acq_time(self, frame_order_id):
        return self.data.at[frame_order_id, "time_acq_s"]

    def get_frame_meas_info(self, frame_order_id):
        if self.data.empty:
            raise_runtime_error("get_frame_meas_info : No data loaded.")

        try:
            row = self.data.iloc[frame_order_id]
        except Exception as e:
            raise_runtime_error(f"Can not find frame with given id: {frame_order_id}. {e}")

        if len(row) >= 6:
            timestamp = convert_str_timestapmp_to_datetime(row["TIME"])
            temperature = float(row.iloc[1])
            pix_count_short = int(row.iloc[2])
            pix_count_long = int(row.iloc[3])
            pix_count_saved = int(row.iloc[4])
            pix_count_unsaved = int(row.iloc[5])
            error_id = str(row.iloc[6])
        else:
            raise_runtime_error("Fail to get frame, not all info is included.")

        return [timestamp, temperature, pix_count_short, pix_count_long, pix_count_saved, pix_count_unsaved, error_id]


    def statistics(self):
        if self.data.empty:
            raise_runtime_error("statistics : No data loaded.")

        self.frame_count = len(self.data)
           
        self.timestamp_first = convert_str_timestapmp_to_datetime(self.data.iloc[0]["TIME"])
        self.timestamp_last = convert_str_timestapmp_to_datetime(self.data.iloc[-1]["TIME"])

        self.duration_sec = datetime_diff_seconds(self.timestamp_last,self.timestamp_first)
        self.duration_hours = self.duration_sec/3600.

    def print(self, do_print_data=True):
        
        msg =  "\n"
        msg += "===============================================================\n"
        msg += "DATA\n"
        msg += "\n"
        if not self.data.empty and do_print_data:
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
        msg += f"count_err_time_jumps:       {self.count_err_time_jumps}\n"        
        msg += "===============================================================\n"

        log_info(msg,self.log_file, self.do_print, self.do_log)
        return msg

if __name__ == '__main__':

    case = 1

    # basic test of file info 
    if case == 1:

        gps_file_path_name = "devel/data/dosimeter_gps_info.csv" 

        gps_file = GpsFile(gps_file_path_name)
        gps_file.load()
        gps_file.print()

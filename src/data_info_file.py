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

class DataInfoFile(object):
    """docstring for DataInfoFile"""
    def __init__(self, file_in_path_name, log_path="", log_name="log.txt"):
        self.file_in_path_name = file_in_path_name
        
        self.data = pd.DataFrame()

        self.do_remove_error_data = True   # removes all data which includes error id

        # stat
        self.frame_count = 0
        self.error_count = 0
        self.saturated_count = 0 # not error id and with unsaved pixels
        self.pix_saved_total = 0
        self.pix_unsaved_total = 0

        self.time_acq_total = 0
        self.time_acq_mean = None
        self.time_acq_std = None
        self.time_acq_min = None
        self.time_acq_max = None

        self.temperature_mean = None
        self.temperature_std = None
        self.temperature_min = None
        self.temperature_max = None

        self.timestamp_first = None
        self.timestamp_last = None

        self.duration_sec = None
        self.duration_hours = None

        self.count_err_duplicities = 0     # count of duplicities in the file   
        self.count_err_bad_temperature = 0 

        # acq time, defaults base don the settings of measurement
        self.long_acquisition_time = 1000
        self.short_acquisition_time = 10
        self.desired_occupancy = 1500
        self.default_acquisition_time = 1000
        self.max_acq_time = 10000
        self.min_acq_time = 10        

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
            raise_runtime_error(f"DataInfoFile.load - fail to load file: {self.file_in_path_name}.")

        try:
            self.data = pd.read_csv(self.file_in_path_name, sep=",") 
            if "time_acq_s" not in self.data:
                self.data["time_acq_s"] = 0.0              
            self._correct_data_for_anomalies()     
            self._add_acq_time()
            self.statistics()
        except Exception as e:
            raise_runtime_error(f"DataInfoFile.load - fail to load data from: {self.file_in_path_name}. {e}")

    """correct data for anomalies:
        * weird temperature values
        * duplicities
        * OPTIONAL - errors
    """
    def _correct_data_for_anomalies(self):
        if self.data.empty:
            raise_runtime_error(f"DataInfoFile._correct_data_for_anomalies - failed to correct for anomalies, because data is empty.")
        try:
            row_prev = None
            idx_bad_rows = []
            for idx, row in self.data.iterrows():
                timestamp = row["TIMESTAMP"]
                temperature = row["Temp"]

                # errors
                if self.do_remove_error_data and not pd.isna(row["Error_id"]):
                    log_error(f"{timestamp} error frame info",self.log_file, self.do_print, self.do_log)

                    self.error_count += 1
                    idx_bad_rows.append(idx)


                # duplicity
                elif row_prev is not None and row_prev["TIMESTAMP"] == timestamp:
                    log_error(f"{timestamp} duplicate frame info" ,self.log_file, self.do_print, self.do_log)
                    
                    self.count_err_duplicities += 1
                    idx_bad_rows.append(idx)

                # weird/bad temperature
                elif temperature < -200 or temperature > 200:
                    log_error(f"{timestamp} weird temperature: {temperature}",self.log_file, self.do_print, self.do_log)

                    self.count_err_bad_temperature += 1
                    idx_bad_rows.append(idx)  

                row_prev = row

            if idx_bad_rows:
                self.data = self.data.drop(idx_bad_rows)
                self.data = self.data.reset_index(drop=True)

        except Exception as e:
            raise_runtime_error(f"DataInfoFile._correct_data_for_anomalies - failed to correct for anomalies. {e}")

    def _add_acq_time(self):
        if self.data.empty:
            raise_runtime_error("_add_acq_time : No data loaded.")

        try:
            if "time_acq_s" not in self.data:
                self.data["time_acq_s"] = 0
            for idx, row in self.data.iterrows():
                self.data.at[idx, "time_acq_s"] = self.extract_acq_time(idx)
        except Exception as e:
            raise_runtime_error(f"_add_acq_time : failed to add acq time to data. {e}")


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
            timestamp = convert_str_timestapmp_to_datetime(row["TIMESTAMP"])
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

        self.frame_count = len(self.data)

        for idx in range(self.frame_count):
            timestamp, temperature, pix_count_short, pix_count_long, pix_count_saved, pix_count_unsaved, error_id = self.get_frame_meas_info(idx)

            if idx == 0:
                self.timestamp_first = timestamp
            if idx == self.frame_count-1:
                self.timestamp_last = timestamp

            if error_id != "nan":
                self.error_count += 1
                continue


            self.pix_saved_total += pix_count_saved
            self.pix_unsaved_total += pix_count_unsaved

            if pix_count_unsaved != 0:
                self.saturated_count += 1
        
        # use only not error data
        data_not_error = self.data[self.data["Error_id"].isna()]

        self.time_acq_total += data_not_error["time_acq_s"].sum()
        self.time_acq_mean = data_not_error["time_acq_s"].mean()
        self.time_acq_max = data_not_error["time_acq_s"].max()
        self.time_acq_std = data_not_error["time_acq_s"].std()
        self.time_acq_min = data_not_error["time_acq_s"].min()

        self.temperature_mean = data_not_error["Temp"].mean()
        self.temperature_max = data_not_error["Temp"].max()
        self.temperature_std = data_not_error["Temp"].std()
        self.temperature_min = data_not_error["Temp"].min()

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
        msg += f"frame_count:                {self.frame_count}\n"
        msg += f"saturated_count:            {self.saturated_count}\n"
        msg += f"pix_saved_total:            {self.pix_saved_total}\n"
        msg += f"pix_unsaved_total:          {self.pix_unsaved_total}\n"        
        msg += "\n"                
        msg += f"time_acq_total:             {self.time_acq_total:.2f} s\n"       
        msg += f"time_acq_mean:              {self.time_acq_mean:.2f} s\n"
        msg += f"time_acq_std:               {self.time_acq_std:.2f} s\n"
        msg += f"time_acq_min:               {self.time_acq_min:.2f} s\n"
        msg += f"time_acq_max:               {self.time_acq_max:.2f} s\n"             
        msg += "\n"                
        msg += "\n"        
        msg += f"temperature_mean:           {self.temperature_mean:.2f} deg\n"
        msg += f"temperature_std:            {self.temperature_std:.2f} deg\n"
        msg += f"temperature_min:            {self.temperature_min:.2f} deg\n"
        msg += f"temperature_max:            {self.temperature_max:.2f} deg\n"
        msg += "\n"        
        msg += f"error_count:                {self.error_count}\n"
        msg += f"count_err_duplicities:      {self.count_err_duplicities}\n"
        msg += f"count_err_bad_temperature:  {self.count_err_bad_temperature}\n"        
        msg += "===============================================================\n"

        log_info(msg,self.log_file, self.do_print, self.do_log)
        return msg

if __name__ == '__main__':

    case = 1

    # basic test of file info 
    if case == 1:

        data_info_file_path_name = "devel/data/dosimeter_measure_info.csv" 

        data_info_file = DataInfoFile(data_info_file_path_name)
        data_info_file.load()
        data_info_file.print()

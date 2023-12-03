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


class DataInfoFile(object):
    """docstring for DataInfoFile"""
    def __init__(self, file_in_path_name):
        self.file_in_path_name = file_in_path_name
        
        self.data = pd.DataFrame()

        self.frame_count = 0
        self.error_count = 0
        self.saturated_count = 0 # not error id and with unsaved pixels
        self.pix_saved_total = 0
        self.pix_unsaved_total = 0

        self.duplicite_frame_info_count = 0

        self.time_acq_total = 0

        self.temperature_mean = None
        self.temperature_std = None
        self.temperature_min = None
        self.temperature_max = None

        self.timestamp_first = None
        self.timestamp_last = None

        self.duration_sec = None
        self.duration_hours = None

    def load(self):
        if not self.file_in_path_name:
            raise_runtime_error(f"DataInfoFile.load - fail to load file: {self.file_in_path_name}.")

        try:
            self.data = pd.read_csv(self.file_in_path_name, sep=",") 
            if "acq_time" not in self.data:
                self.data["acq_time"] = 0.0              
            self.correct_for_duplicities()     
            self.statistics()
        except Exception as e:
            raise_runtime_error(f"DataInfoFileload - fail to load data from: {self.file_in_path_name}. {e}")

    def correct_for_duplicities(self):
        if self.data.empty:
            raise_runtime_error(f"DataInfoFile.correct_for_duplicities - falied to correct for dupliciteis, because data is empty.")

        try:
            row_prev = None
            for index, row in self.data.iterrows():
                if row_prev is not None and row_prev["TIMESTAMP"] == row["TIMESTAMP"]:
                    log_warning(f"Duplicite frame info: \n{row}")
                    self.duplicite_frame_info_count += 1
                    self.data = self.data.drop(index)
                row_prev = row
            self.data = self.data.reset_index(drop=True)
        except Exception as e:
            raise_runtime_error(f"DataInfoFile.correct_for_duplicities - falied to correct for dupliciteis. {e}")

    def print(self, do_print_data=True):
        
        print("===============================================================")
        print("DATA\n")
        if not self.data.empty and do_print_data:
            print(self.data)
        print("\nINFO")
        print(f"timestamp_first:            {self.timestamp_first}")
        print(f"timestamp_last:             {self.timestamp_last}")
        print(f"duration_sec:               {self.duration_sec}")    
        print(f"duration_hours:             {self.duration_hours:.2f}")                    
        print(f"frame_count:                {self.frame_count}")
        print(f"error_count:                {self.error_count}")
        print(f"duplicite_frame_info_count: {self.duplicite_frame_info_count}")
        print(f"time_acq_total:             {self.time_acq_total:.2f}")            
        print(f"saturated_count:            {self.saturated_count}")
        print(f"pix_saved_total:            {self.pix_saved_total}")
        print(f"pix_unsaved_total:          {self.pix_unsaved_total}")
        print(f"temperature_mean:           {self.temperature_mean}")
        print(f"temperature_std:            {self.temperature_std}")
        print(f"temperature_min:            {self.temperature_min}")
        print(f"temperature_max:            {self.temperature_max}")
        print("===============================================================")

    def extract_acq_time(self, frame_order_id):

        frame = []
        acq_time = -1

        long_acquisition_time = 1000
        short_acquisition_time = 10
        desired_occupancy = 1500
        default_acquisition_time = 1000
        max_acq_time = 10000
        min_acq_time = 10

        try:
            timestamp, temperature, pix_count_short, pix_count_long, pix_count_saved, pix_count_unsaved, error_id = self.get_frame_meas_info(frame_order_id)
        except Exception as e:
            raise(f"Fail to extract acq time: {frame_order_id}. {e}")

        pixels_per_ms = float(pix_count_long - pix_count_short) / float(long_acquisition_time - short_acquisition_time)

        if pixels_per_ms > 0:
            pixels_0_ms = pix_count_long - int(pixels_per_ms * float(long_acquisition_time))
            desired_ms = int(float(desired_occupancy - pixels_0_ms) / float(pixels_per_ms))
                
            if desired_ms <= 0:
                desired_ms = default_acquisition_time
        else:
            desired_ms = default_acquisition_time

        if desired_ms > max_acq_time:
            desired_ms = max_acq_time
        elif desired_ms < min_acq_time:
            desired_ms = min_acq_time

        self.data.at[frame_order_id, "acq_time"] = desired_ms/1000.0

        return desired_ms/1000.0

    def get_frame_acq_time(self, frame_order_id):
        return self.data.at[frame_order_id, "acq_time"]

    def get_frame_meas_info(self, frame_order_id):
        if self.data.empty:
            raise("get_frame_meas_info : No data loaded.")

        try:
            row = self.data.iloc[frame_order_id]
        except Exception as e:
            raise(f"Can not find frame with given id: {frame_order_id}. {e}")

        if len(row) >= 6:
            timestamp = datetime.strptime(str(row.iloc[0]), " %Y-%m-%d %H:%M:%S.%f")
            temperature = float(row.iloc[1])
            pix_count_short = int(row.iloc[2])
            pix_count_long = int(row.iloc[3])
            pix_count_saved = int(row.iloc[4])
            pix_count_unsaved = int(row.iloc[5])
            error_id = str(row.iloc[6])
        else:
            raise("Fail to get frame, not all info is included.")

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

            self.time_acq_total += self.extract_acq_time(idx)

            self.pix_saved_total += pix_count_saved
            self.pix_unsaved_total += pix_count_unsaved

            if pix_count_unsaved != 0:
                self.saturated_count += 1

        data_not_error = self.data[self.data["Error_id"].isna()]

        self.temperature_mean = data_not_error["Temp"].mean()
        self.temperature_max = data_not_error["Temp"].max()
        self.temperature_std = data_not_error["Temp"].std()
        self.temperature_min = data_not_error["Temp"].min()

        self.duration_sec = (self.timestamp_last - self.timestamp_first).total_seconds()
        self.duration_hours = self.duration_sec/3600.


if __name__ == '__main__':

    case = 1

    # basic test of file info 
    if case == 1:


        data_info_file_path_name = "/home/lukas/file/analysis/one_web/data/_2023-09-21_00_00_00_000-_2023-09-21_23_59_02_497/dosimeter_measure_info.csv" 

        data_info_file = DataInfoFile(data_info_file_path_name)
        data_info_file.load()
        data_info_file.print()

        print(data_info_file.get_frame_meas_info(100))

        data_info_file.print()
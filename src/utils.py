import os
import sys
import logging
import binascii
import csv
import datetime
import matplotlib.colors as mcolors
import numpy as np


def convert_str_timestapmp_to_datetime(timestamp_str):
    try:
        timestamp = datetime.datetime.strptime(timestamp_str.strip(), "%Y-%m-%d %H:%M:%S.%f")
        return timestamp
    except Exception as e:
        log_error(f"failed to covert |{timestamp_str}| into datetime: {e}")
        return None


def datetime_diff_seconds(datetime_1st, datetime_2nd):
    return (datetime_1st - datetime_2nd).total_seconds()        

def bytes_to_int16(byte1, byte2):
    return byte1<<8 | byte2    

def calc_portion_in_perc(count_part, count_total):
	if count_total == 0:
		return -1
	else:
		return 100.*float(count_part)/float(count_total)

def mean_non_zero(np_arr : np.ndarray):
    excluded_value = 0
    non_zero_np_arr = np_arr[np_arr != excluded_value]
    mean_value = np.mean(non_zero_np_arr)     
    return mean_value      

def std_non_zero(np_arr : np.ndarray):
    excluded_value = 0
    non_zero_np_arr = np_arr[np_arr != excluded_value]
    std_value = np.std(non_zero_np_arr)     
    return std_value 

def mean_std_non_zero(np_arr : np.ndarray):
    excluded_value = 0
    non_zero_np_arr = np_arr[np_arr != excluded_value]
    std_value = np.std(non_zero_np_arr)  
    mean_value = np.mean(non_zero_np_arr)                    
    return mean_value, std_value

def rel_std_non_zero(np_arr : np.ndarray):
    excluded_value = 0
    non_zero_np_arr = np_arr[np_arr != excluded_value]
    std_value = np.std(non_zero_np_arr)   
    mean_value = np.mean(non_zero_np_arr)                                  
    return 100.0*std_value/float(mean_value)        


def progress_bar(total, current, length=50):
    progress = current / total
    num_blocks = int(progress * length)
    bar = '[' + '#' * num_blocks + ' ' * (length - num_blocks) + ']'
    sys.stdout.write('\r' + bar + ' {:.2%}'.format(progress))
    sys.stdout.flush()


def convert_np_to_plt_hist2d(hist_np, x_edges_np, y_edges_np):

    hist_plt = hist_np.flatten().tolist()
    y_edges_plt = (y_edges_np[:-1].tolist())*(len(x_edges_np)-1)
    x_edges_plt = []
    for idx in range(len(x_edges_np)-1):
        x_edges_plt.extend([x_edges_np[idx]]*(len(y_edges_np)-1))

    return hist_plt, x_edges_plt, y_edges_plt    
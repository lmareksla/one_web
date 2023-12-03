import os
import sys
import logging
import binascii
import csv
import datetime
import matplotlib.colors as mcolors


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
		return None
	else:
		return 100.*float(count_part)/float(count_total)
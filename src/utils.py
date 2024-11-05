import os
import sys
import logging
import functools
from functools import wraps
import inspect
import warnings 
import datetime
import re
import shutil
import numpy as np
from pathlib import Path
import zipfile

import coloredlogs


msg_level_intend = ""

def log_entry_exit(func):
    """logging entry and exit of given function"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global msg_level_intend

        logger_name = os.environ.get("DPE_GUI_LOG_NAME")
        if logger_name is None:
            logger_name = "__name__"

        logger = logging.getLogger(logger_name)
        class_name = args[0].__class__.__name__ if args else None
        function_name = func.__name__
        
        func_name = {function_name}
        if class_name:
            func_name = f"{class_name}.{function_name}"

        logger.debug(f"{msg_level_intend} -> {func_name}")
        msg_out = f"{msg_level_intend} <- {func_name}"
        msg_level_intend += " "

        result = func(*args, **kwargs)

        logger.debug(msg_out)
        msg_level_intend = msg_level_intend[:-1]

        return result
    return wrapper


def check(done_attr = None):
    """ 
    Checking specific attribute of class - bool set to true
    TODO - general for any attribute and its value -> if not then not proceed
    """ 

    def wrapper(func):
        @wraps(func)
        def decorator(self, *args, **kwargs):
            done = getattr(self, done_attr, None)  # Fetch the logger attribute from the instance

            do_run_func = True
            if done is not None and not done:
                do_run_func = False

            result = None
            if do_run_func:
                result = func(self, *args, **kwargs)

            return result
        return decorator
    return wrapper    


def get_logger_default_name(log_env_tag : str = "ONE_WEB_LOGGER"):
    logger_name = os.environ.get(log_env_tag)
    return logger_name

def create_logger(  
    logger_name : str =     "log", 
    log_level : str =       "DEBUG", 
    log_path_name : str =   "log.txt", 
    log_env_tag : str =     "ONE_WEB_LOGGER"
    ):
    """
    Creates logger.
    """

    system_logger_name = get_logger_default_name(log_env_tag)
    if system_logger_name:
        return logging.getLogger(system_logger_name)

    os.environ[log_env_tag] = logger_name

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    file_handler = logging.FileHandler(log_path_name)
    file_handler.setLevel(log_level)  # Set the log level for the file handler
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)  # Set the log level for the stream handler
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    coloredlogs.install(level=log_level, logger=logger, fmt=log_format)

    return logger

def create_func_msg(msg : str, stack_level : int = 1):
    """
    creates fuction message incorrporating into the msg the name if the fuciotn and class
    stack_level - defines the level of stack unwrapped
    """

    caller_frame = inspect.stack()[stack_level]
    caller_function = caller_frame.function
    caller_class = caller_frame.frame.f_locals.get('self').__class__.__name__
    full_message = f"{caller_function}: {msg}"
    if caller_class:
        full_message = f"{caller_class}.{full_message}"
    return full_message

def raise_runtime_log(  msg : str,    
                        logger : logging.Logger):

    full_message = create_func_msg(msg, 2)
    if logger is not None:
        logger.error(full_message)
    raise RuntimeError(full_message)

def raise_type_log(  msg : str,    
                        logger : logging.Logger):

    full_message = create_func_msg(msg, 2)
    if logger is not None:
        logger.error(full_message)
    raise TypeError(full_message)

def raise_exception_log(msg : str,  
                        logger : logging.Logger):

    full_message = create_func_msg(msg, 2)
    if logger is not None:    
        logger.error(full_message)
    raise Exception(full_message)

def log_debug(  
    msg : str,    
    logger : logging.Logger
    ):

    full_message = create_func_msg(msg, 2)
    if logger is not None:    
        logger.debug(full_message)

def log_info(  
    msg : str,    
    logger : logging.Logger
    ):

    if logger is not None:    
        logger.info(msg)
    else:
        print(msg)

def log_warning(
    msg : str, 
    logger : logging.Logger
    ):

    full_message = create_func_msg(msg, 2)
    if logger is not None:    
        logger.warning(full_message)

def log_error(  
    msg : str,    
    logger : logging.Logger
    ):

    full_message = create_func_msg(msg, 2)
    if logger is not None:    
        logger.error(full_message)

def hold():
    print("holding - press anything")
    a = input()    

def to_snake_case(name : str):
    """ 
    Converts camelCase or PascalCase to snake_case
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    snake_case_name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    return snake_case_name    

def is_number(s):
    try:
        float(s)  # Try to convert the string to a float
        return True
    except ValueError:
        return False    

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

def check_list_str_in_str(list_str, str_main):
    for str_item in list_str:
        if str_item in str_main:
            return True
    return False

def replace_in_files_name(
    directory : str
    ,old_part : str
    ,new_part : str
    ):
    
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if old_part in filename:
                old_path = os.path.join(root, filename)
                new_filename = filename.replace(old_part, new_part)
                new_path = os.path.join(root, new_filename)
                os.rename(old_path, new_path)
                
        
def check_directory_exists(dir_path):
    """Check if a directory exists using pathlib."""
    directory = Path(dir_path)
    if directory.is_dir():
        return True
    else:
        return False        
    

def count_csv_lines(file_path, exclude_header=True):
    """
    Counts the number of lines in a CSV file.

    Parameters:
    - file_path (str): Path to the CSV file.
    - exclude_header (bool): If True, excludes the header row from the count.

    Returns:
    - int: The number of lines in the CSV file (excluding header if specified).
    """
    with open(file_path, 'r') as infile:
        line_count = sum(1 for _ in infile)
        
    # Subtract one if excluding the header
    if exclude_header:
        line_count -= 1
        
    return line_count
import os
import sys
import logging
import binascii
import csv
import datetime
import multiprocessing
import shutil
import json
import zipfile


def delete_file(file_path):
    # Check if the file exists
    if os.path.exists(file_path):
        try:
            # Delete the file
            os.remove(file_path)
            # print(f"File '{file_path}' deleted successfully.")
        except OSError as e:
            print(f"Error deleting file '{file_path}': {e}")
    else:
        pass
        # print(f"File '{file_path}' does not exist.")

def copy_file(source_path, destination_path):
    shutil.copy(source_path, destination_path)

"""loading directories with data"""
def load_dirs_data(dir_root_path, dir_name = "", dir_excluded=[]):
    dirs_data = []
    do_name_filter = False
    if dir_name:
        do_name_filter = True
    for root, dirs, files in os.walk(dir_root_path):
        for dir_name_curr in dirs:
            if do_name_filter and dir_name not in dir_name_curr:
                continue
            if dir_name_curr in dir_excluded:
                continue
            dir_path_name = os.path.join(root, dir_name_curr)
            dirs_data.append(dir_path_name)
    return dirs_data

def list_cont_of_dir(directory_path):
    print(os.listdir(directory_path))

def list_dirs_of_dir(path):
    with os.scandir(path) as entries:
        directories = [entry.name for entry in entries if entry.is_dir()]
    return directories

def list_files_of_dir(path, base_name):
    with os.scandir(path) as entries:
        files = [entry.name for entry in entries if entry.is_file() and base_name in entry.name]
    return files

def delete_directory(directory):
    shutil.rmtree(directory)
    
def zip_directory(directory, zip_name, do_delete_orig=False):
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(directory):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), directory))

    if do_delete_orig:
        delete_directory(directory)


def unzip_directory(zip_file, extract_to):
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(extract_to)  


def files_in_dir(directory, base_name):
    file_list = []
    for filename in os.listdir(directory):
        if base_name in filename:
            full_path = os.path.join(directory, filename)
            if os.path.isfile(full_path):
                file_list.append(full_path)
    return file_list

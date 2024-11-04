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
import threading

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *
from log import *

sys.path.append("src")

from dir import *
from utils import *
from data_file import *
from data_info_file import *
from gps_file import *
from data_linker import *
from mask import *
from clusterer import *

sys.path.append("src/pydpe/src")

from clist import *


class ProcessingManager(object):
    """
    Handling all data processing - dirs, stages etc.
    """
    
    def __init__(
        self
        ,dir_data_root : str =              "/home/lukas/file/analysis/one_web/data/new/"
        ,dir_raw_name : str =               "raw"
        ,dir_proc_name : str =              "proc"
        ,dir_proc_decode_name : str =       "00_decode"
        ,dir_proc_link_name : str =         "01_link"   
        ,dir_proc_mask_name : str =         "02_mask"
        ,dir_proc_clusterer_name : str =    "03_clusterer"    
        ,dir_proc_dpe_name : str =          "04_dpe"
        ,dir_proc_phys_name : str =         "05_phys"   
        ,dir_excluded : list =              []    
        ,roi : list =                       [[62, 192], [62, 192]]

        ,mask_fixed_pattern_path : str =    "/home/lukas/file/analysis/one_web/data/proc/mask_fixed_pattern.txt"
        ,do_multi_thread : bool =           True
        ):
        
        super(ProcessingManager, self).__init__()
                
        self.dir_data_root = dir_data_root

        self.dir_raw_name = dir_raw_name              
        self.dir_proc_name = dir_proc_name             

        self.dir_proc_decode_name = dir_proc_decode_name      
        self.dir_proc_link_name = dir_proc_link_name            
        self.dir_proc_mask_name = dir_proc_mask_name        
        self.dir_proc_clusterer_name = dir_proc_clusterer_name       
        self.dir_proc_dpe_name = dir_proc_dpe_name         
        self.dir_proc_phys_name = dir_proc_phys_name        

        self.dir_excluded = dir_excluded             

        self.dir_proc = os.path.join(self.dir_data_root, self.dir_proc_name)           
        self.dir_raw = os.path.join(self.dir_data_root, self.dir_raw_name)

        self.dirs_raw_data = []
        
        self.data_file_out_name =   "data_file.json"
        self.info_file_out_name =   "data_info_file.json"
        self.gps_file_out_name =    "gps_file.json"        
        
        self.roi = roi

        self.mask_fixed_pattern_path = mask_fixed_pattern_path
        self.mask_fixed_pattern = None
   
        self.__do_multi_thread = do_multi_thread
        self.__done_init = False
   
        
    def _run_iterative_task_multithread(
        self,
        task,
        kwarg_iters : dict,
        kwargs_static : dict = {},
        ):
        """
        kwargs_iters - "PARAM_NAME" : list, where list is used in iteration to insert one item as kwarg
        """
        
        cpu_count = multiprocessing.cpu_count()
        idx = 0
        processes = [] 
        kwarg_iters_key = list(kwarg_iters.keys())[0]
        iter_count = len(kwarg_iters[kwarg_iters_key])
             
        while idx < iter_count:
            for n in range(cpu_count):
                
                kwargs = kwargs_static
                kwargs[kwarg_iters_key] = kwarg_iters[kwarg_iters_key][idx]
                
                process = multiprocessing.Process(target=task, 
                                                  kwargs=kwargs)
                processes.append(process)
                process.start()
                idx += 1
                if idx == iter_count: 
                    break
            for process in processes:
                process.join()         
           
   
    def init(self):
        
        if not dir_data_root:
            raise RuntimeError("dir_data_root is empty")
        
        #mask fixed pattern
        if self.mask_fixed_pattern_path:
            self.mask_fixed_pattern = Mask()
            self.mask_fixed_pattern.load(self.mask_fixed_pattern_path)

        # find directories
        self.dirs_raw_data = sorted(load_dirs_data(self.dir_raw, dir_excluded=self.dir_excluded))

        self.__done_init = True

    def process(self):
        if not self.__done_init: 
            print("error - init was not done")
            return
        
        self.__decoding_and_linking()
        self.__masking()
        # rename_mask_files(dir_proc, dirs_raw_data, dir_proc_mask_name) # rename files to be correctly processed 
        # clusterization(dir_proc, dir_proc_mask_name, dir_proc_clusterer_name, do_multi_thread=False, frame_base_name="", do_zip_mask=True)    
        # dpe(dir_proc, dir_proc_clusterer_name, dir_proc_dpe_name, do_multi_thread=False, do_zip_cluster=True)        
                                              

    def __decoding_and_linking(self):
        """
        Decodes and links frames with info and gps.
        """
        
        # generate settings meas info
        dir_raw_data = os.path.dirname(self.dirs_raw_data[0])
        cmd = f"python src/generate_meas_set_info.py {dir_raw_data}"
        os.system(cmd)
            
        # create export directories
        os.makedirs(self.dir_proc, exist_ok=True) 

        if self.__do_multi_thread:
            self._run_iterative_task_multithread(task=self.__decoding_and_linking_single_dir
                                                ,kwarg_iters={"dir_raw_data" : self.dirs_raw_data})
        else:
            for dir_raw_data in self.dirs_raw_data:
                self.__decoding_and_linking_single_dir(dir_raw_data = dir_raw_data)                

    def __decoding_and_linking_single_dir(
        self
        ,dir_raw_data : str
        ):

        frames_ext = []

        dir_proc_data = os.path.join(self.dir_proc, os.path.basename(dir_raw_data))

        # create dirs
        dir_proc_decode = os.path.join(dir_proc_data, self.dir_proc_decode_name) 
        dir_proc_link = os.path.join(dir_proc_data, self.dir_proc_link_name)    
             
        os.makedirs(dir_proc_data, exist_ok=True)         
        os.makedirs(dir_proc_decode, exist_ok=True) 
        os.makedirs(dir_proc_link, exist_ok=True) 

        # load 
        gps_file =  GpsFile(os.path.join(dir_raw_data, "dosimeter_gps_info.csv"))
        data_file = DataFile(os.path.join(dir_raw_data, "dosimeter_image_packets.csv"), os.path.join(dir_raw_data, "meas_settings.json"),
                            os.path.join(dir_proc_data, ".." , "global_config.json"))
        info_file = DataInfoFile(os.path.join(dir_raw_data, "dosimeter_measure_info.csv"), os.path.join(dir_raw_data, "meas_settings.json"))                
        
        gps_file.load()
        data_file.load()
        info_file.load() 

        # export
        self.__export_file_stat_info(dir_proc_data, data_file, info_file, gps_file)
        self.__export_frames(data_file.frames, dir_proc_decode)
        self.__export_sum_frames(data_file.frames, dir_proc_decode)

        # link
        data_linker = DataLinker(file_settings_path_name=os.path.join(dir_raw_data, "meas_settings.json"))
        data_linker.load_settings()
        data_linker.link_data_info_gps(data_file, info_file, gps_file, frames_ext, do_print_info=True)
        data_linker.export(os.path.join(dir_proc_data, "data_linker.json"))     

        # export
        self.__export_frames(frames_ext, dir_proc_link)
        self.__export_sum_frames(frames_ext, dir_proc_link)


    def __export_file_stat_info(
        self 
        ,dir_proc_data : str 
        ,data_file : GpsFile 
        ,info_file : DataFile 
        ,gps_file : DataInfoFile
        ):
        """
        Export statistical files of individual data files = gps, data, info.
        """

        if gps_file.get_done_load():
            gps_file.export_stat(os.path.join(dir_proc_data, self.gps_file_out_name))
        
        if data_file.get_done_load():
            data_file.export_stat(os.path.join(dir_proc_data, self.data_file_out_name))
        
        if info_file.get_done_load():    
            info_file.export_stat(os.path.join(dir_proc_data, self.info_file_out_name))     

    def __export_frames(
        self
        ,frames : list
        ,file_out_path : str
        ,do_sparse_matrix : bool = True
        ):
        """
        Export of frames - base and extended.
        """
        for frame in frames:
            frame.export(file_out_path, file_out_path, do_sparse_matrix=do_sparse_matrix)

    def __export_sum_frames(
        self
        ,frames : list
        ,file_out_path : str
        ):
        """
        Export of sum frames - base and extended
        """

        if not len(frames):
            raise RuntimeError("export_sum_frames - frames are empty")

        matrices = {}
        modes_str = []
        delimiter = " "            

        for key, value in frames[0].matrix.items():
            matrices[key] = np.zeros((frames[0].height, frames[0].width)) 
            modes_str.append(convert_tpx3_mode_to_str(key))

        for frame in frames:
            for key, value in frame.matrix.items():
                matrices[key] += frame.matrix[key]

        idx = 0
        for key, matrix in matrices.items():
            matrix_sum_name = f"sum_{modes_str[idx]}.txt"
            np.savetxt(os.path.join(file_out_path, matrix_sum_name), matrix, fmt='%g',  delimiter=delimiter)
            idx += 1


    def __masking(self):
        """
        Masks frames with static and adaptive mask.
        """

        # create export directories
        os.makedirs(self.dir_proc, exist_ok=True) 

        # create fixed pattern mask
        if self.mask_fixed_pattern == None:
            self.mask_fixed_pattern = self.__create_fixed_pattern_mask()

        # process
        if self.__do_multi_thread:
            self._run_iterative_task_multithread(task=self.__masking_single_dir
                                                ,kwarg_iters={"dir_raw_data" : self.dirs_raw_data})
        else:
            for dir_raw_data in self.dirs_raw_data:
                self.__masking_single_dir(dir_raw_data = dir_raw_data) 


    def __create_fixed_pattern_mask(self):
        """
        Creates fixed pattern mask from all data based on count information.
        """

        matrices_tot_sum = []
        matrices_count_sum = []        

        matrices_tot_sum, matrices_count_sum = self.__load_sum_matrices_from_all_dirs()

        # create fixed pattern mask out of count matrices
        mask_fixed_pattern = Mask()
        mask_fixed_pattern.create_fixed_pattern(matrices_count_sum, roi=self.roi)
        mask_fixed_pattern.export(os.path.join(self.dir_proc, "mask_fixed_pattern.txt"))

        return mask_fixed_pattern

    def __load_sum_matrices_from_all_dirs(self):
        
        matrices_tot_sum = []
        matrices_count_sum = []        

        for dir_raw_data in self.dirs_raw_data:
            try:
                dir_proc_data = os.path.join(self.dir_proc, os.path.basename(dir_raw_data))
                dir_proc_link = os.path.join(dir_proc_data, self.dir_proc_link_name)         

                matrix_tot_sum, matrix_count_sum = self.__load_sum_matrices_from_dir(dir_proc_link)

                matrices_tot_sum.append(matrix_tot_sum)
                matrices_count_sum.append(matrix_count_sum)

            except Exception as e:
                log_warning(f"can not load sum matrixes from dir: {dir_raw_data}, {e}")

        return matrices_tot_sum, matrices_count_sum

    def __load_sum_matrices_from_dir(
        self
        ,dir_data : str
        ):
        
        matrix_tot_sum = np.loadtxt(os.path.join(dir_data, "sum_tot.txt"))  
        matrix_count_sum =np.loadtxt(os.path.join(dir_data, "sum_count.txt"))  

        return matrix_tot_sum, matrix_count_sum

    def __masking_single_dir(
        self
        ,dir_in_path : str
        ,dir_out_path : str
        ):
        """
        Applies created mask on given matrices in single directory.
        """
        
        dir_proc_data = os.path.join(self.dir_proc, os.path.basename(dir_raw_data))        
        dir_proc_link = os.path.join(dir_proc_data, self.dir_proc_link_name)         
        dir_proc_mask = os.path.join(dir_proc_data, self.dir_proc_mask_name)   

        os.makedirs(dir_proc_mask, exist_ok=True)     
        
        mask = create_mask_for_dir(dir_in_path, dir_out_path, mask_fixed_pattern)

        frames = load_frames(dir_in_path)

        for frame in frames:
            mask.apply(frame)

        self.__export_frames(frames, dir_out_path, do_sparse_matrix=False)

        dir_proc_data = os.path.dirname(dir_in_path)
        mask.export(os.path.join(dir_proc_data, "mask_adaptive.txt"))   

def create_mask_for_dir(dir_in_path, dir_out_path, mask_fixed_pattern=None):
    count_noisy_pix_fix = 0
    count_noisy_pix_adp = 0
    
    done_mask_fixed_patter = False
    if mask_fixed_pattern is not None and isinstance(mask_fixed_pattern, Mask):
        done_mask_fixed_patter = True
        count_noisy_pix_fix = mask_fixed_pattern.get_count_noisy_pix()

    matrix_tot_sum, matrix_count_sum = load_sum_matrices_from_dir(dir_in_path)

    matrix_tot_sum_orig = copy.deepcopy(matrix_tot_sum)
    matrix_count_sum_orig = copy.deepcopy(matrix_count_sum)

    mask = Mask()
    mask.set_std_differential_limit(-0.1)  # much more loose limit to only discard extreme noisy pixels, rest is done by count matrix
    mask.create(matrix_tot_sum)

    mask_count = Mask()
    mask_count.create(matrix_count_sum)
    count_noisy_pix_adp = mask_count.get_count_noisy_pix()

    if done_mask_fixed_patter: 
        mask.add(mask_fixed_pattern)
    mask.add(mask_count)

    # apply
    mask.apply(matrix_tot_sum)
    mask.apply(matrix_count_sum)

    # plot
    fig, axs = plt.subplots(2,3, figsize=(18,12))
    axs[0, 0].axis('off')
    axs[0, 0].set_xticks([])
    axs[0, 0].set_yticks([])            
    axs[0, 0].text(0.1, 0.5, f"count noisy pix fixed:   {count_noisy_pix_fix}", fontsize=12, ha='center', va='center')
    axs[0, 0].text(0.1, 0.6, f"count noisy pix adt:     {count_noisy_pix_adp}", fontsize=12, ha='center', va='center')
    axs[0, 0].text(0.1, 0.7, f"count noisy pix total:   {count_noisy_pix_fix + count_noisy_pix_adp}", fontsize=12, ha='center', va='center')
    plot_matrix(matrix_tot_sum_orig, fig=fig, ax=axs[0,1], do_log=False)
    plot_matrix(matrix_count_sum_orig, fig=fig, ax=axs[0,2], do_log=False)            
    plot_matrix(mask.matrix_noisy_pix+mask_count.matrix_noisy_pix, fig=fig, ax = axs[1,0], do_log=False, cmap="viridis")
    axs[1,0].set_title("mask of noisy pixels (val 1 = tot, val=2 count, val>2 combined)")
    plot_matrix(matrix_tot_sum, fig=fig, ax=axs[1,1], do_log=False)
    plot_matrix(matrix_count_sum, fig=fig, ax=axs[1,2], do_log=False)
    plt.tight_layout()

    dir_proc_data = os.path.dirname(dir_in_path)    
    plt.savefig(os.path.join(dir_proc_data, "mask_info.png"))
    plt.close()

    return mask

def load_frames(dir_in_path):
    frames = []

    file_names = os.listdir(dir_in_path)
    file_names = sorted(file_names)

    file_ignore_patterns = ["sum", "json", "data", "stat"]

    frame_id_prev = -1
    data_in_path_names = []

    for file_name in file_names: 
        if check_list_str_in_str(file_ignore_patterns, file_name):
            continue

        frame_id, frame_mode = get_frame_id_mode_from_file_name(file_name)

        if len(data_in_path_names) == 2:
            
            frame_ids = []
            for file_path_name in data_in_path_names:
                fr_id, _ = get_frame_id_mode_from_file_name(file_name)
                frame_ids.append(fr_id)
                
            if len(frame_ids) == 2 and frame_ids[0] == frame_ids[1]:
                data_in_name = os.path.basename(data_in_path_names[0])
                info_in_name = data_in_name[: data_in_name.find("_")] + "_info.json"
                info_in_path_name = os.path.join(dir_in_path, info_in_name)
                frame = FrameExtInfo()
                frame.load(data_in_path_names, info_in_path_name)
                frames.append(frame) 
            else:
                a = 1
            data_in_path_names.clear()

        frame_id_prev = frame_id
        data_in_path_names.append(os.path.join(dir_in_path, file_name) )

    return frames

def check_list_str_in_str(list_str, str_main):
    for str_item in list_str:
        if str_item in str_main:
            return True
    return False

def get_frame_id_mode_from_file_name(file_in_name):
    file_in_path_name_no_suffix =  file_in_name[:file_in_name.find(".")]
    frame_id_mode = file_in_path_name_no_suffix.split("_")
    
    if len(frame_id_mode) < 2:
        return None, None

    frame_id = int(frame_id_mode[0])
    frame_mode = frame_id_mode[1]

    return frame_id, frame_mode

def clusterization(dir_proc, dir_proc_mask_name, dir_proc_clusterer_name, do_multi_thread=True, frame_base_name="tot", do_zip_mask=False):

    calib_dir = "/home/lukas/file/analysis/one_web/data/cal_mat/20deg" 

    clusterer = "/home/lukas/file/sw/cpp/data_proc/preproc/clusterer/_out/clusterer"
    # clusterer = "/home/lukas/file/sw/py/one_web/bin/DPE_Linux_1.1.0_231213_5b77c235/clusterer"

    dirs_proc_data = list_dirs_of_dir(dir_proc)
    dirs_proc_data = sorted(dirs_proc_data)


    if do_multi_thread:
        cpu_count = multiprocessing.cpu_count()
        i = 0
        processes = [] 
        while i < len(dirs_proc_data):
            for n in range(cpu_count):
                dir_proc_data = os.path.join(dir_proc, os.path.basename(dirs_proc_data[i]))
                process = multiprocessing.Process(target=clusterization_dir, 
                                                  args=(dirs_proc_data[i], dir_proc_data, dir_proc_mask_name, 
                                                        dir_proc_clusterer_name, clusterer, calib_dir, frame_base_name, do_zip_mask))
                processes.append(process)
                process.start()
                i += 1
                if i == len(dirs_proc_data): 
                    break
            for process in processes:
                process.join()      
    else:
        for dir_proc_data in dirs_proc_data:
            clusterization_dir(dir_proc, dir_proc_data, dir_proc_mask_name, 
                                dir_proc_clusterer_name, clusterer, calib_dir, frame_base_name, do_zip_mask)

def clusterization_dir(dir_proc, dir_proc_data, dir_proc_mask_name, dir_proc_clusterer_name, 
                        clusterer, calib_dir, frame_base_name="tot", do_zip_mask=False):
    
    dir_proc_mask = os.path.join(dir_proc, dir_proc_data, dir_proc_mask_name)
    dir_proc_clusterer = os.path.join(dir_proc, dir_proc_data, dir_proc_clusterer_name)
    lists_base_name = "data"

    os.makedirs(dir_proc_clusterer, exist_ok=True)

    # check mask directory if it is zipped
    try:
        os.makedirs(dir_proc_mask, exist_ok=True)
        unzip_directory(dir_proc_mask + ".zip", dir_proc_mask)
    except Exception as e:
        pass

    # remove old processing directories if they exist
    delete_file(os.path.join(dir_proc_clusterer, "data.clist"))
    delete_file(os.path.join(dir_proc_clusterer, "data.advelist"))

    # use clusterer and export results into dir_proc_clusterer
    cmd = clusterer + " "
    cmd += "--advelist " + os.path.join(dir_proc_clusterer, "data") + " "
    cmd += "--clust-feat-list " + os.path.join(dir_proc_clusterer, "data") + " "
    cmd += "--stat-file " + os.path.join(dir_proc_clusterer, "stat_file.txt") + " "
    cmd += "-c " + calib_dir + " "
    cmd += dir_proc_mask

    print(f"Running clusterer for directory: {dir_proc_mask}")

    os.system(cmd)

    # change time to be time of frame 
    frame_info_files = list_files_of_dir(dir_proc_mask, "info")
    frame_info_files = sorted(frame_info_files)

    frame_ref_times = np.zeros((len(frame_info_files)))
    frame_ids = np.zeros((len(frame_info_files)))
    frame_acq_times = np.zeros((len(frame_info_files)))
    frame_longs = np.zeros((len(frame_info_files)))
    frame_lats = np.zeros((len(frame_info_files)))
    frame_alts = np.zeros((len(frame_info_files)))

    for idx, frame_info_file in enumerate(frame_info_files):
        with open(os.path.join(dir_proc_mask, frame_info_file), 'r') as file:
            data = json.load(file)
            input_format = "%Y-%m-%d %H:%M:%S.%f"
            input_datetime = datetime.datetime.strptime(data["t_ref"], input_format)
            frame_ref_times[idx] = input_datetime.timestamp()

            frame_ids[idx] = data["id"]
            frame_longs[idx] = data["gps"]["longitude_deg"]
            frame_lats[idx] = data["gps"]["latitude_deg"]
            frame_alts[idx] = data["gps"]["altitude_km"]
            frame_acq_times[idx] = data["t_acq"]

    # assign additional variables to clists and elist
    clist = load_clist_or_elist(os.path.join(dir_proc_clusterer, "data.clist"))

    clist_ref_times = np.zeros((len(clist.data)))
    clist_ids = np.zeros((len(clist.data)))
    clist_acq_times = np.zeros((len(clist.data)))
    clist_longs = np.zeros((len(clist.data)))
    clist_lats = np.zeros((len(clist.data)))
    clist_alts = np.zeros((len(clist.data)))

    idx_frame = -1
    frame_id_prev = 0

    for idx, row in clist.data.iterrows():
        if row["Flags"] != frame_id_prev:
            idx_frame += row["Flags"] - frame_id_prev
            frame_id_prev = row["Flags"]
        clist_ref_times[idx] = frame_ref_times[idx_frame]
        clist_ids[idx] = frame_ids[idx_frame]
        clist_acq_times[idx] = frame_acq_times[idx_frame]
        clist_longs[idx] = frame_longs[idx_frame]
        clist_lats[idx] = frame_lats[idx_frame]
        clist_alts[idx] = frame_alts[idx_frame]                    

    clist.data["T"] = clist_ref_times
    clist.data["Flags"] = clist_ids
    clist.data["TAcq"] = clist_acq_times
    clist.data["GpsLong"] = clist_longs
    clist.data["GpsLat"] = clist_lats
    clist.data["GpsAlt"] = clist_alts

    clist.var_keys.extend(["TAcq", "GpsLong", "GpsLat", "GpsAlt"])
    clist.var_units.extend(["s", "deg", "deg", "km"])

    clist.export(os.path.join(dir_proc_clusterer, "data_ext.clist"))

    # elist
    elist = load_clist_or_elist(os.path.join(dir_proc_clusterer, "data.advelist"))
    elist.data["T"] = clist_ref_times*1e9
    elist.data["Flags"] = clist_ids
    elist.data["TAcq"] = clist_acq_times
    elist.data["GpsLong"] = clist_longs
    elist.data["GpsLat"] = clist_lats
    elist.data["GpsAlt"] = clist_alts

    elist.var_keys.extend(["TAcq", "GpsLong", "GpsLat", "GpsAlt"])
    elist.var_units.extend(["s", "deg", "deg", "km"])

    elist.export(os.path.join(dir_proc_clusterer, "data_ext.advelist"))

    # zip masking data
    if do_zip_mask:
        delete_file(dir_proc_mask + ".zip")
        zip_directory(dir_proc_mask, dir_proc_mask + ".zip", do_delete_orig=True)

def load_clist_or_elist(file_in_path_name):
    clist = Clist(file_in_path_name)
    # clist.plot_all()
    return clist

def dpe(dir_proc, dir_proc_clusterer_name, dir_proc_dpe_name, do_multi_thread=True, do_zip_cluster=False ):

    dirs_proc_data = list_dirs_of_dir(dir_proc)
    dirs_proc_data = sorted(dirs_proc_data)

    dpe = "/home/lukas/file/analysis/one_web/bin/DPE_Linux_1.1.0_240619_cd7a7866/dpe.sh"

    if do_multi_thread:
        cpu_count = multiprocessing.cpu_count()
        i = 0
        processes = [] 
        while i < len(dirs_proc_data):
            for n in range(cpu_count):
                dir_proc_data = os.path.join(dir_proc, os.path.basename(dirs_proc_data[i]))
                process = multiprocessing.Process(target=dpe_dir, 
                                                  args=(dir_proc, dir_proc_data, dir_proc_clusterer_name, 
                                                        dir_proc_dpe_name, dpe, do_zip_cluster))
                processes.append(process)
                process.start()
                i += 1
                if i == len(dirs_proc_data): 
                    break
            for process in processes:
                process.join()      
    else:
        for dir_proc_data in dirs_proc_data:
            dpe_dir(dir_proc, dir_proc_data, dir_proc_clusterer_name, dir_proc_dpe_name, dpe, do_zip_cluster)

def dpe_dir(dir_proc, dir_proc_data, dir_proc_clusterer_name, dir_proc_dpe_name, dpe, do_zip_cluster=False):
    
    dir_proc_clusterer = os.path.join(dir_proc, dir_proc_data, dir_proc_clusterer_name)
    dir_proc_dpe = os.path.join(dir_proc, dir_proc_data, dir_proc_dpe_name)

    # remove old processing and create new one
    shutil.rmtree(dir_proc_dpe, ignore_errors=True)
    os.makedirs(dir_proc_dpe, exist_ok=True)


    # check clusterer directory is zipped -> extract
    try:
        os.makedirs(dir_proc_clusterer, exist_ok=True)
        unzip_directory(dir_proc_clusterer + ".zip", dir_proc_clusterer)
    except Exception as e:
        pass

    # get first time if proc
    elist_data = pd.read_csv(dir_proc_clusterer + "/data_ext.advelist", nrows=1,header=0,skiprows = [1],sep="\t")
    time_first = elist_data["T"][0]

    # create dpe config
    dpe_param = os.path.join(dir_proc_dpe, "dpe_param_file.txt")

    with open(dpe_param, "w") as dpe_param_file:

        dpe_param_file.write(f"file_in_path = \"..{ os.sep + dir_proc_clusterer_name + os.sep}\"\n")
        dpe_param_file.write(f"file_in_name = \"data_ext.advelist\"\n")
        dpe_param_file.write(f"file_out_path = \".{os.sep}\"\n")
        dpe_param_file.write(f"hist1d_graphics_rebin = 100\n")
        dpe_param_file.write(f"time_sampling = 540\n")
        dpe_param_file.write(f"elist_ext_out_name = \"data_ext\"\n")
        dpe_param_file.write(f"time_first = {time_first:.0f}\n")
        dpe_param_file.write(f"do_export_graphics = false\n")        

    # chdir into dpe and run then chdir back
    current_directory = os.getcwd()
    cmd = dpe + " " + dpe_param
    os.chdir(dir_proc_dpe)
    os.system(cmd)
    os.chdir(current_directory)

    # copy clist from clusterer stage and extend it with PID class
    copy_file(os.path.join(dir_proc_clusterer, "data_ext.clist"), os.path.join(dir_proc_dpe, "File", "data_ext.clist"))

    clist = Clist(os.path.join(dir_proc_dpe, "File", "data_ext.clist"))
    elist = Clist(os.path.join(dir_proc_dpe, "File", "data_ext.advelist"))
    clist.data["PIDClass"] = elist.data["PIDClass"]
    clist.var_keys.append("PIDClass")
    clist.var_units.append("-")
    clist.export(os.path.join(dir_proc_dpe, "File", "data_ext.clist"))

    # zip clusterization directory
    if do_zip_cluster:
        delete_file(dir_proc_clusterer + ".zip")
        zip_directory(dir_proc_clusterer, dir_proc_clusterer + ".zip", do_delete_orig=True)    

def rename_files(directory, old_part, new_part):
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if old_part in filename:
                old_path = os.path.join(root, filename)
                new_filename = filename.replace(old_part, new_part)
                new_path = os.path.join(root, new_filename)
                os.rename(old_path, new_path)

def rename_mask_files(dir_proc, dirs_raw_data, dir_proc_mask_name):
    for dir_raw_data in dirs_raw_data:
        dir_mask = os.path.join(dir_proc, os.path.basename(dir_raw_data), dir_proc_mask_name)

        rename_files(dir_mask, "tot", "iToT")
        rename_files(dir_mask, "count", "Count")
        rename_files(dir_mask, "toa", "ToA")


if __name__ == '__main__':
   
    case = 4

    if case == 1:

        dir_data_root =             "/home/lukas/file/analysis/one_web/data"

        dir_raw_name =              "raw"
        dir_proc_name =             "proc"

        dir_proc_decode_name =      "00_decode"
        dir_proc_link_name =        "01_link"    
        dir_proc_mask_name =        "02_mask"
        dir_proc_clusterer_name =   "03_clusterer"    
        dir_proc_dpe_name =         "04_dpe"
        dir_proc_phys_name =        "05_phys"

        dir_excluded =              [
                                        "_2023-12-05_00_01_16_797-_2023-12-05_23_59_02_097",
                                        "_2024-01-17_00_00_14_297-_2024-01-17_23_59_31_297",
                                        "_2024-01-19_02_19_36_197-_2024-01-19_23_59_58_297",
                                        "_2024-02-07_04_19_00_197-_2024-02-07_23_59_29_297",
                                        "_2024-02-24_00_00_04_297-_2024-02-24_23_59_31_297",
                                        "_2024-03-13_00_37_26_897-_2024-03-13_23_59_41_297",
                                        "_2024-03-31_00_00_23_297-_2024-03-31_23_59_58_297",
                                        "_2024-04-19_00_00_02_297-_2024-04-19_23_59_55_297",
                                        "_2023-11-12_00_01_47_497-_2023-11-12_23_58_30_596"                                   
                                    ]  

        roi = [[62, 192], [62, 192]]

        dir_proc = os.path.join(dir_data_root, dir_proc_name)
        dir_raw = os.path.join(dir_data_root, dir_raw_name)

        # find directories - 
        # to do - ? skip those which are already processed
        dirs_raw_data = sorted(load_dirs_data(dir_raw, dir_excluded=dir_excluded))

        # process
        # decoding_and_linking_dir(dirs_raw_data, dir_proc, dir_proc_decode_name, dir_proc_link_name)
        # masking(dirs_raw_data, dir_proc, dir_proc_mask_name, dir_proc_link_name, roi, do_zip_decode_link=True)
        rename_mask_files(dir_proc, dirs_raw_data, dir_proc_mask_name) # rename files to be correctly processed         
        clusterization(dir_proc, dir_proc_mask_name, dir_proc_clusterer_name, do_multi_thread=True, frame_base_name="", do_zip_mask=True)    
        dpe(dir_proc, dir_proc_clusterer_name, dir_proc_dpe_name, do_multi_thread=True, do_zip_cluster=True)

    elif case == 2:

        dir_data_root =             "/home/lukas/file/analysis/one_web/data/pile_up/"

        dir_raw_name =              "raw"
        dir_proc_name =             "proc"

        dir_proc_decode_name =      "00_decode"
        dir_proc_link_name =        "01_link"    
        dir_proc_mask_name =        "02_mask"
        dir_proc_clusterer_name =   "03_clusterer"    
        dir_proc_dpe_name =         "04_dpe"
        dir_proc_phys_name =        "05_phys"

        dir_excluded =              ["raw__2023-12-05_00_01_16_797-_2023-12-05_23_59_02_097"]

        roi = [[62, 192], [62, 192]]

        dir_proc = os.path.join(dir_data_root, dir_proc_name)           
        dir_raw = os.path.join(dir_data_root, dir_raw_name)

        # load mask fixed pattern
        mask_fixed_pattern = Mask()
        mask_fixed_pattern.load(os.path.join(dir_proc, "mask_fixed_pattern.txt"))

        # find directories - 
        # to do - ? skip those which are already processed
        dirs_raw_data = sorted(load_dirs_data(dir_raw, dir_excluded=dir_excluded))

        # process
        decoding_and_linking_dir(dirs_raw_data, dir_proc, dir_proc_decode_name, dir_proc_link_name, False)
        masking(dirs_raw_data, dir_proc, dir_proc_mask_name, dir_proc_link_name, roi, mask_fixed_pattern=mask_fixed_pattern, do_zip_decode_link=True)
        rename_mask_files(dir_proc, dirs_raw_data, dir_proc_mask_name) # rename files to be correctly processed 
        clusterization(dir_proc, dir_proc_mask_name, dir_proc_clusterer_name, do_multi_thread=False, frame_base_name="", do_zip_mask=True)    
        dpe(dir_proc, dir_proc_clusterer_name, dir_proc_dpe_name, do_multi_thread=True, do_zip_cluster=True)

    # process new data
    elif case == 3:

        dir_data_root =             "/home/lukas/file/analysis/one_web/data/new/"

        dir_raw_name =              "raw"
        dir_proc_name =             "proc"

        dir_proc_decode_name =      "00_decode"
        dir_proc_link_name =        "01_link"    
        dir_proc_mask_name =        "02_mask"
        dir_proc_clusterer_name =   "03_clusterer"    
        dir_proc_dpe_name =         "04_dpe"
        dir_proc_phys_name =        "05_phys"

        dir_excluded =              []

        roi = [[62, 192], [62, 192]]

        dir_proc = os.path.join(dir_data_root, dir_proc_name)           
        dir_raw = os.path.join(dir_data_root, dir_raw_name)

        # load mask fixed pattern
        mask_fixed_pattern = Mask()
        mask_fixed_pattern.load("/home/lukas/file/analysis/one_web/data/proc/mask_fixed_pattern.txt")

        # find directories - 
        dirs_raw_data = sorted(load_dirs_data(dir_raw, dir_excluded=dir_excluded))

        # process
        decoding_and_linking_dir(dirs_raw_data, dir_proc, dir_proc_decode_name, dir_proc_link_name, do_multi_thread=False)
        masking(dirs_raw_data, dir_proc, dir_proc_mask_name, dir_proc_link_name, roi, mask_fixed_pattern=mask_fixed_pattern, do_zip_decode_link=False, do_multi_thread=False)
        rename_mask_files(dir_proc, dirs_raw_data, dir_proc_mask_name) # rename files to be correctly processed 
        clusterization(dir_proc, dir_proc_mask_name, dir_proc_clusterer_name, do_multi_thread=False, frame_base_name="", do_zip_mask=True)    
        dpe(dir_proc, dir_proc_clusterer_name, dir_proc_dpe_name, do_multi_thread=False, do_zip_cluster=True)        
        
        
    elif case == 4:
        
        dir_data_root = "/home/lukas/file/analysis/one_web/data/new/"        
                
        proc_mgr = ProcessingManager(dir_data_root = dir_data_root)
        
        proc_mgr.init()
        proc_mgr.process()
        
                
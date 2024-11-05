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
import platform

sys.path.append("src")
from utils import *
from dir import *
from data_file import *
from data_info_file import *
from gps_file import *
from data_linker import *
from mask import *
from generate_meas_set_info import generate_meas_info
import phys_time
import phys_map
import stat_info

sys.path.append("src/pxdata/src")
from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *

sys.path.append("src/pydpe/src")
from clist import *

sys.path.append("src/noisy_pixels/src")
from noisy_pixels import plot_matrix
    
class ProcessingManager(object):
    
    class DPESystemVersions():
        WINDOWS_DIR = "bin\\DPE_Windows_1.1.0_240828_57d68abf.zip"
        LINUX_DIR = "bin/DPE_Linux_1.1.0_240828_57d68abf.zip"
        MAC_DIR = ""
        @staticmethod
        def get_system_directory():
            current_system = platform.system()
            if current_system == "Windows":
                return ProcessingManager.DPESystemVersions.WINDOWS_DIR
            elif current_system == "Linux":
                return ProcessingManager.DPESystemVersions.LINUX_DIR
            else:
                raise ValueError("Unsupported system")        
    
    """
    Handling all data processing - dirs, stages etc.
    """    
    def __init__(
        self
        ,dir_data_root : str =              "/home/lukas/file/analysis/one_web/data/new/"
        ,dir_raw_name : str =               "raw"
        ,dir_proc_name : str =              "proc"
        ,dir_phys_name : str =              "phys"   
        ,dir_stat_name : str =              "stat"                     
        ,dir_proc_decode_name : str =       "00_decode"
        ,dir_proc_link_name : str =         "01_link"   
        ,dir_proc_mask_name : str =         "02_mask"
        ,dir_proc_clusterer_name : str =    "03_clusterer"    
        ,dir_proc_dpe_name : str =          "04_dpe"
        ,dir_excluded : list =              []    
        ,gps_transform_alg : GpsTransformAlg = GpsTransformAlg.SPICE
        ,roi : list =                       [[62, 192], [62, 192]]
        ,mask_fixed_pattern_path : str =    ""
        ,calib_dir : str =                  "/home/lukas/file/analysis/one_web/data/cal_mat/20deg" 
        ,do_multi_thread : bool =           False
        ,do_use_global_id : bool =          True
        ,dpe_path : str =                   ""
        ,global_config_path : str =         None
        ,log_level : str =                  "INFO"
        ):
        
        super(ProcessingManager, self).__init__()
                
        self.dir_data_root = dir_data_root

        self.dir_raw_name = dir_raw_name              
        self.dir_proc_name = dir_proc_name             
        self.dir_phys_name = dir_phys_name
        self.dir_stat_name = dir_stat_name

        self.dir_proc_decode_name = dir_proc_decode_name      
        self.dir_proc_link_name = dir_proc_link_name            
        self.dir_proc_mask_name = dir_proc_mask_name        
        self.dir_proc_clusterer_name = dir_proc_clusterer_name       
        self.dir_proc_dpe_name = dir_proc_dpe_name         

        self.dir_excluded = dir_excluded             

        self.dir_proc = os.path.join(self.dir_data_root, self.dir_proc_name)           
        self.dir_raw = os.path.join(self.dir_data_root, self.dir_raw_name)

        self.dirs_raw_data = []
        
        self.data_file_out_name =   "data_file.json"
        self.info_file_out_name =   "data_info_file.json"
        self.gps_file_out_name =    "gps_file.json"      
        self.data_linker_file_out_name = "data_linker.json"  
        
        self.gps_transform_alg = gps_transform_alg
        
        self.roi = roi

        self.mask_fixed_pattern_path = mask_fixed_pattern_path
        self.mask_fixed_pattern = None
   
        self.calib_dir = calib_dir 
        self.clusterer = ""
   
        self.dpe_path = dpe_path
        self.dpe = ""

        self.do_zip_mask_dir = True
        self.do_zip_clusterer_dir = True
        
        self.global_config_path = global_config_path
        self.global_config_name = "global_config.json"
        
        self.__do_use_global_id = do_use_global_id
        self.__do_multi_thread = do_multi_thread
        self.__done_init = False
   
        self.logger = None
        self.log_level = log_level
        
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
        
        # logger
        self.logger = create_logger(log_level=self.log_level)
        
        # dpe and clusterer
        if len(self.dpe_path) == 0:
            self.dpe_path = self.DPESystemVersions.get_system_directory()
            self.dpe_path = os.path.abspath(self.dpe_path)
        
        if len(self.dpe_path) > 4 and ".zip" == self.dpe_path[-4:]:
            self.dpe = os.path.join(self.dpe_path[:-4], self.__dpe_bin_based_on_system())   
            self.__get_dpe_binary()  
            self.dpe_path = self.dpe_path[:-4]
        else:
            self.dpe = os.path.join(self.dpe_path, self.__dpe_bin_based_on_system())        
        
        self.clusterer = os.path.join(self.dpe_path, self.__clusterer_bin_based_on_system())
                
        if platform.system() == "Linux":
            os.system(f"chmod +x {self.clusterer}")
            os.system(f"chmod +x {self.dpe_path}/DPE")
            os.system(f"chmod +x {self.dpe_path}")
                    
        # global config and multi threading
        if self.__do_use_global_id and self.__do_multi_thread:
            log_warning("switching off the multithreading, because global from id should be used", self.logger)
            self.__do_multi_thread = False
                    
        #mask fixed pattern
        if self.mask_fixed_pattern_path:
            self.mask_fixed_pattern = Mask()
            self.mask_fixed_pattern.load(self.mask_fixed_pattern_path)

        # find directories
        self.dirs_raw_data = sorted(load_dirs_data(self.dir_raw, dir_excluded=self.dir_excluded))

        self.__done_init = True


    def __dpe_bin_based_on_system(self):
        system_name = platform.system()
        os_dpe_names = {
            "Linux": "dpe.sh", 
            "Windows": "DPE.exe",
            "Mac": "dpe.sh",
        }
        if system_name not in os_dpe_names:
            raise_runtime_log(f"operation system {system_name} not supported", self.logger)

        return os_dpe_names.get(system_name)        

    def __get_dpe_binary(self):
        if len(self.dpe_path) < 4 and not ".zip" in self.dpe_path:
            return
        
        if check_directory_exists(self.dpe_path[:-4]):
            log_debug("directory with dpe is already extracted - skipping unzip", self.logger)
            return
        
        unzip_directory(self.dpe_path, os.path.dirname(self.dpe_path))

    def __clusterer_bin_based_on_system(self):
        system_name = platform.system()
        os_clusterer_names = {
            "Linux": "clusterer", 
            "Windows": "clusterer.exe",
            "Mac": "clusterer",
        }
        if system_name not in os_clusterer_names:
            raise_runtime_log(f"operation system {system_name} not supported", self.logger)
        return os_clusterer_names.get(system_name)   

    def process(self):
        if not self.__done_init: 
            log_error("init was not done", self.logger)
            return
        
        self.__log_title("START PROCESSING")
                
        # self.__decoding_and_linking()
        # self.__masking()
        # self.__clusterization()    
        # self.__dpe()                 
        # self.__produce_phys()
        # self.__produce_stat() 
               
        try:
            self.__decoding_and_linking()
            self.__masking()
            self.__clusterization()    
            self.__dpe()                 
            self.__produce_phys()
            self.__produce_stat()   
        except Exception as e:
            log_error(f"processing failed {e}", self.logger)  
                     
        self.__log_title("END PROCESSING")
                                              
    # -----------------------------------------
    # DECODING AND LINKING
    # -----------------------------------------
    
    def __decoding_and_linking(self):
        """
        Decodes and links frames with info and gps.
        """
        
        self.__log_title("DECODING & LINKING")
        
        # create export directories
        os.makedirs(self.dir_proc, exist_ok=True)         
        
        # generate initial global config
        if self.__do_use_global_id and self.global_config_path is None:
            self.global_config_path = os.path.join(self.dir_proc, self.global_config_name)        
            with open(self.global_config_path, "w") as json_file:
                json_file.write(' {"frame_id_global_ref": 0} ')
            
        
        # generate settings meas info
        log_info("generating measurement info", self.logger)
        dir_raw_data = os.path.dirname(self.dirs_raw_data[0])
        generate_meas_info(dir_raw_data)
            
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

        log_info(f"decoding and linking of dir: {dir_raw_data}", self.logger)

        frames_ext = []
        dir_proc_data = os.path.join(self.dir_proc, os.path.basename(dir_raw_data))

        # create dirs
        dir_proc_decode = os.path.join(dir_proc_data, self.dir_proc_decode_name) 
        dir_proc_link = os.path.join(dir_proc_data, self.dir_proc_link_name)    
             
        os.makedirs(dir_proc_data, exist_ok=True)         
        os.makedirs(dir_proc_decode, exist_ok=True) 
        os.makedirs(dir_proc_link, exist_ok=True) 


        # load 
        log_info(f"loading files for directory", self.logger)
        
        gps_file =  GpsFile(os.path.join(dir_raw_data, "dosimeter_gps_info.csv"), gps_transform_alg=self.gps_transform_alg)
        data_file = DataFile(os.path.join(dir_raw_data, "dosimeter_image_packets.csv"), os.path.join(dir_raw_data, "meas_settings.json")
                             ,file_global_conf_path_name=self.global_config_path)
        info_file = DataInfoFile(os.path.join(dir_raw_data, "dosimeter_measure_info.csv"), os.path.join(dir_raw_data, "meas_settings.json"))                
        
        gps_file.load()
        data_file.load()
        info_file.load() 

        # export
        log_info(f"exporting stat files of", self.logger)                        
        
        self.__export_file_stat_info(dir_proc_data, data_file, info_file, gps_file)
        self.__export_frames(data_file.frames, dir_proc_decode)
        self.__export_sum_frames(data_file.frames, dir_proc_decode)

        # link
        log_info(f"linking of files", self.logger)        
        
        data_linker = DataLinker(file_settings_path_name=os.path.join(dir_raw_data, "meas_settings.json"))
        data_linker.load_settings()
        data_linker.link_data_info_gps(data_file, info_file, gps_file, frames_ext, do_print_info=True)
        data_linker.export(os.path.join(dir_proc_data, self.data_linker_file_out_name))     

        # export
        log_info(f"exporting frames", self.logger)                
        
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

    # -----------------------------------------
    # MASKING
    # -----------------------------------------

    def __masking(self):
        """
        Masks frames with static and adaptive mask.
        """

        self.__log_title("MASKING")

        # create export directories
        os.makedirs(self.dir_proc, exist_ok=True) 

        # create fixed pattern mask
        if self.mask_fixed_pattern == None:
            self.__create_fixed_pattern_mask()

        # process
        if self.__do_multi_thread:
            self._run_iterative_task_multithread(task=self.__masking_single_dir
                                                ,kwarg_iters={"dir_raw_data" : self.dirs_raw_data})
        else:
            for dir_raw_data in self.dirs_raw_data:
                self.__masking_single_dir(dir_raw_data = dir_raw_data) 

        # rename masked files
        self.__rename_mask_files()

    def __create_fixed_pattern_mask(self):
        """
        Creates fixed pattern mask from all data based on count information.
        """

        log_info("creating fixed pattern mask", self.logger)

        matrices_tot_sum = []
        matrices_count_sum = []        

        matrices_tot_sum, matrices_count_sum = self.__load_sum_matrices_from_all_dirs()

        # create fixed pattern mask out of count matrices
        self.mask_fixed_pattern = Mask()
        self.mask_fixed_pattern.create_fixed_pattern(matrices_count_sum, roi=self.roi)
        self.mask_fixed_pattern.export(os.path.join(self.dir_proc, "mask_fixed_pattern.txt"))

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
        ,dir_raw_data : str
        ):
        """
        Applies created mask on given matrices in single directory.
        """
                
        dir_proc_data = os.path.join(self.dir_proc, os.path.basename(dir_raw_data))        
        dir_proc_link = os.path.join(dir_proc_data, self.dir_proc_link_name)         
        dir_proc_mask = os.path.join(dir_proc_data, self.dir_proc_mask_name)   

        log_info(f"masking directory: {dir_proc_mask}", self.logger)

        os.makedirs(dir_proc_mask, exist_ok=True)     
        mask = self.__create_mask_for_dir(dir_proc_link)
        frames = self.__load_frames(dir_proc_link)
        for frame in frames:
            mask.apply(frame)

        # export 
        log_info(f"exporting frames", self.logger)

        self.__export_frames(frames, dir_proc_mask, do_sparse_matrix=False)
        dir_proc_data = os.path.dirname(dir_proc_link)
        mask.export(os.path.join(dir_proc_data, "mask_adaptive.txt"))   

    def __create_mask_for_dir(
        self
        ,dir_in_path : str
        ):

        log_info(f"creating adaptive mask", self.logger)

        matrix_tot_sum, matrix_count_sum = self.__load_sum_matrices_from_dir(dir_in_path)

        matrix_tot_sum_orig = copy.deepcopy(matrix_tot_sum)
        matrix_count_sum_orig = copy.deepcopy(matrix_count_sum)

        mask = Mask()
        mask.set_std_differential_limit(-0.1)  # much more loose limit to only discard extreme noisy pixels, rest is done by count matrix
        mask.create(matrix_tot_sum)

        mask_count = Mask()
        mask_count.create(matrix_count_sum)

        if self.mask_fixed_pattern is not None: 
            mask.add(self.mask_fixed_pattern)
        mask.add(mask_count)

        # apply
        mask.apply(matrix_tot_sum)
        mask.apply(matrix_count_sum)

        # plot
        fig, axs = plt.subplots(2,3, figsize=(18,12))
        axs[0, 0].axis('off')
        axs[0, 0].set_xticks([])
        axs[0, 0].set_yticks([])            
        axs[0, 0].text(0.1, 0.5, f"count noisy pix fixed:   {self.mask_fixed_pattern.get_count_noisy_pix()}", fontsize=12, ha='center', va='center')
        axs[0, 0].text(0.1, 0.6, f"count noisy pix adt:     {mask_count.get_count_noisy_pix()}", fontsize=12, ha='center', va='center')
        axs[0, 0].text(0.1, 0.7, f"count noisy pix total:   {self.mask_fixed_pattern.get_count_noisy_pix() + mask_count.get_count_noisy_pix()}", fontsize=12, ha='center', va='center')
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


    def __load_frames(
        self
        ,dir_in_path : str
        ):
        """
        Loads frames form directory.
        """
        frames = []

        file_names = os.listdir(dir_in_path)
        file_names = sorted(file_names)

        file_ignore_patterns = ["sum", "json", "data", "stat"]

        data_in_path_names = []

        for file_name in file_names: 
            if check_list_str_in_str(file_ignore_patterns, file_name):
                continue
            
            if len(data_in_path_names) == 2:
                
                frame_ids = []
                for file_path_name in data_in_path_names:
                    frame_id, _ = self.__get_frame_id_mode_from_file_name(file_path_name)
                    frame_ids.append(frame_id)
                    
                if len(frame_ids) == 2 and frame_ids[0] == frame_ids[1]:
                    data_in_name = os.path.basename(data_in_path_names[0])
                    info_in_name = data_in_name[: data_in_name.find("_")] + "_info.json"
                    info_in_path_name = os.path.join(dir_in_path, info_in_name)
                    frame = FrameExtInfo()
                    frame.load(data_in_path_names, info_in_path_name)
                    frames.append(frame) 
                else:
                    log_warning("incompatible two frames", self.logger)
                    
                data_in_path_names.clear()

            data_in_path_names.append(os.path.join(dir_in_path, file_name) )

        return frames

    def __get_frame_id_mode_from_file_name(
        self
        ,file_in_path_name : str
        ):
        
        file_in_name = os.path.basename(file_in_path_name)
        file_in_name_no_suffix =  os.path.splitext(file_in_name)[0] 
        frame_id_mode = file_in_name_no_suffix.split("_")
        
        if len(frame_id_mode) < 2:
            log_warning("could not found id and mode", self.logger)
            return None, None

        frame_id = int(frame_id_mode[0])
        frame_mode = frame_id_mode[1]

        return frame_id, frame_mode


    def __rename_mask_files(self):
        """
        Renames frames to match with standard of clusterer.
        """
        
        for dir_raw_data in self.dirs_raw_data:
            dir_mask = os.path.join(self.dir_proc, os.path.basename(dir_raw_data), self.dir_proc_mask_name)

            replace_in_files_name(dir_mask, "tot", "iToT")
            replace_in_files_name(dir_mask, "count", "Count")
            replace_in_files_name(dir_mask, "toa", "ToA")

    # -----------------------------------------
    # CLUSTERIZTION
    # -----------------------------------------

    def __clusterization(self):

        self.__log_title("CLUSTERIZTION")

        dirs_proc_data = list_dirs_of_dir(self.dir_proc)
        dirs_proc_data = sorted(dirs_proc_data)

        # process
        if self.__do_multi_thread:
            self._run_iterative_task_multithread(task=self.__clusterization_single_dir
                                                ,kwarg_iters={"dir_proc_data" : dirs_proc_data})
        else:
            for dir_proc_data in dirs_proc_data:
                self.__clusterization_single_dir(dir_proc_data = dir_proc_data) 

    def __clusterization_single_dir(
        self
        ,dir_proc_data : str
        ):

        dir_proc_mask = os.path.join(self.dir_proc, dir_proc_data, self.dir_proc_mask_name)
        dir_proc_clusterer = os.path.join(self.dir_proc, dir_proc_data, self.dir_proc_clusterer_name)

        log_info(f"running clusterer for directory: {dir_proc_mask}", self.logger)

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
        cmd = self.clusterer + " "
        cmd += "--advelist " + os.path.join(dir_proc_clusterer, "data") + " "
        cmd += "--clust-feat-list " + os.path.join(dir_proc_clusterer, "data") + " "
        cmd += "--stat-file " + os.path.join(dir_proc_clusterer, "stat_file.txt") + " "
        cmd += "-c " + self.calib_dir + " "
        cmd += dir_proc_mask

        os.system(cmd)

        # change time to be time of frame 
        self.__add_info_to_clist_elist(dir_proc_mask, dir_proc_clusterer)
        
        # zip masking data
        if self.do_zip_mask_dir:
            log_info(f"zipping mask file {dir_proc_mask}", self.logger)
            delete_file(dir_proc_mask + ".zip")
            zip_directory(dir_proc_mask, dir_proc_mask + ".zip", do_delete_orig=True)

    def __add_info_to_clist_elist(
        self
        ,dir_proc_mask : str
        ,dir_proc_clusterer: str
        ):

        log_info(f"adding info about gps and time into clist/elist", self.logger)

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
        clist = self.__load_clist_or_elist(os.path.join(dir_proc_clusterer, "data.clist"))

        ref_times = np.zeros((len(clist.data)))
        ids = np.zeros((len(clist.data)))
        acq_times = np.zeros((len(clist.data)))
        longs = np.zeros((len(clist.data)))
        lats = np.zeros((len(clist.data)))
        alts = np.zeros((len(clist.data)))

        idx_frame = -1
        frame_id_prev = 0
        for idx, row in clist.data.iterrows():
            if row["Flags"] != frame_id_prev:
                idx_frame += row["Flags"] - frame_id_prev
                frame_id_prev = row["Flags"]
            ref_times[idx] = frame_ref_times[idx_frame]
            ids[idx] = frame_ids[idx_frame]
            acq_times[idx] = frame_acq_times[idx_frame]
            longs[idx] = frame_longs[idx_frame]
            lats[idx] = frame_lats[idx_frame]
            alts[idx] = frame_alts[idx_frame]                    

        clist.data["T"] = ref_times
        clist.data["Flags"] = ids
        clist.data["TAcq"] = acq_times
        clist.data["GpsLong"] = longs
        clist.data["GpsLat"] = lats
        clist.data["GpsAlt"] = alts

        clist.var_keys.extend(["TAcq", "GpsLong", "GpsLat", "GpsAlt"])
        clist.var_units.extend(["s", "deg", "deg", "km"])

        clist.export(os.path.join(dir_proc_clusterer, "data_ext.clist"))

        # elist
        elist = self.__load_clist_or_elist(os.path.join(dir_proc_clusterer, "data.advelist"))
        elist.data["T"] = ref_times*1e9
        elist.data["Flags"] = ids
        elist.data["TAcq"] = acq_times
        elist.data["GpsLong"] = longs
        elist.data["GpsLat"] = lats
        elist.data["GpsAlt"] = alts

        elist.var_keys.extend(["TAcq", "GpsLong", "GpsLat", "GpsAlt"])
        elist.var_units.extend(["s", "deg", "deg", "km"])

        elist.export(os.path.join(dir_proc_clusterer, "data_ext.advelist"))  

    def __load_clist_or_elist(
        self, 
        file_in_path_name : str
        ):
        clist = Clist(file_in_path_name)
        return clist

    # -----------------------------------------
    # DPE
    # -----------------------------------------

    def __dpe(self):
        
        self.__log_title("DPE")
        
        dirs_proc_data = list_dirs_of_dir(self.dir_proc)
        dirs_proc_data = sorted(dirs_proc_data)

        # process
        if self.__do_multi_thread:
            self._run_iterative_task_multithread(task=self.__dpe_single_dir
                                                ,kwarg_iters={"dir_proc_data" : dirs_proc_data})
        else:
            for dir_proc_data in dirs_proc_data:
                self.__dpe_single_dir(dir_proc_data = dir_proc_data) 

    def __dpe_single_dir(
        self
        ,dir_proc_data : str
        ):
        
        dir_proc_clusterer = os.path.join(self.dir_proc, dir_proc_data, self.dir_proc_clusterer_name)
        dir_proc_dpe = os.path.join(self.dir_proc, dir_proc_data, self.dir_proc_dpe_name)

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

            dpe_param_file.write(f"file_in_path = \"..{ os.sep + self.dir_proc_clusterer_name + os.sep}\"\n")
            dpe_param_file.write(f"file_in_name = \"data_ext.advelist\"\n")
            dpe_param_file.write(f"file_out_path = \".{os.sep}\"\n")
            dpe_param_file.write(f"hist1d_graphics_rebin = 100\n")
            dpe_param_file.write(f"time_sampling = 540\n")
            dpe_param_file.write(f"elist_ext_out_name = \"data_ext\"\n")
            dpe_param_file.write(f"time_first = {time_first:.0f}\n")
            dpe_param_file.write(f"do_export_graphics = false\n")        

        # chdir into dpe and run then chdir back
        current_directory = os.getcwd()
        cmd = self.dpe + " " + dpe_param
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
        if self.do_zip_clusterer_dir:
            delete_file(dir_proc_clusterer + ".zip")
            zip_directory(dir_proc_clusterer, dir_proc_clusterer + ".zip", do_delete_orig=True)    
            
    def __produce_phys(self):
        """
        Produces physics results:
         * maps
         * time plots
         * frame list
        """
        
        self.__log_title("PRODUCING PHYS")
        
        dir_phys = os.path.join(self.dir_data_root, self.dir_phys_name)
        dir_data_proc = os.path.join(self.dir_data_root, self.dir_proc_name)
        
        phys_map.create_phys_map(
            dir_data_proc=          dir_data_proc
            ,dir_phys =             dir_phys
            ,dir_proc_dpe_name =    self.dir_proc_dpe_name   
            ,roi =                  self.roi
            ,bins =                 [180,90]    
            ,ranges =               [[-180,180],[-90,90]]     
            )
        
        kwargs = {  "dir_data_proc" :         dir_data_proc
                    ,"dir_phys" :             dir_phys   
                    ,"dir_proc_dpe_name" :    self.dir_proc_dpe_name    
                    ,"roi" :                  self.roi
                    ,"time_samplings_hours" : [0.2]#[0.2,0.5, 1, 2, 4, 8, 12, 24] 
                }
        
        phys_time.create_phys_time(
            **kwargs
            ,month =                ""   
            )

    def __produce_stat(self):
        """
        Produces statistical information.
        """
        
        self.__log_title("PRODUCING STAT")
        
        dir_stat = os.path.join(self.dir_data_root, self.dir_stat_name)
        dir_data_proc = os.path.join(self.dir_data_root, self.dir_proc_name)              
        
        stat_info.create_stat_info(
             dir_proc=              dir_data_proc
            ,dir_out=               dir_stat
            ,data_file_json_name=   self.data_file_out_name
            ,info_file_json_name=   self.info_file_out_name
            ,gps_file_json_name=    self.gps_file_out_name
            ,data_linker_json_name= self.data_linker_file_out_name
            ,stat_info_file_name=   "stat.txt"
            )


    def __log_title(
        self
        ,msg : str
        ):
        msg_print = " ---=== " + msg + " ===---"
        log_info(msg_print, self.logger)


if __name__ == '__main__':
       
    args = sys.argv       
         
    dir_data_root = "/home/lukas/file/analysis/one_web/data/new/"    
    calib_dir =   "/home/lukas/file/analysis/one_web/data/cal_mat/20deg" 
    
    if len(args) > 2:
        dir_data_root = args[1] 
        calib_dir = args[2] 

    proc_mgr = ProcessingManager(dir_data_root = dir_data_root
                                 ,calib_dir = calib_dir)
    
    proc_mgr.init()
    proc_mgr.process()
        
                    
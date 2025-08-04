import os
import sys
import logging
import binascii
import csv
import datetime
import matplotlib.colors as mcolors
import copy

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *

sys.path.append("src")

from data_file import *
from gps_file import *
from data_info_file import *
from gps_spice import *
from utils import *

# links data file, data info file and gps file based on the time
class DataLinker(object):
    """docstring for DataLinker"""
    def __init__(
        self
        ,file_settings_path_name=""
        ):
        
        super(DataLinker, self).__init__()
        
        self.file_settings_path_name = file_settings_path_name

        # linker - data + info
        self.time_window_data_info_s = 4             # time window for linking data and info in seconds 
        self.t_acq_max = 10                          # seconds, maximum acq time used for estimation of missing data info 
        self.count_max_hit_pixels = 1500             # maximal count of hit pixels
        self.miss_info_param = 0.5                   # if frame is missing info, try to estimate its time based on hit pixels (see below)

        # linker - data + gps
        self.time_window_data_gps_s = 10              # time window for linking data and gps in seconds 

        # stat
        self.count_in_data_info = 0        
        self.count_linked_data_info = 0
        self.count_no_link_data_info = 0
        self.count_multi_linked_data_info = 0
        self.count_single_linked_data_info = 0
        self.count_t_acq_estim_data_info = 0

        self.count_in_data_gps = 0
        self.count_linked_data_gps = 0
        self.count_no_link_data_gps = 0
        self.count_multi_linked_data_gps = 0
        self.count_single_linked_data_gps = 0

        # log and print
        self.logger = create_logger()

    def load_settings(self):
        if not self.file_settings_path_name:
            return

        try:
            with open(self.file_settings_path_name, "r") as file_json:
                meas_set_data = json.load(file_json)

                # desired_occupancyis in this case in pixels
                self.count_max_hit_pixels = meas_set_data["desired_occupancy"]
                # max_acq_time is in tis case in miliseconds
                self.t_acq_max = meas_set_data["max_acq_time"]*0.001 

        except Exception as e:
            print(f"Can not load meas settings. Using default.")



    def link_data_info_gps(self, data_file : DataFile, info_file : DataInfoFile, gps_file : GpsFile, 
                            frames_ext : list, do_print_info=False):

        # it has to be in this order, because gps link is assuming already existing frames
        self._link_data_and_info(data_file, info_file, frames_ext, do_print_info=do_print_info)
        self._link_data_and_gps(data_file, gps_file, frames_ext, do_print_info=do_print_info)


    def _link_data_and_info(self, data_file : DataFile, info_file : DataInfoFile, frames_ext : list, do_print_info=False):
        """
        Links data file and data info file and fills final frames into.
        Frames ext given by user.
        """
        
        if data_file is None or info_file is None:
            raise_runtime_log(f"none data {data_file} or info  {info_file}", self.logger)
        if not data_file.get_done_load() or not info_file.get_done_load():
            raise_runtime_log(f"no loaded data {data_file.get_done_load()} or info {info_file.get_done_load()}", self.logger)

        try:
            frames_failed_link = []
            info_idx = 0
            info_data_size = len(info_file.data)
            info_row = None
            timestamp_info = None
            timestamp_frame = None
            self.count_in_data_info = len(data_file.frames)

            for frame_idx, frame in enumerate(data_file.frames):
                timestamp_frame = frame.t_ref 
                done_link = False
                count_links = 0

                while info_idx < info_data_size:
            
                    info_row = info_file.data.iloc[info_idx]
                    if info_row is not None:
                        timestamp_info = convert_str_timestapmp_to_datetime(info_row["TIMESTAMP"])

                    if abs(datetime_diff_seconds(timestamp_frame, timestamp_info)) < self.time_window_data_info_s:
                        done_link = True
                        count_links += 1

                        self._add_ext_frame_with_info(frame, info_row, frames_ext)

                    # if time diff is negative then it can be ended and new frame tested with current info
                    # estimation of acq time is tried before frame is marked as unlinked
                    elif datetime_diff_seconds(timestamp_frame, timestamp_info) < 0:
                        if not done_link:
                            t_acq_estimation = self._acq_time_estimation_for_missing_info(frame)
                            if t_acq_estimation != 0:
                                frame.t_acq = float(t_acq_estimation)
                                self._add_ext_frame_with_info(frame, None, frames_ext)
                                self.count_t_acq_estim_data_info += 1
                                count_links += 1
                            else:
                                frames_failed_link.append(frame)
                        break

                    info_idx += 1

                self._eval_frame_stat_of_data_info_link(count_links)

            if do_print_info:
                title = "link of data and info"
                self._print_frame_link_info(title, frames_ext, frames_failed_link, self.count_in_data_info, self.count_linked_data_info,
                                            self.count_no_link_data_info, self. count_single_linked_data_info, self.count_multi_linked_data_info)

            # self._eval_failed_frames(frames_failed_link)

        except Exception as e:
            raise_runtime_log(f"DataLinker.link_data_and_info - failed to link data and info: {e}",
                                self.logger)

    def _add_ext_frame_with_info(self, frame, info, frames_ext):
        frame_ext = FrameExtInfo(frame.mode)
        frame_ext.copy_frame_values(frame)
        frame_ext.raw_info = info
        if info is not None:
            frame_ext.t_acq = info["time_acq_s"]

        frames_ext.append(frame_ext)

    """
    tries to estimate the frame acq from its hit pixels with respect to maximum
    if it can not be estimated, then 0 is returned
    """
    def _acq_time_estimation_for_missing_info(self, frame):
        if frame is None:
            return 0

        count_hit_pixels = frame.get_count_hit_pixels()

        if count_hit_pixels < self.count_max_hit_pixels*self.miss_info_param: 
            return self.t_acq_max
        else:
            return 0


    def _eval_frame_stat_of_data_info_link(self, count_links):
        if count_links == 0:
            self.count_no_link_data_info += 1
        else:
            self.count_linked_data_info += 1
            if count_links == 1:
                self.count_single_linked_data_info += 1
            else:
                self.count_multi_linked_data_info += 1


    def _eval_failed_frames(self, frames_failed_link):

        counts_hit_pixels = np.zeros((len(frames_failed_link)))

        for idx, frame in enumerate(frames_failed_link):
            count_hit_pixels = frame.get_count_hit_pixels()
            counts_hit_pixels[idx] = count_hit_pixels
            print(f"count_hit_pixels of {frame.id}\t{count_hit_pixels}")

        print("           ")
        print(f"mean value of hit pixels  {counts_hit_pixels.mean()}")
        print(f"std value of hit pixels  {counts_hit_pixels.std()}")
        print(f"min value of hit pixels  {counts_hit_pixels.min()}")
        print(f"max value of hit pixels  {counts_hit_pixels.max()}")

    def _link_data_and_gps(self, data_file : DataFile, gps_file : GpsFile, frames_ext : list, do_print_info : bool =False):
        """
        links data file and gps info file and fills final frames into 
        frames ext given by user
        """

        if data_file is None or gps_file is None:
            raise_runtime_log(f"none data {data_file} or gps  {gps_file}", self.logger)
        if not data_file.get_done_load() or not gps_file.get_done_load():
            raise_runtime_log(f"not loaded data {data_file.get_done_load()} or gps {gps_file.get_done_load()}", self.logger)

        try:
            frames_failed_link = []
            frame_idx_to_remove = []
            gps_idx = 0
            gps_data_size = len(gps_file.data)
            gps_row = None
            timestamp_gps = None
            timestamp_frame = None
            self.count_in_data_gps = len(frames_ext)

            for frame_idx, frame_ext in enumerate(frames_ext):
                
                timestamp_frame = frame_ext.t_ref 
                done_link = False
                count_links = 0
                gps_possible_link_data = []               # gps data of possible links which has to be resolved based on some algorithms 

                while gps_idx < gps_data_size:
            
                    gps_row = gps_file.data.iloc[gps_idx]
                    if gps_row is not None:
                        timestamp_gps = convert_str_timestapmp_to_datetime(gps_row["TIME"])

                    if abs(datetime_diff_seconds(timestamp_frame, timestamp_gps)) < self.time_window_data_gps_s:
                        done_link = True

                        # if do_print_info:
                        #     self._print_frame_link(frame_ext, timestamp_frame, timestamp_gps)

                        gps_possible_link_data.append(gps_row)

                    # if time is bigger diff is negative then it can be ended and new frame tested with current gps
                    elif datetime_diff_seconds(timestamp_frame, timestamp_gps) < 0:
                        break

                    gps_idx += 1

                # match of frames with gps info for more than one link
                count_links = self._match_frame_with_gps_info(frames_ext[frame_idx], gps_possible_link_data)
                if count_links == 0:
                    frames_failed_link.append(frame_ext)
                    frame_idx_to_remove.append(frame_idx)

                self._eval_frame_stat_of_data_gps_link(count_links)

            # remove unlinked frames
            for idx in reversed(frame_idx_to_remove):
                frames_ext.pop(idx)           

            if do_print_info:
                title = "link of data and gps"
                self._print_frame_link_info(title, frames_ext, frames_failed_link, self.count_in_data_gps, self.count_linked_data_gps,
                                            self.count_no_link_data_gps, self. count_single_linked_data_gps, self.count_multi_linked_data_gps)

        except Exception as e:
            raise_runtime_log(f"DataLinker.link_data_and_gps - failed to link data and gps: {e}",
                                self.logger)

    """
    matching of frame and gps info links based on their count
    it should be done on several links and use func _match_frame_with_gps_with_time_weighting
    """
    def _match_frame_with_gps_info(self, frame_ext, gps_possible_link_data):

        if frame_ext is None:
            log_error(f"DataLinker._match_frame_with_gps_info - failed to match links with data because frame is None.", self.logger)
            return 0
        
        count_links = len(gps_possible_link_data)

        if count_links == 0:
            return 0
        elif count_links == 1:
            gps_timestamp = gps_possible_link_data[0]["TIME"]
            log_debug(f"match of frame {frame_ext.t_ref} with gps taken from one link {gps_timestamp}", self.logger)
            self._assing_gps_info_to_frame(frame_ext, gps_possible_link_data[0])
            return 1
        else:
            try:
                self._match_frame_with_gps_with_time_weighting(frame_ext, gps_possible_link_data)
            except Exception as e:
                log_debug(f"error - DataLinker._match_frame_with_gps_info - failed to math multiple links. Assigning 1st one. Exp: {e}",
                            self.logger)
                self._assing_gps_info_to_frame(frame_ext, gps_possible_link_data[0])
            count_links = 1
        
        return count_links

    def _assing_gps_info_to_frame(self, frame_ext, gps_data):
        if frame_ext is None:
            return

        if isinstance(gps_data, pd.DataFrame) or isinstance(gps_data, pd.Series):
            frame_ext.gps = gps_data
        # elif isinstance(gps_data, list):
        #     frame_ext.gps = gps_data
        else:
            raise_runtime_log(f"DataLinker._assing_gps_info_to_frame - can not gps info to frame because it is {type(gps_data)}", 
                        self.logger)

    """matching frame with gps links based on time weighting"""
    def _match_frame_with_gps_with_time_weighting(self, frame_ext, gps_data):

        t_diffs = np.zeros((len(gps_data))) # time differences between gps infos and frame 

        for idx, gps_info in enumerate(gps_data):
            gps_timestamp = convert_str_timestapmp_to_datetime(gps_info["TIME"])
            t_diffs[idx] = abs(datetime_diff_seconds(frame_ext.t_ref, gps_timestamp))

        weights = (1./t_diffs) / (1./t_diffs).sum()
        
        gps_info_final = copy.deepcopy(gps_data[0])
        gps_info_final["TIME"] = frame_ext.t_ref
        gps_info_final["longitude_deg"] = 0
        gps_info_final["latitude_deg"] = 0
        gps_info_final["altitude_km"] = 0

        for idx_gps, gps_info in enumerate(gps_data):
            weight = weights[idx_gps]
            for key, val in gps_info.items():  
                # skip first time info, starts from 1
                if key == "TIME":
                    continue
                else:
                    gps_info_final[key] += val*weight

        frame_ext.gps = gps_info_final
        

    def _eval_frame_stat_of_data_gps_link(self, count_links):
        if count_links == 0:
            self.count_no_link_data_gps += 1
        else:
            self.count_linked_data_gps += 1
            if count_links == 1:
                self.count_single_linked_data_gps += 1
            else:
                self.count_multi_linked_data_gps += 1

    def _print_frame_link(self, frame, timestamp_frame, timestamp_ref):
        msg =  "\n"
        msg += "---------------------------\n"
        msg += f"frame id:           {frame.id}\n"                    
        msg += f"timestamp frame:    {timestamp_frame}\n"
        msg += f"timestamp_ref info:     {timestamp_ref}\n"        
        log_info(msg, self.logger)

    def _print_frame_link_info(self, title, frames : list, frames_failed_link, count_in_frame, count_linked_frames, count_no_linked_frames, 
                                count_single_linked_frames, count_multi_linked_frames, do_print_frames=False):
        
        msg =   "\n"
        msg += f"{title}\n"
        msg += "\n"
        msg += f"count_in_frame:                {count_in_frame}\n"
        msg += f"count_linked_frames:           {count_linked_frames}\t[{calc_portion_in_perc(count_linked_frames, count_in_frame):.2f}%]\n"
        msg += f"count_no_linked_frames:        {count_no_linked_frames}\n"
        msg += f"count_single_linked_frames:    {count_single_linked_frames}\n"   
        msg += f"count_multi_linked_frames:     {count_multi_linked_frames}\n"                     
        # msg += "\n"
        # msg += "frames without link\n"
        # for frame in frames_failed_link:
        #     msg += f"\t{frame.t_ref}\t{frame.id}\t{frame.get_count_hit_pixels()}\n"
        msg += "\n"

        if do_print_frames:
            msg += f"final extended frames\n"
            for frame_ext in frames:
                addon = str(frame_ext.raw_info) if frame_ext.raw_info is not None else ""
                addon += " " + str(frame_ext.gps) if frame_ext.gps is not None else ""

                msg += f"\t{frame_ext.t_ref}\t{frame_ext.id}\t{frame_ext.get_count_hit_pixels()}\t{frame_ext.t_acq}\t{addon}\n"

        log_info(msg, self.logger)

    def log_stat(self):
        msg = "\n"

        msg += f"count_in_data_info:                {self.count_in_data_info}\n"
        msg += f"count_linked_data_info:            {self.count_linked_data_info}\t[{calc_portion_in_perc(self.count_linked_data_info, self.count_in_data_info):.2f}%]\n"
        msg += f"count_no_link_data_info:           {self.count_no_link_data_info}\n"
        msg += f"count_multi_linked_data_info:      {self.count_multi_linked_data_info}\n"   
        msg += f"count_single_linked_data_info:     {self.count_single_linked_data_info}\n" 
        msg += f"count_t_acq_estim_data_info:       {self.count_t_acq_estim_data_info}\n"         
        msg +=  "\n"
        msg += f"count_in_data_gps:                 {self.count_in_data_gps}\n"
        msg += f"count_linked_data_gps:             {self.count_linked_data_gps}\t[{calc_portion_in_perc(self.count_linked_data_gps, self.count_in_data_gps):.2f}%]\n"
        msg += f"count_no_link_data_gps:            {self.count_no_link_data_gps}\n"
        msg += f"count_multi_linked_data_gps:       {self.count_multi_linked_data_gps}\n"   
        msg += f"count_single_linked_data_gps:      {self.count_single_linked_data_gps}\n" 

        log_info(msg, self.logger)

        return msg


    def export(self, file_out_path_name):
        data_out = self.create_meta_data_dict()

        with open(file_out_path_name, "w") as json_file:
            json.dump(data_out, json_file, indent=4)

    def create_meta_data_dict(self):
        members_dict = self.__dict__

        # add not included
        

        # remove some unwanted
        members_dict.pop("logger")

        # convert special objects formats to standard python formats
        for key, value in members_dict.items():
            if isinstance(value, np.int64):
                members_dict[key] = int(value)
            if isinstance(value, datetime.datetime):
                members_dict[key] =  value.isoformat()  

        return members_dict

if __name__ == '__main__':
    
    case = 4

    # first implementation without 
    if case == 1:
        
        dir_data = "./devel/data/"
        # dir_data = "/home/lukas/file/analysis/one_web/data/raw/_2023-11-14_00_00_30_897-_2023-11-19_23_59_34_597/"

        gps_file = GpsFile(dir_data + "dosimeter_gps_info.csv")
        data_file = DataFile(dir_data + "dosimeter_image_packets.csv")
        info_file = DataInfoFile(dir_data + "dosimeter_measure_info.csv")        

        gps_file.load()
        data_file.load()
        info_file.load()

        frames_ext = []

        # link with data info


        # link with gps data
        gps_idx = 0
        gps_data_size = len(gps_file.data)
        gps_row = None
        timestamp_gps = None
        timestamp_frame = None

        timestamp_window_s = 5
        count_good_link = 0
        frames_failed_link = []
        frame_idx_to_remove = []

        for frame_idx, frame_ext in enumerate(frames_ext):
            
            print("================================")


            timestamp_frame = frame_ext.t_ref 
            done_link = False

            while gps_idx < gps_data_size:
        
                gps_row = gps_file.data.iloc[gps_idx]
                if gps_row is not None:
                    timestamp_gps = convert_str_timestapmp_to_datetime(gps_row["TIME"])

                if abs(datetime_diff_seconds(timestamp_frame, timestamp_gps)) < timestamp_window_s:
                    done_link = True
                    print("---------------------------")
                    print(f"frame idx:          {frame_idx}")                                        
                    print(f"frame id:           {frame_ext.id}")                    
                    print(f"timestamp frame:    {timestamp_frame}")
                    print(f"timestamp gps:      {timestamp_gps}")
                    count_good_link += 1

                    frame_ext.gps = gps_row.tolist()

                elif datetime_diff_seconds(timestamp_frame, timestamp_gps) < 0:
                    if not done_link:
                        frames_failed_link.append(frame_ext)
                        frame_idx_to_remove.append(frame_idx)
                    break

                gps_idx += 1

        for idx in reversed(frame_idx_to_remove):
            frames_ext.pop(idx)                

        print(f"==================================")
        print(f"final info:")
        print(f"count of frames:       {len(data_file.frames)}")
        print(f"count of good links:   {count_good_link}")
        print(f"count of no links:     {len(frames_failed_link)}")
        print("")
        print("frames without link")
        for frame in frames_failed_link:
            print(f"\t{frame.t_ref}\t{frame.id}\t{frame.get_count_hit_pixels()}")

        print(f"==================================")
        print(f"extended frames after gps file")
        for frame_ext in frames_ext:
            print(f"\t{frame_ext.t_ref}\t{frame_ext.id}\t{frame_ext.get_count_hit_pixels()}\t{frame_ext.t_acq}\t{frame_ext.gps}")

    # basic test of class implementation
    if case == 2:

        dir_data = "./devel/data//"
        file_out_path_name = "./devel/export/data_linker.json"

        gps_file =  GpsFile(dir_data + "dosimeter_gps_info.csv")
        data_file = DataFile(dir_data + "dosimeter_image_packets.csv")
        info_file = DataInfoFile(dir_data + "dosimeter_measure_info.csv")                

        gps_file.load()
        data_file.load()
        info_file.load()

        frames_ext = []

        data_linker = DataLinker()
        data_linker.link_data_info_gps(data_file, info_file, gps_file, frames_ext, do_print_info=True)

        for frame_ext in frames_ext:
            print(frame_ext.gps)

        # export file
        data_linker.export(file_out_path_name) 

    # basic test of run over bigger data set
    if case == 3:

        def load_dirs_data(dir_root_path, data_mask=None):
            dirs_data = []
            for root, dirs, files in os.walk(dir_root_path):
                for dir_name in dirs:
                    dir_path_name = os.path.join(root, dir_name)
                    dirs_data.append(dir_path_name)
            return dirs_data

        dir_data_root = "/home/lukas/file/analysis/one_web/data/raw/"
        dirs_data = load_dirs_data(dir_data_root)

        dir_out = "./devel/report/"

        log_report = open(dir_out + "log.txt", "w")

        for dir_data in dirs_data:

            gps_file =  GpsFile(dir_data + os.sep + "dosimeter_gps_info.csv")
            data_file = DataFile(dir_data + os.sep + "dosimeter_image_packets.csv")
            info_file = DataInfoFile(dir_data + os.sep + "dosimeter_measure_info.csv")                

            gps_file.do_print = False
            gps_file.do_log = False

            data_file.do_print = False
            data_file.do_log = False

            info_file.do_print = False
            info_file.do_log = False

            gps_file.load()
            data_file.load()
            info_file.load()

            frames_ext = []

            data_linker = DataLinker()

            data_linker.do_print = False
            data_linker.do_log = False

            data_linker.link_data_info_gps(data_file, info_file, gps_file, frames_ext, do_print_info=True)

            #  log stat

            log_report.write("=================================================================\n")
            log_report.write(dir_data)
            log_report.write(data_file.log_stat())
            log_report.write(info_file.print(do_print_data=False))
            log_report.write(gps_file.print(do_print_data=False))
            log_report.write(data_linker.print(do_print_data=False))

            exit()

            # for frame_ext in frames_ext:
            #     print(frame_ext.gps)            

    # evaluating contribution of acq time estimation
    if case == 4:

        dir_data = "/home/lukas/file/analysis/one_web/data/raw/_2023-11-14_00_00_30_897-_2023-11-19_23_59_34_597/"
        file_out_path_name = "./devel/data_linker/data_linker.json"

        gps_file =  GpsFile(dir_data + "dosimeter_gps_info.csv")
        data_file = DataFile(dir_data + "dosimeter_image_packets.csv")
        info_file = DataInfoFile(dir_data + "dosimeter_measure_info.csv")                

        gps_file.load()
        data_file.load()
        info_file.load()

        frames_ext = []

        data_linker = DataLinker()
        data_linker.link_data_info_gps(data_file, info_file, gps_file, frames_ext, do_print_info=True)

        for frame_ext in frames_ext:
            print(frame_ext.gps)

        # export file
        data_linker.export(file_out_path_name)             

import os
import sys
import logging
import binascii
import csv
import datetime
import matplotlib.colors as mcolors

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *
from log import *

sys.path.append("src")

from data_file import *
from gps_file import *
from data_info_file import *
from gps_spice import *
from utils import *

# adjusted frame for needs of data extraction with additional extension with information about 
# temperature, gps etc
class FrameExtInfo(Frame, object):
    """docstring for FrameExtInfo"""
    def __init__(self, mode : Tpx3FrameMode):
        super(FrameExtInfo, self).__init__(mode)
        
        self.raw_info = None
        self.temperature = None
        self.error_code = None
        self.gps = None

    def copy_frame_values(self, frame : Frame):
        if not frame:
            return

        self.matrix = frame.matrix
        self.width = frame.width
        self.height = frame.height
        self.mode = frame.mode 
        self.t_acq = frame.t_acq 
        self.t_ref = frame.t_ref 
        self.id = frame.id       


# links data file, data info file and gps file based on the time
class DataLinker(object):
    """docstring for DataLinker"""
    def __init__(self, log_path="", log_name="log.txt"):
        super(DataLinker, self).__init__()
        
        # linker - data + info
        self.time_window_data_info_s = 4             # time window for linking data and info in seconds 

        # linker - data + gps
        self.time_window_data_gps_s = 10              # time window for linking data and gps in seconds 

        # stat
        self.count_linked_data_info = 0
        self.count_no_link_data_info = 0
        self.count_multi_linked_data_info = 0
        self.count_single_linked_data_info = 0

        self.count_linked_data_gps = 0
        self.count_no_link_data_gps = 0
        self.count_multi_linked_data_gps = 0
        self.count_single_linked_data_gps = 0

        # log and print
        self.do_log = True
        self.do_print = True
        self.log_file_path = log_path
        self.log_file_name = log_name
        self.log_file = None

        try:
            self._open_log()
        except Exception as e:
            log_warning(f"failed to open log {os.path.join(self.log_file_path, self.log_file_name)}: {e}",
                        self.log_file, self.do_print, self.do_log)


    def __exit__(self, exc_type, exc_value, traceback):
        if self.log_file:
            self.log_file.close()        

    def _open_log(self):
        self.log_file = open(os.path.join(self.log_file_path, self.log_file_name), "w")

    def link_data_info_gps(self, data_file : DataFile, info_file : DataInfoFile, gps_file : GpsFile, 
                            frames_ext : list, do_print_info=False):

        # it has to be in this order, because gps link is assuming already existing frames
        self._link_data_and_info(data_file, info_file, frames_ext, do_print_info=do_print_info)
        self._link_data_and_gps(data_file, gps_file, frames_ext, do_print_info=do_print_info)

    """
    links data file and data info file and fills final frames into 
    frames ext given by user
    """
    def _link_data_and_info(self, data_file : DataFile, info_file : DataInfoFile, frames_ext : list, do_print_info=False):
        if data_file is None or info_file is None:
            raise_runtime_error(f"DataLinker.link_data_and_info - failed because none data {data_file} or info  {info_file}", 
                                self.log_file, self.do_print, self.do_log)
        if not data_file.get_done_load() or not info_file.get_done_load():
            raise_runtime_error(f"DataLinker.link_data_and_info - failed because not loaded data {data_file.get_done_load()} or info {info_file.get_done_load()}", 
                                self.log_file, self.do_print, self.do_log)

        try:
            frames_failed_link = []
            info_idx = 0
            info_data_size = len(info_file.data)
            info_row = None
            timestamp_info = None
            timestamp_frame = None

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

                        # if do_print_info:
                        #     self._print_frame_link(frame, timestamp_frame, timestamp_info)

                        frame_ext = FrameExtInfo(frame.mode)
                        frame_ext.copy_frame_values(frame)
                        frame_ext.raw_info = info_row.tolist()
                        frame_ext.t_acq = info_row["time_acq_s"]

                        frames_ext.append(frame_ext)

                    # if time diff is negative then it can be ended and new frame tested with current info
                    elif datetime_diff_seconds(timestamp_frame, timestamp_info) < 0:
                        if not done_link:
                            frames_failed_link.append(frame)
                        break

                    info_idx += 1

                self._eval_frame_stat_of_data_info_link(count_links)

            if do_print_info:
                self._print_frame_link_info(frames_ext, frames_failed_link, len(data_file.frames), self.count_linked_data_info,
                                            self.count_no_link_data_info, self. count_single_linked_data_info, self.count_multi_linked_data_info)

        except Exception as e:
            raise_runtime_error(f"DataLinker.link_data_and_info - failed to link data and info: {e}",
                                self.log_file, self.do_print, self.do_log)

    def _eval_frame_stat_of_data_info_link(self, count_links):
        if count_links == 0:
            self.count_no_link_data_info += 1
        else:
            self.count_linked_data_info += 1
            if count_links == 1:
                self.count_single_linked_data_info += 1
            else:
                self.count_multi_linked_data_info += 1


    """
    links data file and gps info file and fills final frames into 
    frames ext given by user
    """
    def _link_data_and_gps(self, data_file : DataFile, gps_file : GpsFile, frames_ext : list, do_print_info=False):
        if data_file is None or gps_file is None:
            raise_runtime_error(f"DataLinker.link_data_and_gps - failed because none data {data_file} or gps  {gps_file}", 
                                self.log_file, self.do_print, self.do_log)
        if not data_file.get_done_load() or not gps_file.get_done_load():
            raise_runtime_error(f"DataLinker.link_data_and_gps - failed because not loaded data {data_file.get_done_load()} or gps {gps_file.get_done_load()}", 
                                self.log_file, self.do_print, self.do_log)

        try:
            frames_failed_link = []
            frame_idx_to_remove = []
            gps_idx = 0
            gps_data_size = len(gps_file.data)
            gps_row = None
            timestamp_gps = None
            timestamp_frame = None
            count_frames_in = len(frames_ext)

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

                        gps_possible_link_data.append(gps_row.tolist())

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
                self._print_frame_link_info(frames_ext, frames_failed_link, count_frames_in, self.count_linked_data_gps,
                                            self.count_no_link_data_gps, self. count_single_linked_data_gps, self.count_multi_linked_data_gps)

        except Exception as e:
            raise_runtime_error(f"DataLinker.link_data_and_gps - failed to link data and gps: {e}",
                                self.log_file, self.do_print, self.do_log)

    """
    matching of frame and gps info links based on their count
    it should be done on several links and use func _match_frame_with_gps_with_time_weighting
    """
    def _match_frame_with_gps_info(self, frame_ext, gps_possible_link_data):

        if frame_ext is None:
            log_error(f"DataLinker._match_frame_with_gps_info - failed to match links with data because frame is None.")
            return 0
        
        count_links = len(gps_possible_link_data)

        if count_links == 0:
            return 0
        elif count_links == 1:
            gps_timestamp = gps_possible_link_data[0][0]
            log_warning(f"match of frame {frame_ext.t_ref} with gps taken from one link {gps_timestamp}", self.log_file, self.do_print, self.do_log)
            self._assing_gps_info_to_frame(frame_ext, gps_possible_link_data[0])
            return 1
        else:
            try:
                self._match_frame_with_gps_with_time_weighting(frame_ext, gps_possible_link_data)
            except Exception as e:
                log_error(f"DataLinker._match_frame_with_gps_info - failed to math multiple links. Assigning 1st one. Exp: {e}",
                            self.log_file, self.do_print, self.do_log)
                self._assing_gps_info_to_frame(frame_ext, gps_possible_link_data[0])
            count_links = 1
        
        return count_links

    def _assing_gps_info_to_frame(self, frame_ext, gps_data):
        if frame_ext is None:
            return

        if isinstance(gps_data, pd.DataFrame):
            frame_ext.gps = gps_data.tolist()
        elif isinstance(gps_data, list):
            frame_ext.gps = gps_data
        else:
            log_error(f"DataLinker._assing_gps_info_to_frame - can not gps info to frame because it is {instance(gps_data)}", 
                        self.log_file, self.do_print, self.do_log)

    """matching frame with gps links based on time weighting"""
    def _match_frame_with_gps_with_time_weighting(self, frame_ext, gps_data):

        t_diffs = np.zeros((len(gps_data))) # time differences between gps infos and frame 

        for idx, gps_info in enumerate(gps_data):
            gps_timestamp = convert_str_timestapmp_to_datetime(gps_info[0])
            t_diffs[idx] = abs(datetime_diff_seconds(frame_ext.t_ref, gps_timestamp))

        weights = (1./t_diffs) / (1./t_diffs).sum()
        
        gps_info_final = [0] * len(gps_data[0])
        gps_info_final[0] = frame_ext.t_ref

        for idx_gps, gps_info in enumerate(gps_data):
            weight = weights[idx_gps]
            for idx, item in enumerate(gps_info):
                if idx == 0:
                    continue
                else:
                    gps_info_final[idx] += gps_info[idx]*weight

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
        log_info(msg, self.log_file, self.do_print, self.do_log)

    def _print_frame_link_info(self, frames : list, frames_failed_link, count_in_frame, count_linked_frames, count_no_linked_frames, 
                                count_single_linked_frames, count_multi_linked_frames, do_print_frames=False):
        
        msg =   "\n"
        msg += f"link frame info:\n"
        msg += "\n"
        msg += f"count_in_frame:                {count_in_frame}\n"
        msg += f"count_linked_frames:           {count_linked_frames}\t[{calc_portion_in_perc(count_linked_frames, count_in_frame):.2f}%]\n"
        msg += f"count_no_linked_frames:        {count_no_linked_frames}\n"
        msg += f"count_single_linked_frames:    {count_single_linked_frames}\n"   
        msg += f"count_multi_linked_frames:     {count_multi_linked_frames}\n"                     
        msg += "\n"
        msg += "frames without link\n"
        for frame in frames_failed_link:
            msg += f"\t{frame.t_ref}\t{frame.id}\t{frame.get_count_hit_pixels()}\n"
        msg += "\n"

        if do_print_frames:
            msg += f"final extended frames\n"
            for frame_ext in frames:
                addon = str(frame_ext.raw_info) if frame_ext.raw_info is not None else ""
                addon += " " + str(frame_ext.gps) if frame_ext.gps is not None else ""

                msg += f"\t{frame_ext.t_ref}\t{frame_ext.id}\t{frame_ext.get_count_hit_pixels()}\t{frame_ext.t_acq}\t{addon}\n"

        log_info(msg, self.log_file, self.do_print, self.do_log)

if __name__ == '__main__':
    
    case = 2

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

        dir_data = "./devel/data/"

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
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

def plot_longlattot(long_list_deg, lat_list_deg, tot_list, color="C1", ax=None, fig=None):

    do_show = True
    if ax is None or fig is None:
        fig, ax = plt.subplots(figsize=(15,9))
    else:
        do_show=False

    fig_eart_path_name = "./fig/Equirectangular-projection.jpg"

    # image_eart = mpimg.imread(fig_eart_path_name)
    image_eart = plt.imread(fig_eart_path_name)
    
    ax.imshow(image_eart, extent=[-180,180,-90,90])



    # ax.scatter(long_list_deg, lat_list_deg, s=1, color=color, alpha=)

    hist2d = ax.hist2d(long_list_deg, lat_list_deg, bins=[50,25], range=[[-180,180], [-90,90]], weights=tot_list,
            alpha=0.5, cmap="jet", norm=mcolors.LogNorm())

    np.savetxt("./devel/data/tot_map.txt" ,hist2d[0])

    print(hist2d)

    cbar = plt.colorbar(hist2d[3], ax=ax, shrink=0.7)
    cbar.set_label("ToT [-]")

    ax.set_xlabel("longitude [deg]")
    ax.set_ylabel("latitude [deg]") 
    ax.set_title("sum of tot in counts")
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)   

    if do_show:
        plt.show()


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

    # def create(self, frame : Frame, raw_info=None, temperature=None, error_code=None, gps=None):


# links data file, data info file and gps file based on the time
class DataLinker(object):
    """docstring for DataLinker"""
    def __init__(self):
        super(DataLinker, self).__init__()
        
        self.frames = []


if __name__ == '__main__':
    
    case = 2

    # basic test
    if case == 1:
        
        # dir_data = "./devel/data/"
        # dir_data = "/home/lukas/file/analysis/one_web/data/raw/_2023-11-14_00_00_30_897-_2023-11-19_23_59_34_597/"

        def load_data(dir_data, long_list_deg, lat_list_deg, tot_list):

            gps_file = GpsFile(dir_data + "dosimeter_gps_info.csv")
            data_file = DataFile(dir_data + "dosimeter_image_packets.csv")
            info_file = DataInfoFile(dir_data + "dosimeter_measure_info.csv")        

            gps_file.load()
            data_file.load()
            info_file.load()

            frames_ext = []

            info_idx = 0
            info_data_size = len(info_file.data)
            info_row = None
            timestamp_info = None
            timestamp_frame = None

            timestamp_window_sec = 4
            count_good_link = 0
            frames_failed_link = []

            for frame_idx, frame_data_file in enumerate(data_file.frames):
                
                timestamp_frame = frame_data_file.t_ref 
                done_link = False

                while info_idx < info_data_size:
            
                    info_row = info_file.data.iloc[info_idx]
                    if info_row is not None:
                        timestamp_info = convert_str_timestapmp_to_datetime(info_row["TIMESTAMP"])

                    if abs(datetime_diff_seconds(timestamp_frame, timestamp_info)) < timestamp_window_sec:
                        done_link = True
                        print("---------------------------")
                        print(f"frame idx:          {frame_idx}")                                        
                        print(f"frame id:           {frame_data_file.id}")                    
                        print(f"timestamp frame:    {timestamp_frame}")
                        print(f"timestamp info:     {timestamp_info}")
                        count_good_link += 1

                        frame_ext = FrameExtInfo(frame_data_file.mode)
                        frame_ext = frame_data_file
                        frame_ext.raw_info = info_row.tolist()
                        frame_ext.t_acq = info_row["acq_time"]

                        frames_ext.append(frame_ext)

                    elif datetime_diff_seconds(timestamp_frame, timestamp_info) < 0:
                        if not done_link:
                            frames_failed_link.append(frame_data_file)
                        break

                    info_idx += 1

            # print(f"==================================")
            # print(f"final info:")
            # print(f"count of frames:       {len(data_file.frames)}")
            # print(f"count of good links:   {count_good_link}")
            # print(f"count of no links:     {len(data_file.frames) - count_good_link}")
            # print("")
            # print("frames without link")
            # for frame in frames_failed_link:
            #     print(f"\t{frame.t_ref}\t{frame.id}\t{frame.get_count_hit_pixels()}")

            # print(f"==================================")
            # print(f"extended frames afrer info file")
            # for frame_ext in frames_ext:
            #     print(f"\t{frame_ext.t_ref}\t{frame_ext.id}\t{frame_ext.get_count_hit_pixels()}\t{frame_ext.t_acq}\t{frame_ext.raw_info}")


            # link with gps data
            gps_idx = 0
            gps_data_size = len(gps_file.data)
            gps_row = None
            timestamp_gps = None
            timestamp_frame = None

            timestamp_window_sec = 5
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

                    if abs(datetime_diff_seconds(timestamp_frame, timestamp_gps)) < timestamp_window_sec:
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

            # print(f"==================================")
            # print(f"final info:")
            # print(f"count of frames:       {len(data_file.frames)}")
            # print(f"count of good links:   {count_good_link}")
            # print(f"count of no links:     {len(frames_failed_link)}")
            # print("")
            # print("frames without link")
            # for frame in frames_failed_link:
            #     print(f"\t{frame.t_ref}\t{frame.id}\t{frame.get_count_hit_pixels()}")

            # print(f"==================================")
            # print(f"extended frames afrer info file")
            # for frame_ext in frames_ext:
            #     print(f"\t{frame_ext.t_ref}\t{frame_ext.id}\t{frame_ext.get_count_hit_pixels()}\t{frame_ext.t_acq}\t{frame_ext.gps}")



            # visulization map of tot sum


            mask_file_path_name = "./devel/data/mask_multiply_count.txt"
            mask = np.loadtxt(mask_file_path_name, delimiter=" ")

            for frame_ext in frames_ext:
                frame_ext.multiply_frame(mask)
                sum_tot = np.sum(frame_ext.matrix[Tpx3Mode.TOT])
                tot_list.append(sum_tot)

                vec_J2000 = np.array([frame_ext.gps[1], frame_ext.gps[2], frame_ext.gps[3]])

                timestamp = frame_ext.gps[0]
                # print(f"{timestamp}\t{frame_ext.id}\t{sum_tot}\t{vec_J2000}")

                vec_ITRF93_lla = transform_J2000_to_ITRF93_lla(vec_J2000 ,timestamp)

                print(f"{timestamp}\t{vec_J2000}\t{vec_ITRF93_lla}")

                long_list_deg.append(vec_ITRF93_lla[1])
                lat_list_deg.append(vec_ITRF93_lla[2])

            return long_list_deg, lat_list_deg, tot_list


        def load_dirs_data(dir_root_path, data_mask=None):
            dirs_data = []
            for root, dirs, files in os.walk(dir_root_path):
                for dir_name in dirs:
                    dir_path_name = os.path.join(root, dir_name)
                    dirs_data.append(dir_path_name)
            return dirs_data

        dirs_data_path_name = "/home/lukas/file/analysis/one_web/data/raw/"
        dirs_data = load_dirs_data(dirs_data_path_name)

        tot_list = []
        long_list_deg = []
        lat_list_deg = []
        for idx, dir_data in enumerate(dirs_data):
            long_list_deg, lat_list_deg, tot_list = load_data(dir_data + os.sep, long_list_deg, lat_list_deg, tot_list)

        file_out = open("./devel/data/long_lat_tot.txt", "w")
        file_out.write("long_deg\tlat_deg\ttot_count\n")
        for idx in range(len(tot_list)):
            file_out.write(f"{long_list_deg[idx]}\t{lat_list_deg[idx]}\t{tot_list[idx]}\n")

        file_out.close()

        plot_longlattot(long_list_deg, lat_list_deg, tot_list)

    if case == 2:

        long_lat_tot_file = "./devel/data/long_lat_tot.txt"

        data = pd.read_csv(long_lat_tot_file, sep="\t")   

        plot_longlattot(data["long_deg"], data["lat_deg"], data["tot_count"])


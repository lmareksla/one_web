import pandas as pd
import sys
import matplotlib.pyplot as plt
import numpy as np

sys.path.append("src/pydpe/src")
from clist import *

sys.path.append("src")
from dir import *
from analysis import *




if __name__ == '__main__':
    
    case = 3

    if case == 1:

        clist_path_name = "/home/lukas/file/analysis/one_web/data/proc/_2023-09-13_14_47_05_697-_2023-09-13_20_18_54_397/04_dpe/File/data_ext.clist"
        clist = Clist(clist_path_name)

        fig, axs = plt.subplots(4,1, figsize=(8,20))

        axs[0].scatter(clist.data["Flags"], clist.data["GpsLat"] )
        axs[1].scatter(clist.data["Flags"], clist.data["GpsLong"] )        
        axs[2].scatter(range(len(clist.data)), clist.data["Flags"]) 
        axs[3].scatter(clist.data["GpsLong"], clist.data["GpsLat"] )                       
        plt.show()


    if case == 2:

        dir_data_proc =     "/home/lukas/file/analysis/one_web/data/proc"
        dir_phys =          "/home/lukas/file/analysis/one_web/data/phys"

        dir_proc_dpe_name = "04_dpe"

        dirs_proc_data_name = sorted(list_dirs_of_dir(dir_data_proc))        


        lats = []
        longs = []
        frame_ids = []

        lats_el = []
        longs_el = []

        lats_prot = []
        longs_prot = []

        for dir_proc_data_name in dirs_proc_data_name:

            dir_proc_dpe_data = os.path.join(dir_data_proc, dir_proc_data_name, dir_proc_dpe_name)
            clist = Clist(os.path.join(dir_proc_dpe_data, "File", "data_ext.clist"))

            data = clist.data

            data = data.drop_duplicates(subset='Flags', keep='first')

            lats.extend((data["GpsLat"]*0.5).to_list())
            longs.extend((data["GpsLong"]*0.5).to_list())
            frame_ids.extend(data["Flags"].to_list())

            lats_prot.extend((data.loc[data['PIDClass'].isin([0,2]), 'GpsLat']*0.5).to_list())
            longs_prot.extend((data.loc[data['PIDClass'].isin([0,2]), 'GpsLong']*0.5).to_list())

            lats_el.extend((data.loc[data['PIDClass'].isin([1]), 'GpsLat']*0.5).to_list())
            longs_el.extend((data.loc[data['PIDClass'].isin([1]), 'GpsLong']*0.5).to_list())


        fig, axs = plt.subplots(3,2, figsize=(20,10))

        histd_res = axs[0,0].hist2d(longs, lats, bins=[20,10])
        cbar = fig.colorbar(histd_res[3], ax=axs[0,0], alpha=1, fraction=0.03, pad=0.04)        
        axs[0,0].set_title("hist2d all")  
        axs[0,1].scatter(longs, lats, alpha=0.1)
        axs[0,1].set_title("scatter all")       

        axs[1,0].hist2d(longs_prot, lats_prot, bins=[100,50])
        axs[1,0].set_title("hist2d protons")  
        axs[1,1].scatter(longs_prot, lats_prot, alpha=0.1)
        axs[1,1].set_title("scatter protons")    

        axs[2,0].hist2d(longs_el, lats_el, bins=[100,50])
        axs[2,0].set_title("hist2d electrons")  
        axs[2,1].scatter(longs_el, lats_el, alpha=0.1)
        axs[2,1].set_title("scatter electrons")                                     
        plt.show()


    if case == 3:

        file_in_path_name = "/home/lukas/file/analysis/one_web/map_power_cycling_detector/Mapping_results_2023-12-01_2024-01-31.csv"

        dir_data_proc =     "/home/lukas/file/analysis/one_web/data/proc"
        dir_phys =          "/home/lukas/file/analysis/one_web/data/phys"

        dir_proc_dpe_name = "04_dpe"

        dirs_proc_data_name = sorted(list_dirs_of_dir(dir_data_proc))        


        lats = []
        longs = []
        frame_ids = []

        for dir_proc_data_name in dirs_proc_data_name:

            dir_proc_dpe_data = os.path.join(dir_data_proc, dir_proc_data_name, dir_proc_dpe_name)
            clist = Clist(os.path.join(dir_proc_dpe_data, "File", "data_ext.clist"))

            data = clist.data

            data = data.drop_duplicates(subset='Flags', keep='first')

            lats.extend((data["GpsLat"]*0.5).to_list())
            longs.extend((data["GpsLong"]*0.5).to_list())
            frame_ids.extend(data["Flags"].to_list())

        data_power_cycle = pd.read_csv(file_in_path_name)
        data_long_power_cycle = copy.deepcopy(data_power_cycle["longitude"])
        data_long_power_cycle = np.array(data_long_power_cycle)        
        data_long_power_cycle[data_long_power_cycle > 180] += 1000
        data_long_power_cycle[data_long_power_cycle < 180] += 180
        data_long_power_cycle[data_long_power_cycle > 1180] -= 1180


        bins = [20,10]

        hist2d_frame_occ, xedges, yedges = np.histogram2d(longs, lats, bins=bins)
        hist2d_power_cycle, xedges, yedges = np.histogram2d(data_long_power_cycle, data_power_cycle["latitude"], 
                                                            bins=bins)

        # plt.imshow(hist2d_frame_occ)
        # plt.show()
        # exit()

        hist2d_sum = hist2d_frame_occ + hist2d_power_cycle

        list_sum, x_edges_list, y_edges_list = convert_np_to_plt_hist2d(hist2d_sum, xedges, yedges)

        fig, ax = plt.subplots(figsize=(15,9))        
        fig_eart_path_name = "./fig/Equirectangular-projection.jpg"

        # image_eart = mpimg.imread(fig_eart_path_name)
        image_eart = plt.imread(fig_eart_path_name)
        
        ax.imshow(image_eart, extent=[-180,180,-90,90], alpha=0.5)

        hist2d_res = ax.hist2d(x=x_edges_list, y=y_edges_list, weights=list_sum, range=[[-180,180],[-90,90]], 
                    bins=bins)
        ax.set_xlabel("longitude [deg]")
        ax.set_ylabel("latitude [deg]") 
        ax.set_title("sum of power cycles and frame occupancy")
        cbar = fig.colorbar(hist2d_res[3], ax=ax, alpha=1, fraction=0.03, pad=0.04)
        cbar.set_label("count [-]")   
        plt.show()
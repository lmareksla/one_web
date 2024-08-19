import os
import sys
import logging
import binascii
import csv
import datetime
import multiprocessing
import shutil
import json
import time
from matplotlib.colors import LogNorm
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import copy
from datetime import datetime

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
from dpe import *
from clist_h5 import *
from plot import *
from analysis import *
from export_phys import *

sys.path.append("src/pydpe/src")

from clist import *
from cluster import *


#@log_entry_exit
def get_info_hist1d(hist_file_base_name : str , hist_file_path : str = None):
    if len(hist_file_path) == 0 and self is not None:
        hist_file_path = os.path.join(self.file_out_path, "Hist")

    info_path_name = os.path.join(hist_file_path, hist_file_base_name + ".hist_info")

    info = configparser.ConfigParser()
    info.read(info_path_name)

    return info

#@log_entry_exit
def get_hist1d_total_from_file(hist_file_path : str = "", hist_file_name : str = "Hist1D_E_EqBin_Total", 
                                max_bin_count : int = 100):


    if len(hist_file_path) == 0:
        hist_file_path = os.path.join(self.file_out_path, "Hist")

    data_path_name = os.path.join(hist_file_path, hist_file_name + ".hist")

    data = pd.read_csv(data_path_name, delimiter="\t")
    data.columns = ["xedges", "bin_conts"]

    info = get_info_hist1d(hist_file_name, hist_file_path)

    name = info["HistPar"]["Name"].replace("\"","")
    ax_titles = info["HistPar"]["AxisTitles"].replace("\"","").split(",")
    nbin = float(info["HistPar"]["NBin"])
    xmin = float(info["HistPar"]["Xmin"])
    xmax = float(info["HistPar"]["Xmax"])
    is_equidist = info["HistPar"]["BinEquidist"] == "1" 

    data_full = pd.DataFrame()

    if is_equidist:

        x_range = xmax - xmin
        bin_width = x_range / nbin
        n_plot_bins = int(data["xedges"][len(data["xedges"])-2] / bin_width) + 1 # plus one for the low edges
        
        do_rebin = False

        rebin = 1
        if n_plot_bins > max_bin_count:
            max_bin_count += 1
            do_rebin = True
            rebin = int(n_plot_bins/max_bin_count)
            if rebin < 1:
                do_rebin = False

        if n_plot_bins <= rebin:
            do_rebin = False

        reverse_bin_width = 1./bin_width
        reverse_bin_width += reverse_bin_width*0.01

        data["idx"] = (data["xedges"] * reverse_bin_width).astype(int)

        series = pd.Series(np.arange(0, n_plot_bins * bin_width, bin_width))

        data_full = pd.DataFrame({"xedges": series})
        data_full["bin_conts"] = 0
        
        for idx, index in enumerate(data["idx"]):
            data_full.loc[index, "bin_conts"] = data.loc[idx, "bin_conts"]

        if do_rebin:

            bin_conts_miss = None
            
            if len(data_full)%rebin != 0:
                n_additional_bins = len(data_full)%rebin
                n_miss_bins = rebin - n_additional_bins

                bin_conts_miss = np.zeros((n_miss_bins))

            bin_conts = data_full["bin_conts"].values

            if bin_conts_miss is not None:
                bin_conts = np.append(bin_conts, bin_conts_miss)

            bin_conts = bin_conts.reshape(-1, rebin)

            bin_conts = np.sum(bin_conts, axis=1)

            arr_edges = data_full["xedges"].values[::rebin]

            return arr_edges, bin_conts, ax_titles, name
    else:
        data_full["xedges"] = data["xedges"]
        data_full["bin_conts"] = data["bin_conts"]

    return data_full["xedges"], data_full["bin_conts"], ax_titles, name


if __name__ == "__main__":

    file_fig_path_name = "/home/lukas/file/analysis/one_web/data/phys/hist_let.png"

    path_hists = "/home/lukas/file/analysis/one_web/data/proc/_2024-02-13_00_00_28_297-_2024-02-13_23_59_31_297/04_dpe/Hist/"
    hist_base_name = "Hist1D_LET_" 
    class_name_suffixes = ["Total", "1", "2", "3"]
    class_names = ["all", "electrons & photons", "protons", "ions"]
    colors = ["C2",  "C9",   "C1",   "C3",   "C4",  "C5",   "C6"]

    fig, ax = plt.subplots(1,1, figsize=(9,6))

    for idx, class_name_suffix in enumerate(class_name_suffixes):
        
        hist_file_path = ""
        hist_file_name = hist_base_name + class_name_suffix

        xedges, bin_conts, ax_titles, name = get_hist1d_total_from_file(path_hists, hist_file_name)


        ax.hist(xedges, xedges, weights=bin_conts, histtype='step', label=class_names[idx],
                color=colors[idx])

        ax.grid(   visible = True, 
                    color ='grey',  
                    linestyle ='-.', 
                    linewidth = 0.4,  
                    alpha = 0.5)        
        
        ax.set_yscale('log')
        ax.set_xscale('log')

    ax.set_xlim(0, 30) 

    font_color = "white"
    fontsize = 16
    # Set labels and title with the specified font color and size
    ax.set_xlabel("LET [kev/um]", fontsize=fontsize, color=font_color)
    ax.set_ylabel("N [-]", fontsize=fontsize, color=font_color) 
    ax.set_title("Distribution of particle LET - linear energy transfer", fontsize=fontsize, color=font_color)
    ax.tick_params(axis='both', which='both', labelsize=fontsize, colors=font_color)
    
    for spine in ax.spines.values():
        spine.set_edgecolor(font_color)
    

    legend = ax.legend(loc='best', fontsize=12)
    # for text in legend.get_texts():
    #     text.set_color(font_color)

    fig.patch.set_facecolor('white')
    fig.patch.set_alpha(0)  # Adjust alpha (transparency) as needed

    plt.savefig(file_fig_path_name, dpi=600, transparent=True) # transparent=True,   
    plt.close()       

    
    # plt.show()
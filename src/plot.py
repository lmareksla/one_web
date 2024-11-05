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

sys.path.append("src")

from dir import *
from utils import *
from data_file import *
from data_info_file import *
from gps_file import *
from data_linker import *
from mask import *
from clusterer import *
from clist_h5 import *
from export_phys import * 

sys.path.append("src/pydpe/src")

from clist import *
from cluster import *


def plot_longlat(long_list_deg, lat_list_deg, color="C1", ax=None, fig=None):

    do_show = True
    if ax is None or fig is None:
        fig, ax = plt.subplots(figsize=(10,6))
    else:
        do_show=False

    fig_eart_path_name = "./fig/Equirectangular-projection.jpg"

    # image_eart = mpimg.imread(fig_eart_path_name)
    image_eart = plt.imread(fig_eart_path_name)
    
    ax.imshow(image_eart, extent=[-180,180,-90,90], alpha=0.95)

    ax.scatter(long_list_deg, lat_list_deg, s=0.1, color=color, alpha=0.1)
    ax.set_xlabel("longitude [deg]")
    ax.set_ylabel("latitude [deg]") 
    ax.set_title("position of satelite")
    # ax.set_xlim(-180, 180)
    # ax.set_ylim(-90, 90)   

    if do_show:
        plt.show()


def plot_longlatvar_simple(long_list_deg : list, lat_list_deg : list , var : list, 
                    ax=None, fig=None, 
                    bins=[180,90], range=[[-180,180],[-90,90]],
                    title="", z_label="", 
                    do_log_z=True, cmap="RdYlBu_r",
                    do_show=False,  
                    file_json_path_name="", do_save_json=False, font_color="black"):

    fig_eart_path_name = "./fig/Equirectangular-projection.jpg"

    norm = None
    if do_log_z:
        norm = matplotlib.colors.LogNorm()

    # plot histogram
    hist2d_res = ax.hist2d(x=long_list_deg, y=lat_list_deg, weights=var, range=range, 
                           bins=bins, cmap=cmap, norm=norm)

    # plot image over the histogram with smaller alpha
    image_eart = plt.imread(fig_eart_path_name)
    ax.imshow(image_eart, extent=[-180,180,-90,90], alpha=0.4)

    # other settigns
    ax.set_xlabel("longitude [deg]", color=font_color)
    ax.set_ylabel("latitude [deg]", color=font_color) 
    # cbar.ax.tick_params(labelsize=12, colors='white')  # Adjust colorbar tick label size    
    ax.set_title(title, color=font_color)
    cbar = fig.colorbar(hist2d_res[3], ax=ax, alpha=1, fraction=0.03, pad=0.04)
    cbar.ax.tick_params(labelsize=12, colors=font_color)  # Adjust colorbar tick label size    
    cbar.set_label(z_label, colors=font_color)   

    if do_show:
        plt.show()

    if do_save_json and len(file_json_path_name) != 0:
        data_z = hist2d_res[0].flatten()
        export_map(file_json_path_name, list(data_z), list(hist2d_res[1]), list(hist2d_res[2]), 
                    "bin_val", "x_edge", "y_edge",
                     z_label, "longitude [deg]", "latitude [deg]", title=title)

    return hist2d_res


def plot_longlatvar(long_list_deg, lat_list_deg, var, color="C1", ax=None, fig=None, title="",
                    z_label="", z_max=None, z_min=None, do_show=False, bins=[180,90], do_log_z=True,
                    cmap="RdYlBu_r", file_json_path_name="", do_save_json=False, font_color="black"):

    fig_eart_path_name = "./fig/Equirectangular-projection.jpg"


    long_list_deg_cp = copy.deepcopy(long_list_deg)
    lat_list_deg_cp = copy.deepcopy(lat_list_deg)
    var_cp = copy.deepcopy(var)

    if z_max is not None:
        long_list_deg_cp.append(179.999)
        lat_list_deg_cp.append(89.99)
        var_cp.append(z_max)

    norm = None
    if do_log_z:
        norm = matplotlib.colors.LogNorm()

    # Plot histogram
    hist2d_res = ax.hist2d(x=long_list_deg_cp, y=lat_list_deg_cp, weights=var_cp, range=[[-180,180],[-90,90]], 
                           bins=bins, cmap=cmap, norm=norm, cmin=z_min)

    # Plot image over the histogram with smaller alpha
    image_eart = plt.imread(fig_eart_path_name)
    ax.imshow(image_eart, extent=[-180,180,-90,90], alpha=0.4)


    fontsize = 12
    # Set labels and title with the specified font color and size
    ax.set_xlabel("longitude [deg]", fontsize=fontsize, color=font_color)
    ax.set_ylabel("latitude [deg]", fontsize=fontsize, color=font_color) 
    ax.set_title(title, fontsize=fontsize, color=font_color)

    # Set tick parameters for both axis and colorbar
    ax.tick_params(axis='both', which='both', labelsize=fontsize, colors=font_color)
    cbar = fig.colorbar(hist2d_res[3], ax=ax, alpha=1, fraction=0.03, pad=0.04)
    cbar.ax.tick_params(labelsize=fontsize, colors=font_color)  # Adjust colorbar tick label size    
    cbar.set_label(z_label, fontsize=fontsize, color=font_color)   

    if do_show:
        plt.show()

    if do_save_json and len(file_json_path_name) != 0:
        data_z = hist2d_res[0].flatten()
        export_map(file_json_path_name, list(data_z), list(hist2d_res[1]), list(hist2d_res[2]), 
                    "bin_val", "x_edge", "y_edge",
                     z_label, "longitude [deg]", "latitude [deg]", title=title)

    return hist2d_res

def plot_clusters(clusters_str, n_clcuster_to_show=None, fig=None, ax=None, title="", do_show=True,
                    z_label=""):

    if not fig or not ax:
        fig, ax = plt.subplots()

    idx = 0 
    hist = None

    for cluster_str in clusters_str:
        try:
            idx += 1
            cluster = Cluster()
            cluster.load_from_string(cluster_str)
            hist, cbar = cluster.plot(fig=fig, ax=ax, show_plot=False)
            cbar.remove()
        except Exception as e:
            print(f"{e}")
            continue
        if idx >= n_clcuster_to_show:
            break

    if hist is None:
        print("[ERROR] No clusters showed in plot_clusters fuction.")
        return

    font_color = "black"
    fontsize = 12
    # Set labels and title with the specified font color and size
    ax.set_xlabel("X [px]", fontsize=fontsize, color=font_color)
    ax.set_ylabel("Y [px]", fontsize=fontsize, color=font_color) 
    ax.set_title(title, fontsize=fontsize, color=font_color)

    # Set tick parameters for both axis and colorbar
    ax.tick_params(axis='both', which='both', labelsize=fontsize, colors=font_color)
    cbar = fig.colorbar(hist[3], ax=ax, alpha=1, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=fontsize, colors=font_color)  # Adjust colorbar tick label size    
    cbar.set_label(z_label, fontsize=fontsize, color=font_color)   

    # fig.patch.set_facecolor('white')

    ax.set_xlim(62,192)
    ax.set_ylim(62,192)


    for spine in ax.spines.values():
        spine.set_edgecolor(font_color)

    if do_show:
        plt.show()

    return cbar


def plot_time_graphs_markers(
        data_and_keys, 
        label_x="", label_y="", title="",
        fig=None, ax=None, 
        do_log_y=False,
        file_fig_path_name="", do_save_fig=False,
        do_show=False):

    if not fig or not ax:
        fig, ax = plt.subplots(figsize=(15,7))
    
    colors =    ["C2",  "C9",   "C1",   "C3",   "C4",   "C5",   "C6"]
    markers =   ["s",   "v",    "^",    "s",    "<",    ">",    "X"]

    for idx, data_and_keys_list in enumerate(data_and_keys): 
        label = data_and_keys_list[3]
        data_x = data_and_keys_list[0]
        data_y = data_and_keys_list[1]

        ax.plot(data_x, data_y, color=colors[idx], linewidth=0, marker=markers[idx], 
                markerfacecolor=colors[idx], markeredgewidth=0, markersize=3, label=label )
    
    if do_log_y:
        ax.set_yscale('log')    

    ax.legend()
    ax.set_xlabel(label_x)
    ax.set_ylabel(label_y)
    ax.set_title(title)

    if do_show:
        plt.show()
        plt.close()
    elif do_save_fig and len(file_fig_path_name) != 0:
        plt.savefig(file_fig_path_name, dpi=600)   
        plt.close()  
    else:
        plt.close()         

def plot_time_graphs_lines(
    data_and_keys, 
    label_x="", label_y="", title="",
    fig=None, ax=None, 
    do_log_y=False,
    file_fig_path_name="", do_save_fig=False,
    do_show=False,
    font_color=None):

    if not fig or not ax:
        fig, ax = plt.subplots(figsize=(15,7))
    
    colors =    ["C2",  "C9",   "C1",   "C3",   "C4",  "C5",   "C6"]

    for idx, data_and_keys_list in enumerate(data_and_keys): 
        label = data_and_keys_list[3]
        data_x = data_and_keys_list[0]
        data_y = data_and_keys_list[1]


        ax.plot(data_x, data_y, color=colors[idx], linewidth=0.7, 
                markeredgewidth=0, markersize=0, label=label )
    
    if do_log_y:
        ax.set_yscale('log')    

    ax.legend()

    font_color = "black"
    fontsize = 16
    # Set labels and title with the specified font color and size
    ax.set_xlabel(label_x, fontsize=fontsize, color=font_color)
    ax.set_ylabel(label_y, fontsize=fontsize, color=font_color) 
    ax.set_title(title, fontsize=fontsize, color=font_color)
    ax.tick_params(axis='both', which='both', labelsize=fontsize, colors=font_color)
    for spine in ax.spines.values():
        spine.set_edgecolor(font_color)
    fig.patch.set_facecolor('white')

    if do_show:
        plt.show()
        plt.close()
    elif do_save_fig and len(file_fig_path_name) != 0:
        plt.savefig(file_fig_path_name, transparent=False, dpi=600)   
        plt.close()   
    else:
        plt.close()     


if __name__ == "__main__":

    data_and_keys = [   [[10,20], [3,2], "time", "all"],
                        [[10,20], [4,1], "time", "electrons & photons"],
                        [[10,20], [6,2], "time", "protons & ions"]]
    
    plot_time_graphs_lines(data_and_keys
                           ,label_x="x"
                           ,label_y="y"
                           ,title="title"
                           ,do_show=True)
    
    plot_time_graphs_markers(data_and_keys
                           ,label_x="x"
                           ,label_y="y"
                           ,title="title"
                           ,do_show=True)    
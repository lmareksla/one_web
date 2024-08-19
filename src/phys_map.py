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



def plot_flux_map_weeks(clists, pid_class, dir_phys, title, name_out, bins, ranges, roi, do_save_json=False):
    
    file_fig_path_name = os.path.join(dir_phys, name_out + ".png")
    file_json_path_name = os.path.join(dir_phys, name_out + ".json")


    pix_size = 55
    sens_width = 256
    sens_height = 256    
    n_roi_pix = (roi[0][1] - roi[0][0])*(roi[1][1] - roi[1][0])
    mask_coef = (sens_width*sens_height)/n_roi_pix
    sens_area = (sens_width*pix_size * sens_height*pix_size)/1e8;
    sens_area /= mask_coef
    # flux coeff to calculate flux from count rate
    flux_coeff = 1./sens_area        

    # weeks = [ 1698793200, 1700002800, 1701385200, 1702594800, 1704063600, 1705273200, 1706742000,
    #         1707951600, 1709247600, 1710457200, 1711922400, 1713132000]

    # for 

    fluxes = []
    latitudes = []
    longitudes = []

    latitudes_frames = []
    longitude_frames = []

    for clist in clists:
        data = clist.data

        longitudes.extend((data.loc[data['PIDClass'].isin(pid_class), 'GpsLong']).to_list())
        latitudes.extend((data.loc[data['PIDClass'].isin(pid_class), 'GpsLat']).to_list())

        t_acqs = data.loc[data['PIDClass'].isin(pid_class), 'TAcq']
        fluxes.extend( (flux_coeff * (1/t_acqs)).to_list() )

        frame_data = data.drop_duplicates(subset='Flags', keep='first')

        longitude_frames.extend((frame_data['GpsLong']).to_list())
        latitudes_frames.extend((frame_data['GpsLat']).to_list())   

    hist_frame_occ, x_edges, y_edges = numpy.histogram2d(longitude_frames, latitudes_frames, bins=bins, range=ranges)    
    hist_flux, x_edges, y_edges = numpy.histogram2d(longitudes, latitudes, bins=bins, range=ranges, weights=fluxes)    

    # to avoid division with zeros, only division with ge 2 is valid (0 and 1 has same effect)
    hist_frame_occ[hist_frame_occ == 0] = 1  

    # avarage over all frames - counts of frames in given bin of long & lat
    hist_flux = hist_flux / hist_frame_occ

    flux_list, x_edges_list, y_edges_list = convert_np_to_plt_hist2d(hist_flux, x_edges, y_edges)

    fig, ax = plt.subplots(figsize=(10,6))        
    hist2d_res = plot_longlatvar(x_edges_list, y_edges_list, flux_list, title=title, 
                    z_label= "flux [cm-2 s-1]", fig=fig, ax=ax, z_max=None,
                    z_min=None, bins=bins, do_save_json=do_save_json, file_json_path_name=file_json_path_name)    
    plt.tight_layout()        
    plt.savefig(file_fig_path_name, transparent=True,dpi=600)
    plt.close()

    return hist2d_res



def plot_flux_map(clists, pid_class, dir_phys, title, name_out, bins, ranges, roi, do_save_json=False):
    
    file_fig_path_name = os.path.join(dir_phys, name_out + ".png")
    file_json_path_name = os.path.join(dir_phys, name_out + ".json")


    pix_size = 55
    sens_width = 256
    sens_height = 256    
    n_roi_pix = (roi[0][1] - roi[0][0])*(roi[1][1] - roi[1][0])
    mask_coef = (sens_width*sens_height)/n_roi_pix
    sens_area = (sens_width*pix_size * sens_height*pix_size)/1e8;
    sens_area /= mask_coef
    # flux coeff to calculate flux from count rate
    flux_coeff = 1./sens_area        

    fluxes = []
    latitudes = []
    longitudes = []

    latitudes_frames = []
    longitude_frames = []

    for clist in clists:
        data = clist.data

        longitudes.extend((data.loc[data['PIDClass'].isin(pid_class), 'GpsLong']).to_list())
        latitudes.extend((data.loc[data['PIDClass'].isin(pid_class), 'GpsLat']).to_list())

        t_acqs = data.loc[data['PIDClass'].isin(pid_class), 'TAcq']
        fluxes.extend( (flux_coeff * (1/t_acqs)).to_list() )

        frame_data = data.drop_duplicates(subset='Flags', keep='first')

        longitude_frames.extend((frame_data['GpsLong']).to_list())
        latitudes_frames.extend((frame_data['GpsLat']).to_list())   

    hist_frame_occ, x_edges, y_edges = numpy.histogram2d(longitude_frames, latitudes_frames, bins=bins, range=ranges)    
    hist_flux, x_edges, y_edges = numpy.histogram2d(longitudes, latitudes, bins=bins, range=ranges, weights=fluxes)    

    # to avoid division with zeros, only division with ge 2 is valid (0 and 1 has same effect)
    hist_frame_occ[hist_frame_occ == 0] = 1  

    # avarage over all frames - counts of frames in given bin of long & lat
    hist_flux = hist_flux / hist_frame_occ

    flux_list, x_edges_list, y_edges_list = convert_np_to_plt_hist2d(hist_flux, x_edges, y_edges)

    fig, ax = plt.subplots(figsize=(10,6))        
    hist2d_res = plot_longlatvar(x_edges_list, y_edges_list, flux_list, title=title, 
                    z_label= "flux [cm-2 s-1]", fig=fig, ax=ax, z_max=None,
                    z_min=None, bins=bins, do_save_json=do_save_json, file_json_path_name=file_json_path_name,
                    cmap="RdYlBu_r", font_color="white")    
    plt.tight_layout()        
    plt.savefig(file_fig_path_name, transparent=True, dpi=600)
    plt.close()

    return hist2d_res


# def plot_dose_rate_map(clists, pid_class, dir_phys, title, name_out, bins, ranges, roi, do_save_json=False):
    
#     file_fig_path_name = os.path.join(dir_phys, name_out + ".png")
#     file_json_path_name = os.path.join(dir_phys, name_out + ".json")


#     pix_size = 55
#     sens_width = 256
#     sens_height = 256    
#     n_roi_pix = (roi[0][1] - roi[0][0])*(roi[1][1] - roi[1][0])
#     mask_coef = (sens_width*sens_height)/n_roi_pix
#     sens_area = (sens_width*pix_size * sens_height*pix_size)/1e8;
#     sens_area /= mask_coef
#     # flux coeff to calculate flux from count rate
#     flux_coeff = 1./sens_area        

#     fluxes = []
#     latitudes = []
#     longitudes = []

#     latitudes_frames = []
#     longitude_frames = []

#     for clist in clists:
#         data = clist.data

#         longitudes.extend((data.loc[data['PIDClass'].isin(pid_class), 'GpsLong']).to_list())
#         latitudes.extend((data.loc[data['PIDClass'].isin(pid_class), 'GpsLat']).to_list())

#         t_acqs = data.loc[data['PIDClass'].isin(pid_class), 'TAcq']
#         energies = data.loc[data['PIDClass'].isin(pid_class), 'TAcq']

#         fluxes.extend( (does_rate_coef_kev_ugy_h * (energies/t_acqs)).to_list() )

#         frame_data = data.drop_duplicates(subset='Flags', keep='first')

#         longitude_frames.extend((frame_data['GpsLong']).to_list())
#         latitudes_frames.extend((frame_data['GpsLat']).to_list())   

#     hist_frame_occ, x_edges, y_edges = numpy.histogram2d(longitude_frames, latitudes_frames, bins=bins, range=ranges)    
#     hist_flux, x_edges, y_edges = numpy.histogram2d(longitudes, latitudes, bins=bins, range=ranges, weights=fluxes)    

#     # to avoid division with zeros, only division with ge 2 is valid (0 and 1 has same effect)
#     hist_frame_occ[hist_frame_occ == 0] = 1  

#     # avarage over all frames - counts of frames in given bin of long & lat
#     hist_flux = hist_flux / hist_frame_occ

#     flux_list, x_edges_list, y_edges_list = convert_np_to_plt_hist2d(hist_flux, x_edges, y_edges)

#     fig, ax = plt.subplots(figsize=(10,6))        
#     hist2d_res = plot_longlatvar(x_edges_list, y_edges_list, flux_list, title=title, 
#                     z_label= "flux [cm-2 s-1]", fig=fig, ax=ax, z_max=None,
#                     z_min=None, bins=bins, do_save_json=do_save_json, file_json_path_name=file_json_path_name)    
#     plt.tight_layout()        
#     plt.savefig(file_fig_path_name)
#     plt.close()

#     return hist2d_res




def plot_phys_maps():

    dir_data_proc =     "/home/lukas/file/analysis/one_web/data/proc"
    dir_phys =          "/home/lukas/file/analysis/one_web/data/phys"

    dir_proc_dpe_name = "04_dpe"

    dirs_proc_data_name = sorted(list_dirs_of_dir(dir_data_proc))
    
    roi = [[62, 192], [62, 192]]

    bins = [180,90]    
    ranges = [[-180,180],[-90,90]]

    vars_max = [2e5, 200, 1e2, 5e-1]
    vars_min = [1e2, 5e-1, 1, 1e-4]

    does_coeff_kev_ugy, does_rate_coef_kev_ugy_h, flux_coeff = create_phys_factors(roi)

    vars_names = ["energy", "LET", "count", "dose"]
    vars_units = ["[keV]", "[kev/um]", "[-]", "[uGy]"]

    long_prot = []
    lat_prot = []

    e_prot=  []
    let_prot=  []
    n_prot=  []
    dose_prot = []
    dose_rate_prot = None
    flux_prot = [] 

    vars_prot = [e_prot, let_prot, n_prot, dose_prot]

    long_el = []
    lat_el = []

    e_el=  []
    let_el=  []
    n_el=  []
    dose_el = []
    dose_rate_el = None
    flux_el = [] 

    vars_el = [e_el, let_el, n_el, dose_el]

    clusters_ion_saa = []
    clusters_prot_saa = []
    clusters_el_saa = []

    clists = []

    for dir_proc_data_name in dirs_proc_data_name:

        dir_proc_dpe_data = os.path.join(dir_data_proc, dir_proc_data_name, dir_proc_dpe_name)
        clist = Clist(os.path.join(dir_proc_dpe_data, "File", "data_ext.clist"))
        clists.append(clist)


    # load
    for clist in clists:

        # maps
        long_prot.extend((clist.data.loc[clist.data['PIDClass'].isin([0,2]), 'GpsLong']).to_list())
        lat_prot.extend((clist.data.loc[clist.data['PIDClass'].isin([0,2]), 'GpsLat']).to_list())
        e_prot.extend((clist.data.loc[clist.data['PIDClass'].isin([0,2]), 'E']).to_list())
        let_prot.extend((clist.data.loc[clist.data['PIDClass'].isin([0,2]), 'LET']).to_list())
        n_prot.extend([1]*len(clist.data.loc[clist.data['PIDClass'].isin([0,2]), 'GpsLong']))
        dose_prot.extend(((clist.data.loc[clist.data['PIDClass'].isin([0,2]), 'E'])*does_coeff_kev_ugy).to_list())

        long_el.extend((clist.data.loc[clist.data['PIDClass'].isin([1]), 'GpsLong']).to_list())
        lat_el.extend((clist.data.loc[clist.data['PIDClass'].isin([1]), 'GpsLat']).to_list())
        e_el.extend((clist.data.loc[clist.data['PIDClass'].isin([1]), 'E']).to_list())
        let_el.extend((clist.data.loc[clist.data['PIDClass'].isin([1]), 'LET']).to_list())
        n_el.extend([1]*len(clist.data.loc[clist.data['PIDClass'].isin([1]), 'GpsLong']))
        dose_el.extend(((clist.data.loc[clist.data['PIDClass'].isin([1]), 'E'])*does_coeff_kev_ugy).to_list())

        # clusters
        clusters_ion_saa.extend((clist.data.loc[clist.data['PIDClass'].isin([2]), 'ClusterPixels']).to_list())        
        clusters_prot_saa.extend((clist.data.loc[clist.data['PIDClass'].isin([0]), 'ClusterPixels']).to_list())
        clusters_el_saa.extend((clist.data.loc[clist.data['PIDClass'].isin([1]), 'ClusterPixels']).to_list())

    # # plot
    # plot_flux_map(clists, [0,1,2],  dir_phys, "flux of all particles", "map_flux_all",bins, ranges,roi, do_save_json=True)
    # plot_flux_map(clists, [0,2],    dir_phys, "flux of protons and ions", "map_flux_protons_ions",bins, ranges,roi, do_save_json=True)
    # plot_flux_map(clists, [1],      dir_phys, "flux of electrons and photons", "map_flux_electrons_photons",bins, ranges,roi, do_save_json=True)
    # plot_flux_map(clists, [2],      dir_phys, "flux of ions", "map_flux_ions",bins, ranges,roi, do_save_json=True)
    # plot_flux_map(clists, [0],      dir_phys, "flux of protons", "map_flux_protons",bins, ranges,roi, do_save_json=True)

    # for idx, var_prot in enumerate(vars_prot):
    #     if var_prot is None:
    #         continue

    #     name_out = "map_" + vars_names[idx] + "_protons"
    #     file_fig_path_name = os.path.join(dir_phys, name_out + ".png")
    #     file_json_path_name = os.path.join(dir_phys, name_out + ".json")

    #     fig, ax = plt.subplots(figsize=(10,6))        
    #     plot_longlatvar(long_prot, lat_prot, var_prot, title="map of protons " + vars_names[idx], 
    #                     z_label= vars_names[idx] + " " + vars_units[idx], fig=fig, ax=ax,
    #                     do_save_json=True, file_json_path_name=file_json_path_name, font_color="white")
    #     plt.tight_layout()        
    #     plt.savefig(file_fig_path_name, transparent=True, dpi=600)
    #     plt.close()



    # for idx, var_el in enumerate(vars_el):
    #     if var_el is None:
    #         continue

    #     name_out = "map_" + vars_names[idx] + "_electrons"
    #     file_fig_path_name = os.path.join(dir_phys, name_out + ".png")
    #     file_json_path_name = os.path.join(dir_phys, name_out + ".json")

    #     fig, ax = plt.subplots(figsize=(10,6))        
    #     plot_longlatvar(long_el, lat_el, var_el, title="map of electrons and photons " + vars_names[idx], 
    #                     z_label= vars_names[idx] + " " + vars_units[idx], fig=fig, ax=ax,
    #                     do_save_json=True, file_json_path_name=file_json_path_name, font_color="white")
    #     plt.tight_layout()        
    #     plt.savefig(file_fig_path_name, transparent=True, dpi=600)
    #     plt.close()


    # clusters
    fig, axes = plt.subplots(1,3,figsize=(25,7))
    plot_clusters(clusters_prot_saa, 50, fig=fig,ax=axes[0], title="visulisation of protons", 
                    z_label="E [keV]", do_show=False)
    plot_clusters(clusters_el_saa, 100, fig=fig,ax=axes[1], title="visulisation of electrons and photons", 
                    z_label="E [keV]", do_show=False)
    plot_clusters(clusters_ion_saa, 15, fig=fig,ax=axes[2], title="visulisation of ions", 
                    z_label="E [keV]", do_show=False)    
    plt.tight_layout()
    plt.savefig(os.path.join(dir_phys, "cluster_visual.png"), transparent=True, dpi=600)
    plt.close()    


if __name__ == "__main__":

    clists = []

    plot_phys_maps()
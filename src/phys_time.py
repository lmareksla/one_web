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

def drop_data_zero(data_and_keys):

    data_y_all = data_and_keys[1][1]

    non_zero_indices = [i for i, value in enumerate(data_y_all) if value != 0]
    
    for idx, data_and_keys_list in enumerate(data_and_keys):
        data_and_keys[idx][0] = [data_and_keys_list[0][i] for i in non_zero_indices]
        data_and_keys[idx][1] = [data_and_keys_list[1][i] for i in non_zero_indices]


def export_and_plot_time_data(data_and_keys,
                              label_x, label_y, title,
                              do_drop_zero=True,
                              fig=None, ax=None, 
                              do_log_y=False, do_log_oposite=False,
                              file_fig_path_name="", file_fig_opp_log_path_name="",
                              file_json_path_name=""):

    if not fig or not ax:
        fig, ax = plt.subplots(figsize=(15,7))

    if do_drop_zero:
        drop_data_zero(data_and_keys)

    file_fig_path_name_base, suffix = os.path.splitext(file_fig_path_name) 
    file_fig_opp_log_path_name_base, suffix_op =  os.path.splitext(file_fig_opp_log_path_name) 

    plot_time_graphs_lines(data_and_keys, label_x=label_x, label_y=label_y,
                    title=title, fig=fig, ax=ax,
                    do_log_y=do_log_y,
                    file_fig_path_name=file_fig_path_name_base + "_l" + suffix, do_save_fig=True)

    plot_time_graphs_markers(data_and_keys, label_x=label_x, label_y=label_y,
                    title=title, fig=fig, ax=ax,
                    do_log_y=do_log_y,
                    file_fig_path_name=file_fig_path_name_base + "_m" + suffix, do_save_fig=True)    

    if do_log_oposite:
        plot_time_graphs_lines(data_and_keys, label_x=label_x, label_y=label_y,
                        title=title, fig=fig, ax=ax,
                        do_log_y=not do_log_y,
                        file_fig_path_name=file_fig_opp_log_path_name_base + "_l" + suffix_op, do_save_fig=True)        

        plot_time_graphs_markers(data_and_keys, label_x=label_x, label_y=label_y,
                        title=title, fig=fig, ax=ax,
                        do_log_y=not do_log_y,
                        file_fig_path_name=file_fig_opp_log_path_name_base + "_m" + suffix_op, do_save_fig=True)        


    if len(file_json_path_name) != 0:
        format_str='%Y-%m-%d %H:%M:%S'
        for idx in range(len(data_and_keys)):
            if isinstance(data_and_keys[idx][0][0], datetime.datetime):
                list_datatime_str = []
                for item in data_and_keys[idx][0]:
                    list_datatime_str.append(item.strftime(format_str))
                data_and_keys[idx][0] = list_datatime_str
            else:
                data_and_keys[idx][0] = list(data_and_keys[idx][0]) 
            data_and_keys[idx][1] = list(data_and_keys[idx][1]) 


        export_graphs(file_json_path_name,
                      data_and_keys, 
                      label_x=label_x, label_y=label_y,
                      title=title)



def create_frame_list(clists : list, file_out_path_name : str):
    
    frame_list_file = open(file_out_path_name, "w")
    delim = "\t"
    header =    f"FrameID{delim}T{delim}TAcq{delim}GpsLong{delim}GpsLat{delim}GpsAlt{delim}" \
                f"CountAll{delim}CountProt{delim}CountElec{delim}" \
                f"EnergyAll{delim}EnergyProt{delim}EnergyElec{delim}" \
                f"FluxAll{delim}FluxProt{delim}FluxElec{delim}" \
                f"DoseAll{delim}DoseProt{delim}DoseElec{delim}" \
                f"DoseRateAll{delim}DoseRateProt{delim}DoseRateElec{delim}" \
                f"LETAll{delim}LETProt{delim}LETElec{delim}" \

    frame_list_file.write(header + "\n")

    doses = doses_prot = doses_el = 0
    let = let_prot = let_el = 0
    count = count_prot = count_el = 0
    e = e_prot = e_el = 0
    flux = flux_prot = flux_el = 0
    dr = dr_prot = dr_el = 0

    frame_id_sum = 0
    frame_id_prev = clists[0].data.loc[0, "Flags"]

    does_coeff_kev_ugy, does_rate_coef_kev_ugy_h, flux_coeff = create_phys_factors(roi)

    for jdx ,clist in enumerate(clists):
        progress_bar(len(clists), jdx+1)
        
        for idx, row in clist.data.iterrows():
            

            frame_id_curr = row["Flags"]

            if frame_id_curr == frame_id_prev:

                doses += row["E"]*does_coeff_kev_ugy
                let += row["LET"]
                count += 1
                e += row["E"]

                if row["PIDClass"] in [0,2]:
                    doses_prot += row["E"]*does_coeff_kev_ugy
                    let_prot += row["LET"]
                    count_prot += 1
                    e_prot += row["E"]

                elif row["PIDClass"] in [1]:
                    doses_el += row["E"]*does_coeff_kev_ugy
                    let_el += row["LET"]
                    count_el += 1
                    e_el += row["E"]

            else:
                flux = flux_coeff*(count/time_acq)
                dr = does_rate_coef_kev_ugy_h*(e/time_acq)

                flux_prot = flux_coeff*(count_prot/time_acq)
                dr_prot = does_rate_coef_kev_ugy_h*(e_prot/time_acq)

                flux_el = flux_coeff*(count_el/time_acq)
                dr_el = does_rate_coef_kev_ugy_h*(e_el/time_acq)

                # export
                data_str = (
                    f"{frame_id_sum}{delim}{t_curr}{delim}{time_acq}{delim}{gps_long:g}{delim}{gps_lat:g}{delim}{gps_alt:g}{delim}"
                    f"{count:g}{delim}{count_prot:g}{delim}{count_el:g}{delim}"
                    f"{e:g}{delim}{e_prot:g}{delim}{e_el:g}{delim}"
                    f"{flux:g}{delim}{flux_prot:g}{delim}{flux_el:g}{delim}"
                    f"{doses:g}{delim}{doses_prot:g}{delim}{doses_el:g}{delim}"
                    f"{dr:g}{delim}{dr_prot:g}{delim}{dr_el:g}{delim}"
                    f"{let:g}{delim}{let_prot:g}{delim}{let_el:g}{delim}"
                )

                                                                                                                                            
                frame_list_file.write(data_str + "\n")

                doses = doses_prot = doses_el = 0
                let = let_prot = let_el = 0
                count = count_prot = count_el = 0
                e = e_prot = e_el = 0
                flux = flux_prot = flux_el = 0
                dr = dr_prot = dr_el = 0
                times = time_acq = frame_count = 0

                frame_id_sum += 1
                frame_id_prev = frame_id_curr


            gps_long = row["GpsLong"]
            gps_lat = row["GpsLat"]
            gps_alt = row["GpsAlt"]
            t_curr = row["T"]
            time_acq = row["TAcq"]

    frame_list_file.close()


def process_frame_list(frame_list_path_name : str):
    """
    Time sampling with interpolation and other data adjustment.
    """

    frame_list = pd.read_csv(frame_list_path_name, sep="\t")

    time_min = 1706742000
    time_max = 1709161140

    frame_drs = { "time" : [], "all" : [], "elph" : [], "ionpr" : []}

    count = 0

    for idx, row in frame_list.iterrows():

        # FrameID T   TAcq    GpsLong GpsLat  GpsAlt  CountAll    CountProt   CountElec   EnergyAll   EnergyProt  
        # EnergyElec  FluxAll FluxProt    FluxElec    DoseAll DoseProt    DoseElec    DoseRateAll DoseRateProt    DoseRateElec LETAll  LETProt LETElec 


        time = row["T"]
        time_acq = row["TAcq"] 

        if time < time_min:
            continue

        if time > time_max:
            break

        if row["DoseRateAll"] == 0 or row["DoseRateElec"] == 0 or row["DoseRateProt"] == 0:
            continue

        count += 1
        frame_drs["time"].append(time)
        frame_drs["all"].append(row["DoseRateAll"])
        frame_drs["elph"].append(row["DoseRateElec"])
        frame_drs["ionpr"].append(row["DoseRateProt"])

    print(f"count {count}")


    date_times_unix = [datetime.datetime.utcfromtimestamp(ts) for ts in frame_drs["time"]]

    fig, axs = plt.subplots(2,1, figsize=(18,8))

    data_and_keys = [   [date_times_unix, frame_drs["all"], "time", "all"],
                        [date_times_unix, frame_drs["elph"], "time", "electrons & photons"],
                        [date_times_unix, frame_drs["ionpr"], "time", "protons & ions"]]

    plot_time_graphs_lines(data_and_keys, fig=fig, ax=axs[0], do_log_y=False)
    plot_time_graphs_lines([[date_times_unix, frame_drs["elph"], "time", "electrons & photons"]], fig=fig, ax=axs[1], do_log_y=False)
    plt.show()

    # data_and_keys, 
    # label_x="", label_y="", title="",
    # fig=None, ax=None, 
    # do_log_y=False,
    # file_fig_path_name="", do_save_fig=False,
    # do_show=False):

def plot_phys_time(clist : list, time_samplings_hours : list, dir_phys : str):

    does_coeff_kev_ugy, does_rate_coef_kev_ugy_h, flux_coeff = create_phys_factors(roi)

    for t_sampling_hour in time_samplings_hours:

        dir_phys_time = os.path.join(dir_phys, str(t_sampling_hour))
        print(dir_phys_time)
        os.makedirs(dir_phys_time, exist_ok=True) 

        # time plots

        time_unix_prot = []
        time_unix_el = []

        t_sampling = t_sampling_hour*3600  # in seconds
        t_first = clists[0].data.loc[0, "T"]
        t_next_sample = t_first + t_sampling
        frame_id_prev = clists[0].data.loc[0, "Flags"]

        start = time.time()

        doses_sample = [0]
        doses_prot_sample = [0]
        doses_el_sample = [0]

        let_sample = [0]
        let_prot_sample = [0]
        let_el_sample = [0]

        count_sample = [0]
        count_prot_sample = [0]
        count_el_sample = [0]

        e_sample = [0]
        e_prot_sample = [0]
        e_el_sample = [0]

        flux_sample = [0]
        flux_prot_sample = [0]
        flux_el_sample = [0]

        dr_sample = [0]
        dr_prot_sample = [0]
        dr_el_sample = [0]

        times_sample = [0]
        time_acq_sample = [0]
        frame_count_sample = [0]

        for jdx ,clist in enumerate(clists):
            progress_bar(len(clists), jdx+1)
            
            for idx, row in clist.data.iterrows():
                
                t_curr = row["T"]
                frame_id_curr = row["Flags"]

                if t_curr > t_next_sample:

                    while t_curr > t_next_sample:
                        t_next_sample += t_sampling


                        # evaluate time dependable variables
                        if e_sample[-1] != 0:

                            flux_sample[-1] = flux_coeff*(count_sample[-1]/time_acq_sample[-1])
                            dr_sample[-1] = does_rate_coef_kev_ugy_h*(e_sample[-1]/time_acq_sample[-1])

                            flux_prot_sample[-1] = flux_coeff*(count_prot_sample[-1]/time_acq_sample[-1])
                            dr_prot_sample[-1] = does_rate_coef_kev_ugy_h*(e_prot_sample[-1]/time_acq_sample[-1])

                            flux_el_sample[-1] = flux_coeff*(count_el_sample[-1]/time_acq_sample[-1])
                            dr_el_sample[-1] = does_rate_coef_kev_ugy_h*(e_el_sample[-1]/time_acq_sample[-1])


                        # append new values for next sample
                        doses_sample.append(0)
                        doses_prot_sample.append(0)
                        doses_el_sample.append(0)

                        let_sample.append(0)
                        let_prot_sample.append(0)
                        let_el_sample.append(0)          

                        count_sample.append(0)
                        count_prot_sample.append(0)
                        count_el_sample.append(0)  

                        e_sample.append(0)
                        e_prot_sample.append(0)
                        e_el_sample.append(0)  

                        flux_sample.append(0)
                        flux_prot_sample.append(0)
                        flux_el_sample.append(0)   

                        dr_sample.append(0)
                        dr_prot_sample.append(0)
                        dr_el_sample.append(0)   

                        time_acq_sample.append(0)
                        frame_count_sample.append(0)

                # increase values in current sample
                else:

                    doses_sample[-1] += row["E"]*does_coeff_kev_ugy
                    let_sample[-1] += row["LET"]
                    count_sample[-1] += 1
                    e_sample[-1] += row["E"]

                    if row["PIDClass"] in [0,2]:
                        doses_prot_sample[-1] += row["E"]*does_coeff_kev_ugy
                        let_prot_sample[-1] += row["LET"]
                        count_prot_sample[-1] += 1
                        e_prot_sample[-1] += row["E"]

                    elif row["PIDClass"] in [1]:
                        doses_el_sample[-1] += row["E"]*does_coeff_kev_ugy
                        let_el_sample[-1] += row["LET"]
                        count_el_sample[-1] += 1
                        e_el_sample[-1] += row["E"]


                    # frames dependable variables
                    if frame_id_curr != frame_id_prev:
                        time_acq_sample[-1] += row["TAcq"]
                        frame_count_sample[-1] += 1
                        frame_id_prev = frame_id_curr


        for idx in range(len(doses_sample)-1):
            times_sample.append(times_sample[-1]+t_sampling)

        doses_sample = np.array(doses_sample)
        times_sample  = np.array(times_sample)
        time_acq_sample = np.array(time_acq_sample) 
        flux_sample = np.array(flux_sample) 
        frame_count_sample = np.array(frame_count_sample)

        # to skip division by zero
        time_acq_sample_no_zero = copy.deepcopy(time_acq_sample)
        time_acq_sample_no_zero[time_acq_sample_no_zero == 0] = 1

        time_acq_scaling = [t_sampling]*len(time_acq_sample_no_zero)
        time_acq_scaling = np.array(time_acq_scaling)/time_acq_sample_no_zero

        time_unix_sample = times_sample + t_first
        datetime_objects = [datetime.datetime.utcfromtimestamp(ts) for ts in time_unix_sample]



        print(f"time to process all particles: {time.time() - start}")


        data_and_keys = [   [datetime_objects, doses_sample*time_acq_scaling, "time", "all"],
                            [datetime_objects, doses_el_sample*time_acq_scaling, "time", "electrons & photons"],
                            [datetime_objects, doses_prot_sample*time_acq_scaling, "time", "protons & ions"]]

        export_and_plot_time_data(  data_and_keys,
                                    label_x=f"time [samplig {t_sampling_hour} hours ]", label_y="dose [uGy]",
                                    title="Time evaluation of dose for all and individual particle classes",
                                    do_log_y=True, do_log_oposite=True,
                                    file_fig_path_name=os.path.join(dir_phys_time, "dose_sampling_time_log.png"),
                                    file_fig_opp_log_path_name= os.path.join(dir_phys_time, "dose_sampling_time_lin.png"),
                                    file_json_path_name=os.path.join(dir_phys_time, "dose_sampling_time.json"))


        data_and_keys = [   [datetime_objects, let_sample*time_acq_scaling, "time", "all"],
                            [datetime_objects, let_el_sample*time_acq_scaling, "time", "electrons & photons"],
                            [datetime_objects, let_prot_sample*time_acq_scaling, "time", "protons & ions"]]

        export_and_plot_time_data(  data_and_keys,
                                    label_x=f"time [samplig {t_sampling_hour} hours ]", label_y="LET [keV/um]",
                                    title="Time evaluation of LET for all and individual particle classes",
                                    do_log_y=True, do_log_oposite=True,
                                    file_fig_path_name=os.path.join(dir_phys_time, "let_sampling_time_log.png"),
                                    file_fig_opp_log_path_name= os.path.join(dir_phys_time, "let_sampling_time_lin.png"),
                                    file_json_path_name=os.path.join(dir_phys_time, "let_sampling_time.json"))


        data_and_keys = [   [datetime_objects, count_sample*time_acq_scaling, "time", "all"],
                            [datetime_objects, count_el_sample*time_acq_scaling, "time", "electrons & photons"],
                            [datetime_objects, count_prot_sample*time_acq_scaling, "time", "protons & ions"]]

        export_and_plot_time_data(  data_and_keys,
                                    label_x=f"time [samplig {t_sampling_hour} hours ]", label_y="count of particles [-]",
                                    title="Time evaluation of particle count for all and individual particle classes",
                                    do_log_y=True, do_log_oposite=True,
                                    file_fig_path_name=os.path.join(dir_phys_time, "count_sampling_time_log.png"),
                                    file_fig_opp_log_path_name= os.path.join(dir_phys_time, "count_sampling_time_lin.png"),
                                    file_json_path_name=os.path.join(dir_phys_time, "count_sampling_time.json"))


        data_and_keys = [   [datetime_objects, flux_sample, "time", "all"],
                            [datetime_objects, flux_el_sample, "time", "electrons & photons"],
                            [datetime_objects, flux_prot_sample, "time", "protons & ions"]]

        export_and_plot_time_data(  data_and_keys,
                                    label_x=f"time [samplig {t_sampling_hour} hours ]", label_y="flux [cm-2 s-1]",
                                    title="Time evaluation of flux for all and individual particle classes",
                                    do_log_y=True, do_log_oposite=True,
                                    file_fig_path_name=os.path.join(dir_phys_time, "flux_sampling_time_log.png"),
                                    file_fig_opp_log_path_name= os.path.join(dir_phys_time, "flux_sampling_time_lin.png"),
                                    file_json_path_name=os.path.join(dir_phys_time, "flux_sampling_time.json"))


        data_and_keys = [   [datetime_objects, dr_sample, "time", "all"],
                            [datetime_objects, dr_el_sample, "time", "electrons & photons"],
                            [datetime_objects, dr_prot_sample, "time", "protons & ions"]]

        export_and_plot_time_data(  data_and_keys,
                                    label_x=f"time [samplig {t_sampling_hour} hours ]", label_y="dose rate [uGy/h]",
                                    title="Time evaluation of dose rate for all and individual particle classes",
                                    do_log_y=True, do_log_oposite=True,
                                    file_fig_path_name=os.path.join(dir_phys_time, "dose_rate_sampling_time_log.png"),
                                    file_fig_opp_log_path_name= os.path.join(dir_phys_time, "dose_rate_sampling_time_lin.png"),
                                    file_json_path_name=os.path.join(dir_phys_time, "dose_rate_sampling_time.json"))



if __name__ == "__main__":

    dir_data_proc =     "/home/lukas/file/analysis/one_web/data/proc"
    dir_phys =          "/home/lukas/file/analysis/one_web/data/phys/"
    dir_phys_time =     os.path.join(dir_phys, "time")

    dir_proc_dpe_name = "04_dpe"

    frame_list_path_name = os.path.join(dir_phys, "frame_list.txt")

    roi = [[62, 192], [62, 192]]
    time_samplings_hours = [0.5]#[0.2,0.5, 1, 2, 4, 8, 12, 24]

    month =  "2024-02" #""

    do_load_clists =    True

    dirs_proc_data_name = sorted(list_dirs_of_dir(dir_data_proc))    

    if len(month) != 0:
        dir_phys_time += "_" + month
        os.makedirs(dir_phys_time, exist_ok=True)

    clists = []

    if do_load_clists: 
        for dir_proc_data_name in dirs_proc_data_name:
            if month not in dir_proc_data_name:
                continue
            dir_proc_dpe_data = os.path.join(dir_data_proc, dir_proc_data_name, dir_proc_dpe_name)
            clist = Clist(os.path.join(dir_proc_dpe_data, "File", "data_ext.clist"))
            clists.append(clist)

    if len(clists) != 0:
        plot_phys_time(clists, time_samplings_hours, dir_phys_time)
        # create_frame_list(clists, frame_list_path_name)

    # process_frame_list(frame_list_path_name)
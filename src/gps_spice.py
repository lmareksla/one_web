
import os
import sys
import logging
import binascii
import csv
import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import math
from mpl_toolkits.mplot3d import Axes3D
import spiceypy as spice
import matplotlib.image as mpimg

sys.path.append("/src/")
from gps_file import *



spice.furnsh('./spice_kernels/earth_200101_990825_predict.bpc')
spice.furnsh('./spice_kernels/naif0012.tls')
spice.furnsh('./spice_kernels/de432s.bsp')
spice.furnsh('./spice_kernels/pck00010.tpc')

def transformation(matrix, vec):
    vec_trans = np.zeros(vec.shape)
    for idx, arr in enumerate(matrix):
        vec_trans[idx] = np.sum(arr*vec)
    return vec_trans

def transform_rec_lla(vec_ret):

    vec_altlonlat = spice.reclat(vec_ret)
    vec_altlonlat = np.array(vec_altlonlat)
    vec_altlonlat[0] /= 1000
    vec_altlonlat[0] -= 6378
    vec_altlonlat[1] *= 57.2957795
    vec_altlonlat[2] *= 57.2957795
    return vec_altlonlat

def transform_J2000_to_ITRF93_lla(vec_J2000, timestamp):
    et = spice.str2et(timestamp)
    matrix_rot = spice.pxform("J2000","ITRF93", et )
    vec_ITRF93 = transformation(matrix_rot, vec_J2000)
    vec_ITRF93_lla = transform_rec_lla(vec_ITRF93)
    return vec_ITRF93_lla



def plot_longlat(long_list_deg, lat_list_deg, color="C1", ax=None, fig=None):

    do_show = True
    if ax is None or fig is None:
        fig, ax = plt.subplots(figsize=(15,9))
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

if __name__ == '__main__':
    case = 3

    if case == 1:

        vec_J2000 = np.array([1.39445e+5,-3.11009e+6,-6.28008e+6])

        et = spice.str2et('2023-09-27T00:00:05.000')

        matrix_rot = spice.pxform("J2000","ITRF93", et )


        vec_ITRF93 = transformation(matrix_rot, vec_J2000)

        vec_ITRF93_lla = transform_rec_lla(vec_ITRF93)


        print(f"vec_J2000        {vec_J2000}")
        print(f"matrix_rot       {matrix_rot}")
        print(f"vec_ITRF93       {vec_ITRF93}")
        print(f"vec_ITRF93_lla   {vec_ITRF93_lla}")

    if case == 2:

        file_in_path_name = "./devel/data/dosimeter_gps_info.csv"

        gps_file = GpsFile(file_in_path_name)

        gps_file.load()

        alt_list_km = []
        long_list_deg = []
        lat_list_deg = []
        timestamp_list = []

        for row in gps_file.data.iterrows():
            vec_J2000 = np.array([row[1]["J2000_X (m)"], row[1]["J2000_Y (m)"], row[1]["J2000_Z (m)"]])

            timestamp = row[1]["TIME"]
            timestamp_list.append(timestamp)

            vec_ITRF93_lla = transform_J2000_to_ITRF93_lla(vec_J2000 ,timestamp)

            if timestamp == " 2023-09-27 17:09:24.000":
                print(f"{timestamp}\t{vec_J2000}\t{vec_ITRF93_lla}")
                print(row)

            # print("----")
            # print(f"altitude      {vec_ITRF93_lla[0]} km")        
            # print(f"longitude     {vec_ITRF93_lla[1]} deg")
            # print(f"latitude      {vec_ITRF93_lla[2]} deg")

            alt_list_km.append(vec_ITRF93_lla[0])
            long_list_deg.append(vec_ITRF93_lla[1])
            lat_list_deg.append(vec_ITRF93_lla[2])


        plot_longlat(long_list_deg, lat_list_deg)

    if case == 3:

        dirs_data_path_name = "/home/lukas/file/analysis/one_web/data/raw/"



        def load_dirs_data(dir_root_path, data_mask=None):
            dirs_data = []
            for root, dirs, files in os.walk(dir_root_path):
                for dir_name in dirs:
                    dir_path_name = os.path.join(root, dir_name)
                    dirs_data.append(dir_path_name)
            return dirs_data


        fig, ax = plt.subplots(figsize=(15, 9))

        dirs_data = load_dirs_data(dirs_data_path_name)


        for idx, dir_data in enumerate(dirs_data):
            print(dir_data)

            file_in_path_name = dir_data + "/dosimeter_gps_info.csv"

            gps_file = GpsFile(file_in_path_name)

            gps_file.load()


            alt_list_km = []
            long_list_deg = []
            lat_list_deg = []

            for row in gps_file.data.iterrows():
                vec_J2000 = np.array([row[1]["J2000_X (m)"], row[1]["J2000_Y (m)"], row[1]["J2000_Z (m)"]])

                timestamp = row[1]["TIME"]

                et = spice.str2et(timestamp)

                matrix_rot = spice.pxform("J2000","ITRF93", et )

                vec_ITRF93 = transformation(matrix_rot, vec_J2000)

                vec_ITRF93_lla = transform_rec_lla(vec_ITRF93)

                # print("----")
                # print(f"altitude      {vec_ITRF93_lla[0]} km")        
                # print(f"longitude     {vec_ITRF93_lla[1]} deg")
                # print(f"latitude      {vec_ITRF93_lla[2]} deg")

                alt_list_km.append(vec_ITRF93_lla[0])
                long_list_deg.append(vec_ITRF93_lla[1])
                lat_list_deg.append(vec_ITRF93_lla[2])

            plot_longlat(long_list_deg, lat_list_deg, fig=fig, ax=ax,color="C" + str(idx) )        

            # if idx == 4:
            #     break
        
        plt.show()        
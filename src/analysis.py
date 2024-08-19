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

sys.path.append("src/pydpe/src")

from clist import *
from cluster import *



def create_phys_factors(roi):
    sens_mat_dens = 2.3290
    sens_thick = 500
    sens_width = 256
    sens_height = 256
    pix_size = 55

    n_roi_pix = (roi[0][1] - roi[0][0])*(roi[1][1] - roi[1][0])

    mask_coef = (sens_width*sens_height)/n_roi_pix

    sens_area = (sens_width*pix_size * sens_height*pix_size)/1e8;
    sens_area /= mask_coef

    # dose_coeff_kev_gy =          mask_coef/(1.2373618279678e+09*sens_mat_dens*sens_thick)     
    does_coeff_kev_ugy =         mask_coef/(1.2373618279678e+03*sens_mat_dens*sens_thick)   
    does_rate_coef_kev_ugy_h =   3600.*does_coeff_kev_ugy    
    flux_coeff =                 1./sens_area        


    return does_coeff_kev_ugy, does_rate_coef_kev_ugy_h, flux_coeff

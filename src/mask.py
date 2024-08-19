import os
import sys
import logging
import binascii
import csv
import datetime
import copy

sys.path.append("src")

from utils import *
from data_file import *

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *
from log import *

sys.path.append("src/noisy_pixels/src")

from noisy_pixels import *


# mask for noisy pixels and other unwanted pixel responses
class Mask(object):
    """docstring for Mask"""
    def __init__(self, width=256, height=256, do_log=True, log_path="", log_name="log.txt"):
        super(Mask, self).__init__()
            
        self.height = height
        self.width = width            
            
        self.__init_default()

        self.roi = None

        self.noisy_pixel_finder = NoisyPixelFinder()
        self.finder_alg_name = "remove_max_std_diff"

        # log and print
        self.do_log = do_log
        self.do_print = True
        self.log_file_path = log_path
        self.log_file_name = log_name
        self.log_file = None

        try:
            self._open_log()
        except Exception as e:
            log_warning(f"failed to open log {os.path.join(self.log_file_path, self.log_file_name)}: {e}",
                        self.log_file, self.do_print, self.do_log)

    def __init_default(self):
        self.matrix = np.ones((self.height, self.width))              # actual mask, ones because it should be applied via multiplication
        self.matrix_noisy_pix = np.zeros((self.height, self.width))   # positions of noisy pixels in matrix
        self.noisy_pix_list = []                                      # list of noisy pixels
        self.done_create = False

    def __exit__(self, exc_type, exc_value, traceback):
        if self.log_file:
            self.log_file.close()        

    def _open_log(self):
        if self.do_log:
            self.log_file = open(os.path.join(self.log_file_path, self.log_file_name), "w")


    def _reset(self):
        self.__init_default()

    """
    creates mask based on input data
    """
    def create(self, frame_data, roi=None):
        if self.done_create:
            log_warning(f"Mask.create - mask already crated. It will be overwritten.", self.log_file, self.do_print, self.do_log)
            self._reset()

        self.roi = roi
        sum_frame = np.zeros((self.height, self.width))

        if frame_data is None:
            pass
        elif isinstance(frame_data, list) and len(frame_data) != 0 and isinstance(frame_data[0], np.ndarray):
            self._create_sum_frame(frame_data, sum_frame)

        elif isinstance(frame_data, np.ndarray):
            if not self._check_same_matrix_shape(sum_frame, frame_data):
                raise_runtime_error(f"Mask.create - shape check of matrices failed", self.log_file, self.do_print, self.do_log)
            sum_frame = frame_data
        
        else:
            raise_runtime_error(f"Mask.create - unsupported data format of frame_data", self.log_file, self.do_print, self.do_log)

        try:
            # noisy pixels
            if sum_frame.sum() != 0: 
                self.matrix_noisy_pix, self.noisy_pix_list, self.matrix = self.noisy_pixel_finder.find_noisy_pixels(sum_frame, self.finder_alg_name)
        
            # apply roi
            if self.roi is not None:
                self._apply_roi_on_mask()
        except Exception as e:
            raise_runtime_error(f"Mask.create - falied to use noisy pixels or roi: {e}", self.log_file, self.do_print, self.do_log)

        self.done_create = True

    def _create_sum_frame(self, frames : list, sum_frame : np.ndarray):
        if not frames:
            raise_runtime_error(f"Mask._create_sum_frame - empty frames", self.log_file, self.do_print, self.do_log)

        sum_frame = np.zeros((self.height, self.width))

        for frame in frames:

            if not self._check_same_matrix_shape(sum_frame, frame):
                log_warning(f"Mask._create_sum_frame - frames has different shapes", self.log_file, self.do_print, self.do_log)
                continue

            sum_frame += frame

    def _check_same_matrix_shape(self, matrix_a : np.ndarray, matrix_b : np.ndarray):
        if matrix_a.shape != matrix_b.shape:
            return False
        else:
            return True

    def _apply_roi_on_mask(self):
        if not _check_roi(self.roi):
            return

        roi_x = self.roi[0]
        roi_y = self.roi[1]

        for j in range(256):
            for i in range(256):   
                if j <= roi_x[0] or j >= roi_x[1]:
                    self.__add_noisy_pixel(j,i)
                if i <= roi_y[0] or i >= roi_y[1]:
                    self.__add_noisy_pixel(j,i)

    def _check_roi(self, roi):
        if roi is None:
            log_error(f"Mask._apply_roi_on_mask - roi is None", self.log_file, self.do_print, self.do_log)
            return True

        elif len(roi) != 2 or len(roi[0]) != 2 or len(roi[1]) != 2:
            log_error(f"Mask._apply_roi_on_mask - incorrect shape of roi: {roi}", self.log_file, self.do_print, self.do_log)            
            return True

        elif roi[0][0] > roi[0][1] or roi[1][0] > roi[1][1]:
            log_error(f"Mask._apply_roi_on_mask - wrong values of roi: {roi}", self.log_file, self.do_print, self.do_log)            
            return True
        else:
            return True

    """
    application of mask on list of matrices or on matrix
    this input is permanently changed
    """
    def apply(self, frame_data):
        if not self.done_create:
            raise_runtime_error(f"Mask.apply - can not be used because mask was not created", self.log_file, self.do_print, self.do_log)

        if isinstance(frame_data, list):
            for matrix in frame_data:
                if isinstance(matrix, np.ndarray) and self._check_same_matrix_shape(self.matrix, matrix):
                    matrix *= self.matrix

        elif isinstance(frame_data, np.ndarray):
            if not self._check_same_matrix_shape(self.matrix, frame_data):
                raise_runtime_error(f"Mask.create - shape check of matrices failed", self.log_file, self.do_print, self.do_log)
            frame_data *= self.matrix

        elif isinstance(frame_data, Frame):
            self.apply_on_frame(frame_data)

        else:
            raise_runtime_error(f"Mask.create - unsupported data format of frame_data", self.log_file, self.do_print, self.do_log)

    def apply_on_frame(self, frame : Frame):
        if not frame.matrix:
            raise_runtime_error(f"Mask.apply_on_frame - no matrix in frame", self.log_file, self.do_print, self.do_log)

        if self.width != frame.width or self.height != frame.height:
            raise_runtime_error(f"Mask.apply_on_frame - incorrect shapes, frame: {frame.width}{frame.height}", 
                                    self.log_file, self.do_print, self.do_log)

        for mode, matrix in frame.matrix.items():
            matrix *= self.matrix

    """
    excepts list of sum frames = sum of all frames in the measurement over over all set of measurements
    applies noisy pixel search algorithms on each of them to receive individual maps of noisy pixels/masks
    find most frequent noisy pixels = fixed patter mask
    min_noisy_pix_occurance states what is the minimal occurrence of pixel over all maps to be accepted as part of a final pattern
    if not set, then default of 80 percent of cases/len(sum_frames)
    """
    def create_fixed_pattern(self, sum_frames : list, min_noisy_pix_occurance=0, use_roi=True, roi=None):
        for sum_frame in sum_frames:
            if not self._check_same_matrix_shape(sum_frame, self.matrix):
                raise_runtime_error(f"Mask.create_fixed_pattern - frames has different shapes {sum_frame.shape} and {self.matrix.shape}"
                                    , self.log_file, self.do_print, self.do_log)

        if self.done_create:
            log_warning(f"Mask.create_fixed_pattern - mask already crated. It will be overwritten.", self.log_file, self.do_print, self.do_log)
            self._reset()

        # roi settings and check
        if use_roi and roi is None:
            if self.roi is not None:
                roi = self.roi
            else:
                use_roi = False

        if use_roi and not self._check_roi(roi):
            use_roi = False

        if min_noisy_pix_occurance <= 0:
            min_noisy_pix_occurance = len(sum_frames)*0.8

        matrix_noisy_pix_sum = np.zeros((self.height, self.width))
        for sum_frame in sum_frames:
            matrix_noisy_pix, noisy_pix_list, matrix = self.noisy_pixel_finder.find_noisy_pixels(sum_frame, self.finder_alg_name)
            matrix_noisy_pix_sum += matrix_noisy_pix

        # remove small occurance of noisy pixels in other data
        matrix_noisy_pix_sum[(matrix_noisy_pix_sum < min_noisy_pix_occurance)] = 0
        matrix_noisy_pix_sum[(matrix_noisy_pix_sum >= 1)] = 1

        if use_roi:
            self._apply_roi_on_noisy_pix_matrix(matrix_noisy_pix_sum, roi, roi_value=1)

        # create fixed patter mask and return
        self.matrix_noisy_pix = matrix_noisy_pix_sum
        self.roi = roi
        self._extract_noisy_pixel_list_from_matrix(self.noisy_pix_list, 1, self.matrix_noisy_pix)
        self._extact_mask_from_noisy_pixel_matrix(self.matrix, self.matrix_noisy_pix) 
        self.done_create = True

    """applies roi on matrix assigning those pixels given roi_value"""
    def _apply_roi_on_noisy_pix_matrix(self, matrix, roi, roi_value):
        roi_x = roi[0]
        roi_y = roi[1]

        for j in range(self.width):
            for i in range(self.height):   
                if j < roi_x[0] or j > roi_x[1]:
                    matrix[j,i] = roi_value
                if i < roi_y[0] or i > roi_y[1]:
                    matrix[j,i] = roi_value

    """
    extracts noisy pixel list from matrix, either from mask or matrix of noisy pixel
    noisy_pix_value - should tell what is the value of noisy pixel in matrix
    """
    def _extract_noisy_pixel_list_from_matrix(self, noisy_pix_list, noisy_pix_value, matrix):
        noisy_pix_list.clear()
        for j in range(self.height):
            for i in range(self.width):
                if matrix[j, i] == noisy_pix_value:
                    noisy_pix_list.append([i,j]) #reversed i=x and j=y   
                    
    """extracts mask from noisy pixel positions"""
    def _extact_mask_from_noisy_pixel_matrix(self, matrix_mask, matrix_noisy_pix):
        matrix_mask[:] = 1
        for j in range(self.height):
            for i in range(self.width):
                if matrix_noisy_pix[j, i] == 1:
                    matrix_mask[j,i] = 0


    def add(self, mask_data):

        if isinstance(mask_data, Mask):
            self.__add_mask(mask_data)
        elif isinstance(mask_data, list) and len(mask_data) == 2 and \
            isinstance(mask_data[0], int) and isinstance(mask_data[1], int): 
            self.__add_noisy_pixel(mask_data[0], mask_data[1])
        else:
            log_error(f"Mask.add - can not add mask_data because they are in unsupported data type", self.log_file, self.do_print, self.do_log)

    def __add_mask(self, mask):

        if mask.width != self.width or mask.height != self.height:
            raise_runtime_error(f"Mask.__add_mask - can not add two masks because they have different shapes", 
                                    self.log_file, self.do_print, self.do_log)

        self.matrix *=  mask.matrix
        self.matrix_noisy_pix += mask.matrix_noisy_pix
        self.matrix_noisy_pix[(self.matrix_noisy_pix > 1)] = 1    
        self._extract_noisy_pixel_list_from_matrix(self.noisy_pix_list, 1, self.matrix_noisy_pix)

    def __add_noisy_pixel(self, x, y):
        self.matrix[y,x] = 0
        self.matrix_noisy_pix[y,x] = 1
        self.noisy_pix_list.append([x,y])

    def set_std_differential_limit(self, value):
        self.noisy_pixel_finder.std_differential_limit = value

    def export(self, file_out_path_name, delimiter = " "):
        np.savetxt(file_out_path_name, self.matrix, fmt='%g',  delimiter=" ")

    def load(self, file_in_path_name, delimiter=" "):
        self.matrix = np.loadtxt(file_in_path_name, delimiter=delimiter)

    def get_count_noisy_pix(self):
        """count of noisy pixels"""
        count_noisy_pix = len(self.noisy_pix_list)
        if self.roi is not None:
            roi_pixel_count = (self.roi[0][1]-self.roi[0][0] + 1)*(self.roi[1][1]-self.roi[1][0] + 1)
            not_roi_pixel_count = self.width*self.height - roi_pixel_count
            count_noisy_pix -= not_roi_pixel_count
        return count_noisy_pix

if __name__ == '__main__':

    case = 4

    # inserting sum frame of tot and count
    if case == 1:
        
        # =============================================
        # load data
        # =============================================

        dir_data = "./devel/data/"
        data_file = DataFile(dir_data + "dosimeter_image_packets.csv")
        data_file.load()

        mask_tot = Mask()
        mask_count = Mask()

        sum_frame_count = np.zeros((256,256))
        sum_frame_tot = np.zeros((256,256))

        for frame in data_file.frames:
            sum_frame_tot += frame.get_matrix(Tpx3Mode.TOT)
            sum_frame_count += frame.get_matrix(Tpx3Mode.COUNT)

        def plot_matrices_overview(matrix_a, matrix_b):
            fig, axs = plt.subplots(2,3, figsize=(15,8))
            plot_matrix_hist(matrix_a, fig=fig, ax=axs[0,0], do_show_meas_std_lines=True)
            plot_matrix(matrix_a, do_log=True,  fig=fig, ax=axs[0,1])
            plot_matrix(matrix_a, do_log=False,  fig=fig, ax=axs[0,2])        
            plot_matrix_hist(matrix_b, fig=fig, ax=axs[1,0], do_show_meas_std_lines=True)
            plot_matrix(matrix_b, do_log=True,  fig=fig, ax=axs[1,1])
            plot_matrix(matrix_b, do_log=False,  fig=fig, ax=axs[1,2])        
            plt.tight_layout()
            plt.show()

        # =============================================
        # cut out only region of interest
        # =============================================
 
        roi_x_min = 63
        roi_x_max = 191
        roi_y_min = 63
        roi_y_max = 191

        def cut_roi_from_matrix(matrix : np.ndarray, roi_x=[roi_x_min, roi_x_max], roi_y=[roi_y_min, roi_y_max]):
            roi_x_range = roi_x_max - roi_x_min
            roi_y_range = roi_y_max - roi_y_min
            matrix_roi = matrix[roi_y[0]:roi_y[1], roi_x[0]:roi_x[1]]
            # plot_matrix(matrix_roi)
            # plt.show()
            return matrix_roi


        sum_frame_tot_roi = cut_roi_from_matrix(sum_frame_tot, roi_x=[roi_x_min, roi_x_max], roi_y=[roi_y_min, roi_y_max])
        sum_frame_count_roi = cut_roi_from_matrix(sum_frame_count, roi_x=[roi_x_min, roi_x_max], roi_y=[roi_y_min, roi_y_max])

        # plot_matrices_overview(sum_frame_tot_roi, sum_frame_count_roi)

        print(f" ")
        print(f"INFO")        
        print(f" ")
        print(f"mean tot                 {sum_frame_tot.mean():.2f}")
        print(f"std tot                  {sum_frame_tot.std():.2f}")
        print(f"rel std tot              {100.*sum_frame_tot.std()/sum_frame_tot.mean():.2f} %")  
        print(f" ")              
        print(f"mean tot non0            {mean_non_zero(sum_frame_tot):.2f}")
        print(f"std tot non0             {std_non_zero(sum_frame_tot):.2f}")
        print(f"rel std tot non 0        {100.*std_non_zero(sum_frame_tot)/mean_non_zero(sum_frame_tot):.2f} %")               
        print(f"\n")
        print(f"mean count               {sum_frame_count.mean():.2f}")
        print(f"std count                {sum_frame_count.std():.2f}")
        print(f"rel std count            {100.*sum_frame_count.std()/sum_frame_count.mean():.2f} %") 
        print(f" ")              
        print(f"mean tot non0            {mean_non_zero(sum_frame_count):.2f}")
        print(f"std tot non0             {std_non_zero(sum_frame_count):.2f}")
        print(f"rel std tot non 0        {100.*std_non_zero(sum_frame_count)/mean_non_zero(sum_frame_count):.2f} %")        

        # =============================================
        # masking
        # =============================================

        def remove_n_max_pixels(matrix, n_pix=3):
            # Flatten the matrix and get the indices of the n largest elements
            flat_indices = np.argsort(matrix.flatten())[-n_pix:]

            # Convert the flat indices to 2D indices
            row_indices, col_indices = np.unravel_index(flat_indices, matrix.shape)

            # Replace the n largest elements with 0
            matrix[row_indices, col_indices] = 0   

            return row_indices, col_indices

        def normalize_list(input_list, norm):
            norm_list = [x / norm for x in input_list]
            return norm_list

        n_step = 100
        n_pixels_remove = 1

        steps = []
        std_rels_tot = []
        std_rels_count = []

        std_tot = []
        std_count = []

        max_tot = []
        max_count = []

        mean_tot = []
        mean_count = []

        sum_frame_count_orig = copy.deepcopy(sum_frame_count)

        for idx in range(n_step):

            steps.append(n_pixels_remove + idx*n_pixels_remove)
            remove_n_max_pixels(sum_frame_tot, n_pixels_remove)
            remove_n_max_pixels(sum_frame_count, n_pixels_remove)

            std_rels_tot.append(rel_std_non_zero(sum_frame_tot))
            std_rels_count.append(rel_std_non_zero(sum_frame_count))

            std_tot.append(std_non_zero(sum_frame_tot))
            std_count.append(std_non_zero(sum_frame_count))

            max_tot.append(sum_frame_tot.max())
            max_count.append(sum_frame_count.max())

            mean_tot.append(mean_non_zero(sum_frame_tot))
            mean_count.append(mean_non_zero(sum_frame_count))                        

        std_count_orig = std_count

        std_rels_tot = normalize_list(std_rels_tot, std_rels_tot[-1])
        std_rels_count = normalize_list(std_rels_count, std_rels_count[-1])
        std_tot = normalize_list(std_tot, std_tot[-1])
        std_count = normalize_list(std_count, std_count[-1])
        max_tot = normalize_list(max_tot, max_tot[-1])
        max_count = normalize_list(max_count, max_count[-1])
        mean_tot = normalize_list(mean_tot, mean_tot[-1])
        mean_count = normalize_list(mean_count, mean_count[-1])        

        # fig, axs = plt.subplots(1,4, figsize=(20,6))
        # axs[0].plot(steps, std_rels_tot, color="C0", label="std_rel")
        # axs[0].plot(steps, std_tot, color="C1", label="std")
        # axs[0].plot(steps, max_tot, color="C2", label="max")
        # axs[0].plot(steps, mean_tot, color="C3", label="mean")
        # axs[0].set_title("tot")
        # # axs[0].set_yscale('log')      
        # axs[0].legend()       
        # axs[0].grid(alpha=0.5, linestyle='--', linewidth=0.5, which='both')   
        # axs[0].set_xlabel("count of removed maximal pixels")           

        # axs[1].plot(steps, std_rels_count, color="C0", label="std_rel")
        # axs[1].plot(steps, std_count, color="C1", label="std")
        # axs[1].plot(steps, max_count, color="C2", label="max")
        # axs[1].plot(steps, mean_count, color="C3", label="mean")        
        # axs[1].set_title("count")
        # # axs[1].set_yscale('log')   
        # axs[1].legend() 
        # axs[1].grid(alpha=0.5, linestyle='--', linewidth=0.5, which='both')
        # axs[1].set_xlabel("count of removed maximal pixels")        

        # axs[2].plot(steps, std_tot, color="C1", label="std_tot")      
        # axs[2].plot(steps, std_count, color="C0", label="std_count")      
        # axs[2].set_title("count")
        # axs[2].set_yscale('log')   
        # axs[2].legend() 
        # axs[2].grid(alpha=0.5, linestyle='--', linewidth=0.5, which='both')
        # axs[2].set_xlabel("count of removed maximal pixels") 

        # axs[3].plot(steps, std_count, color="C0", label="std_count")      
        # axs[3].set_title("count")
        # # axs[3].set_yscale('log')   
        # axs[3].legend() 
        # axs[3].grid(alpha=0.5, linestyle='--', linewidth=0.5, which='both')
        # axs[3].set_xlabel("count of removed maximal pixels") 

        # plt.show()

        # =============================================
        # investigate counts
        # =============================================

        def create_differential_list(val_list):
            diff_val_list = []

            for idx in range(len(val_list)-1):
                diff_val_list.append(val_list[idx+1] - val_list[idx])

            return diff_val_list

        std_count_diff_list = [std_count_orig[0] - std_non_zero(sum_frame_count_orig)]  # add first point - from initial state to first removal
        std_count_diff_list += create_differential_list(std_count_orig)  # diferential std count
    
        # fig, axs = plt.subplots(1,2, figsize=(15,6))

        # axs[0].plot(steps, std_count_orig, color="C0", label="std_count")      
        # axs[0].set_title("count")
        # # axs[0].set_yscale('log')   
        # axs[0].legend() 
        # axs[0].grid(alpha=0.5, linestyle='--', linewidth=0.5, which='both')
        # axs[0].set_xlabel("count of removed maximal pixels") 

        # axs[1].plot(steps, std_count_diff_list, color="C0", label="std_count_diff")   
        # axs[1].plot([np.min(steps), np.max(steps)], [0,0], color="red", label="std_count_diff", alpha=0.6, linestyle="--")                 
        # axs[1].set_title("count")
        # # axs[1].set_yscale('log')   
        # axs[1].legend() 
        # axs[1].grid(alpha=0.5, linestyle='--', linewidth=0.5, which='both')
        # axs[1].set_xlabel("count of removed maximal pixels") 
        # plt.show()        

        # =============================================
        # conclusion 
        # -> remove std_count_diff_list is above -0.01 or -0.001
        # =============================================

        std_count_diff_limit = -0.002
        count_of_max_pixel_remove = 0

        for idx, std_count_diff in enumerate(std_count_diff_list):
            if std_count_diff > std_count_diff_limit:
                break
            count_of_max_pixel_remove += 1

        print(f"count_of_max_pixel_remove        {count_of_max_pixel_remove}")

        matrix_count_removed_max = copy.deepcopy(sum_frame_count_orig)
        row_indices, col_indices = remove_n_max_pixels(matrix_count_removed_max, count_of_max_pixel_remove)

        # plot_matrices_overview(sum_frame_count_orig, matrix_count_removed_max)
        
        for idx in range(len(row_indices)):
            print(col_indices[idx], "\t" ,row_indices[idx])

        # create mask matrix

        # from procedure above
        mask_matrix = np.ones((256, 256))
        mask_matrix[row_indices, col_indices] = 0

        # from roi
        for j in range(256):
            for i in range(256):   
                if j <= 62 or j >= 192:
                    mask_matrix[j,i] = 0
                if i <= 62 or i >= 192:
                    mask_matrix[j,i] = 0

        # special pixels based on observation
        # mask_matrix[112, 149] = 0
        # mask_matrix[112, 148] = 0


        plot_matrix(mask_matrix*sum_frame_count_orig, do_log=False)   

    # test of basic functionality
    if case == 2:

        dir_data = "./devel/data/"
        data_file = DataFile(dir_data + "dosimeter_image_packets.csv")
        data_file.load()

        mask = Mask()

        sum_frame_count = np.zeros((256,256))

        for frame in data_file.frames:
            sum_frame_count += frame.get_matrix(Tpx3Mode.COUNT)

        mask.create(sum_frame_count, roi=[[62, 192], [62, 192]])

        sum_frame_count_orig = copy.deepcopy(sum_frame_count)

        mask.apply(sum_frame_count) 

        plot_matrix(mask.matrix)
        plot_matrix(sum_frame_count)

        # fig, axs = plt.subplots(2,3, figsize=(15,8))
        # plot_matrix_hist(sum_frame_count_orig, fig=fig, ax=axs[0,0], do_show_meas_std_lines=True)
        # plot_matrix(sum_frame_count_orig, do_log=True,  fig=fig, ax=axs[0,1])
        # plot_matrix(sum_frame_count_orig, do_log=False,  fig=fig, ax=axs[0,2])        
        # plot_matrix_hist(sum_frame_count, fig=fig, ax=axs[1,0], do_show_meas_std_lines=True)
        # plot_matrix(sum_frame_count, do_log=True,  fig=fig, ax=axs[1,1])
        # plot_matrix(sum_frame_count, do_log=False,  fig=fig, ax=axs[1,2])        
        # plt.tight_layout()
        # plt.show()

    # change of mask over measurements
    if case == 3:

        dirs_data_path_name = "/home/lukas/file/analysis/one_web/data/raw/"
        dirs_data = load_dirs_data(dirs_data_path_name)

        masks = []
        do_load_data = True

        # load data
        if do_load_data:
            for idx, dir_data in enumerate(dirs_data):
                # if idx != 7:
                #     continue
                print(dir_data)

                data_file = DataFile(dir_data + os.sep + "dosimeter_image_packets.csv")
                data_file.load()

                mask = Mask()

                sum_frame_count = np.zeros((256,256))
                sum_frame_tot = np.zeros((256,256))                
                for frame in data_file.frames:
                    sum_frame_count += frame.get_matrix(Tpx3Mode.COUNT)
                    sum_frame_tot += frame.get_matrix(Tpx3Mode.TOT)

                mask.create(sum_frame_count, roi=[[62, 192], [62, 192]])

                sum_frame_count_orig = copy.deepcopy(sum_frame_count)
                sum_frame_tot_orig = copy.deepcopy(sum_frame_tot)

                mask.apply(sum_frame_count) 
                mask.apply(sum_frame_tot) 

                dir_data_name = os.path.basename(os.path.normpath(dir_data))

                fig, axs = plt.subplots(2,3, figsize=(25,14))
                plot_matrix(mask.matrix, fig=fig, ax=axs[0,0], title="mask")
                plot_matrix(sum_frame_count, fig=fig, ax=axs[0,1], title="count mask")
                plot_matrix(sum_frame_count_orig, fig=fig, ax=axs[0,2], title="count")     
                plot_matrix(sum_frame_tot, fig=fig, ax=axs[1,1], title="tot mask")
                plot_matrix(sum_frame_tot_orig, fig=fig, ax=axs[1,2], title="tot")                           
                plt.savefig(f"devel/mask/out/mask{dir_data_name}.png")
                plt.close()

                np.savetxt(f"devel/mask/out/mask{dir_data_name}.txt", mask.matrix, fmt='%g',  delimiter=" ")
                np.savetxt(f"devel/mask/out/noisy_pix{dir_data_name}.txt", mask.matrix_noisy_pix, fmt='%g',  delimiter=" ")
                np.savetxt(f"devel/mask/out/count_mask{dir_data_name}.txt", sum_frame_count, fmt='%g',  delimiter=" ")
                np.savetxt(f"devel/mask/out/count{dir_data_name}.txt", sum_frame_count_orig, fmt='%g',  delimiter=" ")                
                np.savetxt(f"devel/mask/out/tot_mask{dir_data_name}.txt", sum_frame_tot, fmt='%g',  delimiter=" ")
                np.savetxt(f"devel/mask/out/tot{dir_data_name}.txt", sum_frame_tot_orig, fmt='%g',  delimiter=" ")                

        # investigate created masks and derive general mask
        dir_mask_out = "./devel/mask/out/"
        file_names = os.listdir(dir_mask_out)

        matrix_noisy_pix_sum = np.zeros((256, 256))
        for file_name in file_names:
            if "txt" in file_name and "noisy_pix" in file_name:
                matrix_noisy_pix_sum += np.loadtxt(dir_mask_out + file_name)
        # matrix_noisy_pix_sum = matrix_noisy_pix_sum[63:191, 63:191]
        # plot_matrix(matrix_noisy_pix_sum, do_log=False)

        cout_pix_accept = 20

        mask = Mask()
        mask.create(None, roi=[[62, 192], [62, 192]])
        mask.matrix[(matrix_noisy_pix_sum >= cout_pix_accept)] = 0

        plot_matrix(mask.matrix, do_log=False)

        for file_name in file_names:
            if "tot" in file_name and "mask" not in file_name:
                tot_sum = np.loadtxt(dir_mask_out + file_name)  
                count_sum = np.loadtxt(dir_mask_out + file_name.replace("tot", "count"))  

                mask.apply(tot_sum)
                mask.apply(count_sum)

                fig, axs = plt.subplots(1,2 ,figsize=(30,12))
                plot_matrix(tot_sum, do_log=False, fig=fig,ax=axs[0])   
                plot_matrix(count_sum, do_log=False, fig=fig,ax=axs[1])                     
                plt.show()

    # example of final application on data 
    # using fixed pattern mask and adaptive masking
    if case == 4:

        dir_mask_out = "./devel/mask/out/"
        file_names = os.listdir(dir_mask_out)

        # load all sum matrices
        matrices_tot_sum = []
        matrices_count_sum = []        

        for file_name in file_names:
            if not "tot" in file_name or "mask" in file_name:
                    continue

            matrix_tot_sum = np.loadtxt(dir_mask_out + file_name)  
            matrix_count_sum = np.loadtxt(dir_mask_out + file_name.replace("tot", "count"))  

            matrices_tot_sum.append(matrix_tot_sum)
            matrices_count_sum.append(matrix_count_sum)

        # create fixed pattern mask out of count matrices

        mask_fixed_pattern = Mask()
        mask_fixed_pattern.create_fixed_pattern(matrices_count_sum, roi=[[62, 192], [62, 192]])

        # create individual masks for data batches

        for file_name in file_names:
            if not "tot" in file_name or "mask" in file_name:
                    continue

            matrix_tot_sum = np.loadtxt(dir_mask_out + file_name)  
            matrix_count_sum = np.loadtxt(dir_mask_out + file_name.replace("tot", "count"))  

            matrix_tot_sum_orig = copy.deepcopy(matrix_tot_sum)
            matrix_count_sum_orig = copy.deepcopy(matrix_count_sum)

            mask_tot = Mask()
            mask_tot.set_std_differential_limit(-0.1)  # much more loose limit to only discard extreme noisy pixels, rest is done by count matrix
            mask_tot.create(matrix_tot_sum)

            mask = Mask()
            mask.create(matrix_count_sum)
            mask.add(mask_fixed_pattern)
            mask.add(mask_tot)

            # apply
            mask.apply(matrix_tot_sum)
            mask.apply(matrix_count_sum)

            # plot
            fig, axs = plt.subplots(2,3, figsize=(18,12))
            axs[0, 0].axis('off')
            axs[0, 0].set_xticks([])
            axs[0, 0].set_yticks([])            
            plot_matrix(matrix_tot_sum_orig, fig=fig, ax=axs[0,1], do_log=False)
            plot_matrix(matrix_count_sum_orig, fig=fig, ax=axs[0,2], do_log=False)            
            plot_matrix(mask.matrix_noisy_pix+mask_tot.matrix_noisy_pix, fig=fig, ax = axs[1,0], do_log=False, cmap="viridis")
            axs[1,0].set_title("mask of noisy pixels (val 1 = count, val=2 tot, val>2 combined)")
            plot_matrix(matrix_tot_sum, fig=fig, ax=axs[1,1], do_log=False)
            plot_matrix(matrix_count_sum, fig=fig, ax=axs[1,2], do_log=False)
            plt.tight_layout()
            plt.savefig("./devel/mask/" + "mask_count_" + file_name.replace("txt", "png"))
            plt.close()


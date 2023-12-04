import os
import sys
import logging
import binascii
import csv
import datetime

sys.path.append("src/pxdata/src")

from tpx3_mode import *
from pixel import *
from frame import *
from llcp import *
from decoder import *
from log import *

sys.path.append("src")

from utils import *


# data packet of incoming data stream from space minipix
class DataPacket(object):
    def __init__(self, frame_id=None, packet_id=None, mode=None, 
                 n_pixels=None, checksum_matched=None, timestamp=None):

        self.frame_id         = frame_id
        self.packet_id        = packet_id
        self.mode             = mode
        self.n_pixels         = n_pixels
        self.checksum_matched = checksum_matched
        self.pixels           = []
        self.timestamp        = timestamp 
        self.do_include_terminator = False

class DataFile(object):
    """docstring for DataFile"""
    def __init__(self, file_in_path_name, log_path="", log_name="log.txt"):
        super(DataFile, self).__init__()

        self.file_in_path_name = file_in_path_name

        self.batch_separator = '55AA55AA5555AA55AA55'   # separates data batches which are evaluated and with whole frames should 

        self.frames = []

        self.frames_data_packets = []

        self.done_load = False

        self.decoder = Decoder()

        self.do_integrity_check_of_data_pck = True      # control whether integrity check of data packets should be done
        self.do_decode_help_msg = False 
        self.do_force_itot_count_mode = True
        self.do_skip_empty_data_packets = True 

        self.size_data_line = 0                         # size of data line (should be 218 characters)

        # stat
        self.count_err_load_pix = 0                     # count of failed pixels in load
        self.count_err_integrity_check_pix = 0          # count of pixels refused for fail in data packet integrity check       
        self.count_err_load_data_pck = 0                # count of fails of loading of data packet
        self.count_err_integrity_check_data_pck = 0     # count of fails in integrity check of data packets
        self.count_err_integrity_check_frames = 0       # count of filed frames in integrity check
        self.count_err_integrity_check_frames_miss = 0  # count of filed frames in integrity check -> due to missing packet
        self.count_err_integrity_check_frames_zero = 0  # count of filed frames in integrity check -> due to start packet is not 0
        self.count_err_integrity_check_frames_term = 0  # count of filed frames in integrity check -> due to start packet is not 0

        self.count_err_data_duplicity = 0               # count of data duplicities
        self.cout_err_lost_frames_based_id = 0          # count of lost frames based on the id order (each next should be +3)

        self.count_err_pix = 0                          # count of error/lost pixels
        self.count_err_data_pck = 0                     # count of error/lost data packets
        self.count_err_frames = 0                       # count of error/lost frames

        self.count_ok_pix = 0                           # count of loaded valid pixels
        self.count_ok_data_pck = 0                      # count of loaded valid data packets
        self.count_ok_frames = 0                        # count of loaded valid frames

        self.count_all_pix = 0                          # count of all pixels
        self.count_all_data_pck = 0                     # count of all data packets
        self.count_all_frames = 0                       # count of all frames

        # log and print
        self.do_log = True
        self.do_print = True
        self.log_file_path = log_path
        self.log_file_name = log_name
        self.log_file = None

        try:
            self._open_log()
        except Exception as e:
            log_warning(f"failed to open log {os.path.join(self.log_file_path, self.log_file_name)}: {e}")

    def __exit__(self, exc_type, exc_value, traceback):
        if self.log_file:
            self.log_file.close()        

    def _open_log(self):
        self.log_file = open(os.path.join(self.log_file_path, self.log_file_name), "w")

    def load(self):
        log_info(f"loading file: {self.file_in_path_name}", self.log_file, self.do_print, self.do_log)

        # Define the separator string - separation of two measurements, but not necessarily has to appear
        start_separ_line =  '00000000000000000000'
        len_start_separ_line = len(start_separ_line)

        self._find_size_of_data_line()

        try:
            infile = open(self.file_in_path_name, "r", encoding="ascii")
        except:
            log_error(f"can not open input file {self.file_in_path_name}")
            exit()

        csv_reader = csv.reader(infile)

        data = ""
        timestamp_list = []
        timestamp = None
        data_idx_shift = 0  # data idx shift with respect to the original file and needed for timestamp 

        for idx, row in enumerate(csv_reader):

            # skip empty lines
            if len(row) < 2:
                continue

            row_timestamp = row[0]
            row_data = row[1]

            # skip header
            if row_timestamp == "TIMESTAMP":
                continue

            # skip 00000 lines 
            if row[1][:len_start_separ_line] == start_separ_line and \
                self.batch_separator not in row_data:
                continue

            timestamp =  convert_str_timestapmp_to_datetime(row_timestamp);
            timestamp_list.append(timestamp)

            if self.batch_separator in row_data:
                log_info(f"{timestamp}    OBC terminator position {idx}", self.log_file, self.do_print, self.do_log)

                separator_index = row_data.index(self.batch_separator)
                data += row_data[0:separator_index]

                self._process_data_stream(data, timestamp_list, data_idx_shift)

                # reset and append current data if needed
                timestamp_list = []
                data = row_data[separator_index+len(self.batch_separator):] # add string after separator
                if len(data) != 0:
                    timestamp_list.append(timestamp)
                data_idx_shift = len(row_data) - (separator_index+len(self.batch_separator))

            else:
                data += row_data

        # processing of last data batch
        if data:
            self._process_data_stream(data, timestamp_list, data_idx_shift)

        self._evaluate_final_ok_stat()

        infile.close()

    """gets the size of data line"""
    def _find_size_of_data_line(self):
        try:
            infile = open(self.file_in_path_name, "r", encoding="ascii")
        except:
            log_error(f"can not open input file {self.file_in_path_name}", self.log_file, self.do_print, self.do_log)
            exit()        
        csv_reader = csv.reader(infile)

        for idx, row in enumerate(csv_reader):

            # skip empty lines
            if len(row) < 2 or row[0] == "TIMESTAMP":
                continue   

            self.size_data_line = len(row[1])
            break      

        infile.close()

    """process data stream alias one batch"""
    def _process_data_stream(self, data_stream, timestamp_list, data_idx_shift):
        self._parse_detector_data_stream(data_stream, timestamp_list, data_idx_shift)
        if self.do_integrity_check_of_data_pck:
            self._check_and_correct_data_packets_integrity()
        self._convert_data_packets_into_frames()

    """parses detector data stream looking for help and data msg/packets"""
    def _parse_detector_data_stream(self, data, timestamp_list, data_idx_shift):
        self.frames_data_packets = []
        timestamp_idx = 0

        try:
            byte_stream = binascii.unhexlify(data)
        except:
            log_error(f"unhexification failed on data at timestamp {timestamp}", self.log_file, self.do_print, self.do_log)
            return 
        
        idx = 0
        while idx < len(byte_stream):

            timestamp, timestamp_idx =  self._get_current_timestamp(idx, data_idx_shift, timestamp_idx, timestamp_list)

            if timestamp is None:
                idx += 1
                continue
            
            # help msgs - status, temperature, errors etc
            if self.do_decode_help_msg:
                if byte_stream[idx] == LLCP_STATUS_MSG_ID:
                    log_info(f"{timestamp}    status", self.log_file, self.do_print, self.do_log)
                    idx = idx + LLCP_STATUS_MSG_SIZE
                    continue

                if byte_stream[idx] == LLCP_TEMPERATURE_MSG_ID:
                    temperature = bytes_to_int16(byte_stream[idx+2], byte_stream[idx+1])
                    log_info(f"{timestamp}    temperature: {temperature}", self.log_file, self.do_print, self.do_log)
                    idx = idx + LLCP_TEMPERATURE_MSG_SIZE
                    continue

                if byte_stream[idx] == LLCP_FRAME_DATA_TERMINATOR_MSG_ID:
                    frame_id = bytes_to_int16(byte_stream[idx+2], byte_stream[idx+1])
                    num_of_packets = bytes_to_int16(byte_stream[idx+4], byte_stream[idx+3])
                    log_info(f"{timestamp}    data terminator: frame_id {frame_id}, num_of_packets {num_of_packets}", self.log_file, self.do_print, self.do_log)
                    idx = idx + LLCP_FRAME_DATA_TERMINATOR_MSG_SIZE
                    continue

                if byte_stream[idx] == LLCP_FRAME_MEASUREMENT_FINISHED_MSG_ID:
                    log_info(f"{timestamp}    measurement finished", self.log_file, self.do_print, self.do_log)
                    idx = idx + LLCP_FRAME_MEASUREMENT_FINISHED_MSG_SIZE
                    continue

                if byte_stream[idx] == LLCP_ACK_MSG_ID:
                    log_info(f"{timestamp}    ack", self.log_file, self.do_print, self.do_log)
                    idx = idx + LLCP_ACK_MSG_SIZE
                    continue

                if byte_stream[idx] == LLCP_MINIPIX_ERROR_MSG_ID:
                    error_id = byte_stream[idx+1]
                    log_error(f"{timestamp}    error: {error_id}", self.log_file, self.do_print, self.do_log)
                    try:    log_error(f"\t error typr {error_id}", self.log_file, self.do_print, self.do_log)
                    except: pass
                    idx = idx + LLCP_MINIPIX_ERROR_MSG_SIZE
                    continue

            # data packets
            if byte_stream[idx] == LLCP_FRAME_DATA_MSG_ID:
                log_info(f"{timestamp}    data packet: idx {idx}", self.log_file, self.do_print, self.do_log)

                try:
                    data_packet, idx = self._extract_data_packet_from_byte_stream(byte_stream, idx, timestamp)
                    if data_packet is not None:
                        self.frames_data_packets.append(data_packet)
                except Exception as e:
                    self.count_err_load_data_pck += 1
                    idx += 8
                    log_error(f"failed to extract data packet: {e}", self.log_file, self.do_print, self.do_log)

                continue

            idx = idx + 1

    def _get_current_timestamp(self, data_idx, data_idx_shift, timestamp_idx, timestamp_list):
        # increase timestamp if new line in data file is read
        # 2*(idx+1) is to include reading of hexadecimal NN and not N which is used for line size estimation        
        file_idx = data_idx_shift + 2*(data_idx+1)
        if file_idx > (1+timestamp_idx)*self.size_data_line:
            timestamp_idx = int(file_idx/self.size_data_line)
            timestamp_idx = timestamp_idx if file_idx%self.size_data_line != 0 else timestamp_idx - 1

        if timestamp_idx < len(timestamp_list):
            return timestamp_list[timestamp_idx], timestamp_idx
        else:
            log_warning(f"failed to get timestamp for current data - last timestamp {timestamp_list[-1]}", self.log_file, self.do_print, self.do_log)
            return None, timestamp_idx

    def _extract_data_packet_from_byte_stream(self, byte_stream, idx, timestamp ):
        if len(byte_stream) < idx+7:
            log_error(f"{timestamp}    failed to read data packet because stream is short {len(byte_stream)} vs {idx}+7", self.log_file, self.do_print, self.do_log)
            self.count_err_load_data_pck += 1
            idx += len(byte_stream) - idx  # ends reading
            return None, idx

        data_packet = DataPacket()

        # extract the bytes
        # the following ones are not encoded and can be just copied
        data_packet.frame_id         = bytes_to_int16(byte_stream[idx+2], byte_stream[idx+1])
        data_packet.packet_id        = bytes_to_int16(byte_stream[idx+4], byte_stream[idx+3])
        data_packet.mode             = Tpx3FrameMode(byte_stream[idx+5])
        data_packet.n_pixels         = byte_stream[idx+6]
        data_packet.checksum_matched = byte_stream[idx+7]
        data_packet.timestamp        = timestamp 

        # skip non itot+count frames
        if self.do_force_itot_count_mode and data_packet.mode != Tpx3FrameMode.ITOT_COUNT:
            log_warning(f"{timestamp}    skipping frame in mode {data_packet.mode}", self.log_file, self.do_print, self.do_log)
            idx += 8
            return None, idx
           
        # skip empty frames
        if self.do_skip_empty_data_packets and data_packet.n_pixels == 0:
            log_warning(f"{timestamp}    skipping empty data packet", self.log_file, self.do_print, self.do_log)            
            idx += 8
            return None, idx

        final_idx = 0

        # the following pixel data are encoded and need to be
        # deserialized and derandomized
        # for each pixel in the packet
        for pix_idx in range(0, data_packet.n_pixels):

            # list of 6 bytes
            pixel_data = []

            decoding_error = False

            # for each one of the 6 bytes encoding the pixel data
            for pix_byte_idx in range(0, 6):

                try:
                    data_start = idx + 8 # 8 = skip header length
                    final_idx = data_start + pix_idx*6 + pix_byte_idx
                    pixel_data.append(byte_stream[final_idx])
                except:
                    log_error(f"{timestamp}    pixel decoding error {final_idx}", self.log_file, self.do_print, self.do_log)
                    decoding_error = True
                    continue

            if decoding_error:
                continue

            # deserialize and derandomize the pixel data
            pixel = self.decoder.convert_frame_packet(pixel_data, data_packet.mode)

            if pixel:
                data_packet.pixels.append(pixel)
            else:
                self.count_err_load_pix += 1 

            # terminator pixel
            if self._check_terminator_pixel(pixel):
                data_packet.do_include_terminator = True

        if final_idx > 0:
            idx = final_idx + 1
        else:
            idx = idx + 8

        return data_packet, idx

    def _check_terminator_pixel(self, pixel):
        if not pixel:
            return False
        if pixel.x == 26 and pixel.y == 0:
            return True
        else:
            return False


    """
    checks whether given data packets are corrupted with respect to a frames:
        * order of packet id data_packets[i+1].packet_id == data_packets[i].packet_id + 1 
        * starting packet id should be 0
    """
    def _check_and_correct_data_packets_integrity(self):
        if not self.frames_data_packets:
            log_warning(f"no data packets were given for integrity check", self.log_file, self.do_print, self.do_log)
            return []

        frame_id_ref = -1
        data_packet_id_prev = -1
        data_packet_prev = None

        is_currupted_frame = False
        idx_currupted_data_packets = []

        for idx, data_packet in enumerate(self.frames_data_packets):
            
            if data_packet.frame_id == frame_id_ref: 

                is_next_data_packet = (data_packet.packet_id - data_packet_id_prev) == 1

                if is_currupted_frame:
                    idx_currupted_data_packets.append(idx)
                # if it is not next data packet then something might be missing -> corrupted frame
                elif not is_next_data_packet: 
                    is_currupted_frame = True

                    # most likely duplicity data
                    if data_packet_id_prev > data_packet.packet_id:
                        log_error(f"corrupted frame {data_packet.frame_id} - duplicity: packet id {data_packet.packet_id} is less then previous {data_packet_id_prev}: {data_packet.timestamp}",
                                  self.log_file, self.do_print, self.do_log)
                        idx_currupted_data_packets.append(idx)

                        # stat
                        self.count_err_data_duplicity += 1  
                    # missing data packet in order                      
                    else:
                        log_error(f"corrupted frame {data_packet.frame_id} - missing packet: packet id {data_packet.packet_id} jump with respect to prev {data_packet_id_prev}: {data_packet.timestamp}",
                                  self.log_file, self.do_print, self.do_log)                      
                        idx_currupted_data_packets += list(range(idx - data_packet.packet_id+1, idx))  # idxs of previous data packets
                        idx_currupted_data_packets.append(idx)

                        # stat
                        self.count_err_integrity_check_frames_miss += 1
                        
                    continue

            # new frame
            else:
                is_currupted_frame = False
                frame_id_ref = data_packet.frame_id

                # check whether first data packet is with id 0 if not -> corrupted frame
                if data_packet.packet_id != 0:
                    log_error(f"corrupted frame {data_packet.frame_id} - packet id {data_packet.packet_id} does not start with 0: {data_packet.timestamp}",
                              self.log_file, self.do_print, self.do_log)

                    is_currupted_frame = True
                    
                    # stat
                    self.count_err_integrity_check_frames_zero += 1

                # check for missing terminator
                if data_packet_prev and not data_packet_prev.do_include_terminator:
                    log_error(f"corrupted frame {data_packet.frame_id} - packet id {data_packet.packet_id} is last but not terminator: {data_packet.timestamp}",
                              self.log_file, self.do_print, self.do_log)

                    idx_currupted_data_packets += list(range(idx - data_packet.packet_id+1, idx+1))  # idxs of all data packets

                    # stat
                    self.count_err_integrity_check_frames_term += 1


            data_packet_prev = data_packet
            data_packet_id_prev = data_packet.packet_id

        if idx_currupted_data_packets:
            self._correct_data_packtes(idx_currupted_data_packets)

    """removes data packets from list which were marked as part of corrupted frame"""
    def _correct_data_packtes(self, idx_currupted_data_packets):
        frame_id_ref = self.frames_data_packets[idx_currupted_data_packets[-1]].frame_id
        for idx in reversed(idx_currupted_data_packets):

            data_packet_corrupted = self.frames_data_packets[idx]

            # stat
            self.count_err_integrity_check_pix += data_packet_corrupted.n_pixels
            self.count_err_integrity_check_data_pck += 1

            self.frames_data_packets.pop(idx)                

    def _convert_data_packets_into_frames(self):
        if len(self.frames_data_packets) == 0:
            return

        # stat
        self.count_ok_data_pck += len(self.frames_data_packets)

        frame_id_ref = self.frames_data_packets[0].frame_id

        frame = self._create_frame_based_on_data_packet(self.frames_data_packets[0])     
        self.frames.append(frame)

        for data_packet in self.frames_data_packets:
            if data_packet.frame_id != frame_id_ref:
                frame = self._create_frame_based_on_data_packet(data_packet)
                self.frames.append(frame)

                frame_id_ref = data_packet.frame_id

            # skipping last pixel because it is terminator
            for pixel in data_packet.pixels[:-1]:
                self.frames[-1].add_pixel_value(pixel)

    def _create_frame_based_on_data_packet(self, data_packet):
        frame = Frame(data_packet.mode)
        frame.t_ref = data_packet.timestamp
        frame.id = data_packet.frame_id 
        return frame

    def _evaluate_final_ok_stat(self):
        self.count_ok_frames = len(self.frames)
        for frame in self.frames:
            self.count_ok_pix += frame.get_count_hit_pixels()

        self.count_err_integrity_check_frames += self.count_err_integrity_check_frames_miss + self.count_err_integrity_check_frames_zero + \
                                                 self.count_err_integrity_check_frames_term

        self.count_err_pix += self.count_err_load_pix + self.count_err_integrity_check_pix
        self.count_err_data_pck += self.count_err_load_data_pck + self.count_err_integrity_check_data_pck 
        self.count_err_frames += self.count_err_integrity_check_frames
        
        self.count_all_pix = self.count_ok_pix + self.count_err_pix
        self.count_all_data_pck = self.count_ok_data_pck + self.count_err_data_pck
        self.count_all_frames = self.count_ok_frames + self.count_err_frames

        self.cout_err_lost_frames_based_id = self._estimate_lost_frames_based_on_id() 

    def _estimate_lost_frames_based_on_id(self):
        frame_id_prev = -1
        step = 3
        count_lost_frames = 0
        for frame in self.frames:
            if frame_id_prev == -1:
                frame_id_prev = frame.id
                continue
            if frame.id != frame_id_prev + step: 
                count_lost_frames += ((frame.id - frame_id_prev)/step) - 1
            frame_id_prev = frame.id
        return count_lost_frames


    def log_stat(self):

        msg =   "\n"        
        msg +=  "\n"        
        msg +=  " statistics:\n"
        msg +=  "\n"        
        msg += f"  * count of OK frames:                {self.count_ok_frames} \t[{calc_portion_in_perc(self.count_ok_frames, self.count_all_frames):.2f}%]\n"
        msg += f"  * count of OK data pck:              {self.count_ok_data_pck} \t[{calc_portion_in_perc(self.count_ok_data_pck, self.count_all_data_pck):.2f}%]\n"
        msg += f"  * count of OK pixels:                {self.count_ok_pix} \t[{calc_portion_in_perc(self.count_ok_pix, self.count_all_pix):.2f}%]\n"
        msg +=  "\n"
        msg += f"  * count of ALL frames:               {self.count_all_frames}\n"
        msg += f"  * count of ALL data pck:             {self.count_all_data_pck}\n"
        msg += f"  * count of ALL pixels:               {self.count_all_pix}\n"
        msg +=  "\n"
        msg += f"  * count of ERROR/lost frames:        {self.count_err_frames} \t[{calc_portion_in_perc(self.count_err_frames, self.count_all_frames):.2f}%]\n"
        msg += f"      * missing 0 data pck:            {self.count_err_integrity_check_frames_zero}\n"
        msg += f"      * missing other data pck:        {self.count_err_integrity_check_frames_miss}\n" 
        msg += f"      * missing terminator:            {self.count_err_integrity_check_frames_term}\n"         
        msg +=  "\n"               
        msg += f"  * count of ERROR/lost data pck:      {self.count_err_data_pck} \t[{calc_portion_in_perc(self.count_err_data_pck, self.count_all_data_pck):.2f}%]\n"
        msg += f"      * load:                          {self.count_err_load_data_pck}\n"         
        msg += f"      * integrity check:               {self.count_err_integrity_check_data_pck}\n"
        msg +=  "\n"        
        msg += f"  * count of ERROR/lost pixels:        {self.count_err_pix} \t[{calc_portion_in_perc(self.count_err_pix, self.count_all_pix):.2f}%]\n"
        msg += f"      * load:                          {self.count_err_load_pix}\n"         
        msg += f"      * integrity check:               {self.count_err_integrity_check_pix}\n"
        msg +=  "\n"        
        msg += f"  * count of ERROR duplicities:        {self.count_err_data_duplicity}\n"
        msg += f"  * count of ERROR lost frames bs id:  {int(self.cout_err_lost_frames_based_id)}\n"

        log_info(msg, self.log_file, self.do_print, self.do_log)

        return msg

    def log_frames(self):
        msg = "\n\n frames:\n\n"
        
        for idx, frame in enumerate(self.frames):
            n_pixels = frame.get_count_hit_pixels()
            msg += f"  {idx}\t{frame.t_ref}\t{frame.id}\t{frame.mode}\t{n_pixels}\n"

        log_info(msg, self.log_file, self.do_print, self.do_log)
        return msg

if __name__ == '__main__':

    case = 1

    # basic example of class usage
    if case == 1:

        file_in_path_name = "./devel/data/dosimeter_image_packets.csv"
        data_file = DataFile(file_in_path_name)
        data_file.load()

        for idx, frame in enumerate(data_file.frames):
            # frame_sum.add_frame(frame)
            n_pixels = np.count_nonzero(frame.matrix[Tpx3Mode.COUNT])
            print(f"{idx}\t{frame.t_ref}\t{frame.id}\t{frame.mode}\t{n_pixels}")

        data_file.log_stat()


    if case == 2:
        pass

        # frame_sum = Frame(Tpx3FrameMode.ITOT_COUNT)

        # print(f"count of non zero pixesl:   {np.count_nonzero(data_file.frames[11].matrix[Tpx3Mode.COUNT])}")
        # data_file.frames[11].plot_matrix(Tpx3Mode.COUNT, do_log_z=True)

        # for i in range(256):
        #     for j in range(256):
        #         if data_file.frames[11].matrix[Tpx3Mode.COUNT][i, j] != 0:
        #             data_file.frames[11].matrix[Tpx3Mode.COUNT][i, j] = 1   

        # data_file.frames[11].plot_matrix(Tpx3Mode.COUNT, do_log_z=True)


        # mask_file_path_name = "./devel/data_file/mask_multiply_count.txt"
        # mask = np.loadtxt(mask_file_path_name, delimiter=" ")

        # data_file.frames[11].multiply_frame(mask)
        # print(f"count of non zero pixesl:   {np.count_nonzero(data_file.frames[11].matrix[Tpx3Mode.COUNT])}")
        # data_file.frames[11].plot_matrix(Tpx3Mode.COUNT)

        # data_file.frames[11].plot_matrix(Tpx3Mode.TOT, do_log_z=True)


        # print(f"count of loaded frames:   {len(data_file.frames)}")





        # np.savetxt("./devel/data_file/frame_matrix_count_suM.txt", frame_sum.matrix[Tpx3Mode.COUNT], delimiter=" ", fmt='%g')

        # frame_sum.plot_matrix(Tpx3Mode.TOT  , do_log_z=False)
        # frame_sum.plot_matrix(Tpx3Mode.COUNT, do_log_z=False)

        # mask_file_path_name = "./devel/data_file/mask_multiply_count.txt"
        # mask = np.loadtxt(mask_file_path_name, delimiter=" ")

        # frame_sum.multiply_frame(mask)

        # frame_sum.plot_matrix(Tpx3Mode.TOT  , do_log_z=False)
        # frame_sum.plot_matrix(Tpx3Mode.COUNT, do_log_z=False)    
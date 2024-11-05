Data processing for One Web data
===============================================================
Version:            -
Date:               -/-/2024
Author:             Lukas Marek (lukas.marek@advacam.cz)  

-------------------------------------------------------------------------------
Introduction
-------------------------------------------------------------------------------

This software severs for processing of data acquired with minipix TPX3 placed
on OneWeb satellite.

-------------------------------------------------------------------------------
Requirements and Installation
-------------------------------------------------------------------------------

Requirements:
 - `python` - tested with version 3.10
 - `DPE` - the DPE should be placed in the directory `bin` in main directory.
 
List of python packages can be found in the `requirements.txt` (in main directory) 
and can be installed with:
```
pip install -r requirements.txt
``` 
-------------------------------------------------------------------------------
Start
-------------------------------------------------------------------------------

Certain data directory structure is needed to use this processing tool. 
The raw data should be separated into days with following name:
```
_2024-05-13_00_00_12_297-_2024-05-13_23_59_52_297
_2024-05-14_00_00_29_497-_2024-05-14_23_59_30_297
...
``` 
This directories should be placed in one global directory with so-called `raw` data.

The processing is then started with execution of the `python src/main.py` or `run_linux.sh`
with two arguments which points to the parent directory of `raw` and calibration directory.
This means that if for example the `raw` is placed in `PATH/TO/DIR/one_web/raw`, then
it should be with argument `PATH/TO/DIR/one_web` (without the `raw`):
```
./run_linux.sh  PATH/TO/DIR/one_web  PAT/TO/CALIB/MATRICES
```

-------------------------------------------------------------------------------
Processing
-------------------------------------------------------------------------------

The processing will do following steps:
 - decoding_and_linking - decodes the data and linked between each other
 - masking() - masking of data for noisy pixels
 - clusterization() 
 - dpe() - applies dpe and adjusts the elist/clists to also contain gps and time     
 - produce_phys() - produces physics information as maps and time evolutions of physics products, frame list
 - produce_stat() - produces statistical information  

All the outputs are placed into separate directories in `PATH/TO/DIR/one_web` alias at the 
same level as `raw`:
 - `proc` - include processing output from all steps **till** `produce_phys()`
 - `phys` - physics information from `produce_phys()`
 - `stat` - stat info from `produce_stat()`

-------------------------------------------------------------------------------
Notes
-------------------------------------------------------------------------------

## Additional adjustment of processing

Additional adjustments are possible in the `main.py` in init of `ProcessingManager`
(find `proc_mgr = ProcessingManager(`):

```python
,dir_data_root : str =              "/home/lukas/file/analysis/one_web/data/new/"
,dir_raw_name : str =               "raw"
,dir_proc_name : str =              "proc"
,dir_phys_name : str =              "phys"   
,dir_stat_name : str =              "stat"                     
,dir_proc_decode_name : str =       "00_decode"
,dir_proc_link_name : str =         "01_link"   
,dir_proc_mask_name : str =         "02_mask"
,dir_proc_clusterer_name : str =    "03_clusterer"    
,dir_proc_dpe_name : str =          "04_dpe"
,dir_excluded : list =              []    
,gps_transform_alg : GpsTransformAlg = GpsTransformAlg.SPICE
,roi : list =                       [[62, 192], [62, 192]]
,mask_fixed_pattern_path : str =    ""
,calib_dir : str =                  "/home/lukas/file/analysis/one_web/data/cal_mat/20deg" 
,do_multi_thread : bool =           False
,do_use_global_id : bool =          True
,dpe_path : str =                   ""
,global_config_path : str =         None
,log_level : str =                  "INFO"
```

## Logging

Processing creates logging into `log.txt` in the main working directory.

-------------------------------------------------------------------------------
TO-DO
-------------------------------------------------------------------------------
 
 - [ ] create virtual environment
 - [ ] proc refactoring
    - [x] create processing manager
    - [x] convert functions in proc.py/main.py under processing manager
    - [x] better logging into processing etc
    - [ ] add and handling of exceptions
    - [x] add zipped binaries of dpe into processing to keep correct version with the project
        - [x] add zip
        - [x] add unzipping into processing chain (check exists and unzip etc)
    - [x] switch for gps alg
    - [x] switch for keeping history between processing - global frame id
    - [x] `generate_meas_set_info.py` run as module
    - [x] automatic creation of plots and outputs

-------------------------------------------------------------------------------
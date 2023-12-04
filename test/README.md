Testing Procedure for one web
===============================================================
Date:               14/11/2023   
Author:             Lukas Marek (lukas.marek@advacam.cz) 

-------------------------------------------------------------------------------
Intro and Run
-------------------------------------------------------------------------------

`python test/tests.py`

where release is name of one of the releases.

-------------------------------------------------------------------------------
Tests
-------------------------------------------------------------------------------

List of tests which are implemented:

 1) **basics of data file** - testing loading of data file with outpu into log
 2) **basics of data info file** - testing loading of data info file with outpu into log
 3) **basics of gps file** - testing loading of gps file with outpu into log

-------------------------------------------------------------------------------
Creating New Reference Files
-------------------------------------------------------------------------------

Only if major change is done in the file/directory structure  

 * Run the tests
 * Copy the content of out into ref


-------------------------------------------------------------------------------
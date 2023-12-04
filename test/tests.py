#%%
#Run from main System dir with command on linux: python ./test/tests.py -b ./Release/Linux/ for testing bin in dir release
#
import argparse
import unittest
import platform
import os
import filecmp
from pathlib import Path
import shutil
import sys
from datetime import datetime


class SystemTests(unittest.TestCase):
    
    def __init__(self, testname, python_exe = ""):
        super(SystemTests, self).__init__(testname)
        if python_exe:
            self.python_exe = python_exe 
        else:
            self.python_exe = "python"

        self.do_mirror_compare = True

        self.dir_in = "test" + os.path.sep + "in"
        self.dir_out = "test" + os.path.sep + "out"
        self.dir_ref = "test" + os.path.sep + "ref_lin"

        if platform.system() == "Windows":
            self.dir_ref = "test" + os.path.sep + "ref_win"


    def add_log_entry(self, entry):
        file_log = open("test_log.txt", 'a')
        file_log.write(entry + "\n")
        file_log.close()

    def compare_files(self, path_out, path_ref, file):
        if file.find(".") == 0:     return True
        if file.find(".png") != -1: return True
        if file.find(".idx") != -1: return True               
        if os.path.isdir(path_out + file): 
            return self.compare_dir(path_out, path_ref, file)

        rv = filecmp.cmp(path_out + file, path_ref + file, shallow=False)

        if(not rv):
            print(path_out + file)
            # self.add_log_entry(path_out + file)

        return rv        

    def compare_dir(self, dir_out, dir_ref, directory):
        dir_cont_sub = os.listdir(dir_out + os.path.sep + directory)

        rv = os.path.isdir(dir_ref + os.path.sep + directory) 
        if not rv: 
            return rv           

        for cont in dir_cont_sub:
            curr_rv = self.compare_files(dir_out + os.path.sep + directory + os.path.sep, 
                                         dir_ref + os.path.sep + directory + os.path.sep, cont)
            if not curr_rv: rv = curr_rv

        return rv

    def compare_outputs(self, dir_out, dir_ref, directory):
        return self.compare_dir(dir_out, dir_ref, directory)

    def run_test(self, test_num):
        directory = "test_" + test_num    
        os.mkdir(os.path.join(self.dir_out, directory))    
        cmd = self.python_exe + " " + os.path.join(self.dir_in, directory, "proc.py")
        rv = os.system(cmd) 
        self.assertEqual(rv, 0)

    def output_test(self, test_num):
        self.run_test(test_num)
        directory = "test_" + test_num
        self.assertTrue(self.compare_outputs(self.dir_out, self.dir_ref, directory))
        if self.do_mirror_compare: 
            self.assertTrue(self.compare_outputs(self.dir_ref, self.dir_out, directory))       

    # test with investigation of returned errors in .ret_val_dpe.txt
    def error_test(self, num, rv_expected):
        file_config = self.dir_in + os.path.sep + "test_" + num + os.path.sep + "ParametersFile.txt"
        rv_run = os.system( str(self.python_exe) + ' ' + str(file_config)) 
        file_rv = open(".ret_val_dpe.txt", 'r')
        rv = []
        for line in file_rv:
            line_list = line.split(";")
            for item in line_list:
                if len(item) > 0: rv.append(int(item))
        os.remove(".ret_val_dpe.txt")     
        self.assertTrue(len(rv) == len(rv_expected))
        for i in range(len(rv)):
            self.assertEqual(rv[i], rv_expected[i])


    def test_001(self):  self.output_test("001")
    def test_002(self):  self.output_test("002")
    def test_003(self):  self.output_test("003")
    def test_004(self):  self.output_test("004")


def remove_old_files_directories():
    shutil.rmtree("test" + os.path.sep + "out" + os.path.sep + "")
    os.mkdir("test" + os.path.sep + "out" + os.path.sep + "")
    if os.path.exists("test_log.txt"):  
        os.remove("test_log.txt")    

def format_failure_msg(failure):
    test_method_name = failure[0].__str__().split()[0]  
    msg =  "======================================================================\n"
    msg += f"{test_method_name}:\n"   
    msg += "----------------------------------------------------------------------\n"               
    msg += failure[1]
    msg += "----------------------------------------------------------------------\n"               
    return msg

def report_tests(output_test, file_out_path_name = "", do_print = True, do_log = True):

    if output_test.wasSuccessful():
        result_summary = "All tests passed!\n"
    else:
        result_summary = "Some tests failed.\n"

    num_tests_run = output_test.testsRun
    num_failures = len(output_test.failures)
    num_errors = len(output_test.errors)
    num_skipped = len(output_test.skipped)
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


    msg = ""
    msg += f"Date:                         {date}\n" 
    msg += "\n"   
    msg += result_summary
    msg += "\n"
    msg += f"Number of tests run:          {num_tests_run}\n"
    msg += f"Number of failures:           {num_failures}\n"
    msg += f"Number of errors:             {num_errors}\n"
    msg += f"Number of skipped tests:      {num_skipped}\n"


    # Print details about failures and errors
    if output_test.failures:
        msg += f"\nFailures:\n"
        for failure in output_test.failures:
            msg += format_failure_msg(failure)

    if output_test.errors:
        msg += f"\nErrors:\n"            
        for error in output_test.errors:
            msg += format_failure_msg(error)

    # print and export
    if do_print:
        print(msg)

    if do_log:
        if not file_out_path_name:
            file_out_path_name = "test_log_" + datetime.now().strftime("%Y_%m_%d_%H_%M_%S") + ".txt"
        with open(file_out_path_name, "w") as file_out:
            file_out.write(msg)


if __name__ == '__main__':

    test_loader = unittest.TestLoader()
    test_names = test_loader.getTestCaseNames(SystemTests)

    suite = unittest.TestSuite()
    
    #Run all tests    
    for test_name in test_names:
       suite.addTest(SystemTests(test_name))

    # Run specific test        
    # suite.addTest(SystemTests("test_001"))            

    #Remove old out and test_log and create new out
    remove_old_files_directories()

    #Run main testing routine
    test_run_testner = unittest.TextTestRunner(buffer = False)
    output_test = test_run_testner.run(suite)

    # create_export_test_report(output_test)
    report_tests(output_test)

# %%

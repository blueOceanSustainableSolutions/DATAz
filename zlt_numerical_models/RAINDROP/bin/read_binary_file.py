from numpy import *
import binascii
import glob
import re
import subprocess
import os
import re
import sys

case_name = sys.argv[1]

pattern = r'\d+'

#To correct faulty .mod files!
for path in glob.glob(f'./calcs/freq/freq*/envFiles/{case_name}_*.mod'):
    print(path, end='\r')
    with open(path, 'rb') as file:
        occurences = len(re.findall(case_name,str(file.read())))
        if occurences == 2:
            print(path)
            #Get .mod file name and number, to substitute it by the one immediately before
            mod_name = os.path.basename(path)
            mod_number = int(re.search(pattern, mod_name).group())
            path_dir = os.path.dirname(path)
            subprocess.run(['cp', '-f', path_dir+'/{}_{}.mod'.format(case_name, mod_number-1), path_dir+'/{}_{}.mod'.format(case_name, mod_number)])
            print('Copied {} to {}!'.format(path_dir+'/{}_{}.mod'.format(case_name, mod_number-1), path_dir+'/{}_{}.mod'.format(case_name, mod_number)))
        #print(file.read())
    #recl  = int( fromfile( file, int32, 1 ) )
    #print(recl)
    #title = file.read(80)
    #print(title)
    #print()
    #fid.seek( 4*recl )
    #PlotType = fid.read(10)
    #for i in range(0,50):
    #print(file.read())
    #    b = file.read(16)
    #    ascii = binascii.b2a_uu(b)
    #    print(ascii)
        #print(b)

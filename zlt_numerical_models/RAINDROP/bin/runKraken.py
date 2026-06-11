import sys
import os
import subprocess
import glob
import csv
import yaml
from writeEnvironment import writeEnv
from writeBathymetry import bathymetry
#from alive_progress import alive_bar
import subprocess
import pandas as pd
from tqdm import tqdm

def kraken(pathEnv, pid):
    """
    Open configuration file
    """
    #Open user controls in YAML format
    with open(pathEnv+'/controls.yaml', 'r') as f:
        config = yaml.safe_load(f)

    #Get SSP path
    pathSSP = config['KRAKEN']['SSP']['SSP1']['path']

    title = config['GENERAL']['title']

    krakenExe = config['KRAKEN']['krakenExe']

    #Only write bty file if it does not exist, to prevent conflicts with multiprocessing
    if not os.path.exists('bathymetry/bathymetry.bty'):
        nPoints, refLon, refLat = bathymetry(config)

    frequency = config['KRAKEN']['frequency']

    #If not stated, path is current one
    if pathEnv == None:
        pathEnv = '.'

    #Import existent .bty file
    bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
    lon = bath[0].to_list()
    lat = bath[1].to_list()
    depths = bath[2].to_list()
    lonOrg = bath[3].to_list()
    latOrg = bath[4].to_list()

    nPoints = len(lon)
    refLon = min(lonOrg)
    refLat = min(latOrg)


    #Important to know if Delaunay triangulation is necessary
    #and how the .env files will be produced
    if config['GENERAL']['dimensions'] == '3D':
        is3D = True
    else:
        is3D = False


    #If 3D, generate an .env file for each bathymetry point
    if is3D:
        #os.system("rm -rf {0}/envFiles".format(pathEnv))
        #os.system("mkdir {0}/envFiles".format(pathEnv))
        subprocess.run(['rm', '-rf', '{0}/envFiles'.format(pathEnv)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['mkdir', '{0}/envFiles'.format(pathEnv)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        #print("\n")
        description = "Writing env. files [{} Hz]".format(frequency)
        units = "oper."
        color = 'blue'
        with tqdm(total=len(depths)+1, desc=description, position=pid+1, unit=units, colour=color, leave=False) as pbar:
            for depth, nDepth in zip(depths, range(0, len(depths))):
                writeEnv(config, depth, nDepth, pathEnv)
                #os.system("mv {0}/dummy.env {0}/envFiles/{1}_{2}.env".format(pathEnv, title, nDepth))
                subprocess.run(['mv', '{0}/dummy.env'.format(pathEnv), '{0}/envFiles/{1}_{2}.env'.format(pathEnv, title, nDepth)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                pbar.update(1)
            
            pbar.reset()
            description = "Running KRAKEN [{} Hz]".format(frequency)
            pbar.set_description(description)

            #Run KRAKEN for each .env file
            for depth, nDepth in zip(depths, range(0, len(depths))):
                #os.system("{0} {1}/envFiles/{2}_{3} &> /dev/null".format(krakenExe, pathEnv, title, nDepth))
                subprocess.run([krakenExe, '{0}/envFiles/{1}_{2}'.format(pathEnv, title, nDepth)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                pbar.update(1)

            pbar.reset()
            description = "Checking .mod files [{} Hz]".format(frequency)
            pbar.set_description(description)

            #Since KRAKEN output is silenced, provide number of .mod files not generated
            #Filter those that were not run because depth != 0.0m
            modFilesReal = 0
            modFilesExpected = 0
            for depth, nDepth in zip(depths, range(0, len(depths))):
                if float(depth)!=0.0:
                    success = int(subprocess.check_output("cd {0}/envFiles; find . -name '{1}_{2}.mod' | wc -l".format(pathEnv,title, nDepth), shell=True).decode('utf-8').strip())
                    
                    modFilesExpected += 1
                    if success==1:
                        modFilesReal += 1
                else:
                    #Dummy file for 0m depths, although empty
                    #os.system("touch {0}/envFiles/{1}_{2}.mod".format(pathEnv, title, nDepth))
                    subprocess.run(['touch', '{0}/envFiles/{1}_{2}.mod'.format(pathEnv, title, nDepth)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                pbar.update(1)
            
            if modFilesReal == modFilesExpected:
                return "[bold green]Success - All .mod files produced."
            else:
                return "[bold red]Warning - Only {0} from {1} .mod files were produced, check for errors.".format(modFilesReal,modFilesExpected)





if __name__ == "__main__":
    kraken(pathEnv)

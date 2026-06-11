import sys
import os
import subprocess
import glob
import yaml
import numpy as np
import runField3D
import multiprocessing
from tqdm import tqdm
from rich import print

def runField3DSingleFrequency(sourceFieldList):

    """
    Open configuration file
    """
    #Open user controls in YAML format
    with open('controls.yaml', 'r') as f:
        config = yaml.load(f, Loader=yaml.Loader)


    src  = sourceFieldList[0]
    pos  = sourceFieldList[1]
    freq = sourceFieldList[2]
    tol  = sourceFieldList[3]
    pid  = sourceFieldList[4]
    nSource = sourceFieldList[5]

    #Dump YAML general config file with correct frequency
    pathEnv = 'calcs/freq/freq{0}/{1}'.format(int(freq), src)
    #os.system('rm -r {0}; mkdir -p {0}'.format(pathEnv))
    #os.system('touch {0}/controls.yaml'.format(pathEnv))
    subprocess.run(['rm', '-r', pathEnv],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['mkdir', '-p', pathEnv],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['touch', '{0}/controls.yaml'.format(pathEnv)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with open('{0}/controls.yaml'.format(pathEnv), 'w') as ff:
        config['KRAKEN']['frequency']                   = float(freq)
        config['FIELD3D']['SourcePosition']['nSources'] = 1.0
        config['FIELD3D']['SourcePosition']['source1']  = pos
        config['PLOTS']['SPL']['source1']               = tol
        yaml.dump(config, ff, default_flow_style=False)

    #Redefine pathEnv, to not define source
    pathEnv = 'calcs/freq/freq{0}'.format(int(freq))

    #Run FIELD3D in single frequency mode
    runField3D.field3d(pathEnv,pid,nSource)

    return


def runNoiseMapField3D():
    """
    Open configuration file
    """
    #Open user controls in YAML format
    with open('controls.yaml', 'r') as f:
        config = yaml.load(f, Loader=yaml.Loader)

    #Get number of cores to parallelize
    nCores = int(config['GENERAL']['nCores'])

    #Source characterization
    freqs = []
    tols  = []
    #Get frequencies from available sources TOL
    source_list = glob.glob('sources/*.srcs')
    nSourcesList = len(source_list)
    for source in source_list:
        ff = []
        tt = []
        with open(source, 'r') as f:
            # Read the first line to get the column headers
            headers = f.readline().strip().split(' ')
            # Read the remaining lines and split each line on tab
            for line in f:
                f, t = line.strip().split(' ')
                ff.append(float(f))
                tt.append(float(t))
            freqs.append(ff)
            tols.append(tt)

    pos = []
    #Read their positions in their general controls
    for s in range(1, len(source_list)+1):
        x = float(config['FIELD3D']['SourcePosition']['source{}'.format(s)][0])
        y = float(config['FIELD3D']['SourcePosition']['source{}'.format(s)][1])
        pos.append([x,y])

    sourceFieldList = []
    #Create a list with each source frequencies and TOL
    #Include a PID like number, for the progress bar
    pid = 0
    for s in range(0, len(source_list)):
        for f,t in zip(freqs[s], tols[s]):
            sourceFieldList.append(['source{}'.format(s+1), pos[s], f, t, pid, s+1])
            if (pid == (nCores-1)):
                pid=0
            else:
                pid+=1

    #Run FIELD3D in parallel for each source and frequency
    with multiprocessing.Pool(processes=nCores, initargs=(multiprocessing.RLock(),), initializer=tqdm.set_lock) as pool:
        pool.map(runField3DSingleFrequency, sourceFieldList)
        pool.close()
        pool.join()

    return

if __name__ == "__main__":
    runNoiseMapField3D()

    
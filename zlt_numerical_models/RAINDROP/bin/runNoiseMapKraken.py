import sys
import subprocess
import glob
import yaml
import numpy as np
import runKraken
import multiprocessing
from writeBathymetry import bathymetry
from tqdm import tqdm
from rich import print

def runKrakenSingleFrequency(freqs_pid):

    freq, pid = freqs_pid

    #Create calculation folder and go there
    #os.system('mkdir -p calcs/freq/freq{0}'.format(int(freq)))
    subprocess.run(['mkdir', '-p', 'calcs/freq/freq{0}'.format(int(freq))],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    #Dump YAML general config file with correct frequency
    #os.system('touch calcs/freq/freq{0}/controls.yaml'.format(int(freq)))
    subprocess.run(['touch', 'calcs/freq/freq{0}/controls.yaml'.format(int(freq))],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open('calcs/freq/freq{0}/controls.yaml'.format(int(freq)), 'w') as ff:
        config['KRAKEN']['frequency'] = str(freq)#float(freq)
        yaml.dump(config, ff, default_flow_style=False)

    #Run KRAKEN in single frequency mode
    results = runKraken.kraken('calcs/freq/freq{0}'.format(int(freq)), pid)

    return results




if __name__ == "__main__":

    multiprocessing.set_start_method('fork')

    """
    Open configuration file
    """
    #Open user controls in YAML format
    with open('controls.yaml', 'r') as f:
        config = yaml.load(f, Loader=yaml.Loader)

    #Bathymetry write file
    bathymetry(config)

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

    #Round and deduplicate freqs
    freqs = np.unique(np.around(freqs,1))
    #Remove existent folder with old calcs
    #os.system('rm -r calcs/freq; mkdir -p calcs/freq')
    subprocess.run(['rm', '-r', 'calcs/freq'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['mkdir', '-p', 'calcs/freq'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


    #Get number of cores to parallelize
    nCores = int(config['GENERAL']['nCores'])
    #Associate the index of the frequency in the list in a tuple
    #This is to associate a PID-like number to the multiprocessing
    freqs_pid = [(value, index%nCores) for index, value in enumerate(freqs)]
    #chunk_size = len(freqs) // (nCores * 2) + 1
    #Run KRAKEN in parallel for each frequency
    with multiprocessing.Pool(processes=nCores, initargs=(multiprocessing.RLock(),), initializer=tqdm.set_lock) as pool:
        results = pool.map(runKrakenSingleFrequency, freqs_pid)
        pool.close()
        pool.join()

    for freq, result in zip(freqs, results):
        print("{0} Hz - {1}".format(freq, result))
        
        

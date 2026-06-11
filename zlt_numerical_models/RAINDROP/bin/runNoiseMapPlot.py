import sys
import subprocess
import glob
import yaml
import numpy as np
import runField3D
import multiprocessing
import runPlot


def runNoiseMapPlot(time=None, isEmpty=False):
    """
    Open configuration file
    """
    #Open user controls in YAML format
    with open('controls.yaml', 'r') as f:
        config = yaml.load(f, Loader=yaml.Loader)

    backgroundNoise = float(config['PLOTS']['backgroundNoise'])
    maxNoise        = float(config['PLOTS']['maxNoise'])

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
    for s in range(0, len(source_list)):
        for f,t in zip(freqs[s], tols[s]):
            sourceFieldList.append(['source{}'.format(s+1), pos[s], f, t])

  
    #Delete existent pickle with coordinates, to be rerwitten in plot functions!
    subprocess.run(['rm', '-f', './bathymetry/coords.pickle'])

    #runPlot.plotBathymetry(config)

    #for s in range(0, len(source_list)):
    #    for f,t in zip(freqs[s], tols[s]):
    #        runPlot.plotTL(config,f,s+1,pos[s])
    #        runPlot.plotSPL(config,f,s+1,pos[s],t, time, backgroundNoise, maxNoise)
    #    runPlot.plotSPLBroadband(config,freqs[s],s+1,pos[s],tols[s], time, backgroundNoise, maxNoise)

    #runPlot.plotSPLBroadbandAll(config,freqs[s],len(source_list), time, backgroundNoise, maxNoise)

    #runPlot.plotSPLBroadbandAllEfficient(config, sourceFieldList, freqs[-1], time, backgroundNoise, maxNoise, isEmpty)

    runPlot.plotSPLwithAIS(config, sourceFieldList, freqs[-1], time, backgroundNoise, maxNoise, isEmpty)

    return

if __name__ == "__main__":
    runNoiseMapPlot()

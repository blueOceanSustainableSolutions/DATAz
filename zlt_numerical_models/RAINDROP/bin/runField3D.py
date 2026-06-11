import sys
import subprocess
import os
import csv
import yaml
import pandas as pd
import numpy as np
from scipy.interpolate import griddata
import pickle
from writeFLP import writeFLP
from readshd import readshd
import warnings
from tqdm import tqdm


def savePressureMatrix(pressure, geometry, config, sourceLon, sourceLat, nSidePoints, pathEnv, nSource):
        #Open bathymetry CSV file, with DEPTH[m], LON, LAT
        bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
        lonNormUTM = bath[0].to_list()
        latNormUTM = bath[1].to_list()
        lonOrg     = bath[3].to_list()
        latOrg     = bath[4].to_list()
        depths     = bath[2].to_list()
        lonOrgUTM  = bath[5].to_list()
        latOrgUTM  = bath[6].to_list()

        pathEnv = pathEnv + '/' + 'source' + str(nSource)

        #General info
        freq  = float(config['KRAKEN']['frequency'])
        #From special config file in flpFiles, which for source1 has correct SPL from TOL
        #spl = float(config['PLOTS']['SPL']['source1'])
        xs = sourceLon
        ys = sourceLat

        #Coordinates of pressure by FIELD3D
        thetas = geometry["thetas"]
        rarray = geometry["rarray"]
        zarray = geometry["zarray"]
        R,Thetas= np.meshgrid(rarray,thetas)
        X = R*np.cos( Thetas*np.pi/180.0 )
        Y = R*np.sin( Thetas*np.pi/180.0 )

        #Cartesian coordinates to be interpolated to
        x_str = np.linspace(np.min(lonNormUTM), np.max(lonNormUTM), nSidePoints)
        y_str = np.linspace(np.min(latNormUTM), np.max(latNormUTM), nSidePoints)
        X_str, Y_str = np.meshgrid(x_str, y_str)

        #Interpolate pressure to cartesian grid
        pressure = np.squeeze( pressure )
        pressure_xy = griddata((X.flatten()*1e-3+xs,Y.flatten()*1e-3+ys), pressure.flatten(), (X_str,Y_str), method='linear')

        #Add respective TOL SPL
        #Assume that they are in phase?
        #pressure_xy = pressure_xy*(10.0**(spl/20.0))

        #os.system('touch {0}/source_{1}.pickle'.format(pathEnv, int(freq)))
        subprocess.run(['touch', '{0}/source_{1}.pickle'.format(pathEnv, int(freq))],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open('{0}/source_{1}.pickle'.format(pathEnv, int(freq)), 'wb') as f:
            pickle.dump(pressure_xy, f)

        return


def field3d(pathEnv,pid,nSource):

    warnings.filterwarnings("ignore",category=UserWarning)
    warnings.filterwarnings("ignore",category=RuntimeWarning)

    #If not stated, path is current one
    if pathEnv == None:
        pathEnv = '.'

    """
    Open configuration file
    """
    #Open user controls in YAML format
    with open('{0}/controls.yaml'.format(pathEnv), 'r') as f:
        config = yaml.safe_load(f)

    #Open user controls in YAML format
    #General, to enable FIELD3D to be adapted from the main controls,
    #after KRAKEN was already executed
    with open('./controls.yaml', 'r') as f:
        config_general = yaml.safe_load(f)

    nSources = int(config_general['FIELD3D']['SourcePosition']['nSources'])

    frequency = int(float(config['KRAKEN']['frequency']))

    nSideTL  = int(config_general['PLOTS']['TL']['nSide'])

    #plot_TL  = config['PLOTS']['TL']['plot']
    plot_SPL = config_general['PLOTS']['SPL']['plot']
    sourceSPL = []
    sourceLonAll = []
    sourceLatAll = []
    pressureAll = []
    geometryAll = []

    units = "oper."
    color = 'green'
    with tqdm(total=4, position=pid+1, unit=units, colour=color, leave=False) as pbar:
            
        description = "Writing .FLP file [{0}/{1} - {2} Hz]".format(nSource, nSources, frequency)
        pbar.set_description(description)
        #Write FPL file
        sourceLon, sourceLat = writeFLP(config, config_general, nSource, pathEnv)

        pbar.update(1)

        description = "Running FIELD3D [{0}/{1} - {2} Hz]".format(nSource, nSources, frequency)
        pbar.set_description(description)
        #Execute FIELD3D
        #print("Running FIELD3D for source {} of {}...".format(n, nSources))
        title      = config_general['GENERAL']['title']
        field3dExe = config_general['FIELD3D']['field3dExe']
        os.system('cd {0}/source{3}/flpFiles; {1} {2}; mv {2}.shd {2}_{3}.shd; cd ..'.format(pathEnv, field3dExe, title, nSource))
        

        pbar.update(1)

        description = "Reading SHD files [{0}/{1} - {2} Hz]".format(nSource, nSources, frequency)
        pbar.set_description(description)
        #Read SHD file
        pressure, geometry = readshd(pathEnv+"/source"+str(nSource)+"/flpFiles/"+title+"_"+str(nSource)+".shd", sourceLon[0], sourceLat[0])


        pbar.update(1)

        description = "Saving pressure matrix [{0}/{1} - {2} Hz]".format(nSource, nSources, frequency)
        pbar.set_description(description)
        #Save pressure for plot
        savePressureMatrix(pressure, geometry, config, sourceLon[0], sourceLat[0], nSideTL, pathEnv, nSource)

        pbar.update(1)

        #description = "Plotting [{0}/{1} - {2} Hz]".format(n, nSources, frequency)
        #pbar.set_description(description)
        #Plot
        #if plot_TL == 'yes':
        #    plot3DTL(pressure, geometry, config, sourceLon, sourceLat, n)

        #if plot_SPL == 'yes':
        #    sourceSPL.append(float(config['PLOTS']['SPL']['source{}'.format(n)]))
        #    pressureAll.append(pressure)
        #    geometryAll.append(geometry)
        #    sourceLonAll.append(sourceLon)
        #    sourceLatAll.append(sourceLat)

    pbar.reset()

    #if plot_SPL == 'yes':
    #    plot3DSPL(pressureAll, geometryAll, config, sourceLonAll, sourceLatAll, nSources)



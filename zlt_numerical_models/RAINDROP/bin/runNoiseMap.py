import numpy as np
import pandas as pd
from tqdm import tqdm
import yaml
import subprocess
from readAIS import readAIS
from writeSPL import writeSPL
from runNoiseMapField3D import runNoiseMapField3D
from runNoiseMapPlot import runNoiseMapPlot
import gc
import datetime
import os
import glob


def main(aisPath, aisShipInfoPath, realTime, stepTime, startTime=None, endTime=None):

    #TODO: adapt to real-time data
    #Read historical AIS data
    #Standardize column names

    if not realTime:
        ais = pd.read_csv(aisPath)
        ais_identifications = pd.read_csv(aisShipInfoPath)

        #Get times rounded to the lowest minute
        ais['WriteTime'] = pd.to_datetime(ais['WriteTime'])
        ais['WriteTimeRounded'] = ais['WriteTime'].dt.floor('min')

        #Get start and end time of data, to iterate later
        #start_time = ais['WriteTimeRounded'].values[0]
        #end_time   = ais['WriteTimeRounded'].values[-1]
        if endTime != None:
            total_minutes = (pd.to_datetime(endTime)-pd.to_datetime(startTime)).total_seconds()/60
        else:
            #No duration defined
            total_minutes = None
            endTime = np.datetime64('2100-04-21T00:00:00')

        time = startTime
    
    else:
        #Real time, file will have to be relative to clock time. UTC to prevent confusions!!!
        now = np.datetime64(datetime.datetime.utcnow())
        startTime = now - np.timedelta64(stepTime, 'm')
        #Round to nearest lower minute
        startTime = np.datetime64(pd.to_datetime(startTime).floor('T'))

        #Very large date to endTime, in order to never stop - hopefully :)
        endTime = np.datetime64('2100-04-21T00:00:00')

        total_minutes = None

        time = startTime


    subprocess.run(['mkdir', '-p', 'out/maps', 'out/pickles', 'out/ais', 'out/latest_maps', 'out/nc'])

    #Open user controls in YAML format
    with open('controls.yaml', 'r') as f:
        config = yaml.load(f, Loader=yaml.Loader)


    #Save a copy, since it will be changed
    subprocess.run(['cp', 'controls.yaml', 'controls_original.yaml'])

    min_f = int(config['GENERAL']['frequencyBand'][0])
    max_f = int(config['GENERAL']['frequencyBand'][1])

    with tqdm(total=total_minutes, colour='red', leave=False) as pbar:
        while (time <= endTime):

            #If realTime, we need to update always the variable, to get the latest data from file
            if realTime:
                ais = pd.read_csv(aisPath)
                ais_identifications = pd.read_csv(aisShipInfoPath)
                #Get times rounded to the lowest minute
                ais['WriteTime'] = pd.to_datetime(ais['WriteTime'])
                ais['WriteTimeRounded'] = ais['WriteTime'].dt.floor('min')

            
            #Check if auxiliary file depth exists, to easily modify it on the fly
            if os.path.isfile('depth.dat'):
                with open('depth.dat', 'r') as f:
                    newDepth = f.readline().splitlines()[0]

                with open('controls.yaml', 'w') as ff:
                    config['FIELD3D']['ReceiverDepths']['depths'] = [newDepth]
                    yaml.dump(config, ff, default_flow_style=False)

                #Re-Open user controls in YAML format
                with open('controls.yaml', 'r') as f:
                    config = yaml.load(f, Loader=yaml.Loader)

            # Get limits of AIS domain, to prevent boundary effects in the calculations
            lon_max = float(config['GENERAL']['aisLimits']['xEnd'])
            lon_min = float(config['GENERAL']['aisLimits']['xStart'])
            lat_max = float(config['GENERAL']['aisLimits']['yEnd'])
            lat_min = float(config['GENERAL']['aisLimits']['yStart'])

            #Search AIS for ships in nearest minute, get pos, vel and type. Skip the rest if no ships
            nShips, lons, lats, velocities, lengths, types = readAIS(ais, time, ais_identifications, lon_min, lon_max, lat_min, lat_max)

            #Get for each ship the spectrum and create sources/source*.srcs folder until a maximum frequency
            if (nShips != 0):
                subprocess.run(['rm', '-rf', './sources'])
                for nShip in range(0, nShips):
                    subprocess.run(['mkdir', '-p', './sources'])
                    pathSource = './sources'
                    writeSPL(pathSource, nShip+1, types[nShip], velocities[nShip], lengths[nShip], min_f, max_f)

                #   Update yaml file with source positions!
                with open("controls.yaml", 'w') as f:
                    config['FIELD3D']['SourcePosition'] = {}
                    config['FIELD3D']['SourcePosition']['nSources'] = str(nShips)
                    config['FIELD3D']['SourcePosition']['units'] = 'WGS84'
                    for n in range(1, nShips+1):
                        config['FIELD3D']['SourcePosition']['source{}'.format(n)] = [str(lons[n-1]), str(lats[n-1])]
                    yaml.dump(config, f)

                runNoiseMapField3D()

                runNoiseMapPlot(time, isEmpty=False)

                #Collect and clean garbage
                gc.collect()

                subprocess.run(['mv', 'calcs/freq/SPL_ALL.pickle', 'out/pickles/SPL_{}.pickle'.format(time)])

                listPickles = glob.glob('calcs/freq/*.pickle')
                for pickle in listPickles:
                    freq = pickle.split('_')[-1].split('.')[0]
                    if freq!='31':
                        freq = freq + '.0'
                    else:
                        freq = freq + '.5'
                    subprocess.run(['mv', 'calcs/freq/SPL_ALL_{}.pickle'.format(freq), 'out/pickles/SPL_{0}_{1}.pickle'.format(time, freq)])
                
                subprocess.run(['mv', 'noise_map.png', 'out/maps/noise_map_{}.png'.format(time)])
                #Copy map, to have a file always updated for showing
                subprocess.run(['cp', '-f', 'out/maps/noise_map_{}.png'.format(time), 'out/latest_maps/latest_map.png'])


            else:
                runNoiseMapPlot(time, isEmpty=True)

                subprocess.run(['mv', 'calcs/freq/SPL_ALL.pickle', 'out/pickles/SPL_{}.pickle'.format(time)])

                listPickles = glob.glob('calcs/freq/*.pickle')
                for pickle in listPickles:
                    freq = pickle.split('_')[-1].split('.')[0]
                    freq = freq + '.0'
                    subprocess.run(['mv', 'calcs/freq/SPL_ALL_{}.pickle'.format(freq), 'out/pickles/SPL_{0}_{1}.pickle'.format(time, freq)])

                subprocess.run(['mv', 'noise_map.png', 'out/maps/noise_map_{}.png'.format(time)])
                #Copy map, to have a file always updated for showing
                subprocess.run(['cp', '-f', 'out/maps/noise_map_{}.png'.format(time), 'out/latest_maps/latest_map.png'])


            #else:
            #    runNoiseMapPlot(empty=True)
            #    subprocess.run(['mv', 'noise_map.png', 'out/maps/noise_map_{}.pickle'.format(time)])

            #If real-time, wait for the next time period to have happened!
            if realTime:
                now = np.datetime64(datetime.datetime.utcnow())
                while now <= (time + 2*np.timedelta64(stepTime, 'm')):
                    now = np.datetime64(datetime.datetime.utcnow())

            pbar.update(1)
            time += np.timedelta64(stepTime, 'm')

    #Save and delete copy, since it will be changed
    subprocess.run(['cp', 'controls_original.yaml', 'controls.yaml'])
    subprocess.run(['rm', 'controls_original.yaml'])

    return

if __name__=="__main__":
    """
    Open configuration file
    """
    #Open user controls in YAML format
    with open('controls.yaml', 'r') as f:
      config = yaml.load(f, Loader=yaml.Loader)

    realTime = config['GENERAL']['realTime']
    stepTime = int(config['GENERAL']['stepTime'])
    aisPath  = config['GENERAL']['aisPath']
    aisShipInfoPath  = config['GENERAL']['aisShipInfoPath']

    startTime = None
    endTime=None

    if not realTime:
        startTime = np.datetime64(config['GENERAL']['startTime'])
        endTime = np.datetime64(config['GENERAL']['endTime'])

    main(aisPath, aisShipInfoPath, realTime, stepTime, startTime, endTime)

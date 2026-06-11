import numpy as np
import pandas as pd
import datetime
from time import sleep
import pickle
import keplergl
from keplergl_cli import Visualize


def plotKepler(time, ais, spl, config):

    #if config!=None:
        #map = keplergl.KeplerGl(height=500, data={'AIS': ais, 'SPL': spl}, config=config)
    #else:
        #map = keplergl.KeplerGl(height=500, data={'AIS': ais, 'SPL': spl})

    map = Visualize(api_key='')
    map.add_data(data=ais, names='AIS')
    map.add_data(data=spl, names='SPL')
    map.render(open_browser=False)

    return map


def saveHTML(map, time, now, config, read_only=False):

    if now == None:
        map.save_to_html('./out/kepler/map_{}.html'.format(time), config=config, read_only=read_only)
    else:
        #If real time, save only last map
        map.save_to_html('./out/kepler/map_now.html'.format(time), config=config, read_only=read_only)

    return


def readFiles(time):

    #Read coordinates
    with open('./coords.pickle', 'rb') as f:
        coords = pickle.load(f)

    #Read SPL
    with open('./out/pickles/SPL_{}.pickle'.format(time), 'rb') as f:
        spl = pd.DataFrame(pickle.load(f).flatten())

    #Concatenate coords with SPL
    spl = pd.concat([coords, spl])

    #Read AIS
    with open('./out/ais/AIS_{}.pickle'.format(time), 'rb') as f:
        ais = pickle.load(f)

    #Read config, it is exists
    try:
        with open('./config_kepler.dat', 'r') as f:
            config = f.read(f)
    except:
        config = None

    return ais, spl, config



def main(start_time, end_time, dt):

    #dt is in minutes

    #Run until infinity
    if end_time==None:
        end_time = np.datetime64('2100-04-21T00:00:00')

    #Now means real-time analysis!
    if start_time=='now':
        start_time = np.datetime64(datetime.datetime.now())
        now = start_time
        start_time = start_time - np.timedelta64(dt, 'm')
        #Round to nearest lower minute
        start_time = np.datetime64(pd.to_datetime(start_time).floor('T'))
    #If not real-time analysis
    else:
        now=None

    time = start_time
    
    while time <= end_time:

        #Read input files
        ais, spl, config = readFiles(time)

        #Create map
        map = plotKepler(time, ais, spl, config)

        #Save html
        saveHTML(map, time, now, config, read_only=False)

        #Save png


        #If real-time, wait for the next time period to have happened :)
        if now != None:
            while now <= (time + 2*np.timedelta64(dt, 'm')):
                now = datetime.datetime.now()

        time += np.timedelta64(dt, 'm')

    return

if __name__ == "__main__":
    #main('.', 'now', None, 1)
    main(np.datetime64('2023-07-30T16:32:00'), None, 1)

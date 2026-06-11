import numpy as np
import pandas as pd
import json
import pickle

def readAIS(ais_data, time, ais_identifications, lon_min, lon_max, lat_min, lat_max):

    #TODO: Do here the rounding of time, when using real-time
    #Velocity is capped at a minimum of 1kts
    ais = ais_data[(ais_data['WriteTimeRounded'] == time) & (ais_data['Sog'] >= 1.0)]
    # Further filter based on coordinates:
    ais = ais[(ais['Longitude'] >= lon_min) & (ais['Longitude'] <= lon_max) & (ais['Latitude'] >= lat_min) & (ais['Latitude'] <= lat_max)]
    
    ais_ships = ais.groupby('UserID')


    lons       = []
    lats       = []
    velocities = []
    lengths    = []
    types      = []
    names      = []
    nShips = 0

    for ship_id, group in ais_ships:

        longitude = group['Longitude'].mean()
        latitude  = group['Latitude'].mean()
        velocity  = group['Sog'].mean()

        #Identify ship data from ais_identifications
        try:
            ship_info = ais_identifications.loc[ais_identifications['UserID'] == ship_id]
            ship_type = ship_info['Type'].values[-1]
            length = ship_info['DimensionA'].values[-1] + ship_info['DimensionB'].values[-1]
            ship_name = ship_info['Name'].values[-1]
        except:
            ship_type = None
            length = None
            ship_name = None


        lons.append(longitude)
        lats.append(latitude)
        velocities.append(velocity)
        types.append(ship_type)
        lengths.append(length)
        names.append(ship_name)
        nShips += 1

        #JSON time, for compatibility with external plotting software
        time_json = json.dumps(pd.to_datetime(time), default=str)

        data_to_pickle = pd.DataFrame({'Longitude'      : lons,
                                        'Latitude'       : lats,
                                        'Name'           : names,
                                        'Velocity [kts]' : velocities,
                                        'Type'           : types,
                                        'Length [m]'     : lengths,
                                        'Time'           : time_json
                                        })
        
        with open('./out/ais/AIS_{}.pickle'.format(time), 'wb') as f:
            pickle.dump(data_to_pickle, f)
        


    return nShips, lons, lats, velocities, lengths, types

import numpy as np
import pandas as pd
import pickle
import yaml
import geopandas as gpd
import utm


path = './out/pickles/SPL_2023-07-24T10:48:00.000000000.pickle'

"""
Open configuration file
"""
#Open user controls in YAML format
with open('controls.yaml', 'r') as f:
    config = yaml.load(f, Loader=yaml.Loader)

#Open bathymetry CSV file, with DEPTH[m], LON, LAT
bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
lonNormUTM = bath[0].to_list()
latNormUTM = bath[1].to_list()
lonOrg     = bath[3].to_list()
latOrg     = bath[4].to_list()
depths     = bath[2].to_list()
lonUTM = (bath[5]*1e3).to_list()
latUTM = (bath[6]*1e3).to_list()

nSideTL  = int(config['PLOTS']['TL']['nSide'])

x_org = np.linspace(np.min(lonOrg), np.max(lonOrg), nSideTL)
y_org = np.linspace(np.min(latOrg), np.max(latOrg), nSideTL)
X_org, Y_org = np.meshgrid(x_org, y_org)

x_str = np.linspace(np.min(lonUTM), np.max(lonUTM), nSideTL)
y_str = np.linspace(np.min(latUTM), np.max(latUTM), nSideTL)
X_str, Y_str = np.meshgrid(x_str, y_str)

X_str = X_str.flatten()
Y_str = Y_str.flatten()

Y_org, X_org = utm.to_latlon(X_str, Y_str,29,'S')


with open(path, 'rb') as f: 
    SPL = pickle.load(f)

data = {
        'lon': X_org.flatten(),
        'lat': Y_org.flatten()
        #'SPL': SPL.flatten()
}

df = pd.DataFrame(data)
#df.drop(df[df['SPL'] <= 101.0].index, inplace = True)

with open('coords.pickle', 'wb') as f:
    pickle.dump(df, f)

#gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['lon'], df['lat']))

#gdf.crs = 'EPSG:4326'

#output_shapefile = 'test.shp'
#gdf.to_file(output_shapefile)
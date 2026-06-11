import pickle
import pandas as pd
import numpy as np
from netCDF4 import Dataset
import time as tm
from datetime import datetime
import xarray as xr
import matplotlib.pyplot as plt
import glob

def export_netCDF(lon, lat, spl, depth_value, filename):
    
    # Latitude is assumed to have the same size
    nSize = np.shape(lon)[0]

    # Creat netCDF variable
    nc = Dataset(filename, "w", format="NETCDF4_CLASSIC")

    # Assign metadata
    nc.Conventions = "CF-1.7"
    nc.title = "Underwater noise map"
    nc.institution = "RAINDROP"
    nc.source = "RAINDROP"
    nc.history = "Written at " + str(datetime.utcnow()) + " in Python"

    # Assign dimensions
    time = nc.createDimension("time", 1)
    depth = nc.createDimension("depth", 1)
    latitude = nc.createDimension("lat", nSize)
    longitude = nc.createDimension("lon", nSize)

    #Time variable
    time_var = nc.createVariable("time", np.float64, ("time",))
    time_var.long_name = "Time"
    time_var.standard_name = "time"
    #time_var.calendar = "gregorian"
    #time_var.units = "minutes since 2023-08-02 00:00:00"

    #Depth variable
    depth_var = nc.createVariable("depth", np.float32, ("depth",))
    depth_var.long_name = "depth"
    depth_var.standard_name = "Depth"
    depth_var.positive = "down"
    depth_var.units = "meter"

    #Latitude
    latitude_var = nc.createVariable("lat", np.float32 ,("lat",))
    latitude_var[:] = lat
    latitude_var.units = 'degrees_north'
    latitude_var.standard_name = 'projection_y_coordinate'
    latitude_var.long_name = 'latitude'

    #Longitude
    longitude_var = nc.createVariable("lon", np.float32 ,("lon",))
    longitude_var[:] = lon
    longitude_var.units = 'degrees_east'
    longitude_var.standard_name = 'projection_x_coordinate'
    longitude_var.long_name = 'longitude'


    # SPL Variable
    spl_var = nc.createVariable("spl", np.float32, ("time","depth","lat","lon",), zlib=True)
    spl_var.units = "dB"
    spl_var.standard_name = "sound_pressure_level_in_water"
    spl_var.long_name = "Sound pressure level in water"
    spl_var.missing_value = 0.0
    spl_var.coordinates = "lon lat"
    #spl_var.grid_mapping = "longitude_latitude"


    #Assign variables
    depth_var[:] = depth_value

    t = 0
    spl_var[t,0,:,:] = spl

    nc.close()

    return
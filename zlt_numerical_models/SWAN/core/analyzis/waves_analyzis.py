import datetime
import os
import numpy as np

import matplotlib.pyplot as plt
import pandas as pd

from core.simulation_case.case import Case
from core.swan.utils import format_datetime
from core.utils.netcdf import extract_nearest_ts

from netCDF4 import Dataset, num2date
from matplotlib.animation import FuncAnimation

import glob

plt.style.use('classic')
plt.rcParams['font.size'] = 16
plt.rcParams['font.family'] = 'Serif'
plt.rcParams['axes.facecolor'] = 'white'  # White background for the plot area
plt.rcParams['figure.facecolor'] = 'white'  # White background outside the plot area
plt.rcParams['savefig.facecolor'] = 'white'  # White background when saving figures
plt.close('all')

#%%


class WaveProcessing:
    def __init__(self, case: Case,
                 Hs_output_file = None,
                 elevation_file = None):
        
        if '*' in Hs_output_file:
            matching_files = glob.glob(Hs_output_file)
            if matching_files:
                self.Hs_output_file = matching_files[0]
            else:
                raise FileNotFoundError(f"No files match the pattern: {Hs_output_file}")
        else:
            self.Hs_output_file = Hs_output_file  # Directly use the provided file if no wildcard

        print(f"Using Hs_output_file: {self.Hs_output_file}")
        
        # self.Hs_output_file = Hs_output_file
        self.case = case
        self.elevation_file = elevation_file

    def plot_Hs(self):
        df = Dataset(self.Hs_output_file, mode='r')
        
        try:
            lons = df.variables['longitude'][:]
            lats = df.variables['latitude'][:]
            
            hs = df.variables['swh'][:]
        except:
            lons = df.variables['lon'][:]
            lats = df.variables['lat'][:]
            
            hs = df.variables['hs'][:]
        
        print("Variables in the dataset:")
        for var_name in df.variables:
            print(var_name)
            
        try:
            time_var = df.variables['valid_time']
        except:
            time_var = df.variables['time']
        
        # Get raw time values
        time_values = time_var[:]
        print(f"\nRaw time values: {time_values[:10]} (showing first 10)")
        
        # Decode time values to human-readable dates if a 'units' attribute exists
        if 'units' in time_var.ncattrs():
            time_units = time_var.units
            print(f"\nTime units: {time_units}")
            
            # Convert to human-readable dates using num2date
            time_dates = num2date(time_values, units=time_units)
            print(f"Decoded time values: {time_dates[:10]} (showing first 10)")
            
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        
        target = 'data/bathy_atlantic.nc'
        df = Dataset(target, mode='r')
        
        print("Variables in the dataset:")
        for var_name in df.variables:
            print(var_name)
            
        lonsbat = df.variables['lon'][:]
        latsbat = df.variables['lat'][:]
        
        elevation = df.variables['elevation'][:]
        
        lonbat_grid, latbat_grid = np.meshgrid(lonsbat, latsbat)
        elevation_masked = elevation # np.ma.masked_where(elevation > 0, elevation)
        ####
        time_index = 0
        hs_ini = hs[:, :, time_index]  
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        cmap = ax.pcolormesh(
            lon_grid, lat_grid, hs_ini, shading='auto', cmap='coolwarm'
        )
        # TODO plot contour
        contour = ax.contour(
            lonbat_grid, latbat_grid, elevation, levels=[0], colors='black', linewidths=0.8
        )
        cb = fig.colorbar(cmap, ax=ax, orientation='vertical', label='Hs (m)')
      
        ax.set_xlabel('Longitude ($^{\circ}$)')
        ax.set_ylabel('Latitude ($^{\circ}$)')
        title = ax.set_title(f'Wave field at {time_dates[0]}')
        print(f"{time_dates}")
        ax.grid(True)
        
        def update(frame):
            cmap = ax.pcolormesh(
                lon_grid, lat_grid, hs[:,:,frame], shading='auto', cmap='coolwarm'
            )
            title.set_text(f"Wave field at {time_dates[frame]}")  # Update title
            return cmap, title
        
        frames = len(time_dates)
        
        # Create the animation
        anim = FuncAnimation(fig, update, frames=frames, interval=200, blit=False)
        anim.save('results/Hs_animation.mp4', fps=1, extra_args=['-vcodec', 'libx264'])
        
        # Show the animation
        plt.show()
        
        df.close()


def _get_sim_pt(pt_id: str, conf_id: str, start_date: datetime, end_date: datetime):
    output_point_file = \
        f'./results/{pt_id}_{conf_id}_{format_datetime(start_date)}_{format_datetime(end_date)}.tab'
    pt_sim_data = pd.read_csv(output_point_file, skiprows=7,
                              header=None, delimiter=r'\s+', dtype=str)
    dates = [datetime.datetime.strptime(_, '%Y%m%d.%H%M%S') for _ in list(pt_sim_data[0])]
    hs = [float(_) for _ in list(pt_sim_data[2])]
    return dates, hs


def _get_sim_pt_from_field(pt_lon, pt_lat, conf_id: str, start_date: datetime, end_date: datetime):
    output_field_file = \
        f'./results/HSig_{conf_id}_{format_datetime(start_date)}_{format_datetime(end_date)}.nc'
    time_sim, hs_sim = extract_nearest_ts(output_field_file, pt_lon, pt_lat)
    return time_sim, hs_sim

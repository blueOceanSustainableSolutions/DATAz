import copernicusmarine
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import xarray as xr
import numpy as np


#### INPUTS ####

# Copernicus water salinity and temperature data product - check if it contains your desired location
# Atlantic - Iberian Biscay Irish - https://data.marine.copernicus.eu/product/IBI_ANALYSISFORECAST_PHY_005_001/description
model_name = "cmems_mod_ibi_phy_anfc_0.027deg-3D_P1D-m"

# Date and time - check availability in the model selected
date = "2025-01-15T08:00:00"

# Bounding box
lon = [-9.2486, -8.6782]
lat = [38.1, 38.53]

# Coordinate to sample SSP
coord = [-9.138889, 38.194443]

# Final depth to extrapolate SSP
final_depth = 2000.0

################





# UNESCO salinity formula
def unesco(T,S,Z,latitude):

    c00,c01,c02,c03,c04,c05=1402.388,5.03830,-5.81090E-2,3.3432E-4,-1.47797E-6,3.1419E-9
    c10,c11,c12,c13,c14,c20=0.153563,6.8999E-4,-8.1829E-6,1.3632E-7,-6.1260E-10,3.1260E-5
    c21,c22,c23,c24,c30,c31=-1.7111E-6,2.5986E-8,-2.5353E-10,1.0415E-12,-9.7729E-9,3.8513E-10
    c32,a00,a01,a02,a03,a04=-2.3654E-12,1.389,-1.262E-2,7.166E-5,2.008E-6,-3.21E-8
    a10,a11,a12,a13,a14,a20=9.4742E-5,-1.2583E-5,-6.4928E-8,1.0515E-8,-2.0142E-10,-3.9064E-7
    a21,a22,a23,a30,a31,a32=9.1061E-9,-1.6009E-10,7.994E-12,1.100E-10,6.651E-12,-3.391E-13
    b00,b01,b10,b11,d00,d10=-1.922E-2,-4.42E-5,7.3637E-5,1.7950E-7,1.727E-3,-7.9836E-6

    g = 9.7803*(1 + 5.2788e-3 * (np.sin(np.deg2rad(latitude)))**2)
    k = (g - 2e-5 * Z)/(9.80612 - 2e-5 * Z)
    h45 = 1.00818e-2 * Z + 2.465e-8 * Z**2 - 1.25e-13 * Z**3 + 2.8e-19 * Z**4
    h = h45 * k

    #MPa to bar
    P = h * 10.0

    d = d00 + d10*P
    b = b00 + b01*T + (b10 + b11*T)*P
    a = (a00 + a01*T + a02*T**2 + a03*T**3 + a04*T**4) + \
        (a10 + a11*T + a12*T**2 + a13*T**3 + a14*T**4)*P + \
        (a20 + a21*T + a22*T**2 + a23*T**3)*P**2 + \
        (a30 + a31*T + a32*T**2)*P**3
    cw = (c00 + c01*T + c02*T**2 + c03*T**3 + c04*T**4 + c05*T**5) + \
         (c10 + c11*T + c12*T**2 + c13*T**3 + c14*T**4)*P + \
         (c20 + c21*T + c22*T**2 + c23*T**3 + c24*T**4)*P**2 + \
         (c30 + c31*T + c32*T**2)*P**3
    c = cw + a*S + b*S**(3/2) + d*S**2

    return c


# Request temperature data
data_request = {
    "dataset_id_sst_gap_l3s" : model_name,
    "longitude" : lon, 
    "latitude" : lat,
    "time" : [date, date],
    "variables" : ["thetao"]
}

# Load xarray dataset
dsto = copernicusmarine.open_dataset(
    dataset_id = data_request["dataset_id_sst_gap_l3s"],
    minimum_longitude = data_request["longitude"][0],
    maximum_longitude = data_request["longitude"][1],
    minimum_latitude = data_request["latitude"][0],
    maximum_latitude = data_request["latitude"][1],
    start_datetime = data_request["time"][0],
    end_datetime = data_request["time"][1],
    variables = data_request["variables"]
)

# Request salinity temperature
data_request = {
    "dataset_id_sst_gap_l3s" : model_name,
    "longitude" : lon, 
    "latitude" : lat,
    "time" : [date, date],
    "variables" : ["so"]
}

# Load xarray dataset
dsso = copernicusmarine.open_dataset(
    dataset_id = data_request["dataset_id_sst_gap_l3s"],
    minimum_longitude = data_request["longitude"][0],
    maximum_longitude = data_request["longitude"][1],
    minimum_latitude = data_request["latitude"][0],
    maximum_latitude = data_request["latitude"][1],
    start_datetime = data_request["time"][0],
    end_datetime = data_request["time"][1],
    variables = data_request["variables"]
)

temperature_at_depth = dsto['thetao'].sel(longitude=coord[0], latitude=coord[1], method='nearest').values
salinity_at_depth = dsso['so'].sel(longitude=coord[0], latitude=coord[1], method='nearest').values

ssp_at_depth = salinity_at_depth[0]
for i, dep in enumerate(dsso['depth']):
    t = temperature_at_depth[0, i]
    s = salinity_at_depth[0, i]
    lat = coord[1]
    c = unesco(t,s,dep,lat)
    ssp_at_depth[i] = c


#Remove NaN depths and extrapolate last value until a predefined depth
depths = dsso['depth'].values[~np.isnan(ssp_at_depth)]
ssp    = ssp_at_depth[~np.isnan(ssp_at_depth)]

ssp_final_depth = (ssp[-1] - ssp[-2])/(depths[-1] - depths[-2])*(final_depth - depths[-1]) + ssp[-1]

depths = np.append(depths, final_depth)
ssp = np.append(ssp, ssp_final_depth)

#Add the zero depth:
if depths[0]!=0.0:
    depths = np.insert(depths, 0, 0.0)
    ssp = np.insert(ssp, 0, ssp[0])

# Save to file in RAINDROP format
ssp_depths = np.column_stack((depths,ssp))
np.savetxt('SSP1.dat', ssp_depths, delimiter=' ', fmt='%.2f')

# Plot
plt.figure(figsize=(3, 6))
plt.plot(ssp, -depths, '.-', color='tab:red')
plt.legend()
plt.ylim(top=0)
plt.ylabel("Depth [m]")
plt.xlabel("Sound Speed [m/s]")
plt.tight_layout()
plt.savefig('ssp_profile.png', dpi=300)

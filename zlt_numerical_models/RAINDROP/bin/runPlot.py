import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import griddata
import yaml
import glob
from scipy.ndimage.filters import gaussian_filter
import pickle
import subprocess
import pandas as pd
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.io import shapereader
import matplotlib.pyplot as plt
import gc
#from mpl_toolkits.basemap import Basemap
import warnings
warnings.filterwarnings("ignore",category=UserWarning)
warnings.filterwarnings("ignore",category=RuntimeWarning)
#Non-interactive backend, might help with memory according to StackOverflow
import matplotlib
import os
import matplotlib.patheffects as PathEffects
import generateNetCDF
matplotlib.use('Agg')


def plot_bO_logo(config,f):
    # Add bO logo
    im = plt.imread(config['GENERAL']['bin']+'/assets/logo_bo.png')
    newax = f.add_axes([0.83, 0.83, 0.15, 0.15], anchor='NE', zorder=10)
    newax.imshow(im)
    newax.axis('off')
    return

def plot_bO_RAINDROP_logo(config,f):
    # Add bO logo
    im = plt.imread(config['GENERAL']['bin']+'/assets/logo_bo.png')
    newax = f.add_axes([0.83, 0.83, 0.15, 0.15], anchor='NE', zorder=10)
    newax.imshow(im)
    newax.axis('off')

    # Add RAINDROP logo
    im = plt.imread(config['GENERAL']['bin']+'/assets/logo_raindrop.png')
    #newax1 = f.add_axes([0.66, 0.835, 0.15, 0.15], anchor='NE', zorder=10)
    newax1 = f.add_axes([0.835, 0.77, 0.14, 0.14], anchor='NE', zorder=10)
    newax1.imshow(im)
    newax1.axis('off')

    return



def plotBathymetry(config):


    nSide = int(config['GENERAL']['bathymetry']['nSidePoints'])

    thresholdCoast = float(config['PLOTS']['bathymetry']['thresholdCoast'])
    gaussianFilter = float(config['PLOTS']['bathymetry']['gaussianFilter'])

    bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
    lonNormUTM = bath[0].to_list()
    latNormUTM = bath[1].to_list()
    lonOrg     = bath[0].to_list()
    latOrg     = bath[1].to_list()
    depths     = bath[2].to_list()

    maxDepth   = np.max(np.abs(depths))

    # Interpolate the data onto a regular grid
    xi = np.linspace(min(lonNormUTM), max(lonNormUTM), nSide)
    yi = np.linspace(min(latNormUTM), max(latNormUTM), nSide)
    X, Y = np.meshgrid(xi, yi)
    Z = griddata((lonNormUTM, latNormUTM), depths, (X, Y), method='linear')
    

    fig, ax = plt.subplots(1,1,figsize=(6,5), dpi=300)
    col = ax.pcolormesh(X, Y, Z, cmap='Blues', vmin=0, vmax=maxDepth)
    ax.contour(X,Y,gaussian_filter(Z, gaussianFilter), [thresholdCoast], colors='k')
    #ax.contour(X,Y,gaussian_filter(Z, 1.0), [2.0], colors='k')
    fig.colorbar(col, label='Depth [m]', ax=ax, pad=0.02, shrink=1.0)
    ax.set_xlabel('X [km]')
    ax.set_ylabel('Y [km]')
    ax.set_aspect('equal')
    ax.set_title( "Bathymetry - nSide: {}".format(nSide) , fontweight='bold')

    plt.tight_layout()

    fig.savefig("bathymetry.png", dpi=300)

    return



def plotTL(config, freq, source, position):
    
    #Open bathymetry CSV file, with DEPTH[m], LON, LAT
    bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
    lonNormUTM = bath[0].to_list()
    latNormUTM = bath[1].to_list()
    lonOrg     = bath[3].to_list()
    latOrg     = bath[4].to_list()
    depths     = bath[2].to_list()


    xs = position[0]*(np.max(lonNormUTM)-np.min(lonNormUTM))+np.min(lonNormUTM)
    ys = position[1]*(np.max(latNormUTM)-np.min(latNormUTM))+np.min(latNormUTM)

    #Grid to which the pressure was interpolated in the pickle
    nSideTL  = int(config['PLOTS']['TL']['nSide'])
    x_str = np.linspace(np.min(lonNormUTM), np.max(lonNormUTM), nSideTL)
    y_str = np.linspace(np.min(latNormUTM), np.max(latNormUTM), nSideTL)
    X_str, Y_str = np.meshgrid(x_str, y_str)

    x_org = np.linspace(np.min(lonOrg), np.max(lonOrg), nSideTL)
    y_org = np.linspace(np.min(latOrg), np.max(latOrg), nSideTL)
    X_org, Y_org = np.meshgrid(x_org, y_org)

    pathEnv = 'calcs/freq/freq{0}/source{1}'.format(int(freq), source)
    with open('{0}/source_{1}.pickle'.format(pathEnv, int(freq)), 'rb') as f:
        pressure_xy = pickle.load(f)

    # Transform the complex pressure into an intensity
    TL_xy = 20.0*np.log10((np.abs(pressure_xy)))
    TL_xy = np.nan_to_num(TL_xy, nan=-200.0, neginf=-200.0, posinf=-200.0)

    #Get bathymetry data to plot
    #X,Y,Z,thresholdCoast,gaussianFilter = plotBathymetry(config, plot=False)

    land_10m = cfeature.NaturalEarthFeature('physical', 'land', '10m',
                                            edgecolor='face',
                                            facecolor=cfeature.COLORS['land'])

    f   = plt.figure(figsize=(8,6), dpi=300)
    ax1 = plt.subplot(111, projection=ccrs.PlateCarree())
    thetitle = 'Noise Map - ' + str(freq) + ' Hz'# @ z=' + str(zarray[0]) + ' m' 
    ax1.set_title( thetitle , fontweight='bold')
    ax1.set_xlabel("Longitude [deg]")
    ax1.set_ylabel("Latitude [deg]")
    ax1.coastlines(resolution='10m')
    ax1.add_feature(land_10m)
    col = ax1.pcolormesh(X_org, Y_org, TL_xy, cmap='jet', vmin=-200)#, vmax=-30)
    f.colorbar(col, label='Transmission Loss [dB]', ax=ax1, pad=0.1, shrink=0.85)
    ax1.gridlines(draw_labels=True, linewidth=0.5)

    #Add bO logo
    plot_bO_logo(config,f)

    f.savefig("{0}/TL_source{1}_freq{2}Hz.png".format(pathEnv,source,int(freq)))

    return



def plotSPL(config, freq, source, position, spl, time, backgroundNoise, maxNoise):
    
    #Open bathymetry CSV file, with DEPTH[m], LON, LAT
    bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
    lonNormUTM = bath[0].to_list()
    latNormUTM = bath[1].to_list()
    lonOrg     = bath[3].to_list()
    latOrg     = bath[4].to_list()
    depths     = bath[2].to_list()


    xs = position[0]*(np.max(lonNormUTM)-np.min(lonNormUTM))+np.min(lonNormUTM)
    ys = position[1]*(np.max(latNormUTM)-np.min(latNormUTM))+np.min(latNormUTM)

    #Grid to which the pressure was interpolated in the pickle
    nSideTL  = int(config['PLOTS']['TL']['nSide'])
    x_str = np.linspace(np.min(lonNormUTM), np.max(lonNormUTM), nSideTL)
    y_str = np.linspace(np.min(latNormUTM), np.max(latNormUTM), nSideTL)
    X_str, Y_str = np.meshgrid(x_str, y_str)

    x_org = np.linspace(np.min(lonOrg), np.max(lonOrg), nSideTL)
    y_org = np.linspace(np.min(latOrg), np.max(latOrg), nSideTL)
    X_org, Y_org = np.meshgrid(x_org, y_org)

    pathEnv = 'calcs/freq/freq{0}/source{1}'.format(int(freq), source)
    with open('{0}/source_{1}.pickle'.format(pathEnv, int(freq)), 'rb') as f:
        pressure_xy = pickle.load(f)

    # Transform the complex pressure into an intensity
    TL_xy = 20.0*np.log10((np.abs(pressure_xy)))
    TL_xy = np.nan_to_num(TL_xy, nan=-200.0, neginf=-200.0, posinf=-200.0)

    SPL_xy = TL_xy + spl

    #Get bathymetry data to plot
    #X,Y,Z,thresholdCoast,gaussianFilter = plotBathymetry(config, plot=False)

    land_10m = cfeature.NaturalEarthFeature('physical', 'land', '10m',
                                            edgecolor='face',
                                            facecolor=cfeature.COLORS['land'])

    f   = plt.figure(figsize=(8,6), dpi=300)
    ax1 = plt.subplot(111, projection=ccrs.PlateCarree())
    thetitle = 'Noise Map - ' + str(freq) + ' Hz'# @ z=' + str(zarray[0]) + ' m' 
    plt.suptitle( thetitle , fontweight='bold')
    if time != None:
        ax1.set_title(pd.to_datetime(str(time)).strftime('%Y-%m-%d %H:%M:%S'))
    ax1.set_xlabel("Longitude [deg]")
    ax1.set_ylabel("Latitude [deg]")
    ax1.coastlines(resolution='10m')
    ax1.add_feature(land_10m)
    col = ax1.pcolormesh(X_org, Y_org, SPL_xy, cmap='jet', vmin=backgroundNoise, vmax=maxNoise)
    f.colorbar(col, label=r'Sound Pressure Level [dB re 1$\mu$Pa]', ax=ax1, pad=0.1, shrink=0.85)
    ax1.gridlines(draw_labels=True, linewidth=0.5)

    #Add bO logo
    plot_bO_logo(config,f)

    f.savefig("{0}/SPL_source{1}_freq{2}Hz.png".format(pathEnv,source,int(freq)))

    return





def plotSPLBroadband(config, freqs, source, position, spls, time, backgroundNoise, maxNoise):
    
    #Open bathymetry CSV file, with DEPTH[m], LON, LAT
    bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
    lonNormUTM = bath[0].to_list()
    latNormUTM = bath[1].to_list()
    lonOrg     = bath[3].to_list()
    latOrg     = bath[4].to_list()
    depths     = bath[2].to_list()


    xs = position[0]*(np.max(lonNormUTM)-np.min(lonNormUTM))+np.min(lonNormUTM)
    ys = position[1]*(np.max(latNormUTM)-np.min(latNormUTM))+np.min(latNormUTM)

    #Grid to which the pressure was interpolated in the pickle
    nSideTL  = int(config['PLOTS']['TL']['nSide'])
    x_str = np.linspace(np.min(lonNormUTM), np.max(lonNormUTM), nSideTL)
    y_str = np.linspace(np.min(latNormUTM), np.max(latNormUTM), nSideTL)
    X_str, Y_str = np.meshgrid(x_str, y_str)

    x_org = np.linspace(np.min(lonOrg), np.max(lonOrg), nSideTL)
    y_org = np.linspace(np.min(latOrg), np.max(latOrg), nSideTL)
    X_org, Y_org = np.meshgrid(x_org, y_org)


    p_freqs = []

    for freq, spl in zip(freqs,spls):
        pathEnv = 'calcs/freq/freq{0}/source{1}'.format(int(freq), source)
        with open('{0}/source_{1}.pickle'.format(pathEnv, int(freq)), 'rb') as f:
            pressure_xy = pickle.load(f)

        # Transform the complex pressure into an intensity
        TL_xy = 20.0*np.log10((np.abs(pressure_xy)))
        TL_xy = np.nan_to_num(TL_xy, nan=-200.0, neginf=-200.0, posinf=-200.0)

        SPL_xy = TL_xy + spl

        p_freqs.append(10**(SPL_xy/20.0))

    SPL_xy_bb = 20.0*np.log10(np.sum(p_freqs, axis=0))

    #Save SPL to pickle, to later plot with all sources
    #os.system('touch calcs/freq/SPL_source_{0}.pickle'.format(source))
    subprocess.run(['touch', 'calcs/freq/SPL_source_{0}.pickle'.format(source)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open('calcs/freq/SPL_source_{0}.pickle'.format(source), 'wb') as f:
        pickle.dump(SPL_xy_bb, f)

    land_10m = cfeature.NaturalEarthFeature('physical', 'land', '10m',
                                            edgecolor='face',
                                            facecolor=cfeature.COLORS['land'])

    f   = plt.figure(figsize=(8,6), dpi=300)
    ax1 = plt.subplot(111, projection=ccrs.PlateCarree())
    thetitle = 'Noise Map - Broadband - ' + str(int(freqs[0]))+ '-' + str(int(freqs[-1])) + ' Hz'# @ z=' + str(zarray[0]) + ' m' 
    plt.suptitle( thetitle , fontweight='bold')
    if time != None:
        ax1.set_title(pd.to_datetime(str(time)).strftime('%Y-%m-%d %H:%M:%S'))
    ax1.set_xlabel("Longitude [deg]")
    ax1.set_ylabel("Latitude [deg]")
    ax1.coastlines(resolution='10m')
    ax1.add_feature(land_10m)
    col = ax1.pcolormesh(X_org, Y_org, SPL_xy_bb, cmap='jet', vmin=backgroundNoise, vmax=maxNoise)
    f.colorbar(col, label=r'Sound Pressure Level [dB re 1$\mu$Pa]', ax=ax1, pad=0.1, shrink=0.9)
    ax1.gridlines(draw_labels=True, linewidth=0.5)

    #Add bO logo
    plot_bO_logo(config,f)

    f.savefig("{0}/../../SPL_source{1}_broadband.png".format(pathEnv,source))

    return




def plotSPLBroadbandAll(config, freqs, nSources, time, backgroundNoise, maxNoise):
    
    #Open bathymetry CSV file, with DEPTH[m], LON, LAT
    bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
    lonNormUTM = bath[0].to_list()
    latNormUTM = bath[1].to_list()
    lonOrg     = bath[3].to_list()
    latOrg     = bath[4].to_list()
    depths     = bath[2].to_list()


    #Grid to which the pressure was interpolated in the pickle
    nSideTL  = int(config['PLOTS']['TL']['nSide'])
    x_str = np.linspace(np.min(lonNormUTM), np.max(lonNormUTM), nSideTL)
    y_str = np.linspace(np.min(latNormUTM), np.max(latNormUTM), nSideTL)
    X_str, Y_str = np.meshgrid(x_str, y_str)

    x_org = np.linspace(np.min(lonOrg), np.max(lonOrg), nSideTL)
    y_org = np.linspace(np.min(latOrg), np.max(latOrg), nSideTL)
    X_org, Y_org = np.meshgrid(x_org, y_org)



    pressure_xy_bb_all = []

    for source in range(1, nSources+1):
        with open('calcs/freq/SPL_source_{0}.pickle'.format(source), 'rb') as f:
            SPL_xy_bb = pickle.load(f)

        pressure_xy_bb_all.append(10**(SPL_xy_bb/20.0))

    SPL_xy_bb_all = 20.0*np.log10(np.sum(pressure_xy_bb_all, axis=0))

    #Save SPL to pickle
    subprocess.run(['touch', 'calcs/freq/SPL_ALL.pickle'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open('calcs/freq/SPL_ALL.pickle', 'wb') as f:
        pickle.dump(SPL_xy_bb_all, f)

    #Get bathymetry data to plot
    #X,Y,Z,thresholdCoast,gaussianFilter = plotBathymetry(config, plot=False)

    land_10m = cfeature.NaturalEarthFeature('physical', 'land', '10m',
                                            edgecolor='face',
                                            facecolor=cfeature.COLORS['land'])

    f   = plt.figure(figsize=(8,6), dpi=300)
    ax1 = plt.subplot(111, projection=ccrs.PlateCarree())
    thetitle = 'Noise Map - Broadband - ' + str(int(freqs[0]))+ '-' + str(int(freqs[-1])) + ' Hz'# @ z=' + str(zarray[0]) + ' m' 
    plt.suptitle( thetitle, fontweight='bold')
    if time != None:
        ax1.set_title(pd.to_datetime(str(time)).strftime('%Y-%m-%d %H:%M:%S'))
    ax1.set_xlabel("Longitude [deg]")
    ax1.set_ylabel("Latitude [deg]")
    ax1.coastlines(resolution='10m')
    ax1.add_feature(land_10m)
    col = ax1.pcolormesh(X_org, Y_org, SPL_xy_bb_all, cmap='jet', vmin=backgroundNoise, vmax=maxNoise)
    f.colorbar(col, label=r'Sound Pressure Level [dB re 1$\mu$Pa]', ax=ax1, pad=0.1, shrink=0.9)
    ax1.gridlines(draw_labels=True, linewidth=0.5)

    #Add bO logo
    plot_bO_logo(config,f)

    f.savefig("./noise_map.png")

    return





def plotSPLBroadbandAllEfficient(config, sourceFieldList, freqs, time, backgroundNoise, maxNoise, isEmpty):

    #Open bathymetry CSV file, with DEPTH[m], LON, LAT
    bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
    lonNormUTM = bath[0].to_list()
    latNormUTM = bath[1].to_list()
    lonOrg     = bath[3].to_list()
    latOrg     = bath[4].to_list()
    depths     = bath[2].to_list()


    #Grid to which the pressure was interpolated in the pickle
    nSideTL  = int(config['PLOTS']['TL']['nSide'])
    x_str = np.linspace(np.min(lonNormUTM), np.max(lonNormUTM), nSideTL)
    y_str = np.linspace(np.min(latNormUTM), np.max(latNormUTM), nSideTL)
    X_str, Y_str = np.meshgrid(x_str, y_str)

    x_org = np.linspace(np.min(lonOrg), np.max(lonOrg), nSideTL)
    y_org = np.linspace(np.min(latOrg), np.max(latOrg), nSideTL)
    X_org, Y_org = np.meshgrid(x_org, y_org)

    freqArray = []          

    pressure_xy_all = []
    if isEmpty == False:
        for n in sourceFieldList:
            source = n[0]
            #position n[1]
            freq = n[2]
            tol  = n[3]
            freqArray.append(freq)

            pathEnv = 'calcs/freq/freq{0}/{1}'.format(int(freq), source)
            with open('{0}/source_{1}.pickle'.format(pathEnv, int(freq)), 'rb') as f:
                pressure_xy = pickle.load(f)

            TL_xy = 20.0*np.log10((np.abs(pressure_xy)))
            TL_xy = np.nan_to_num(TL_xy, nan=-200.0, neginf=-200.0, posinf=-200.0)

            #print(source, np.min(TL_xy), np.max(TL_xy))

            #Transform to SPL
            SPL_xy = TL_xy + tol

            pressure_xy_all.append(10**(SPL_xy/20.0))

    # If there are no sources, it's all background noise
    else:
        SPL_xy = np.ones((nSideTL,nSideTL))*backgroundNoise
        pressure_xy_all.append(10**(SPL_xy/20.0))

        #freqArray = 0

    SPL_xy_bb_all = 20.0*np.log10(np.sum(pressure_xy_all, axis=0))
    #Clip minimum to backgorund noise, for statistics
    SPL_xy_bb_all = np.clip(SPL_xy_bb_all, a_min=backgroundNoise, a_max=None)


    #Save SPL to pickle
    subprocess.run(['touch', 'calcs/freq/SPL_ALL.pickle'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open('calcs/freq/SPL_ALL.pickle', 'wb') as f:
        pickle.dump(SPL_xy_bb_all, f)

    if (freqArray != 0) and not isEmpty:
        #Sum all sources for a given frequency, in order to save for a pickle also
        nFrequencies = int(config['GENERAL']['nFrequencies'])
        nSources = int(config['FIELD3D']['SourcePosition']['nSources'])
        freqArray = np.sort(np.unique(freqArray))
        SPL_xy_freq_all = []
        for n in range(0, nFrequencies):
            SPL_xy_freq_all = 20.0*np.log10(np.sum(pressure_xy_all[n::nFrequencies], axis=0))
            #SPL_xy_freq_all = np.clip(SPL_xy_freq_all, a_min=backgroundNoise, a_max=None)
            #Save SPL of each freq. to pickle
            subprocess.run(['touch', 'calcs/freq/SPL_ALL_{}.pickle'.format(freqArray[n])],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open('calcs/freq/SPL_ALL_{}.pickle'.format(freqArray[n]), 'wb') as f:
                pickle.dump(SPL_xy_freq_all, f)

    #Get bathymetry data to plot
    #X,Y,Z,thresholdCoast,gaussianFilter = plotBathymetry(config, plot=False)

    #land_10m = cfeature.NaturalEarthFeature('physical', 'land', '10m',
    #                                        edgecolor='face',
    #                                        facecolor=cfeature.COLORS['land'])

    f   = plt.figure(figsize=(8,6), dpi=300)
    ax1 = plt.subplot(111, projection=ccrs.PlateCarree())
    thetitle = 'Noise Map - Broadband - ' + str(int(freqs[0]))+ '-' + str(int(freqs[-1])) + ' Hz'# @ z=' + str(zarray[0]) + ' m' 
    plt.suptitle( thetitle, fontweight='bold')
    if time != None:
        ax1.set_title(pd.to_datetime(str(time)).strftime('%Y-%m-%d %H:%M:%S')+' (UTC)')
    ax1.set_xlabel("Longitude [deg]")
    ax1.set_ylabel("Latitude [deg]")
    #ax1.coastlines(resolution='10m')
    #ax1.add_feature(land_10m)

    for path in glob.glob('bathymetry/coastline/*.shp'):
      coastline = shapereader.Reader(path)
      for record, geometry in zip(coastline.records(), coastline.geometries()):
          ax1.add_geometries([geometry], ccrs.PlateCarree(), facecolor=cfeature.COLORS['land'],
                              edgecolor='black')

    col = ax1.pcolormesh(X_org, Y_org, SPL_xy_bb_all, cmap='jet', vmin=backgroundNoise, vmax=maxNoise)
    f.colorbar(col, label=r'Sound Pressure Level [dB re (1$\mu$Pa)$^2$]', ax=ax1, pad=0.12, shrink=0.9)
    ax1.gridlines(draw_labels=True, linewidth=0.5)

    # Just for Naples case, can remove!!!!!!
    xmin = (np.max(X_org) - np.min(X_org))*0.02 + np.min(X_org)
    xmax = -(np.max(X_org) - np.min(X_org))*0.02 + np.max(X_org)
    ymin = (np.max(Y_org) - np.min(Y_org))*0.02 + np.min(Y_org)
    ymax = -(np.max(Y_org) - np.min(Y_org))*0.02 + np.max(Y_org)
    ax1.set_xlim(left=xmin, right=xmax)
    ax1.set_ylim(top=ymax, bottom=ymin)


    #Add bO logo
    plot_bO_logo(config,f)

    f.savefig("./noise_map.png")

    #Try to reduce memory leaks
    ax1.cla()
    plt.clf()

    try:
        del pressure_xy
    except:
        pass

    try:
        del pressure_xy_all
    except:
        pass

    try:
        del TL_xy
    except:
        pass

    try:
        del SPL_xy
    except:
        pass

    try:
        del SPL_xy_bb_all
    except:
        pass

    try:
        del SPL_xy_freq_all
    except:
        pass
    
    del ax1
    del f
    del col
    gc.collect()

    return



def plotSPLwithAIS(config, sourceFieldList, freqs, time, backgroundNoise, maxNoise, isEmpty):

    #Open bathymetry CSV file, with DEPTH[m], LON, LAT
    bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
    lonNormUTM = bath[0].to_list()
    latNormUTM = bath[1].to_list()
    lonOrg     = bath[3].to_list()
    latOrg     = bath[4].to_list()
    depths     = bath[2].to_list()


    #Grid to which the pressure was interpolated in the pickle
    nSideTL  = int(config['PLOTS']['TL']['nSide'])
    x_str = np.linspace(np.min(lonNormUTM), np.max(lonNormUTM), nSideTL)
    y_str = np.linspace(np.min(latNormUTM), np.max(latNormUTM), nSideTL)
    X_str, Y_str = np.meshgrid(x_str, y_str)

    x_org = np.linspace(np.min(lonOrg), np.max(lonOrg), nSideTL)
    y_org = np.linspace(np.min(latOrg), np.max(latOrg), nSideTL)
    X_org, Y_org = np.meshgrid(x_org, y_org)

    freqArray = []          

    pressure_xy_all = []
    if isEmpty == False:
        for n in sourceFieldList:
            source = n[0]
            #position n[1]
            freq = n[2]
            tol  = n[3]
            freqArray.append(freq)

            pathEnv = 'calcs/freq/freq{0}/{1}'.format(int(freq), source)
            with open('{0}/source_{1}.pickle'.format(pathEnv, int(freq)), 'rb') as f:
                pressure_xy = pickle.load(f)

            TL_xy = 20.0*np.log10((np.abs(pressure_xy)))
            TL_xy = np.nan_to_num(TL_xy, nan=-200.0, neginf=-200.0, posinf=-200.0)

            #print(source, np.min(TL_xy), np.max(TL_xy))

            #Transform to SPL
            SPL_xy = TL_xy + tol

            pressure_xy_all.append(10**(SPL_xy/20.0))

    # If there are no sources, it's all background noise
    else:
        SPL_xy = np.ones((nSideTL,nSideTL))*backgroundNoise
        pressure_xy_all.append(10**(SPL_xy/20.0))

        #freqArray = 0

    SPL_xy_bb_all = 20.0*np.log10(np.sum(pressure_xy_all, axis=0))
    #Clip minimum to backgorund noise, for statistics
    SPL_xy_bb_all = np.clip(SPL_xy_bb_all, a_min=backgroundNoise, a_max=None)


    #Save SPL to pickle
    subprocess.run(['touch', 'calcs/freq/SPL_ALL.pickle'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open('calcs/freq/SPL_ALL.pickle', 'wb') as f:
        pickle.dump(SPL_xy_bb_all, f)

    if (freqArray != 0) and not isEmpty:
        #Sum all sources for a given frequency, in order to save for a pickle also
        nFrequencies = int(config['GENERAL']['nFrequencies'])
        nSources = int(config['FIELD3D']['SourcePosition']['nSources'])
        freqArray = np.sort(np.unique(freqArray))
        SPL_xy_freq_all = []
        for n in range(0, nFrequencies):
            SPL_xy_freq_all = 20.0*np.log10(np.sum(pressure_xy_all[n::nFrequencies], axis=0))
            #SPL_xy_freq_all = np.clip(SPL_xy_freq_all, a_min=backgroundNoise, a_max=None)
            #Save SPL of each freq. to pickle
            subprocess.run(['touch', 'calcs/freq/SPL_ALL_{}.pickle'.format(freqArray[n])],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open('calcs/freq/SPL_ALL_{}.pickle'.format(freqArray[n]), 'wb') as f:
                pickle.dump(SPL_xy_freq_all, f)

    #Get bathymetry data to plot
    #X,Y,Z,thresholdCoast,gaussianFilter = plotBathymetry(config, plot=False)

    #land_10m = cfeature.NaturalEarthFeature('physical', 'land', '10m',
    #                                        edgecolor='face',
    #                                        facecolor=cfeature.COLORS['land'])

    f   = plt.figure(figsize=(9,7), dpi=300)
    ax1 = plt.subplot(111, projection=ccrs.PlateCarree())
    thetitle = 'Noise Map - Broadband - ' + str(int(freqs[0]))+ '-' + str(int(freqs[-1])) + ' Hz'# @ z=' + str(zarray[0]) + ' m' 
    #plt.suptitle( thetitle, fontweight='bold')
    #if time != None:
    #    ax1.set_title(pd.to_datetime(str(time)).strftime('%Y-%m-%d %H:%M:%S')+' (UTC)')
    ax1.set_title(r"$\mathbf{Underwater\ Acoustics\ Map}$" "\n" r"$\mathbf{Shipping\ Noise}$" "\n" r"$f_{TOL}=63\ \mathrm{Hz}$" "\n" + (pd.to_datetime(str(time)) + np.timedelta64(2, "m")).strftime("%Y-%m-%d %H:%M:%S") + " (UTC)", pad=5)
    ax1.set_xlabel("Longitude [deg]")
    ax1.set_ylabel("Latitude [deg]")
    #ax1.coastlines(resolution='10m')
    #ax1.add_feature(land_10m)

    for path in glob.glob('bathymetry/coastline/*.shp'):
      coastline = shapereader.Reader(path)
      for record, geometry in zip(coastline.records(), coastline.geometries()):
          ax1.add_geometries([geometry], ccrs.PlateCarree(), facecolor=cfeature.COLORS['land'],
                              edgecolor='black')

    # Open AIS and plot text
    time_str = pd.to_datetime(str(time)).strftime('%Y-%m-%dT%H:%M:%S')
    try:    
      with open(f'out/ais/AIS_{time_str}.000000.pickle', 'rb') as fl:
        AIS_instance = pickle.load(fl)
    except:
      with open(f'out/ais/AIS_{time_str}.pickle', 'rb') as fl:
        AIS_instance = pickle.load(fl)

    for _, ship in AIS_instance.iterrows():

      try:
        real_name = ship['Name']
        ais_type = int(ship['Type'])
        length = float(ship['Length [m]'])
        velocity = float(ship['Velocity [kts]'])
        if ais_type == 30:
            name = "Fishing Vessel"
        elif ais_type == 35:
            name = "Naval Vessel"
        elif (ais_type >= 60 and ais_type <= 68 and length > 100.0):
            name = "Cruise Vessel"
        elif (ais_type >=60 and ais_type <=68 and length <= 100.0):
            name = "Passenger Vessel"
        elif (ais_type == 70 or (ais_type >= 75 and ais_type <= 79 and velocity<=16.0)):
            name = "Bulker"
        elif ((ais_type >= 71 and ais_type <= 74) or (ais_type >= 75 and ais_type <= 79 and velocity>16.0)):
            name = "Container Ship"
        elif (ais_type >= 80 and ais_type <= 89):
            name = "Tanker"
        else:
            name = "General Vessel"
      except:
        name = "General Vessel"

      ais_text = "{}\n{}\n{:.1f} m | {:.1f} kts".format(real_name, name, float(ship['Length [m]']), float(ship['Velocity [kts]']))
      ax1.plot(ship['Longitude'], ship['Latitude'], marker=None, color='black', markersize=2)
      ax1.text(ship['Longitude']+0.005, ship['Latitude']+0.005, ais_text, transform=ccrs.PlateCarree(),
              fontsize=8, color='black', ha='left', va='bottom', fontweight='bold', clip_on=True,
              path_effects=[PathEffects.withStroke(linewidth=2, foreground="white")])

    col = ax1.pcolormesh(X_org, Y_org, SPL_xy_bb_all, cmap='jet', vmin=backgroundNoise, vmax=maxNoise)
    f.colorbar(col, label=r'Sound Pressure Level [dB re (1$\mu$Pa)$^2$]', ax=ax1, pad=0.04, shrink=0.7)
    grids = ax1.gridlines(draw_labels=True, linewidth=0.0)
    grids.xlabels_top = False
    grids.ylabels_right = False

    # Just for Naples case, can remove!!!!!!
    xmin = (np.max(X_org) - np.min(X_org))*0.02 + np.min(X_org)
    xmax = -(np.max(X_org) - np.min(X_org))*0.02 + np.max(X_org)
    ymin = (np.max(Y_org) - np.min(Y_org))*0.02 + np.min(Y_org)
    ymax = -(np.max(Y_org) - np.min(Y_org))*0.02 + np.max(Y_org)
    ax1.set_xlim(left=xmin, right=xmax)
    ax1.set_ylim(top=ymax, bottom=ymin)


    #Add bO logo
    plot_bO_RAINDROP_logo(config,f)

    plt.tight_layout()

    f.savefig("./noise_map.png")

    # Export to netCDF
    generateNetCDF.export_netCDF(x_org, y_org, SPL_xy_bb_all, config['FIELD3D']['ReceiverDepths']['depths'], f"./out/nc/SPL_{time_str}.nc")

    #Try to reduce memory leaks
    ax1.cla()
    plt.clf()

    try:
        del pressure_xy
    except:
        pass

    try:
        del pressure_xy_all
    except:
        pass

    try:
        del TL_xy
    except:
        pass

    try:
        del SPL_xy
    except:
        pass

    try:
        del SPL_xy_bb_all
    except:
        pass

    try:
        del SPL_xy_freq_all
    except:
        pass
    
    del ax1
    del f
    del col
    gc.collect()

    return







def plotSPLBroadbandAllEfficientCumulative():
    
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


    #Grid to which the pressure was interpolated in the pickle
    nSideTL  = int(config['PLOTS']['TL']['nSide'])
    x_str = np.linspace(np.min(lonNormUTM), np.max(lonNormUTM), nSideTL)
    y_str = np.linspace(np.min(latNormUTM), np.max(latNormUTM), nSideTL)
    X_str, Y_str = np.meshgrid(x_str, y_str)

    x_org = np.linspace(np.min(lonOrg), np.max(lonOrg), nSideTL)
    y_org = np.linspace(np.min(latOrg), np.max(latOrg), nSideTL)
    X_org, Y_org = np.meshgrid(x_org, y_org)

    #If files does not exist, write coordinates for external plotting
    if not os.path.exists('./coords.pickle'):
        with open('./coords.pickle', 'wb') as f:
            coords = pd.DataFrame({'lon': X_org.flatten(), 'lat': Y_org.flatten()})
            pickle.dump(coords, f)

    counter = 0
    SPL_xy_mean = []
    for instance in list(glob.glob('./out/pickles/*.pickle')):
        with open(instance, 'rb') as f:
            SPL_xy_instance = pickle.load(f)

        if counter == 0:
            SPL_xy_mean = SPL_xy_instance
        else:
            SPL_xy_mean = np.sum([SPL_xy_mean*counter, SPL_xy_instance], axis=0)/(counter+1)

        counter += 1

    #Get bathymetry data to plot
    #X,Y,Z,thresholdCoast,gaussianFilter = plotBathymetry(config, plot=False)

    #land_10m = cfeature.NaturalEarthFeature('physical', 'land', '10m',
    #                                        edgecolor='face',
    #                                        facecolor=cfeature.COLORS['land'])


    f   = plt.figure(figsize=(8,6), dpi=300)
    ax1 = plt.subplot(111, projection=ccrs.PlateCarree())
    thetitle = 'Noise Map - Broadband - ' + str(int(20))+ '-' + str(int(1000)) + ' Hz'# @ z=' + str(zarray[0]) + ' m' 
    plt.suptitle( thetitle, fontweight='bold')
    #if time != None:
    #    ax1.set_title(pd.to_datetime(str(time)).strftime('%Y-%m-%d %H:%M:%S'))
    ax1.set_title("Cumulative Map")
    ax1.set_xlabel("Longitude [deg]")
    ax1.set_ylabel("Latitude [deg]")
    #ax1.coastlines(resolution='10m')
    #ax1.add_feature(land_10m)

    #coastline = shapereader.Reader('bathymetry/coastline/repmus_coastline.shp')
    #for record, geometry in zip(coastline.records(), coastline.geometries()):
    #    ax1.add_geometries([geometry], ccrs.PlateCarree(), facecolor=cfeature.COLORS['land'],
    #                        edgecolor='black')


    for path in glob.glob('bathymetry/coastline/*.shp'):
      coastline = shapereader.Reader(path)
      for record, geometry in zip(coastline.records(), coastline.geometries()):
          ax1.add_geometries([geometry], ccrs.PlateCarree(), facecolor=cfeature.COLORS['land'],
                              edgecolor='black')


    col = ax1.pcolormesh(X_org, Y_org, SPL_xy_mean, cmap='jet', vmin=85, vmax=100)
    f.colorbar(col, label=r'Sound Pressure Level [dB re 1$\mu$Pa]', ax=ax1, pad=0.1, shrink=0.9)
    ax1.gridlines(draw_labels=True, linewidth=0.5)

    #Add bO logo
    plot_bO_logo(config,f)

    f.savefig("./noise_map_cumulative.png")

    return




def plotNoiseThresholdMap():
    
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


    #Grid to which the pressure was interpolated in the pickle
    nSideTL  = int(config['PLOTS']['TL']['nSide'])
    x_str = np.linspace(np.min(lonNormUTM), np.max(lonNormUTM), nSideTL)
    y_str = np.linspace(np.min(latNormUTM), np.max(latNormUTM), nSideTL)
    X_str, Y_str = np.meshgrid(x_str, y_str)

    x_org = np.linspace(np.min(lonOrg), np.max(lonOrg), nSideTL)
    y_org = np.linspace(np.min(latOrg), np.max(latOrg), nSideTL)
    X_org, Y_org = np.meshgrid(x_org, y_org)

    #If files does not exist, write coordinates for external plotting
    if not os.path.exists('./coords.pickle'):
        with open('./coords.pickle', 'wb') as f:
            coords = pd.DataFrame({'lon': X_org.flatten(), 'lat': Y_org.flatten()})
            pickle.dump(coords, f)


    nSizeSquares = 25 #data points
    finalGridSize= int(nSideTL/nSizeSquares)
    downsampling = nSizeSquares
    LOBE   = 100.0
    LOBE_p = 10.0**(LOBE/20.0)

    X_org_down = X_org.reshape(finalGridSize, downsampling, finalGridSize, downsampling)
    Y_org_down = Y_org.reshape(finalGridSize, downsampling, finalGridSize, downsampling)

    X_org_down = X_org_down.mean(axis=(1,3))
    Y_org_down = Y_org_down.mean(axis=(1,3))
    Z_org_down = Y_org_down*X_org_down

    counter = 0
    SPL_xy_mean = []
    pressure_xy_mean = []
    for instance in list(glob.glob('./out/pickles/SPL_*:00.pickle')):
        with open(instance, 'rb') as f:
            SPL_xy_instance = pickle.load(f)

        pressure_xy_instance = 10.0**(np.array(SPL_xy_instance)/20.0)
        pressure_xy_instance_down = pressure_xy_instance.reshape(finalGridSize, downsampling, finalGridSize, downsampling)
        pressure_xy_instance_down = pressure_xy_instance_down.mean(axis=(1,3))
        pressure_xy_instance_down = (pressure_xy_instance_down > LOBE_p).astype(int)

        if counter == 0:
            pressure_xy_mean = pressure_xy_instance_down
        else:
            pressure_xy_mean = np.sum([pressure_xy_mean*counter, pressure_xy_instance_down], axis=0)/(counter+1)

        counter += 1

    #Get bathymetry data to plot
    #X,Y,Z,thresholdCoast,gaussianFilter = plotBathymetry(config, plot=False)

    #land_10m = cfeature.NaturalEarthFeature('physical', 'land', '10m',
    #                                        edgecolor='face',
    #                                        facecolor=cfeature.COLORS['land'])


    f   = plt.figure(figsize=(8,6), dpi=300)
    ax1 = plt.subplot(111, projection=ccrs.PlateCarree())
    #thetitle = 'Noise Map - Broadband - ' + str(int(20))+ '-' + str(int(1000)) + ' Hz'# @ z=' + str(zarray[0]) + ' m' 
    #plt.suptitle( thetitle, fontweight='bold')
    #if time != None:
    #    ax1.set_title(pd.to_datetime(str(time)).strftime('%Y-%m-%d %H:%M:%S'))
    #ax1.set_title("$f_{TOL} = $125 Hz | 03/12/2024 - 08/12/2024\n")
    #ax1.set_title("$f_{TOL} = $63 Hz\n")
    ax1.set_xlabel("Longitude [deg]")
    ax1.set_ylabel("Latitude [deg]")
    #ax1.coastlines(resolution='10m')
    #ax1.add_feature(land_10m)

    #coastline = shapereader.Reader('bathymetry/coastline/repmus_coastline.shp')
    #for record, geometry in zip(coastline.records(), coastline.geometries()):
    #    ax1.add_geometries([geometry], ccrs.PlateCarree(), facecolor=cfeature.COLORS['land'],
    #                        edgecolor='black')


    for path in glob.glob('bathymetry/coastline/*.shp'):
      coastline = shapereader.Reader(path)
      for record, geometry in zip(coastline.records(), coastline.geometries()):
          ax1.add_geometries([geometry], ccrs.PlateCarree(), facecolor=cfeature.COLORS['land'],
                              edgecolor='black')


    for path in glob.glob('bathymetry/windfarms/*.shp'):
      coastline = shapereader.Reader(path)
      for record, geometry in zip(coastline.records(), coastline.geometries()):
          ax1.add_geometries([geometry], ccrs.PlateCarree(), facecolor='white',
                              edgecolor='white', alpha=0.5)


    col = ax1.pcolormesh(X_org_down, Y_org_down, pressure_xy_mean*100.0, cmap='jet', edgecolors="k", linewidth=0.2, vmin=0.0, vmax=50.0)
    f.colorbar(col, label='% Time above 100dB LOBE [%]', ax=ax1, pad=0.11, shrink=0.9)
    ax1.gridlines(draw_labels=True, linewidth=0.0)


    # Just for Naples case, can remove!!!!!!
    xmin = (np.max(X_org) - np.min(X_org))*0.02 + np.min(X_org)
    xmax = -(np.max(X_org) - np.min(X_org))*0.02 + np.max(X_org)
    ymin = (np.max(Y_org) - np.min(Y_org))*0.02 + np.min(Y_org)
    ymax = -(np.max(Y_org) - np.min(Y_org))*0.02 + np.max(Y_org)
    ax1.set_xlim(left=xmin, right=xmax)
    ax1.set_ylim(top=ymax, bottom=ymin)


    #Add bO logo
    plot_bO_logo(config,f)

    f.savefig("./threshold_map.png")

    return



if __name__=="__main__":
    #This is done as a stand-alone postprocessing step
    #Delete if incorporated into another way
    #plotSPLBroadbandAllEfficientCumulative()
    plotNoiseThresholdMap()

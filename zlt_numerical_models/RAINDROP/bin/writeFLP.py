import yaml
import sys
import os
import subprocess
import numpy as np
import csv
from scipy.spatial import Delaunay
import pandas as pd
import utm


def writeFLP(config, config_general, nSource, pathEnv):

    
    bath = pd.read_csv('bathymetry/bathymetry.bty', header=None)
    lon = bath[0].to_list()
    lat = bath[1].to_list()
    lonOrg = bath[3].to_list()
    latOrg = bath[4].to_list()
    lonOrgUTM = bath[5].to_list()
    latOrgUTM = bath[6].to_list()    

    pathEnv = pathEnv + '/' + 'source' + str(nSource) 

    #Title
    title = config_general['GENERAL']['title']
    
    #Open FLP file
    #os.system("rm -rf {0}/flpFiles; mkdir {0}/flpFiles".format(pathEnv))
    subprocess.run(['rm', '-rf', '{0}/flpFiles'.format(pathEnv)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['mkdir', '{0}/flpFiles'.format(pathEnv)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    flpFile = open("{0}/flpFiles/{1}.flp".format(pathEnv, title), "a")
    
    #Write title
    flpFile.write("'" + title + "'" + "\n")

    #Write options
    runType         = config_general['FIELD3D']['runType']
    tessCheck       = config_general['FIELD3D']['tesselationCheck']
    beamType        = config_general['FIELD3D']['beamType']
    raySaveFlag     = config_general['FIELD3D']['raySaveFlag']
    beamPatternFile = config_general['FIELD3D']['beamPatternFile']
    flpFile.write("'" +
                  runType +
                  tessCheck +
                  beamType +
                  raySaveFlag +
                  beamPatternFile +
                  "'" + "\n")


    #Write number of modes
    nModes = config_general['FIELD3D']['nModes']
    flpFile.write(nModes + "\n")


    #Write source coordinates
    #nSources = int(config['FIELD3D']['SourcePosition']['nSources'])
    nSources = 1
    units    = config_general['FIELD3D']['SourcePosition']['units']

    sourceLon = []
    sourceLat = []

    sourceCoord = config_general['FIELD3D']['SourcePosition']['source{}'.format(nSource)]
    if units == 'rel':
        #Get extremes
        minLon = np.min(lon)
        minLat = np.min(lat)
        maxLon = np.max(lon)
        maxLat = np.max(lat)

        sourceLon.append((maxLon - minLon) * float(sourceCoord[0]) + minLon)
        sourceLat.append((maxLat - minLat) * float(sourceCoord[1]) + minLat)
    elif units == 'WGS84':

        #Updated/Commented because UTM is unreliable if domain is too large (Azores case) - check if this matches in the map! 
        #Transform source WGS TO UTM
        #coordsUTM = utm.from_latlon(float(sourceCoord[1]), float(sourceCoord[0]))
        #sourceCoord = []
        #sourceCoord.append(coordsUTM[0]*1e-3)
        #sourceCoord.append(coordsUTM[1]*1e-3)

        #Get extremes of UTM coordinates
        minLonOrgUTM = np.min(lonOrgUTM)
        minLatOrgUTM = np.min(latOrgUTM)
        maxLonOrgUTM = np.max(lonOrgUTM)
        maxLatOrgUTM = np.max(latOrgUTM)

        #Get extremes of normalized UTM coordinates
        minLon = np.min(lon)
        minLat = np.min(lat)
        maxLon = np.max(lon)
        maxLat = np.max(lat)

        #Interpolate the UTM coordinates into normalized UTM ones
        #lonInterp = (maxLon - minLon)/(maxLonOrgUTM - minLonOrgUTM) * (float(sourceCoord[0]) - minLonOrgUTM)
        #latInterp = (maxLat - minLat)/(maxLatOrgUTM - minLatOrgUTM) * (float(sourceCoord[1]) - minLatOrgUTM)
        #Updated because UTM is unreliable if domain is too large (Azores case) - check if this matches in the map!        
        lonInterp = (maxLon - minLon)/(np.max(lonOrg) - np.min(lonOrg)) * (float(sourceCoord[0]) - np.min(lonOrg))
        latInterp = (maxLat - minLat)/(np.max(latOrg) - np.min(latOrg)) * (float(sourceCoord[1]) - np.min(latOrg))
        

        sourceLon.append(lonInterp)
        sourceLat.append(latInterp)


    #for n in range(1, nSources+1):
    #    sourceCoord = config['FIELD3D']['SourcePosition']['source{}'.format(n)]

        #TODO: Add 'WGS84' and 'UTM' possibilities
    #    if units == 'rel':
            #Get extremes
    #        minLon = np.min(lon)
    #        minLat = np.min(lat)
    #        maxLon = np.max(lon)
    #        maxLat = np.max(lat)

    #        sourceLon.append((maxLon - minLon) * float(sourceCoord[0]) + minLon)
    #        sourceLat.append((maxLat - minLat) * float(sourceCoord[1]) + minLat)

    flpFile.write(str(nSources) + "\n")
    for n in range(0, nSources):
        flpFile.write("{:.15f}".format(sourceLon[n]) + " ")
    flpFile.write("\n")

    flpFile.write(str(nSources) + "\n")
    for n in range(0, nSources):
        flpFile.write("{:.15f}".format(sourceLat[n]) + " ")
    flpFile.write("\n")



    #Source depths
    nSourcesDepths = config_general['FIELD3D']['SourceDepths']['nSourceDepths']
    depths         = config_general['FIELD3D']['SourceDepths']['depths']

    flpFile.write(nSourcesDepths + "\n")
    if int(nSourcesDepths)==1:
        flpFile.write(depths[0] + "\n")
    else:
        flpFile.write(depths[0] + " " + depths[1] + " /\n")


    #Receiver depths
    nReceiverDepths = config_general['FIELD3D']['ReceiverDepths']['nReceiverDepths']
    depths          = config_general['FIELD3D']['ReceiverDepths']['depths']

    flpFile.write(nReceiverDepths + "\n")
    if int(nReceiverDepths)==1:
        flpFile.write(depths[0] + "\n")
    else:
        flpFile.write(depths[0] + " " + depths[1] + " /\n")


    #Receiver ranges
    nReceiverRanges = config_general['FIELD3D']['ReceiverRanges']['nReceiverRanges']
    units           = config_general['FIELD3D']['ReceiverRanges']['units']
    maxRange        = config_general['FIELD3D']['ReceiverRanges']['maxRange']

    #TODO: Implement option of km or m
    if units == "rel":
        #Get extremes
        minLon = np.min(lon)
        minLat = np.min(lat)
        maxLon = np.max(lon)
        maxLat = np.max(lat)
        
        maxRange = max(maxLon - minLon, maxLat - minLat)*float(maxRange)

    flpFile.write(nReceiverRanges + "\n")
    flpFile.write("0.0" + " " + "{:.2f}".format(maxRange) + " /\n")


    #Radials
    nThetas  = config_general['FIELD3D']['Radials']['nThetas']
    thetas  = config_general['FIELD3D']['Radials']['thetas']

    flpFile.write(nThetas + "\n")
    flpFile.write(thetas[0] + " " + thetas[1] + " /\n")


    #Write bathymetry points (nodes) and corredpondent .mod file
    nNodes = len(lon)
    flpFile.write(str(nNodes) + "\n")
    for node in range(0, nNodes):
        flpFile.write(str(lon[node]) + " " +
                      str(lat[node]) + " " +
                      "'"+"../../envFiles/{0}_{1}".format(title, str(node)) + "'" + " \n")


    #Perform Delaunay triangulation and write elements
    #Select x and y; and ignore first line that tells number of points
    tri = Delaunay(list(zip(lon,lat)))
    elements = tri.simplices
    nElements = np.shape(elements)[0]
    flpFile.write(str(nElements) + "\n")

    for ele in elements:
        flpFile.write(str(ele[0]+1) + " " +
                      str(ele[1]+1) + " " +
                      str(ele[2]+1) + "\n")

   
    #Gaussian Beam
    beamFanAngles     = config_general['FIELD3D']['GaussianBeam']['beamFanAngles']
    nBeams            = config_general['FIELD3D']['GaussianBeam']['nBeams']
    sizeStep          = config_general['FIELD3D']['GaussianBeam']['sizeStep'] 
    nSteps            = config_general['FIELD3D']['GaussianBeam']['nSteps'] 
    epsilonMultiplier = config_general['FIELD3D']['GaussianBeam']['epsilonMultiplier'] 

    flpFile.write(beamFanAngles[0] + " " + beamFanAngles[1] + " " + nBeams + "\n")
    flpFile.write(sizeStep + " " + nSteps + "\n")
    flpFile.write(epsilonMultiplier + "\n")

    flpFile.close()

    return sourceLon, sourceLat

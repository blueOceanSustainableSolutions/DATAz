import yaml
import sys
import subprocess
import numpy as np

def find_closest_value(arr, x):
    for i in range(len(arr)):
        if arr[i] >= x:
            return i

    return None



def writeEnv(config, maxDepth, n, pathEnv):
    """
    In KRAKEN, each bathymetry point requires the settings to be defined,
    based on local depth and correspondent SSP.

    Inputs:
        - control: dictionary with YAML inputs
        - maxDepth
        - pathSSP: path to this point's SSP
        - n: point control number 
    """

    #Open environmental file
    #fileName = config['GENERAL']['title']
    #os.system("rm -f {}/dummy.env".format(pathEnv))
    subprocess.run(['rm', '-f', '{}/dummy.env'.format(pathEnv)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    envFile = open("{}/dummy.env".format(pathEnv), "a")

    #Title
    title = config['GENERAL']['title']
    envFile.write("'" + title + "#{}'".format(n) + "\n")

    #Frequency
    freq = config['KRAKEN']['frequency']
    envFile.write(freq + "\n")

    #Number of media
    nMedia = config['KRAKEN']['numberMedia']
    envFile.write(nMedia + "\n")

    #General options and Top BC
    interp     = config['KRAKEN']['generalOptions']['interpolation']
    topBC      = config['KRAKEN']['topBC']['bc']
    attUnits   = config['KRAKEN']['generalOptions']['attUnits']['option']
    attVolume  = config['KRAKEN']['generalOptions']['attVolume']['option']
    rootFinder = config['KRAKEN']['generalOptions']['rootFinder']
    envFile.write("'" + interp + topBC + attUnits + attVolume + rootFinder + "'\n")

    if attVolume == 'F':
        attTemperature = config['KRAKEN']['generalOptions']['attVolume']['FrancoisGarrison']['attTemperature']
        attSalinity    = config['KRAKEN']['generalOptions']['attVolume']['FrancoisGarrison']['attSalinity']
        attPH          = config['KRAKEN']['generalOptions']['attVolume']['FrancoisGarrison']['attPH']
        attZBar        = config['KRAKEN']['generalOptions']['attVolume']['FrancoisGarrison']['attZBar']
        if (attTemperature==None or attSalinity==None or attPH==None or attZBar==None):
            raise ValueError('Undefined parameters for Francois-Garrison volume attenuation formula.')
        envFile.write(attTemperature + ' ' +
                    attSalinity + ' ' +
                    attPH + ' ' +
                    attZBar + '\n')
    elif attVolume=='B':
        raise Exception('Volume attenuation with Biological Layer not implemented yet.')

    if topBC == 'A':
        depth      = config['KRAKEN']['topBC']['depth']
        pWaveSpeed = config['KRAKEN']['topBC']['pWaveSpeed']
        sWaveSpeed = config['KRAKEN']['topBC']['sWaveSpeed']
        rho        = config['KRAKEN']['topBC']['rho']
        pWaveAtt   = config['KRAKEN']['topBC']['pWaveAtt']
        sWaveAtt   = config['KRAKEN']['topBC']['sWaveAtt']
        if (depth==None or pWaveSpeed==None or sWaveSpeed==None or rho==None or pWaveAtt==None or sWaveAtt==None):
            raise ValueError('Undefined parameters for TopBC with Acousto-Elastic halfspace.')
        envFile.write(depth + ' ' +
                    pWaveSpeed + ' ' +
                    sWaveSpeed + ' ' +
                    rho + ' ' +
                    pWaveAtt + ' ' +
                    sWaveAtt + '\n')
    elif topBC == 'F':
        raise ValueError("Top BC with option F still not implemented.")



    #SSP
    nSSP = config['KRAKEN']['SSP']['nSSP']

    for n in range(1, int(nSSP)+1):
        sspRef    = 'SSP{0}'.format(n)
        fileSSP   = config['KRAKEN']['SSP'][sspRef]['path']
        nMeshZ    = config['KRAKEN']['SSP'][sspRef]['nMesh']
        sigma     = config['KRAKEN']['SSP'][sspRef]['sigma']
        zMax      = "{:.2f}".format(maxDepth)#config['KRAKEN']['SSP'][sspRef]['zMax']
        density   = config['KRAKEN']['SSP'][sspRef]['density']
        sWaveSpeed= config['KRAKEN']['SSP'][sspRef]['sWaveSpeed']
        pWaveAtt  = config['KRAKEN']['SSP'][sspRef]['pWaveAtt']
        sWaveAtt  = config['KRAKEN']['SSP'][sspRef]['sWaveAtt']

        #If depth is null, substitutde by small value, so a .mod file is always created.
        if ((zMax == '0.00') or (zMax == '-0.00')):
            zMax = '0.01'

        #Write SSP options and characteristics
        if (attUnits=="m"):
            beta = config['KRAKEN']['generalOptions']['attUnits']['beta']
            ft   = config['KRAKEN']['generalOptions']['attUnits']['ft']
            if (beta==None or ft==None):
                raise ValueError("Undefined beta and ft with option m in attUnits.")
            envFile.write(nMeshZ + " " + sigma + " " + zMax + " " + beta + " " + ft + "\n")
        else:
            envFile.write(nMeshZ + " " + sigma + " " + zMax + "\n")

        #Read respective SSP file
        with open("SSP/"+fileSSP, 'r') as f:
            depths = []
            soundSpeed = []
            for line in f:
                values = line.strip().split()
                if len(values)!=0:
                    depths.append(values[0])
                    soundSpeed.append(values[1])


        #Write first line of SSP and following in compact form
        envFile.write(depths[0] + " " +
                      soundSpeed[0] + " " +
                      sWaveSpeed + " " +
                      density + " " +
                      pWaveAtt + " " +
                      sWaveAtt + " /\n")
        
        #Define until when the SSP depths are necessary, based on zMax
        zMaxIndex = find_closest_value(np.array(depths).astype(np.float64), float(zMax))
        if zMaxIndex==None:
            raise ValueError('SSP does not contain information for the depths defined.Provide more SSP depths, to prevent extrapolation.')

        #In case of null depth, which is substituted by a small one, add respective SSP
        if zMax == '0.01':
            depths = depths[:zMaxIndex] + ['0.01']
            soundSpeed = soundSpeed[:zMaxIndex] + [soundSpeed[0]]
        #If zMax is not defined, interpolate and remove following SSP data in depth
        #Extrapolation is not allowed in this script
        elif (depths[zMaxIndex] != zMax):
            soundSpeedInterm = np.interp(float(zMax),
                                        [float(depths[zMaxIndex-1]), float(depths[zMaxIndex])],
                                        [float(soundSpeed[zMaxIndex-1]), float(soundSpeed[zMaxIndex])])

            depths = depths[:zMaxIndex] + [zMax]
            soundSpeed = soundSpeed[:zMaxIndex] + ["{:.2f}".format(soundSpeedInterm)]
        else:
            depths = depths[:zMaxIndex+1]
            soundSpeed = soundSpeed[:zMaxIndex+1]
        
        #Write the SSP to the env file
        for i in range(1, len(depths)):
            envFile.write(depths[i] + " " +
                          soundSpeed[i] + " /\n")


    #Bottom BC
    bottomBC = config['KRAKEN']['bottomBC']['bc']
    sigma    = config['KRAKEN']['bottomBC']['sigma']
    if attUnits=='m':
        envFile.write("'" + bottomBC + "' " + sigma + " " + beta + " " + ft + "\n")
    else:
        envFile.write("'" + bottomBC + "' " + sigma + "\n")

    if bottomBC == 'A':
        depth      = config['KRAKEN']['bottomBC']['depth']
        pWaveSpeed = config['KRAKEN']['bottomBC']['pWaveSpeed']
        sWaveSpeed = config['KRAKEN']['bottomBC']['sWaveSpeed']
        pWaveAtt   = config['KRAKEN']['bottomBC']['pWaveAtt']
        sWaveAtt   = config['KRAKEN']['bottomBC']['sWaveAtt']
        density    = config['KRAKEN']['bottomBC']['density']

        if maxDepth == 0.0:
            maxDepth = 0.01

        #Only one line defining the bottom half space
        envFile.write("{:.2f}".format(maxDepth) + " " +
                      pWaveSpeed + " " +
                      sWaveSpeed + " " +
                      density + " " +
                      pWaveAtt + " " +
                      sWaveAtt + " /\n")
    elif bottomBC == 'G':
        grainSize = config['KRAKEN']['bottomBC']['grainSize']
        envFile.write(depth + " " +
                    grainSize + "\n")
    elif bottomBC == 'F':
        raise ValueError('Bottom BC option F still not implemented.')
    elif bottomBC == 'P':
        raise ValueError('Bottom BC option P still not implemented.')


    #KRAKEN Phase Speed Limits
    cLow = config['KRAKEN']['PhaseSpeedLimits']['cLow']
    cHigh = config['KRAKEN']['PhaseSpeedLimits']['cHigh']
    envFile.write(cLow + " " + cHigh + " \n")

    #Maximum Range - Richardson Extrapolation
    maxRange = config['KRAKEN']['MaximumRange']
    envFile.write(maxRange + " \n")

    #Source/Receiver Depths
    nSources              = config['KRAKEN']['Sources']['number']
    rangeDepthSources     = config['KRAKEN']['Sources']['depths']
    nReceivers            = config['KRAKEN']['Receivers']['number']
    rangeDepthReceivers   = config['KRAKEN']['Receivers']['depths']

    envFile.write(nSources + " \n")
    if int(nSources) == 1:
        envFile.write(rangeDepthSources[0] + " /\n")
    else:
        envFile.write(rangeDepthSources[0] + " " + rangeDepthSources[1] + " /\n")

    envFile.write(nReceivers + " \n")
    if int(nReceivers) == 1:
        envFile.write(rangeDepthReceivers[0] + " /\n")
    else:
        envFile.write(rangeDepthReceivers[0] + " " + rangeDepthReceivers[1] + " /\n")


    """
    Close env file
    """
    envFile.close()

    return
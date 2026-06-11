import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import math
import subprocess


def source_level_TOL(f, v, l, id):

    K = 191.0 #dB, from JOMOPANS-ECHO model
    l0 = 300.0*0.3048 # 300.0 ft, from RANDI3.1c model, updated to receive meters
    f_ref = 1.0
    v_ref = 1.0

    #In case L is not provided (e.g. military ships), assume reference L
    if l==0:
        l = l0
    if l==0.0:
        l = l0

    ship, v_ref_1, v_ref_2, D, container = ship_parameters(id, v, l)

    f_til = f/f_ref
    f_til_1 = 480.0 * (v_ref/v_ref_2)

    # Baseline spectrum, Ls0
    Ls0 = K - 20*np.log10(f_til_1) - 10*np.log10((1 - f_til/f_til_1)**2 + D**2)
    
    # In case it is a container, Ls0 must have an enhanced peak below 100.0Hz
    if (container and (f_til<100.0)):
        K = 208.0
        if (ship=='Container Ship' or ship=='Bulker'):
            D = 0.8
        else:
            D = 1.0
        f_til_1 = 600.0*(v_ref/v_ref_2)
        Ls0 = K - 40*np.log10(f_til_1) + 10*np.log10(f_til) - 10*np.log10((1 - (f_til/f_til_1)**2)**2 + D**2)

    # Ship spectrum
    Ls = Ls0 + 60*np.log10(v/v_ref_2) + 20*np.log10(l/l0)

    # Transform to source level, as suggested by the model in Macgillivray et al, 2021
    # Note that this is only done when the frequencies where we are working are already decidecade bands (1/3 octaves)
    Ls = Ls + 10*np.log10(0.231*f_til)

    return Ls, ship
    

def ship_parameters(id, v, l):
    # First and second interation models
    # Speeds in kts
    #TODO: Vehicle Carrier, which has no ID code

    # For all ships, D=3, except cruise vessel where D=4
    D = 3

    # Check if container ship:
    container = False

    if (id==30):
        ship = 'Fishing Vessel'
        v_ref_1 = 7.5
        v_ref_2 = 6.4
    elif (id==31 or id==32 or id==52):
        ship = 'Tug'
        v_ref_1 = 4.9
        v_ref_2 = 3.7
    elif (id==35):
        ship = 'Naval vessel'
        v_ref_1 = 14.2
        v_ref_2 = 11.1
    elif (id==36 or id==37):
        ship = 'Recreational vessel'
        v_ref_1 = 14.0
        v_ref_2 = 10.6
    elif (id==51 or id==53 or id==55):
        ship = 'Government/Research'
        v_ref_1 = 9.2
        v_ref_2 = 8.0
    elif (id>=60 and id<=68 and l>100.0):
        ship = 'Cruise vessel'
        v_ref_1 = 20.2
        v_ref_2 = 17.1
        D = 4
    elif (id>=60 and id<=68 and l<=100.0):
        ship = 'Passenger vessel'
        v_ref_1 = 11.7
        v_ref_2 = 9.7
    elif (id==70 or (id>=75 and id<=79 and v<=16.0)):
        ship = 'Bulker'
        v_ref_1 = 14.1
        v_ref_2 = 13.9
        container = True
    elif ((id>=75 and id<=79 and v>16.0) or (id>=71 and id<=74)):
        ship = 'Container Ship'
        v_ref_1 = 19.3
        v_ref_2 = 18.0
        container = True
    elif (id>=80 and id<=89):
        ship = 'Tanker'
        v_ref_1 = 13.1
        v_ref_2 = 12.4
        container = True
    elif (id==33):
        ship = 'Dredger'
        v_ref_1 = 8.8
        v_ref_2 = 7.4
    else:
        ship = 'Other'
        v_ref_1 = 9.5
        v_ref_2 = 9.5

    return ship, v_ref_1, v_ref_2, D, container

def third_octave_bands(freq_min, freq_max):
    f_ref = 1000.0
    i_min = math.floor(10*np.log10(freq_min/f_ref))
    i_max = math.floor(10*np.log10(freq_max/f_ref))
    f = []
    for i in range(i_min, i_max+1):
        f.append(f_ref*10**(i/10))
    return np.array(f)


def writeSPL(pathSource, nShip, id, v, l, min_f, max_f):

    #Defaults
    if id==None:
        id = -1
    if v==None:
        v  = 0.01   #kts, to be defined based on 'Other' ship type
    if l==None:
        l  = 300.0*0.3048 #m, default l0

    if v==0.0:
        v = 0.01 #To prevent issues with logs!

    f_nominal = np.array([10,12.5,16,20,25,31.5,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500,3150,4000,5000,6300,8000,10000,12500,16000,20000])

    index_nearest_min = np.argmin(np.abs(f_nominal - min_f))
    index_nearest_max = np.argmin(np.abs(f_nominal - max_f))

    f_spectrogram = third_octave_bands(f_nominal[index_nearest_min], f_nominal[index_nearest_max])
    f_nominal = f_nominal[index_nearest_min:index_nearest_max+1]

    Ls_spectrogram = []
    for f in f_spectrogram:
        Ls, ship = source_level_TOL(f, v, l, id)
        if Ls < 50.0:
            Ls = 50.0 #Cap value, so it is not extremely low
        Ls_spectrogram.append(Ls)

    #Write to file
    #Write the nominal centre frequencies!
    # create a file and write the lists to it
    subprocess.run(['touch', '{}/source{}.srcs'.format(pathSource, nShip)])
    with open('{}/source{}.srcs'.format(pathSource, nShip), 'w') as f:
        f.write('#TOL SL\n')
        for x, y in zip(f_nominal, Ls_spectrogram):
            f.write(f'{x} {round(y, 1)}\n')

    return

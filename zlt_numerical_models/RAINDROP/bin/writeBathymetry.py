import sys
import subprocess
import numpy as np
import utm
import csv
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
#from mpl_toolkits.basemap import Basemap
import pandas as pd
import yaml
from scipy.spatial import Delaunay, ConvexHull
from shapely.geometry import Polygon, Point
import pickle

def generate_initial_mesh(box_min, box_max, nSideX, nSideY):
    dx = (box_max[0] - box_min[0]) / nSideX
    dy = (box_max[1] - box_min[1]) / nSideY

    points = []
    for i in range(nSideX + 1):
        for j in range(nSideY + 1):
            x = box_min[0] + i * dx
            y = box_min[1] + j * dy
            points.append([x, y])

    return points

def refine_sub_box(points, sub_box_min, sub_box_max, refinement_factor):
    sub_box_indices = []
    for i, point in enumerate(points):
        if sub_box_min[0] <= point[0] <= sub_box_max[0] and sub_box_min[1] <= point[1] <= sub_box_max[1]:
            sub_box_indices.append(i)

    #Analyze box of points to be refined, in terms of point number and extremes
    points_x_num = np.count_nonzero(np.array(points)[sub_box_indices][:,1] == np.array(points)[sub_box_indices][:,1][0])
    points_y_num = np.count_nonzero(np.array(points)[sub_box_indices][:,0] == np.array(points)[sub_box_indices][:,0][0])
    points_x_min = np.array(points)[sub_box_indices][:,0].min()
    points_x_max = np.array(points)[sub_box_indices][:,0].max()
    points_y_min = np.array(points)[sub_box_indices][:,1].min()
    points_y_max = np.array(points)[sub_box_indices][:,1].max()

    #Now, delete the points, to redo them afterwards!
    refined_points = np.delete(np.array(points), sub_box_indices, axis=0)

    #Calculate the number of side points, based on the refinement level
    nPointsX = points_x_num + refinement_factor*(points_x_num-1)
    nPointsY = points_y_num + refinement_factor*(points_y_num-1)

    #Generate refined mesh in specific box
    pointsBoxRefinement = generate_initial_mesh([points_x_min, points_y_min], [points_x_max, points_y_max], nPointsX, nPointsY)

    #Concatenate with initial mesh
    refined_points = np.concatenate((refined_points, pointsBoxRefinement), axis=0)

    return refined_points










def bathymetry(config):
    """
    This function receives a CSV with coordinates and depths, and outputs a .bty file
    with an interpolated structured mesh and respective Delaunay triangulation for 3D runs.
    """
    
    #Open bathymetry CSV file, with DEPTH[m], LON, LAT in WGS84
    bath = config['GENERAL']['bathymetry']['path']

    #General refinement information
    xStart = 0.0
    xEnd   = 1.0
    yStart = 0.0
    yEnd   = 1.0
    nSidePoints = int(config['GENERAL']['bathymetry']['nSidePoints'])

    #Generate initial mesh in normalized coordinates
    points = generate_initial_mesh([xStart, yStart], [xEnd, yEnd], nSidePoints, nSidePoints)

    #Refine within defined boxes
    nRefinementRegions = int(config['GENERAL']['bathymetry']['nRefinementRegions'])
    if nRefinementRegions > 0:
        for nRefinement in range(1, nRefinementRegions+1):
            ref = "refinement{}".format(nRefinement)
            xStartRefinement = float(config['GENERAL']['bathymetry'][ref]['xStart'])
            xEndRefinement = float(config['GENERAL']['bathymetry'][ref]['xEnd'])
            yStartRefinement = float(config['GENERAL']['bathymetry'][ref]['yStart'])
            yEndRefinement = float(config['GENERAL']['bathymetry'][ref]['yEnd'])
            refinementFactor = int(config['GENERAL']['bathymetry'][ref]['refinementFactor'])

            points = refine_sub_box(points, [xStartRefinement,yStartRefinement], [xEndRefinement,yEndRefinement], refinementFactor)

    else:
        points = refine_sub_box(points, [0,0], [1,1], 0)





    #Import existent .csv file
    bathcsv = pd.read_csv('bathymetry/' + bath, header=None, skiprows=1)
    lonOrgWGS84 = bathcsv[1].to_list()
    latOrgWGS84 = bathcsv[2].to_list()
    depths = bathcsv[0].to_list()

    # Convert to UTM in km
    coordsUTM = utm.from_latlon(np.array(latOrgWGS84), np.array(lonOrgWGS84))
    lonOrgUTM = coordsUTM[0]*1e-3
    latOrgUTM = coordsUTM[1]*1e-3
    zone1     = coordsUTM[2]
    zone2     = coordsUTM[3]

    #Get extreme coordinates in UTM
    minLonOrgUTM = np.min(lonOrgUTM)
    minLatOrgUTM = np.min(latOrgUTM)
    maxLonOrgUTM = np.max(lonOrgUTM)
    maxLatOrgUTM = np.max(latOrgUTM)

    #Get extreme coordinates in WGS84
    minLonOrgWGS84 = np.min(lonOrgWGS84)
    minLatOrgWGS84 = np.min(latOrgWGS84)
    maxLonOrgWGS84 = np.max(lonOrgWGS84)
    maxLatOrgWGS84 = np.max(latOrgWGS84)

    #Get ranges in UTM
    rangeLonOrgUTM = maxLonOrgUTM - minLonOrgUTM
    rangeLatOrgUTM = maxLatOrgUTM - minLatOrgUTM

    #Get ranges in WGS84
    rangeLonOrgWGS84 = maxLonOrgWGS84 - minLonOrgWGS84
    rangeLatOrgWGS84 = maxLatOrgWGS84 - minLatOrgWGS84


    #Normalize original UTM, for interpolation
    lonOrgNormUTM = lonOrgUTM - minLonOrgUTM
    latOrgNormUTM = latOrgUTM - minLatOrgUTM


    #Scale grid to UTM, based on boundary limits. Lower left corner is zero
    lonStrNormUTM = points[:,0]*rangeLonOrgUTM
    latStrNormUTM = points[:,1]*rangeLatOrgUTM

    #Scale grid to WGS84, based on boundary limits. Lower left corner is zero
    lonStrNormWGS84 = points[:,0]*rangeLonOrgWGS84
    latStrNormWGS84 = points[:,1]*rangeLatOrgWGS84

    #Scale grid to UTM, based on boundary limits
    lonStrUTM = points[:,0]*rangeLonOrgUTM + minLonOrgUTM
    latStrUTM = points[:,1]*rangeLatOrgUTM + minLatOrgUTM

    #Scale grid to WGS84, based on boundary limits. Use utm tool
    #lonStrWGS84 = points[:,0]*rangeLonOrgWGS84 + minLonOrgWGS84
    #latStrWGS84 = points[:,1]*rangeLatOrgWGS84 + minLatOrgWGS84
    latStrWGS84, lonStrWGS84 = utm.to_latlon(lonStrUTM*1e3, latStrUTM*1e3, zone1, zone2, strict=False)

    #Interpolate depths from original UTM to grid UTM
    depthsStr = griddata((lonOrgNormUTM, latOrgNormUTM), depths, list(zip(lonStrNormUTM, latStrNormUTM)), method='nearest', fill_value=2000.0, rescale=True)


    #TODO: Careful! Deleting cells in the edges ruins the scaling.
    #If to be implemented, keep this in mind!
    #Delete cells which were fill_value in interp.
    #delete_indexes = np.where(depthsStr==10000.0)
    #depthsStr = np.delete(depthsStr, delete_indexes)
    #lonStrNormUTM = np.delete(lonStrNormUTM, delete_indexes)
    #latStrNormUTM = np.delete(latStrNormUTM, delete_indexes)
    #lonStrWGS84 = np.delete(lonStrWGS84, delete_indexes)
    #latStrWGS84 = np.delete(latStrWGS84, delete_indexes)


    #Clip values, to ensure that depths are always positive, which would cause problems in KRAKEN
    depthsStr = np.clip(depthsStr, a_min=0.0, a_max=None)

    #Now, if there's a coastline alphashape, use it
    #To clip values to 0m depth
    try:
        with open('bathymetry/coast_polygon.pickle', 'rb') as f:
            coastPoly = pickle.load(f)

        for i in range(0, len(lonStrWGS84)):
            point = Point(lonStrWGS84[i], latStrWGS84[i])
            if point.within(coastPoly):
                depthsStr[i] = 0.0
    except:
        pass


    # write the grid data to a text file
    coordinates = []
    with open('bathymetry/bathymetry.bty', 'w') as file:
        #file.write(f'{len(lonStr)} {len(latStr)} {len(depthsStr)}\n')  # write the first line
        for i in range(len(lonStrNormUTM)):
            file.write(f'{lonStrNormUTM[i]:.6f},{latStrNormUTM[i]:.6f},{depthsStr[i]:.6f},{lonStrWGS84[i]:.6f},{latStrWGS84[i]:.6f},{lonStrUTM[i]:.6f},{latStrUTM[i]:.6f}\n')  # write the data to the file

    #plt.axis('equal')
    f   = plt.figure(figsize=(8,6), dpi=300)
    ax1 = plt.subplot(111)
    col = plt.tricontourf(lonStrWGS84, latStrWGS84, depthsStr, cmap='jet', levels=np.linspace(0,50.0,100))
    plt.colorbar(col, label = "Depth [m]")
    tri = Delaunay(list(zip(lonStrWGS84, latStrWGS84)))
    elements = tri.simplices
    lon = [c[0] for c in points]
    lat = [c[1] for c in points]
    ax1.triplot(lonStrWGS84, latStrWGS84, elements, linewidth=0.3, color='black')
    #ax1.scatter(lonStrWGS84, latStrWGS84, s=0.1, color='black')
    #ax1.scatter(lonOrgWGS84, latOrgWGS84, s=0.1, color='black')
    #ax1.plot(points[hull.vertices,0], points[hull.vertices,1], 'r--', lw=2)
    #col = plt.scatter(lonStrNormUTM, latStrNormUTM, c=depthsStr, s=24.0, marker='s', cmap='jet')
    ax1.set_xlabel('Longitude')
    ax1.set_ylabel('Latitude')
    f.savefig('bathymetry/bathymetry.png', dpi=300)


    return #len(depthsStr), min(lonOrg), min(latOrg)

if __name__=="__main__":
    #Open user controls in YAML format
    with open('controls.yaml', 'r') as f:
        config = yaml.safe_load(f)
    bathymetry(config)

import json
import os
from ast import literal_eval
from datetime import datetime
import numpy as np


class Coupling:
    def __init__(self, json_path: str, coords):
        self.json_path = json_path
        print('Coupling domain coordinates:')
        print(coords)
        with open(json_path, 'r') as file:
            case_data = json.load(file)
            case_description = case_data['case_description']

            self.case_id = case_data['id']
            self.area_description = case_description["area_name"]
            self.output_points = case_data["output"]["points"]
            
        self.case_data = case_data
        self.coords = coords
        self.pts_coupling = self.edge_midpoints(coords)
        print('Coupling at points:')
        print(self.pts_coupling)
        

    def prepare_output(self):
        print(f'Coupling {self.case_id} preparation started.')
        print(self.area_description)
        
        points = list(self.output_points.keys())
        start_point = points[0] if points else "P1"  
        start_label = start_point[:-1]  
        start_index = int(start_point[-1])  
        
        new_points = {}
        for i, pt in enumerate(self.pts_coupling, start=start_index):
            point_label = f"{start_label}{i+1}"
            description = f"coupling point {i}"
            new_points[point_label] = f"({pt[0]}, {pt[1]}, '{description}')"

        # Update the case_data JSON
        self.case_data["output"]["points"].update(new_points)

        # Output updated points
        print("Updated points in JSON:")
        for label, point_str in new_points.items():
            print(f"{label}: {point_str}")

        with open(self.json_path, "w") as outfile:
            json.dump(self.case_data, outfile, indent=2)
        
    def edge_midpoints(self, coords):
        """Calculate the midpoints of edges formed by consecutive coordinates."""
        midpoints = []
        for i in range(len(coords)):
            x1, y1 = coords[i]
            x2, y2 = coords[(i + 1) % len(coords)]  
            midpoint = ((x1 + x2) / 2, (y1 + y2) / 2)
            midpoints.append(np.round(midpoint,2))
        return midpoints



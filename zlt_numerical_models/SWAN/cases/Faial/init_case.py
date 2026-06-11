import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.simulation_case.case import Case

os.chdir(os.path.dirname(os.path.abspath(__file__)))
case = Case('./input.json')
case.prepare_case()
case.run()

#!/bin/bash
#SBATCH --nodes=
#SBATCH --ntasks=
#SBATCH --cpus-per-task=
#SBATCH --time=
#SBATCH --partition 
#SBATCH --gpus=                                 # When training it is recommended to use a GPU partition
#SBATCH --account=
#SBATCH --output=results/test_%j_stdout.txt
#SBATCH --error=results/test_%j_stderr.txt


source PATH_TO_YOUR_ENV/bin/activate


#python PATH_TO_PROJECT/scripts/train.py        # For training
python PATH_TO_PROJECT/scripts/evaluate.py      # For evaluation


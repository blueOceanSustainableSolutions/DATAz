#!/bin/bash

# swanrun.sh
# This script runs the SWAN program with the specified input file.
# Usage: ./swanrun.sh inputfile [nprocs]

nprocs=1  # Default to 1 processor if not specified

# Check if input file is provided
if [ -z "$1" ]; then
  echo "Usage: ./swanrun.sh inputfile -n [nprocs]"
  exit 1
fi

inputfile=$1
shift

# Check if the input file exists
if [ ! -f "${inputfile}.swn" ]; then
  echo "Error: file ${inputfile}.swn does not exist"
  exit 1
fi

# Check if the second argument is provided and is a valid integer
if [ ! -z "$1" ] && [[ "$1" =~ ^[0-9]+$ ]]; then
  nprocs=$1
else
  echo "nprocs: $1"
  # If not a valid number, show an error and exit
  if [ ! -z "$1" ]; then
    echo "Error: nprocs must be a positive integer."
    exit 1
  fi
fi

# Copy the input file to INPUT
cp "${inputfile}.swn" INPUT

# Run SWAN in parallel or single mode
if [ "$nprocs" -eq 1 ]; then
  ./swan.exe
else
  mpirun -np "$nprocs" ./swan.exe
fi

# Handle the PRINT files
if [ "$nprocs" -eq 1 ]; then
  if [ -f PRINT ]; then
    cp PRINT "${inputfile}.prt"
    rm PRINT
  fi
else
  if [ -f PRINT-001 ]; then
    for i in $(seq 1 $nprocs); do
      if [ -f "PRINT-00$i" ]; then
        cp "PRINT-00$i" "${inputfile}.prt-00$i"
        rm "PRINT-00$i"
      fi
    done
  fi
fi

# Clean up
rm INPUT
if [ -f norm_end ]; then
  cat norm_end
fi

#!/bin/bash
#SBATCH -J ifg_po
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 32
#SBATCH --time=06:00:00
#SBATCH --mem=0
#SBATCH --array=1-64
#SBATCH -o logs/%x_%A_%a.out
#SBATCH -e logs/%x_%A_%a.err

MISSION="S1"  # change to ERS / ENV / ALOS / S1
PAIRS="pairs/pairs_${MISSION}.csv"

# Make sure array max matches number of pairs (or cap it)
IDX=${SLURM_ARRAY_TASK_ID}

bash scripts/run_one_pair.sh "$MISSION" "$PAIRS" "$IDX"

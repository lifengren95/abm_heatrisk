#!/bin/bash -l

#SBATCH --job-name=heat_risk_alldates


#SBATCH --array=0-367

#SBATCH --partition=msismall

#SBATCH --nodes=1

#SBATCH --ntasks=32               # 32 cores per job

#SBATCH --mem=128G                 # 128GB per job

#SBATCH --time=48:00:00          # 48 hours for 1 date

#SBATCH --tmp=50G

#SBATCH --mail-type=ALL


#SBATCH --output=logs/heat_32c_%A_%a.out

#SBATCH --error=logs/heat_32c_%A_%a.err



# Create logs directory

mkdir -p logs



# Load Python module

module load python3/3.10.9_anaconda2023.03_libmamba



# Activate environment

source "${HEAT_VENV:?Set HEAT_VENV to your virtual environment}/bin/activate"



# Change directory

cd "${SLURM_SUBMIT_DIR:?Submit from the repository root}"



# Each job processes 1 date

export START_DATE_IDX=$SLURM_ARRAY_TASK_ID

export END_DATE_IDX=$SLURM_ARRAY_TASK_ID



# Log info

echo "================================="

echo "HEAT RISK MODEL - 32 CORE VERSION"

echo "================================="

echo "Job ID: $SLURM_JOB_ID"

echo "Array Task ID: $SLURM_ARRAY_TASK_ID"

echo "Node: $SLURMD_NODENAME"

echo "Date index: $START_DATE_IDX"

echo "Start time: $(date)"

echo "================================="



# Run with 30 workers (leaving 2 cores for system)

python run_heat_risk_model_msi_07232025.py



echo "================================="

echo "End time: $(date)"

echo "================================="

#!/bin/bash -l
#SBATCH --job-name=heat_array_test
#SBATCH --array=0-1%2
#SBATCH --partition=msismall
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --tmp=100G
#SBATCH --mail-type=ALL
#SBATCH --output=logs/heat_array_%A_%a.out
#SBATCH --error=logs/heat_array_%A_%a.err

# Create logs directory (if it doesn't exist)
mkdir -p logs

# Load Python module
module load python3/3.10.9_anaconda2023.03_libmamba

# Activate environment
source "${HEAT_VENV:?Set HEAT_VENV to your virtual environment}/bin/activate"

# Change directory
cd "${SLURM_SUBMIT_DIR:?Submit from the repository root}"

# Calculate which dates this array job should process
# Each job processes 2 dates (4 dates total / 2 jobs = 2 dates per job)
START_IDX=$((SLURM_ARRAY_TASK_ID * 2))
END_IDX=$((START_IDX + 1))

# Log job information
echo "================================="
echo "HEAT RISK MODEL TEST - JOB INFO"
echo "================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Array Task ID: $SLURM_ARRAY_TASK_ID"
echo "Node: $SLURMD_NODENAME"
echo "Partition: $SLURM_JOB_PARTITION"
echo "Date indices: $START_IDX to $END_IDX"
echo "Start time: $(date)"
echo "================================="

# Run the Python script with array job parameters
# --test-mode runs 10 iterations instead of 1000
python run_test_MSI_heat_risk_model_new_ac_data_parallel.py --date-indices $START_IDX $END_IDX --test-mode

echo "================================="
echo "End time: $(date)"
echo "================================="
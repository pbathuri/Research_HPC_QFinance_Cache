#!/bin/bash
#SBATCH --job-name=qhpc_mpi_scaling
#SBATCH --partition=general
#SBATCH --nodes=4
#SBATCH --ntasks=16
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=slurm_mpi_scaling_%j.out
#SBATCH --error=slurm_mpi_scaling_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail

module load python/3.11 2>/dev/null || true
module load openmpi/4.1 2>/dev/null || true

cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"

source venv/bin/activate 2>/dev/null || true
export PYTHONPATH=src

OUTPUT="outputs/mpi_scaling_$(date +%Y%m%d_%H%M%S)"

srun --mpi=pmix python3 run_mpi_scaling_study.py \
    --scale-label standard \
    --strategy all \
    --output-root "$OUTPUT"

echo "Completed: $OUTPUT"

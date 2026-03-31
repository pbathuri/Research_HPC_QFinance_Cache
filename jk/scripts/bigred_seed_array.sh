#!/bin/bash
#SBATCH --job-name=qhpc_seed_array
#SBATCH --partition=general
#SBATCH --array=42-46
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=slurm_seed_%A_%a.out
#SBATCH --error=slurm_seed_%A_%a.err
#SBATCH --mail-type=END,FAIL
# Seed sweep array job: standard scale across seeds 42-46
# Enables cross-run aggregation and seed stability analysis

set -euo pipefail

module load python/3.11 2>/dev/null || true
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"

source venv/bin/activate 2>/dev/null || true
export PYTHONPATH=src

SEED=${SLURM_ARRAY_TASK_ID}
OUTPUT="outputs/bigred_seed_array_${SLURM_ARRAY_JOB_ID}/seed_${SEED}"

python3 run_repeated_workload_study.py \
    --lane both \
    --scale-label standard \
    --seed "$SEED" \
    --output-root "$OUTPUT" \
    --budget-minutes 90 \
    --requested-backend slurm_bigred200 \
    --no-plots

echo "Seed $SEED completed: $OUTPUT"

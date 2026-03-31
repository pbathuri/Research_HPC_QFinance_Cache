#!/bin/bash
#SBATCH --job-name=qhpc_rws_long_wave
#SBATCH --partition=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --output=slurm_rws_longwave_%j.out
#SBATCH --error=slurm_rws_longwave_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
module load python/3.11 2>/dev/null || true
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source venv/bin/activate 2>/dev/null || true
export PYTHONPATH=src

SEED="${1:-42}"
OUTPUT="outputs/bigred_rws_longwave_seed${SEED}_$(date +%Y%m%d_%H%M%S)"

python3 run_repeated_workload_study.py \
    --lane both \
    --scale-label long_wave \
    --seed "$SEED" \
    --output-root "$OUTPUT" \
    --budget-minutes 300 \
    --requested-backend slurm_bigred200 \
    --no-plots

echo "Completed: $OUTPUT"
echo "SLURM_JOB_ID=$SLURM_JOB_ID"

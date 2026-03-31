#!/bin/bash
#SBATCH --job-name=qhpc_full_longbudget
#SBATCH --partition=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=slurm_full_longbudget_%j.out
#SBATCH --error=slurm_full_longbudget_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
module load python/3.11 2>/dev/null || true
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source venv/bin/activate 2>/dev/null || true
export PYTHONPATH=src

BUDGET="${1:-180}"
OUTPUT="outputs/bigred_full_longbudget_$(date +%Y%m%d_%H%M%S)"

python3 run_full_research_pipeline.py \
    --mode full \
    --budget "$BUDGET" \
    --output-root "$OUTPUT" \
    --requested-backend slurm_bigred200

echo "Completed: $OUTPUT"
echo "SLURM_JOB_ID=$SLURM_JOB_ID"

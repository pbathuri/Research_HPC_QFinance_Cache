#!/bin/bash
#SBATCH --job-name=qhpc_full_pipeline
#SBATCH --partition=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=slurm_full_%j.out
#SBATCH --error=slurm_full_%j.err
#SBATCH --mail-type=END,FAIL
# Full research pipeline on BigRed200

set -euo pipefail

module load python/3.11 2>/dev/null || true
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"

source venv/bin/activate 2>/dev/null || true
export PYTHONPATH=src

BUDGET="${1:-60}"
OUTPUT="outputs/bigred_full_$(date +%Y%m%d_%H%M%S)"

python3 run_full_research_pipeline.py \
    --mode full \
    --budget "$BUDGET" \
    --output-root "$OUTPUT" \
    --requested-backend slurm_bigred200

echo "Completed: $OUTPUT"

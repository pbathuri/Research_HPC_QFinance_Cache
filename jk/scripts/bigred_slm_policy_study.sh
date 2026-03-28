#!/bin/bash
#SBATCH --job-name=qhpc_slm_policy
#SBATCH --partition=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=slurm_slm_policy_%j.out
#SBATCH --error=slurm_slm_policy_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail

module load python/3.11 2>/dev/null || true
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"

source venv/bin/activate 2>/dev/null || true
export PYTHONPATH=src

OUTPUT="outputs/slm_policy_$(date +%Y%m%d_%H%M%S)"

python3 run_slm_policy_study.py \
    --scale-label standard \
    --output-root "$OUTPUT" \
    --model-type gradient_boosting

echo "Completed: $OUTPUT"

#!/bin/bash
#SBATCH --partition=main
#SBATCH --time=00:20:00
#SBATCH --mem=4G
#SBATCH --output=slurm_logs/%x_%j.out
#SBATCH --error=slurm_logs/%x_%j.err

set -euo pipefail

cd "$HOME/student-course-reassignment"
source .venv/bin/activate

python src/resolver_familia.py \
  --L 9 \
  --P 3 \
  --C 4 \
  --tiempo 60 \
  --hilos "${SLURM_CPUS_PER_TASK}" \
  --salida "${SALIDA}"

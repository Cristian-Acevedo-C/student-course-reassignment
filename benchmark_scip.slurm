#!/bin/bash
#SBATCH --partition=debug
#SBATCH --time=00:05:00
#SBATCH --mem=4G
#SBATCH --output=slurm_logs/%x_%j.out
#SBATCH --error=slurm_logs/%x_%j.err

set -euo pipefail

cd "$HOME/student-course-reassignment"
source .venv/bin/activate

echo "Nodo: $(hostname)"
echo "Fecha: $(date)"
echo "CPUs asignadas: ${SLURM_CPUS_PER_TASK}"
echo "Salida: ${SALIDA}"

python src/resolver_familia.py \
  --L 9 \
  --P 3 \
  --C 4 \
  --tiempo 60 \
  --hilos "${SLURM_CPUS_PER_TASK}" \
  --replicas 0 \
  --preflight \
  --salida "${SALIDA}"

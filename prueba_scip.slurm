#!/bin/bash
#SBATCH --job-name=scip_preflight
#SBATCH --partition=debug
#SBATCH --cpus-per-task=1
#SBATCH --time=00:05:00
#SBATCH --mem=4G
#SBATCH --output=slurm_logs/scip_preflight_%j.out
#SBATCH --error=slurm_logs/scip_preflight_%j.err

set -euo pipefail

cd "$HOME/student-course-reassignment"
source .venv/bin/activate

echo "Nodo: $(hostname)"
echo "Fecha: $(date)"
echo "CPUs asignadas: ${SLURM_CPUS_PER_TASK}"
python --version

python src/resolver_familia.py \
  --L 9 \
  --P 3 \
  --C 4 \
  --tiempo 60 \
  --hilos 1 \
  --replicas 0 \
  --preflight \
  --salida corridas_nlhpc/preflight_1cpu

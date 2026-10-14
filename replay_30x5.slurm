#!/bin/bash
#SBATCH --job-name=scip_replay
#SBATCH --partition=main
#SBATCH --array=0-29%30
#SBATCH --cpus-per-task=5
#SBATCH --mem=4G
#SBATCH --time=01:15:00
#SBATCH --output=logs/replay_%A_%a.out
#SBATCH --error=logs/replay_%A_%a.err
set -euo pipefail
cd "$HOME/student-course-reassignment"
C=$((4 + SLURM_ARRAY_TASK_ID / 10))
I=$((SLURM_ARRAY_TASK_ID % 10))
"$HOME/venv_scip/bin/python" src/replay_inicial_scip.py \
  --L 9 --P 3 --C "$C" --replica "$I" \
  --tiempo 3600 --hilos "$SLURM_CPUS_PER_TASK" \
  --base-root corridas_nlhpc/base_5cpu_v1/T3600 \
  --salida "corridas_nlhpc/replay_scip_base_5cpu_v1/T3600/C${C}/i${I}"

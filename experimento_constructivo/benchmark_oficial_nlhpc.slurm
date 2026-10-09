#!/bin/bash
#SBATCH --job-name=scrp_warm
#SBATCH --partition=main
#SBATCH --array=0-29%8
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=03:00:00
#SBATCH --output=logs/scrp_warm_%A_%a.out
#SBATCH --error=logs/scrp_warm_%A_%a.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Ejecutar sbatch desde la raiz del paquete SCRP}"
if [[ ! -f experimento_constructivo/comparar_oficial_checkpoint.py ]]; then
  echo "Falta el script en la raiz del paquete" >&2
  exit 2
fi

# C=4,5,6; diez réplicas por familia. Cada elemento usa el mismo presupuesto
# de 3600 s para el pipeline de cada condición y un núcleo por solve.
family=$((4 + SLURM_ARRAY_TASK_ID / 10))
replica=$((SLURM_ARRAY_TASK_ID % 10))
case "$family" in
  4) attempts=20; nodes=50000 ;;
  5) attempts=8; nodes=80000 ;;
  6) attempts=8; nodes=100000 ;;
esac

python -u experimento_constructivo/comparar_oficial_checkpoint.py \
  --patron "c_n_9_l_3_s_${family}_i_${replica}.txt" \
  --salida "resultados_warm_start/oficial_3600s/C${family}_i${replica}" \
  --presupuesto 3600 \
  --seed-scip 0 \
  --seed-heuristica 20261001 \
  --intentos "$attempts" \
  --limite-nodos "$nodes"

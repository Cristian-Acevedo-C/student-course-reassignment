#!/bin/bash
#SBATCH --job-name=warm_30x5_v2
#SBATCH --partition=main
#SBATCH --array=0-29%30
#SBATCH --cpus-per-task=5
#SBATCH --mem=4G
#SBATCH --time=01:15:00
#SBATCH --output=slurm_logs/%x_%A_%a.out
#SBATCH --error=slurm_logs/%x_%A_%a.err

set -euo pipefail

REPO="$HOME/student-course-reassignment"
PY="$HOME/venv_scip/bin/python"
cd "$REPO"

[[ -x "$PY" ]] || { echo "ERROR: no existe $PY" >&2; exit 2; }
TASK="${SLURM_ARRAY_TASK_ID:?Este archivo requiere un job array}"
[[ "$TASK" =~ ^[0-9]+$ ]] && (( TASK >= 0 && TASK < 30 )) || { echo "ID invalido: $TASK" >&2; exit 2; }

C=$((4 + TASK / 10))
I=$((TASK % 10))
INSTANCIA="c_n_9_l_3_s_${C}_i_${I}"
SOLUCIONES="warm_start/constructivo/L9_P3_C${C}"
LIMITE_SCIP="${LIMITE_SCIP:-3600}"
[[ "$LIMITE_SCIP" =~ ^[0-9]+$ ]] && (( LIMITE_SCIP >= 1 && LIMITE_SCIP <= 3600 )) || { echo "LIMITE_SCIP invalido" >&2; exit 2; }
SALIDA="corridas_nlhpc/warm_5cpu_v2/T${LIMITE_SCIP}/C${C}/i${I}"

[[ -f "${SOLUCIONES}/heur_${INSTANCIA}.txt" ]] || { echo "Falta heur_${INSTANCIA}.txt" >&2; exit 2; }
if [[ -e "$SALIDA" ]]; then
  echo "ERROR: salida ya existente: $SALIDA; no sobreescribo" >&2
  exit 3
fi

AYUDA="$($PY src/resolver_familia.py --help 2>&1)"
grep -q -- '--replicas' <<<"$AYUDA" && grep -q -- '--preflight' <<<"$AYUDA" || {
 echo 'ERROR: faltan los argumentos --replicas o --preflight' >&2; exit 4;
}

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-5}"
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

printf 'SLURM_JOB_ID=%s TASK=%s HOST=%s C=%s I=%s CPUS=%s\n' \
 "$SLURM_JOB_ID" "$TASK" "$(hostname)" "$C" "$I" "${SLURM_CPUS_PER_TASK:-unset}"
echo "SCIP time limit: $LIMITE_SCIP; output: $SALIDA"
echo 'Modo --preflight obligatorio porque el ejecutor admite --replicas solo en pruebas tecnicas.'
echo 'Reservar 5 CPU no garantiza que SCIP utilice los 5 nucleos.'

"$PY" src/resolver_familia_warm.py \
 --L 9 --P 3 --C "$C" \
 --tiempo "$LIMITE_SCIP" --hilos 5 \
 --replicas "$I" --preflight \
 --salida "$SALIDA" \
 --soluciones-ws "$SOLUCIONES"

"$PY" - "$SALIDA" "$INSTANCIA" <<'PY'
import csv, pathlib, sys
out, expected = pathlib.Path(sys.argv[1]), sys.argv[2]
p = out / 'resultados_familia.csv'
if not p.is_file():
    raise SystemExit(f'ERROR: no se genero {p}')
with p.open(newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
if len(rows) != 1 or rows[0].get('instancia') != expected:
    raise SystemExit(f'ERROR: resultado inesperado; filas={len(rows)}, esperada={expected}, obtenida={rows[0].get("instancia") if rows else "sin filas"}')
print(f'OK: exactamente una replica: {expected}')
PY

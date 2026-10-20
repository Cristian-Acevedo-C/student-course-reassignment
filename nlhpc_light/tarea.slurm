#!/bin/bash
# =====================================================================
#  UNA instancia por tarea del job array, 1 CPU, sin warm start.
#  No se lanza a mano: lo lanza nlhpc_light/lanzar.sh
#  Variables (las pone lanzar.sh): LISTA, FORMULACION, LIMITE_SCIP, ETIQUETA
# =====================================================================
#SBATCH --job-name=scrp
#SBATCH --partition=main
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:15:00
#SBATCH --output=slurm_logs/%x_%A_%a.out
#SBATCH --error=slurm_logs/%x_%A_%a.err

set -euo pipefail

REPO="${REPO:-$HOME/student-course-reassignment}"
PY="${PY:-$HOME/venv_scip/bin/python}"
cd "$REPO"

[[ -x "$PY" ]] || { echo "ERROR: no existe $PY (corre nlhpc_light/instalar.sh)" >&2; exit 2; }
: "${LISTA:?falta LISTA}" "${FORMULACION:?falta FORMULACION}" "${ETIQUETA:?falta ETIQUETA}"
LIMITE="${LIMITE_SCIP:-3600}"
TASK="${SLURM_ARRAY_TASK_ID:?Se requiere un job array}"

INSTANCIA="$(sed -n "$((TASK + 1))p" "$LISTA")"
[[ "$INSTANCIA" =~ ^c_n_([0-9]+)_l_([0-9]+)_s_([0-9]+)_i_([0-9])$ ]] || {
  echo "ERROR: linea $((TASK + 1)) de $LISTA no es una instancia valida: '$INSTANCIA'" >&2; exit 2; }
L="${BASH_REMATCH[1]}"; P="${BASH_REMATCH[2]}"; C="${BASH_REMATCH[3]}"; I="${BASH_REMATCH[4]}"

SALIDA="corridas_nlhpc/${ETIQUETA}/T${LIMITE}/L${L}_P${P}_C${C}/i${I}"
if [[ -e "$SALIDA/resultados_familia.csv" ]]; then
  echo "YA EXISTE $SALIDA: se omite (borra la carpeta si quieres repetirla)."; exit 0
fi
rm -rf "$SALIDA"   # restos de una tarea interrumpida (sin CSV)

export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

printf 'JOB=%s TASK=%s HOST=%s INST=%s FORM=%s LIMIT=%s\n' \
  "${SLURM_JOB_ID:-?}" "$TASK" "$(hostname)" "$INSTANCIA" "$FORMULACION" "$LIMITE"

"$PY" src/resolver_familia.py \
  --L "$L" --P "$P" --C "$C" \
  --tiempo "$LIMITE" --hilos 1 --gap 0 --lambda-0 1 --lambda-1 1 \
  --replicas "$I" --preflight \
  --formulacion "$FORMULACION" \
  --salida "$SALIDA"

"$PY" - "$SALIDA" "$INSTANCIA" <<'PYEOF'
import csv, pathlib, sys
salida, esperado = pathlib.Path(sys.argv[1]), sys.argv[2]
p = salida / 'resultados_familia.csv'
if not p.is_file():
    raise SystemExit(f'ERROR: falta {p}')
with p.open(newline='', encoding='utf-8-sig') as f:
    filas = list(csv.DictReader(f))
if len(filas) != 1 or filas[0].get('instancia') != esperado:
    raise SystemExit(f'ERROR: se esperaba {esperado}')
r = filas[0]
print(f"OK {esperado}: estado={r['estado']} tiempo={r['tiempo_scip_seg']} "
      f"primal={r['primal_bound']} dual={r['dual_bound']} auditada={r['solucion_auditada']}")
PYEOF

# Actualiza el Excel/tablas consolidadas con lo que haya terminado hasta ahora.
# flock evita que dos tareas que terminan a la vez escriban al mismo tiempo.
mkdir -p corridas_nlhpc
flock corridas_nlhpc/.consolidar.lock \
  "$PY" nlhpc_light/consolidar.py --limite "$LIMITE" > /dev/null \
  || echo "AVISO: no se pudo actualizar el consolidado (la corrida de la instancia esta bien)."

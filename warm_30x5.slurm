#!/bin/bash
#SBATCH --job-name=warm_30x5
#SBATCH --partition=main
#SBATCH --array=0-29%30
#SBATCH --cpus-per-task=5
#SBATCH --mem=4G
#SBATCH --time=01:10:00
#SBATCH --output=slurm_logs/%x_%A_%a.out
#SBATCH --error=slurm_logs/%x_%A_%a.err

set -euo pipefail

REPO="$HOME/student-course-reassignment"
PY="$HOME/venv_scip/bin/python"
cd "$REPO"

if [[ ! -x "$PY" ]]; then
  echo "ERROR: No existe $PY" >&2
  exit 2
fi

TASK="${SLURM_ARRAY_TASK_ID:?Se requiere SLURM_ARRAY_TASK_ID}"
C=$((4 + TASK / 10))
I=$((TASK % 10))
INSTANCIA="c_n_9_l_3_s_${C}_i_${I}"
SOLUCIONES="warm_start/constructivo/L9_P3_C${C}"
SALIDA="corridas_nlhpc/warm_5cpu_exp/C${C}/i${I}"

# Verificaciones previas: evitan consumir recursos en una tarea mal mapeada.
[[ "$TASK" =~ ^[0-9]+$ ]] && ((TASK >= 0 && TASK < 30)) || { echo "ID de tarea invalido" >&2; exit 2; }
[[ -f "${SOLUCIONES}/heur_${INSTANCIA}.txt" ]] || { echo "Falta solucion heur_${INSTANCIA}.txt" >&2; exit 2; }

# El resolver de familia puede iterar por todas las replicas. No ejecutar sin
# comprobar que soporta un filtro de UNA sola instancia.
AYUDA="$($PY src/resolver_familia.py --help 2>&1 || true)"
SELECTOR=()
if grep -Eq -- '(^|[[:space:],])--patron([[:space:],=]|$)' <<< "$AYUDA"; then
  SELECTOR=(--patron "${INSTANCIA}.txt")
elif grep -Eq -- '(^|[[:space:],])--instancia([[:space:],=]|$)' <<< "$AYUDA"; then
  SELECTOR=(--instancia "$INSTANCIA")
else
  echo "ERROR SEGURO: resolver_familia.py no expone --patron ni --instancia." >&2
  echo "No se lanza una familia completa por cada tarea (evita 300 corridas)." >&2
  echo "Inspeccionar: sed -n '890,970p' src/resolver_familia.py" >&2
  exit 78
fi

mkdir -p "$SALIDA"
if [[ -f "${SALIDA}/resultados_familia.csv" ]]; then
  echo "ERROR: salida preexistente en $SALIDA. No se sobrescribe." >&2
  exit 3
fi

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-5}"
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

echo "SLURM job=$SLURM_JOB_ID task=$TASK host=$(hostname)"
echo "Instancia=$INSTANCIA; CPUs reservadas=${SLURM_CPUS_PER_TASK:-desconocido}"
echo "NOTA: reservar 5 CPUs no garantiza paralelismo efectivo en m.optimize()."
echo "Comando: $PY src/resolver_familia_warm.py --L 9 --P 3 --C $C --tiempo 3600 --hilos 5 --salida $SALIDA --soluciones-ws $SOLUCIONES ${SELECTOR[*]}"

"$PY" src/resolver_familia_warm.py \
  --L 9 --P 3 --C "$C" \
  --tiempo 3600 --hilos 5 \
  --salida "$SALIDA" \
  --soluciones-ws "$SOLUCIONES" \
  "${SELECTOR[@]}"

# Al finalizar, corroborar que no se hayan procesado varias instancias.
"$PY" - "$SALIDA" "$INSTANCIA" <<'PY'
import csv, pathlib, sys
out, expected = pathlib.Path(sys.argv[1]), sys.argv[2]
path = out / 'resultados_familia.csv'
if not path.is_file():
    raise SystemExit('ERROR: no se genero ' + str(path))
with path.open(newline='', encoding='utf-8-sig') as f:
    data = list(csv.DictReader(f))
if len(data) != 1:
    raise SystemExit(f'ERROR: se esperaban 1 replica, hay {len(data)} en {path}')
name = data[0].get('instancia')
if name != expected:
    raise SystemExit(f'ERROR: se esperaba {expected} y se obtuvo {name}')
print('OK: una sola replica y nombre esperado:', expected)
PY

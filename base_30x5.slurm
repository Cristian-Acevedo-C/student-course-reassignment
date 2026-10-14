#!/bin/bash
#SBATCH --job-name=base_30x5
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
TASK="${SLURM_ARRAY_TASK_ID:?Se requiere un job array}"
[[ "$TASK" =~ ^[0-9]+$ ]] && (( TASK >= 0 && TASK < 30 )) || {
  echo "ERROR: ID de tarea invalido: $TASK" >&2; exit 2;
}

C=$((4 + TASK / 10))
I=$((TASK % 10))
INSTANCIA="c_n_9_l_3_s_${C}_i_${I}"
LIMITE="${LIMITE_SCIP:-3600}"
[[ "$LIMITE" =~ ^[0-9]+$ ]] && (( LIMITE >= 1 && LIMITE <= 3600 )) || {
  echo "ERROR: LIMITE_SCIP debe ser un entero entre 1 y 3600" >&2; exit 2;
}
SALIDA="corridas_nlhpc/base_5cpu_v1/T${LIMITE}/C${C}/i${I}"

[[ ! -e "$SALIDA" ]] || {
  echo "ERROR: salida existente $SALIDA. No se sobrescribira." >&2; exit 3;
}

AYUDA="$($PY src/resolver_familia.py --help 2>&1)"
grep -q -- '--replicas' <<< "$AYUDA" && grep -q -- '--preflight' <<< "$AYUDA" || {
  echo "ERROR: ejecutor no admite --replicas/--preflight" >&2; exit 4;
}

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-5}"
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

printf 'BASELINE JOB=%s TASK=%s HOST=%s C=%s I=%s CPUS=%s LIMIT=%s\n' \
  "${SLURM_JOB_ID:-?}" "$TASK" "$(hostname)" "$C" "$I" "${SLURM_CPUS_PER_TASK:-?}" "$LIMITE"
echo "Salidas: $SALIDA"
echo 'Modo --preflight solo para habilitar la seleccion individual --replicas; verificar protocolo al analizar.'

"$PY" src/resolver_familia.py \
  --L 9 --P 3 --C "$C" \
  --tiempo "$LIMITE" --hilos 5 \
  --replicas "$I" --preflight \
  --salida "$SALIDA"

"$PY" - "$SALIDA" "$INSTANCIA" <<'PY'
import csv, pathlib, sys
salida, esperado = pathlib.Path(sys.argv[1]), sys.argv[2]
p = salida / 'resultados_familia.csv'
if not p.is_file():
    raise SystemExit(f'ERROR: falta {p}')
with p.open(newline='', encoding='utf-8-sig') as f:
    filas = list(csv.DictReader(f))
if len(filas) != 1 or filas[0].get('instancia') != esperado:
    raise SystemExit(f'ERROR: se esperaba exactamente {esperado}; se obtuvo {[f.get("instancia") for f in filas]}')
if filas[0].get('hilos') != '5':
    raise SystemExit(f'ERROR: hilos inesperados: {filas[0].get("hilos")}')
if filas[0].get('modo') != 'preflight':
    print(f'AVISO: modo={filas[0].get("modo")}; revisar protocolo')
print(f'OK: exactamente una replica sin warm start: {esperado}')
PY

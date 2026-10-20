#!/bin/bash
# =====================================================================
#  Lanza instancias en NLHPC como job array (1 instancia = 1 tarea = 1 CPU).
#
#  Uso:
#    nlhpc_light/lanzar.sh <light|baseline> <seleccion> [limite_seg] [max_simultaneas]
#
#  <seleccion>:
#    L9_P3_C5        una familia (10 replicas)
#    C5              todas las familias con C=5 (120 instancias)
#    todo            las 480 instancias
#    archivo.txt     lista propia (un nombre de instancia por linea)
#
#  Ejemplos:
#    nlhpc_light/lanzar.sh light L9_P3_C4 60          # prueba de 60 s
#    nlhpc_light/lanzar.sh light L9_P3_C5             # familia, 3600 s
#    nlhpc_light/lanzar.sh baseline L9_P3_C5          # su par baseline
#    nlhpc_light/lanzar.sh light todo 3600 40         # 480, max 40 a la vez
# =====================================================================
set -euo pipefail
REPO="${REPO:-$HOME/student-course-reassignment}"
cd "$REPO"

FORM="${1:?formulacion: light o baseline}"
SEL="${2:?seleccion: L9_P3_C5 | C5 | todo | archivo.txt}"
LIMITE="${3:-3600}"
MAXSIM="${4:-30}"
[[ "$FORM" == "light" || "$FORM" == "baseline" ]] || { echo "formulacion invalida: $FORM"; exit 1; }
[[ "$LIMITE" =~ ^[0-9]+$ ]] && (( LIMITE >= 1 && LIMITE <= 3600 )) || { echo "limite entre 1 y 3600"; exit 1; }

mkdir -p slurm_logs nlhpc_light/listas
if [[ -f "$SEL" ]]; then
  LISTA="$SEL"
else
  LISTA="nlhpc_light/listas/${FORM}_${SEL}_T${LIMITE}.txt"
  case "$SEL" in
    todo)            PATRON='c_n_*_l_*_s_*_i_*.txt' ;;
    C[4-7])          PATRON="c_n_*_l_*_s_${SEL#C}_i_*.txt" ;;
    L*_P*_C*)        IFS=_ read -r A B D <<< "$SEL"
                     PATRON="c_n_${A#L}_l_${B#P}_s_${D#C}_i_*.txt" ;;
    *) echo "seleccion no reconocida: $SEL"; exit 1 ;;
  esac
  { ls instancias/$PATRON 2>/dev/null || true; } | xargs -r -n1 basename | sed "s/\.txt$//" | sort -V > "$LISTA"
fi
N=$(grep -c . "$LISTA" || true)
(( N > 0 )) || { echo "ERROR: la seleccion no tiene instancias ($LISTA)"; exit 1; }

# Para comparar formulaciones, ambas deben quedar en el mismo tipo de nodo.
ETIQUETA="${FORM}_v1"
HORAS=$(( (LIMITE + 900) / 3600 )); MIN=$(( ((LIMITE + 900) % 3600) / 60 ))
TIEMPO=$(printf '%02d:%02d:00' "$HORAS" "$MIN")

echo "Formulacion: $FORM | instancias: $N | limite SCIP: ${LIMITE}s | walltime: $TIEMPO | simultaneas: $MAXSIM"
echo "Lista: $LISTA"
echo "Salidas: corridas_nlhpc/${ETIQUETA}/T${LIMITE}/"
sbatch --job-name="${FORM}" --array="0-$((N - 1))%${MAXSIM}" --time="$TIEMPO" \
  --export=ALL,LISTA="$LISTA",FORMULACION="$FORM",LIMITE_SCIP="$LIMITE",ETIQUETA="$ETIQUETA",REPO="$REPO" \
  nlhpc_light/tarea.slurm

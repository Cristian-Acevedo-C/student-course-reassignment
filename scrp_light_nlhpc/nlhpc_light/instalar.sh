#!/bin/bash
# Crea (si no existe) el entorno ~/venv_scip con PySCIPOpt 6.2.1 / SCIP 10.0.2
# y comprueba que el repo funciona. Correr UNA vez en el nodo de login.
set -euo pipefail
REPO="${REPO:-$HOME/student-course-reassignment}"
VENV="${VENV:-$HOME/venv_scip}"
cd "$REPO"
if [[ ! -x "$VENV/bin/python" ]]; then
  if command -v module >/dev/null 2>&1; then module load python 2>/dev/null || true; fi
  python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip
  "$VENV/bin/python" -m pip install -r requirements.txt
fi
PY="$VENV/bin/python"
# openpyxl: para el Excel de resultados (consolidar.py)
"$PY" -c "import openpyxl" 2>/dev/null || "$PY" -m pip install openpyxl
"$PY" - <<'PYEOF'
import pyscipopt
m = pyscipopt.Model()
v = f"{m.getMajorVersion()}.{m.getMinorVersion()}.{m.getTechVersion()}"
print("PySCIPOpt", pyscipopt.__version__, "| SCIP", v)
assert pyscipopt.__version__ == "6.2.1" and v == "10.0.2", "versiones distintas al protocolo"
PYEOF
"$PY" -m unittest discover -s tests 2>&1 | tail -n 3
"$PY" src/resolver_familia.py --help | grep -q -- "--formulacion" && echo "OK: resolver_familia.py admite --formulacion"
mkdir -p slurm_logs
echo "Instalacion lista. Siguiente: nlhpc_light/lanzar.sh light L9_P3_C4 60"

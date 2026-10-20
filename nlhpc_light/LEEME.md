# Formulación light en NLHPC

Archivos de la formulación light dentro del repo:

| Archivo | Qué es |
|---|---|
| `src/modelo_light.py` | Formulación compacta equivalente (nuevo; `modelo.py` no cambia) |
| `src/resolver_familia.py` | Ejecutor con la opción `--formulacion light` (por defecto sigue siendo `baseline`) |
| `correr_familia.ps1` | Lanzador de Windows con `-Formulacion light` |
| `nlhpc_light/instalar.sh` | Comprueba (o crea) `~/venv_scip` y el repo |
| `nlhpc_light/lanzar.sh` | Lanza instancias como job array: 1 instancia = 1 tarea = 1 CPU |
| `nlhpc_light/tarea.slurm` | Lo que corre cada tarea (no se lanza a mano) |
| `nlhpc_light/consolidar.py` | Junta resultados, compara light vs baseline y genera el Excel `resumen_resultados.xlsx` |

## 1. Subir y descomprimir (repo completo)

Sube `student-course-reassignment-light.zip` a tu home de NLHPC (panel SFTP de MobaXterm)
y en la terminal:

```bash
cd ~
unzip -o student-course-reassignment-light.zip     # crea/actualiza ~/student-course-reassignment
cd ~/student-course-reassignment
chmod +x nlhpc_light/*.sh nlhpc_light/tarea.slurm
```
Si ya existía `~/student-course-reassignment`, se actualiza el código y se conservan
las carpetas de corridas anteriores (`corridas_nlhpc/`, etc.).

## 2. Comprobar (una vez, en el login)

```bash
nlhpc_light/instalar.sh
```
Debe terminar con `OK: resolver_familia.py admite --formulacion` y los tests en `OK`.

## 3. Prueba corta (60 s por instancia, una familia)

```bash
nlhpc_light/lanzar.sh light L9_P3_C4 60
squeue -u $USER                       # ver cola
tail slurm_logs/light_*_0.out         # cada tarea termina con "OK <instancia>: estado=..."
```

## 4. Corridas reales (3600 s)

```bash
nlhpc_light/lanzar.sh light L9_P3_C5            # una familia (10 instancias)
nlhpc_light/lanzar.sh light C5                  # todas las de C=5 (120)
nlhpc_light/lanzar.sh light todo 3600 40        # las 480, máx 40 simultáneas
```
Para comparar en el MISMO hardware, lanza también el baseline de las mismas instancias:
```bash
nlhpc_light/lanzar.sh baseline L9_P3_C5
```
- Cada instancia queda en `corridas_nlhpc/<light|baseline>_v1/T3600/L*_P*_C*/i*/` con el
  mismo contenido de siempre (CSV, TXT, log SCIP, estadísticas, solución, auditoría).
- Relanzar es seguro: las instancias ya terminadas se omiten; las interrumpidas se repiten.
- Walltime por tarea = límite + 15 min. 1 CPU y 4 GB por tarea.
- Las tareas quedan con `modo=preflight` porque el ejecutor solo llama "oficial" a una familia
  completa en un único proceso; el protocolo (3600 s, 1 hilo, gap 0, λ0 = λ1 = 1) es el oficial.

## 5. Excel de resultados (se actualiza solo)

Cada tarea, al terminar, regenera
`corridas_nlhpc/consolidado_T<limite>/resumen_resultados.xlsx` con lo que haya
terminado hasta ese momento:

- Hoja **Resumen**: una fila por familia y formulación con instancia (familia),
  réplicas terminadas, óptimas, sin incumbente, gap promedio (%), gap desv. estándar (%),
  tiempo promedio (s) y tiempo desv. estándar (s). Desviación muestral (n−1).
- Hoja **Detalle**: una fila por instancia (estado, gap, tiempo, cotas, nodos, auditoría).
- Hoja **Asignaciones**: una fila por estudiante e instancia (curso nuevo, preferidos en su
  curso, satisfecho), leída de cada `sol_*.txt`.

Además, todas las soluciones `.txt` se copian juntas a
`corridas_nlhpc/consolidado_T<limite>/soluciones/<light|baseline>/`.
Los entregables de siempre siguen en la carpeta de cada instancia
(`corridas_nlhpc/<formulacion>_v1/T3600/L*_P*_C*/i*/`): `soluciones/sol_*.txt` y `.sol`,
`logs/`, `stats/`, `auditorias/`, `trayectorias/`, `resultados_familia.csv/.txt`,
`resumen_familia.*`, `resumen_global_familia_*.txt`, `entorno.txt`, `manifiesto.json`.

Se puede descargar en cualquier momento desde el panel SFTP de MobaXterm
(`student-course-reassignment/corridas_nlhpc/consolidado_T3600/`).

## 6. Consolidar a mano y descargar

```bash
python3 nlhpc_light/consolidar.py               # o ~/venv_scip/bin/python
cat corridas_nlhpc/consolidado_T3600/resumen_por_familia.txt
cat corridas_nlhpc/consolidado_T3600/comparacion_pares.txt
```
Desde tu PC:
```bash
scp -r USUARIO@leftraru.nlhpc.cl:~/student-course-reassignment/corridas_nlhpc/consolidado_T3600 .
```
`comparacion_pares.txt` marca con ALERTA cualquier par cuyo óptimo difiera o cuyo primal
quede bajo la cota dual de la otra formulación (no debería ocurrir nunca).

## Si tu repo o tu Python están en otra ruta

```bash
export REPO=/ruta/al/repo PY=/ruta/a/python
nlhpc_light/lanzar.sh light L9_P3_C5
```
Si la partición no se llama `main`, cambia `#SBATCH --partition=main` en `nlhpc_light/tarea.slurm`.

## Volver al estado anterior

```bash
mv src/resolver_familia.py.antes_light src/resolver_familia.py
mv correr_familia.ps1.antes_light correr_familia.ps1
rm -r src/modelo_light.py nlhpc_light
```

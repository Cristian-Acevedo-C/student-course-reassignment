# Prueba de una familia (10 réplicas) antes del benchmark de 480

Acordado en la reunión del 8-sep-2026: antes de lanzar las 480 instancias se
ejecuta **una** familia `(L, P, C)` con sus 10 réplicas, se calcula la media y la
desviación estándar del tiempo y del gap, se revisan los logs de SCIP y se
comparte esa fila con los profesores. La familia piloto es `L=9, P=3, C=4`
(`c_n_9_l_3_s_4_i_0` … `i_9`, N = 36).

Esta prueba **no** modifica la formulación (`src/modelo.py` no cambia), usa
`λ0 = λ1 = 1`, gap objetivo 0, 1 hilo, 3600 s por réplica, sin *warm start* y
sin leer `testigos/`.

## 1. Preflight técnico (≈ 1 minuto)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\correr_familia.ps1 -L 9 -P 3 -C 4 -Preflight
```

Resuelve solo la réplica 0 con 60 s y guarda todo en
`corridas\preflight\prueba_familia_L9_P3_C4_T60s_i0\`. Sirve para comprobar que
el modelo se construye, SCIP arranca, se escriben log, estadísticas, CSV y
solución, y la auditoría funciona. **No es evidencia del benchmark.**

## 2. Corrida oficial de la familia (hasta 10 h)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\correr_familia.ps1 -L 9 -P 3 -C 4 -Tiempo 3600
```

Equivalente sin PowerShell (Linux, NLHPC):

```bash
OMP_NUM_THREADS=1 python src/resolver_familia.py --L 9 --P 3 --C 4 \
    --tiempo 3600 --hilos 1 --gap 0 --lambda-0 1 --lambda-1 1
```

Salida: `corridas/prueba_familia_L9_P3_C4_T3600s/`. Si se interrumpe, relanzar
el mismo comando con `-Reanudar` (`--reanudar`): conserva las réplicas ya
terminadas con el mismo protocolo. Nunca sobrescribe una carpeta existente sin
esa opción.

Protecciones del ejecutor:

- aborta si la familia no tiene exactamente las 10 réplicas `i=0..9`;
- aborta si dos réplicas tienen la misma semilla, el mismo SHA-256 o el mismo
  contenido (perfiles, preferencias y separaciones);
- ejecuta antes `src/validar_repositorio.py` (grilla de 480 y testigos);
- exige la versión de PySCIPOpt fijada en `requirements.txt` para la corrida
  oficial, junto con SCIP 10.0.2; ambos se verifican también en Python;
- fija explícitamente `parallel/maxnthreads=1`, `lp/threads=1` y reloj de pared;
- al reanudar exige el mismo manifiesto (versiones, protocolo, código e instancias)
  y verifica hashes de los artefactos antes de omitir una réplica;
- marca la corrida como `oficial` solo si son las 10 réplicas con 3600 s, 1 hilo,
  gap 0 y λ = (1, 1); si no, `no_oficial` o `preflight`.

Los pesos oficiales son invariables entre réplicas: `lambda_0 = 1` y
`lambda_1 = 1`. Se validan antes de construir cada modelo y al exportar una
familia oficial. Un peso diferente en una sola fila impide guardar el resumen
como oficial. Pedir otros pesos en la CLI Python produce una advertencia y
modo `no_oficial`. Esta familia no hace sensibilidad de lambdas ni cambia la
función objetivo. El manifiesto y los controles de reanudación preservan los pesos.

## 3. Archivos generados

| Archivo | Contenido |
|---|---|
| `resultados_familia.csv` | una fila por réplica (columnas abajo) |
| `resultados_familia.txt` | todos los campos del mismo registro usado en el CSV, incluidos lambda_0 y lambda_1 por réplica |
| `resumen_familia.csv` | una fila para la familia |
| `resumen_familia.txt` | todos los campos del mismo resumen usado en el CSV, incluidos lambda_0 y lambda_1 |
| `resumen_familia.md` | el resumen con el subconjunto usado en cada estadística |
| `resumen_global_familia_L9_P3_C4.txt` | nombre según L/P/C; detalle de i_0 a i_9, auditorías, conteos y medias/desviaciones del CSV; réplicas sin resultados marcadas pendientes |
| `verificacion_familia.txt` | semillas, SHA-256 y diferencias entre los 45 pares de réplicas |
| `entorno.txt` | fecha, SO, CPU, RAM, Python, PySCIPOpt, SCIP, parámetros, commit, comando |
| `manifiesto.json` | identidad verificable de versiones, protocolo, código e instancias para reanudar |
| `parametros_scip.set` | parámetros SCIP distintos del *default* |
| `logs/<instancia>.log` | log completo de SCIP (presolve, tabla de progreso, estadísticas finales) |
| `stats/<instancia>.stats` | `writeStatistics` de SCIP |
| `stats/<instancia>.json` | `writeStatisticsJson` de SCIP |
| `trayectorias/<instancia>_incumbentes.csv` | cada mejora del incumbente: tiempo, objetivo, cota dual, nodos |
| `trayectorias/<instancia>_log.csv` | filas de la tabla del log: tiempo, nodo, dual, primal, gap, heurística |
| `soluciones/sol_<instancia>.txt` | asignación, composición por curso, balance, separaciones y auditoría |
| `soluciones/<instancia>.sol` | solución SCIP original con todas las variables, incluidos ceros; solo si hay incumbente |
| `auditorias/<instancia>.json` | auditoría independiente completa y resultado de checkSol; ausencia explícita si no hay incumbente |

Los TXT global, de resumen, de resultados, de entorno y de solución individual
declaran los valores con el formato `lambda_0 = 1` y `lambda_1 = 1` en una corrida
oficial. Los CSV se mantienen. Los datos numéricos y estadísticos de los nuevos
TXT proceden de los mismos registros que los CSV; `NO DISPONIBLE` representa
una celda vacía, nunca un cero inventado. Los archivos de corridas históricas
se conservan sin cambiar su trazabilidad.

## 4. Columnas de `resultados_familia.csv`

- **Identificación:** `instancia, L, P, C, replica, N, semilla, sha256_instancia, modo`.
- **Estado:** `estado` (clasificación propia) y `estado_scip` (texto de SCIP).
  `estado` ∈ `optimal`, `timelimit_with_incumbent`, `timelimit_without_incumbent`,
  `infeasible`, `interrupted`, `error`, u otro `<estado_scip>_with/without_incumbent`.
  Un límite de tiempo sin solución **nunca** se clasifica como `infeasible`.
- **Tiempos:** `tiempo_total_seg` (lectura, construcción, optimización y exportación por réplica;
  excluye validación global, captura del entorno y CSV conjunto),
  `tiempo_scip_seg` (`getSolvingTime`, incluye presolve), `tiempo_presolve_seg`,
  `tiempo_construccion_seg` (armar el MILP en Python; incluido en el total) y
  `tiempo_optimizacion_pared_seg` (reloj de pared alrededor de `optimize()`).
- **Protocolo:** `limite_seg, hilos, gap_objetivo, lambda_0, lambda_1`.
- **Cotas:** `tiene_incumbente, numero_soluciones, objetivo_incumbente, primal_bound,
  dual_bound, dual_bound_raiz, gap, gap_pct, gap_absoluto`.
  `gap` es el de SCIP: `|primal − dual| / min(|primal|, |dual|)`; se escribe `inf`
  cuando la cota dual es 0 y la primal no, o tienen signos opuestos.
  Si ambas son iguales el gap es 0. `gap_absoluto = primal − dual`.
- **Objetivo según SCIP:** `T, suma_z, no_satisfechos`.
- **Tamaño y árbol:** `nodos, variables, restricciones` (modelo original, antes de presolve).
- **Primera solución y mejor incumbente:** `tiempo_primera_solucion_factible,
  objetivo_primera_solucion_factible, nodos_primera_solucion,
  heuristica_primera_solucion, tiempo_mejor_incumbente_final,
  nodos_mejor_incumbente, heuristica_mejor_incumbente, fuente_tiempos_incumbente`.
- **Auditoría:** `solucion_auditada, n_violaciones, n_inconsistencias_objetivo,
  satisfechos_recalculado, T_recalculado, objetivo_recalculado, checksol_scip`.
- **Rutas:** `log_scip, stats_scip, stats_json, trayectoria_incumbentes,
  trayectoria_log, solucion, solucion_completa, auditoria, artefactos_sha256, error`.

### Cómo se obtienen los tiempos de primera solución

Dos fuentes independientes:

1. un manejador del evento `BESTSOLFOUND` de SCIP registra, en cada mejora del
   incumbente, `getSolvingTime()`, el objetivo, la cota dual y los nodos;
2. las líneas `First Solution` y `Primal Bound` de las estadísticas de SCIP
   (que también dan la heurística que encontró la solución).

`fuente_tiempos_incumbente = eventhdlr=stats` indica que ambas coinciden. Si no,
se deja constancia y se revisa el log; no se inventa un valor.

### Auditoría de la solución

`src/auditar_solucion.py` recalcula sin SCIP, desde los valores de todos los
`x_ic`: integralidad y asignación única (7), capacidad (8), separaciones (9),
balance de género (10–11) y mínimos por curso de origen (12). Además comprueba la
coherencia con el objetivo reportado:

- estudiantes realmente satisfechos **=** `suma_z` de SCIP (igualdad exacta
  de conteos: el MILP impone `z_i >= w_ij` y `z_i <= sum_j w_ij`);
- `T` recalculado ≤ `T` de SCIP (T solo está acotada abajo);
- `objetivo = λ0 (N − Σz) + λ1 T`.

`solucion_auditada = TRUE` exige cero violaciones, cero inconsistencias y
`checkSol` de SCIP aprobado para la solución completa. Si no
hay incumbente, queda vacía (no hay nada que auditar).

## 5. Estadísticas del resumen y subconjuntos

La desviación estándar es muestral (n − 1). Un valor vacío significa que no hay
datos suficientes; nunca se reemplaza por cero.

| Estadística | Subconjunto |
|---|---|
| `tiempo_total_promedio_seg`, `tiempo_total_desviacion_estandar_seg` | réplicas terminadas: óptimas, time limit con/sin incumbente e infactibles demostradas |
| `tiempo_scip_promedio_seg`, `tiempo_scip_desviacion_estandar_seg` | mismo subconjunto; tiempo interno SCIP, separado del total |
| `gap_promedio`, `gap_desviacion_estandar` (y `_pct`) | réplicas con incumbente y gap SCIP finito, incluidas las óptimas (gap 0) |
| `gap_promedio_solo_timelimit_pct` | solo time limit con incumbente y gap finito |
| `n_gap_infinito` | réplicas con incumbente pero cota dual 0 (excluidas del gap relativo) |
| `gap_absoluto_promedio` | réplicas con incumbente y diferencia finita; se cuentan aparte las no finitas |
| `tiempo_primera_factible_*`, `tiempo_mejor_incumbente_*` | réplicas donde SCIP encontró al menos una solución |
| `nodos_promedio`, `nodos_desviacion_estandar` | réplicas sin error ni interrupción |

Cada estadística trae su `n_*` en el CSV. Los nombres antiguos
`tiempo_promedio_seg` y `tiempo_desviacion_estandar_seg` son alias del total.
`familia_completa` y `numero_pendientes` permiten distinguir una familia completa
de un resumen parcial. `modo=oficial` solo identifica el protocolo.

El CSV de resultados se reemplaza atómicamente después de cada réplica y conserva
las terminadas posteriores aunque otra pendiente se interrumpa. La reanudación
reinicia cada pendiente desde cero, no recupera el árbol SCIP. Una carpeta antigua
sin manifiesto exige una nueva `-Salida`; no se mezcla automáticamente. Los archivos
de una réplica incompleta se reemplazan al repetirla. No iniciar dos procesos sobre
la misma salida ni mantener el CSV bloqueado en Excel.

## 6. Qué mirar en los logs (pregunta de la reunión)

- **Caso A:** `tiempo_primera_solucion_factible` alto o réplicas sin incumbente →
  SCIP tarda en encontrar factibilidad; una heurística constructiva aporta directamente.
- **Caso B:** primera solución casi inmediata, el primal mejora, pero `dual_bound`
  queda estancado (ver `trayectorias/*_log.csv`, columna `dualbound`) → la
  dificultad está en cerrar la cota; un *warm start* ayuda menos a podar.

Ejemplo de columnas útiles del log: `dualbound`, `primalbound`, `gap`, `node`,
`left` (nodos abiertos), `cuts`, y la letra inicial de cada fila (heurística que
encontró un incumbente). La sección `Primal Heuristics`, `Separators` y
`Root Node` de `stats/*.stats` resume heurísticas, cortes y cota en la raíz.

## 7. Limitaciones conocidas

- SCIP mide con reloj de pared (`timing/clocktype = 2`). Si la máquina está
  cargada, los tiempos se inflan: correr sin otras tareas pesadas.
- Con 60 s en el preflight la cota dual se quedó en el valor de la raíz; si esto
  se repite con 3600 s, el gap relativo puede ser grande aunque la diferencia
  absoluta sea de pocas unidades. Por eso se reportan también `gap_absoluto` y
  `dual_bound_raiz`.
- La columna `tiempo_total_seg` incluye construcción y exportación; para comparar
  con el límite usar `tiempo_scip_seg`. La suma de límites (10 h) no es un límite
  estricto para la duración de pared de toda la campaña.

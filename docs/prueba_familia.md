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
  oficial;
- marca la corrida como `oficial` solo si son las 10 réplicas con 3600 s, 1 hilo,
  gap 0 y λ = (1, 1); si no, `no_oficial` o `preflight`.

## 3. Archivos generados

| Archivo | Contenido |
|---|---|
| `resultados_familia.csv` | una fila por réplica (columnas abajo) |
| `resumen_familia.csv` | una fila para la familia |
| `resumen_familia.md` | el resumen con el subconjunto usado en cada estadística |
| `verificacion_familia.txt` | semillas, SHA-256 y diferencias entre los 45 pares de réplicas |
| `entorno.txt` | fecha, SO, CPU, RAM, Python, PySCIPOpt, SCIP, parámetros, commit, comando |
| `parametros_scip.set` | parámetros SCIP distintos del *default* |
| `logs/<instancia>.log` | log completo de SCIP (presolve, tabla de progreso, estadísticas finales) |
| `stats/<instancia>.stats` | `writeStatistics` de SCIP |
| `stats/<instancia>.json` | `writeStatisticsJson` de SCIP |
| `trayectorias/<instancia>_incumbentes.csv` | cada mejora del incumbente: tiempo, objetivo, cota dual, nodos |
| `trayectorias/<instancia>_log.csv` | filas de la tabla del log: tiempo, nodo, dual, primal, gap, heurística |
| `soluciones/sol_<instancia>.txt` | asignación, composición por curso, balance, separaciones y auditoría |

## 4. Columnas de `resultados_familia.csv`

- **Identificación:** `instancia, L, P, C, replica, N, semilla, sha256_instancia, modo`.
- **Estado:** `estado` (clasificación propia) y `estado_scip` (texto de SCIP).
  `estado` ∈ `optimal`, `timelimit_with_incumbent`, `timelimit_without_incumbent`,
  `infeasible`, `interrupted`, `error`, u otro `<estado_scip>_with/without_incumbent`.
  Un límite de tiempo sin solución **nunca** se clasifica como `infeasible`.
- **Tiempos:** `tiempo_total_seg` (reloj de pared alrededor de `optimize()`),
  `tiempo_scip_seg` (`getSolvingTime`, incluye presolve), `tiempo_presolve_seg`,
  `tiempo_construccion_seg` (armar el MILP en Python; no está incluido en los anteriores).
- **Protocolo:** `limite_seg, hilos, gap_objetivo, lambda_0, lambda_1`.
- **Cotas:** `tiene_incumbente, numero_soluciones, objetivo_incumbente, primal_bound,
  dual_bound, dual_bound_raiz, gap, gap_pct, gap_absoluto`.
  `gap` es el de SCIP: `|primal − dual| / min(|primal|, |dual|)`; se escribe `inf`
  cuando la cota dual es 0. `gap_absoluto = primal − dual`.
- **Objetivo según SCIP:** `T, suma_z, no_satisfechos`.
- **Tamaño y árbol:** `nodos, variables, restricciones` (modelo original, antes de presolve).
- **Primera solución y mejor incumbente:** `tiempo_primera_solucion_factible,
  objetivo_primera_solucion_factible, nodos_primera_solucion,
  heuristica_primera_solucion, tiempo_mejor_incumbente_final,
  nodos_mejor_incumbente, heuristica_mejor_incumbente, fuente_tiempos_incumbente`.
- **Auditoría:** `solucion_auditada, n_violaciones, n_inconsistencias_objetivo,
  satisfechos_recalculado, T_recalculado, objetivo_recalculado, checksol_scip`.
- **Rutas:** `log_scip, stats_scip, stats_json, trayectoria_incumbentes,
  trayectoria_log, solucion, error`.

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

- estudiantes realmente satisfechos ≥ `suma_z` de SCIP (z solo está acotada arriba);
- `T` recalculado ≤ `T` de SCIP (T solo está acotada abajo);
- `objetivo = λ0 (N − Σz) + λ1 T`.

`solucion_auditada = TRUE` exige cero violaciones y cero inconsistencias. Si no
hay incumbente, queda vacía (no hay nada que auditar).

## 5. Estadísticas del resumen y subconjuntos

La desviación estándar es muestral (n − 1). Un valor vacío significa que no hay
datos suficientes; nunca se reemplaza por cero.

| Estadística | Subconjunto |
|---|---|
| `tiempo_promedio_seg`, `tiempo_desviacion_estandar_seg` | réplicas sin error ni interrupción (óptimas y con límite de tiempo) |
| `gap_promedio`, `gap_desviacion_estandar` (y `_pct`) | réplicas con incumbente y gap SCIP finito, incluidas las óptimas (gap 0) |
| `gap_promedio_solo_timelimit_pct` | réplicas con incumbente, gap finito y no óptimas |
| `n_gap_infinito` | réplicas con incumbente pero cota dual 0 (excluidas del gap relativo) |
| `gap_absoluto_promedio` | réplicas con incumbente |
| `tiempo_primera_factible_*`, `tiempo_mejor_incumbente_*` | réplicas donde SCIP encontró al menos una solución |
| `nodos_promedio`, `nodos_desviacion_estandar` | réplicas sin error ni interrupción |

Cada estadística trae su `n_*` en el CSV.

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
- La columna `tiempo_total_seg` incluye unos milisegundos de Python fuera de SCIP;
  para comparar con el límite usar `tiempo_scip_seg`.

# Student–Course Reassignment

Repositorio reproducible para un modelo exacto de reasignación de estudiantes
con restricciones sociales, de capacidad, composición y balance educativo.
Todos los datos versionados son **sintéticos**.

## Estado del proyecto

| Componente | Estado verificable |
|---|---|
| Formulación MILP ponderada | Implementada en `src/modelo.py` |
| Grilla experimental | 480 instancias y 480 testigos disponibles |
| Validación estructural de la grilla | Disponible, sin resolver el MILP |
| Ejemplo ilustrativo I00C (27 estudiantes) | Completo y reproducible |
| Sensibilidad de los pesos en I00C | 7 escenarios resueltos a optimalidad |
| Ejecutor de una familia (10 réplicas) con logs, estadísticas SCIP y auditoría | Implementado; preflight técnico superado; corrida oficial pendiente |
| Benchmark de 480 instancias a 3600 s | Pendiente; no se publican resultados todavía |

La ausencia de resultados del benchmark es deliberada: las instancias quedan
preparadas para una ejecución posterior en un computador cuya configuración de
hardware y software deberá documentarse.

## Comprobación rápida, sin resolver instancias

Desde la raíz del repositorio:

```powershell
python src\validar_repositorio.py
```

La validación comprueba la grilla completa, la coherencia interna de cada
instancia, la factibilidad de los 480 testigos y la consistencia de los
resultados versionados del ejemplo I00C. **No invoca SCIP ni ejecuta la campaña
computacional.**

## Modelo vigente

La función objetivo implementada es

\[
\min\; \lambda_0\left(|S|-\sum_{i\in S}z_i\right)+\lambda_1T,
\]

donde la primera componente cuenta estudiantes sin al menos una preferencia
satisfecha y `T` representa la máxima dispersión de los perfiles considerados.
Las preferencias son **blandas**: `z_i` no se fija obligatoriamente en uno.

La implementación incluye:

- asignación única y capacidad;
- pares de separación;
- balance de género;
- representación mínima por curso de origen;
- satisfacción blanda de preferencias;
- balance de perfiles académico, socioemocional y de convivencia.

No se ha reemplazado esta formulación por epsilon-constraint, prioridades
lexicográficas ni otra formulación biobjetivo.

## Protocolo experimental definitivo

| Factor | Símbolo documental | Valores |
|---|---:|---|
| Estudiantes por curso | `L` | 9, 18, 27, 36 |
| Preferencias por estudiante | `P` | 3, 5, 7 |
| Cursos de origen y destino | `C` | 4, 5, 6, 7 |
| Réplicas | `i` | 0, ..., 9 |
| Límite por instancia | — | 3600 s |
| Hilos por ejecución | — | 1 |

La grilla contiene

\[
4\times3\times4\times10=480
\]

instancias. Para cada valor de `C` hay 120 archivos; el total de estudiantes de
una instancia es `N=L*C` y varía entre 36 y 252.

### Convención de nombres

```text
c_n_[L]_l_[P]_s_[C]_i_[réplica].txt
```

Por compatibilidad histórica, el nombre del archivo utiliza `n`, `l` y `s`;
en la documentación se presentan como `L`, `P` y `C`, respectivamente. Ejemplo:

```text
c_n_36_l_7_s_4_i_0.txt
```

## Dos experimentos, dos alcances

1. [Sensibilidad computacional](experimentos/sensibilidad_computacional/README.md):
   estudia el efecto de `L`, `P` y `C` sobre el esfuerzo de resolución. Las 480
   instancias están disponibles, pero la campaña definitiva sigue pendiente.
2. [Sensibilidad de los pesos](experimentos/sensibilidad_lambda/README.md):
   utiliza solo `I00C_DRAFT_ILUSTRATIVO_27` y contiene datos, scripts,
   resultados, figura y texto LaTeX.

Los resultados históricos de la antigua grilla de 360 instancias están
claramente aislados en
`experimentos/sensibilidad_computacional/calibracion_15s_grilla_360/` y no son
evidencia del protocolo actual.

## Requisitos e instalación

Windows PowerShell 5.1 o PowerShell 7, Python de 64 bits (verificado con 3.13),
**PySCIPOpt 6.2.1 y SCIP 10.0.2**. La versión de SCIP se comprueba en ejecución;
no basta con que coincida la versión de PySCIPOpt. Desde la raíz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`correr_familia.ps1` prioriza `.venv\Scripts\python.exe`; no hace falta activar
el entorno. Si no existe, busca Python en PATH. El instalador necesita red.

## Validación sin resolver

```powershell
.\.venv\Scripts\python.exe src\validar_repositorio.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La primera orden revisa estructura y testigos, sin optimización. Las pruebas
usan réplicas simuladas para comprobar secuencia, reanudación, interrupciones,
resúmenes y errores; **no resuelven las diez instancias**.

## Preflight, corrida oficial y reanudación

Antes de la campaña completa se valida una familia (acuerdo de la reunión del
8-sep-2026). Ver [docs/prueba_familia.md](docs/prueba_familia.md).
La [auditoría del pipeline y preflight del 16-sep-2026](docs/auditoria_pipeline_familia_2026-09-16.md)
documenta los controles ejecutados, resultados y riesgos pendientes.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\correr_familia.ps1 -L 9 -P 3 -C 4 -Preflight -Tiempo 60 -Replicas 0
```

Resuelve únicamente `c_n_9_l_3_s_4_i_0`. El límite de 60 s corresponde a SCIP;
la validación, construcción y exportación agregan tiempo de pared. Salida:
`corridas\preflight\prueba_familia_L9_P3_C4_T60s_i0\`.

Para iniciar **la familia oficial** después de revisar el preflight:

```powershell
.\correr_familia.ps1 -L 9 -P 3 -C 4 -Tiempo 3600
```

Ejecuta automáticamente **i_0, i_1, …, i_9, en ese orden y de forma secuencial**.
Cada optimalidad o time limit (con o sin incumbente) da paso a la siguiente.
Usa λ₀ = λ₁ = 1, gap objetivo 0, `parallel/maxnthreads=1` y `lp/threads=1`
(soportado y verificado con SCIP 10.0.2). No utiliza testigos como warm start.
El modo oficial exige ambas versiones, los parámetros y las diez réplicas,
incluso cuando se llama directamente al ejecutor Python.

Los pesos de la familia piloto oficial son fijos para **todas las réplicas**:

```text
lambda_0 = 1
lambda_1 = 1
```

El lanzador pasa esos mismos valores al ejecutor y este los comprueba antes de
resolver cada réplica y antes de guardar resultados oficiales. No hay variación
de lambdas ni análisis de sensibilidad en esta corrida. Si se solicitan otros
pesos por Python, se emite una advertencia y el modo es `no_oficial`; si se intenta
forzar el modo oficial internamente, se rechaza antes de construir el modelo.
También se rechaza un resumen oficial que contenga una réplica con pesos distintos.

Para continuar una corrida interrumpida:

```powershell
.\correr_familia.ps1 -L 9 -P 3 -C 4 -Tiempo 3600 -Reanudar
```

Salida oficial: `corridas\prueba_familia_L9_P3_C4_T3600s\`. `-Reanudar` omite
solo réplicas terminadas con artefactos íntegros; vuelve a ejecutar desde cero
las pendientes, fallidas, interrumpidas o con archivos ausentes/modificados.
No continúa el árbol interno de SCIP. Un manifiesto comprueba versiones,
parámetros, hashes de instancias y código. Si cambian o es una corrida antigua
sin manifiesto, rechaza la mezcla: hay que escoger otra `-Salida`.
Si se usó `-Salida`, repetir esa misma ruta al reanudar.

Por réplica guarda log SCIP, estadísticas de texto y JSON, cotas primal/dual,
gap relativo y absoluto, nodos, objetivo, T, suma_z, primera solución factible,
trayectoria de incumbentes, asignación legible, **todas las variables en `.sol`**
y auditoría independiente en JSON. Sin incumbente deja explícita su ausencia;
no inventa solución ni tiempos de primera factibilidad.

`resultados_familia.csv` se actualiza atómicamente después de cada réplica.
Al terminar se generan `resumen_familia.csv` y `.md`, con media y desviación
estándar, y `resumen_global_familia_L9_P3_C4.txt` (nombre según L, P y C), con
el detalle de las diez réplicas y los conteos y estadísticos finales. Si la
ejecución es parcial, muestra las réplicas sin resultados como pendientes.
El TXT conserva las mismas medias y desviaciones del CSV. La desviación estándar
es **muestral** para `tiempo_scip_seg`, `tiempo_total_seg` y gaps. El tiempo
total abarca lectura, construcción, optimización y exportación por réplica;
el tiempo SCIP incluye presolve. No incluye en ese total la validación global,
captura del entorno ni escritura del CSV conjunto. Se conserva además
`tiempo_optimizacion_pared_seg` para medir solo la llamada `optimize()`.
Con una sola réplica, la desviación estándar queda vacía. Los gaps no finitos
se cuentan por separado y se excluyen de la media correspondiente.

Para revisión en texto se generan además `resumen_familia.txt` (todos los campos
de `resumen_familia.csv`) y `resultados_familia.txt` (todos los campos por réplica
de `resultados_familia.csv`, actualizado junto con el CSV). Ambos provienen de
los mismos datos en memoria, sin recalcular ni cambiar resultados. Una celda
vacía del CSV se representa como `NO DISPONIBLE` en el TXT.
Los dos pesos aparecen explícitos como `lambda_0 = 1` y `lambda_1 = 1` en esos
TXT, en el consolidado global, en `entorno.txt` y en cada TXT individual de
solución. Los CSV y el manifiesto conservan también ambos pesos. Los archivos
históricos no se reescriben automáticamente para aplicar este formato.

Revisar `familia_completa`, `numero_pendientes`, errores y auditorías antes de
usar el resumen: `modo=oficial` identifica el protocolo, no certifica que la
familia haya terminado. Una interrupción devuelve código 130; fallos, auditoría
no aprobada o réplicas pendientes devuelven código 1.

El máximo de 10 h es la suma de límites SCIP; el tiempo real será mayor por
preparación y exportación. Mantener el equipo conectado, sin suspensión ni
cargas intensivas, y ejecutar un solo proceso sobre cada carpeta de salida.
No editar código o instancias entre una corrida y su reanudación. No abrir
el CSV en una aplicación que bloquee su escritura durante la ejecución.

## Ejecución futura del benchmark

Instala las dependencias:

```powershell
python -m pip install -r requirements.txt
```

Luego consulta:

- [protocolo y ejecución reproducible](docs/ejecucion.md);
- [guía paso a paso para Windows](docs/guia_windows.md).

La ejecución completa se inicia con:

```powershell
.\correr.ps1 -Modo todo
```

Este comando se documenta para uso futuro; **no debe lanzarse antes de que los
profesores validen la familia piloto**. `resolver_lote.py` todavía no guarda logs
ni estadísticas de SCIP.

## Estructura

```text
student-course-reassignment/
├── docs/                         # protocolo y guías de uso
├── experimentos/
│   ├── sensibilidad_computacional/
│   └── sensibilidad_lambda/      # paquete reproducible de I00C
├── instancias/                   # 480 entradas del benchmark
├── src/                          # generador, modelo, ejecución y validación
├── testigos/                     # 480 testigos de factibilidad
├── correr.ps1                    # campaña por bloques de C (futuro)
├── correr_familia.ps1            # una familia (L,P,C) = 10 réplicas
├── requirements.txt
└── README.md
```

Las carpetas raíz `corridas/`, `resultados/`, `soluciones/` y `analisis/` se crean solo al
ejecutar el benchmark y se excluyen del control de versiones. Los resultados
pequeños y auditados de I00C sí se conservan dentro de su experimento.

## Reproducibilidad y límites

- Las semillas de la grilla se derivan de sus parámetros y réplica.
- Los testigos se usan únicamente para verificar factibilidad; no se entregan
  al solver como *warm start*.
- Un límite de tiempo con una solución incumbente no implica optimalidad.
- La calibración histórica no debe combinarse con el benchmark vigente.
- Los resultados de I00C ilustran el comportamiento de una instancia sintética;
  no calibran automáticamente los pesos para una aplicación real.

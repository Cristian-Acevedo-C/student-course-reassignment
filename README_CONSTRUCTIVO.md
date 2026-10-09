# Heurística constructiva y warm start para el SCRP

Implementación reproducible de una heurística de dominio para construir soluciones iniciales factibles del problema de reasignación de estudiantes y entregarlas a SCIP/PySCIPOpt como incumbente inicial.

## Principios del experimento

- Se usa `src/modelo.py` vigente sin modificarlo.
- La heurística no lee ni importa testigos.
- Toda solución se valida primero con una auditoría propia y después con el verificador independiente `tools/evaluar_asignacion.py`.
- La solución entregada a SCIP incluye valores consistentes para las 796 variables del caso C=4: `x`, `y`, `w`, `z`, `d+`, `d-`, `F` y `T`.
- En PySCIPOpt 6.2.1 la carga previa al solve se realiza mediante `checkSol(..., original=True)` y `addSol()`. `trySol()` no es invocable durante la etapa de creación del problema.
- Los resultados cortos incluidos son diagnósticos exploratorios; el protocolo oficial sigue usando 3600 segundos, un hilo, gap objetivo 0 y `lambda_0=lambda_1=1`.

## Archivos principales

- `experimento_constructivo/constructivo.py`: construcción greedy, look-ahead, retroceso, reparación y búsqueda local.
- `experimento_constructivo/ejecutar_constructivo.py`: ejecución por familia, TXT/CSV y validación independiente.
- `experimento_constructivo/comparar_warm_start.py`: comparación pareada SCIP default vs warm start.
- `experimento_constructivo/validar_salida.py`: revalidación independiente y registros JSON por solución.
- `experimento_constructivo/generar_resumen.py`: consolida las tablas agregadas y pareadas.
- `experimento_constructivo/comparar_oficial_checkpoint.py`: comparación pareada con construcción medida en el mismo entorno y checkpoints por instancia.
- `experimento_constructivo/benchmark_oficial_nlhpc.slurm`: arreglo de 30 trabajos para NLHPC.
- `experimento_constructivo/consolidar_benchmark.py`: tabla de 30 réplicas con pendientes explícitos.
- `tests/test_constructivo.py`: pruebas de factibilidad, cobertura completa del warm start y ausencia de dependencia de testigos.
- `INFORME_TECNICO_CONSTRUCTIVO.md`: auditoría, algoritmo, resultados y conclusión científica provisional.

## Instalación

Desde la raíz del paquete:

```bash
python -m pip install -r requirements_constructivo.txt
```

La versión validada fue PySCIPOpt 6.2.1 con SCIP 10.0.2.

## Validar el paquete de instancias

```bash
python tools/verificar_paquete.py
```

Debe informar 30 instancias únicas y parseables: 10 de C=4, 10 de C=5 y 10 de C=6.

## Ejecutar el constructivo

Familia piloto C=4:

```bash
python experimento_constructivo/ejecutar_constructivo.py \
  --patron "c_n_9_l_3_s_4_i_*.txt" \
  --salida resultados_constructivo/L9_P3_C4 \
  --intentos 20 \
  --limite-nodos 50000
```

Escalabilidad C=5 y C=6:

```bash
python experimento_constructivo/ejecutar_constructivo.py \
  --patron "c_n_9_l_3_s_5_i_*.txt" \
  --salida resultados_constructivo/L9_P3_C5 \
  --intentos 8 \
  --limite-nodos 80000

python experimento_constructivo/ejecutar_constructivo.py \
  --patron "c_n_9_l_3_s_6_i_*.txt" \
  --salida resultados_constructivo/L9_P3_C6 \
  --intentos 8 \
  --limite-nodos 100000
```

Cada carpeta contiene:

- `resultados_constructivo.csv`;
- `asignaciones_constructivo.csv`;
- un TXT por solución;
- `metadata.json` con comando, entorno y confirmación de no uso de testigos.

## Comparar SCIP y warm start

Diagnóstico con el mismo tiempo de SCIP para ambas condiciones:

```bash
python experimento_constructivo/comparar_warm_start.py \
  --patron "c_n_9_l_3_s_4_i_*.txt" \
  --presupuesto 5 \
  --modo-presupuesto igual_scip \
  --salida resultados_warm_start/L9_P3_C4_diag5s
```

Comparación justa incluyendo el costo de la heurística dentro del presupuesto total:

```bash
python experimento_constructivo/comparar_warm_start.py \
  --patron "c_n_9_l_3_s_4_i_*.txt" \
  --presupuesto 3600 \
  --modo-presupuesto igual_total \
  --salida resultados_warm_start/L9_P3_C4_oficial3600s
```

En modo `igual_total`, el baseline recibe todo el presupuesto y la configuración warm recibe `presupuesto - tiempo_heuristica` para SCIP.

## Pruebas

```bash
python -m unittest -v tests/test_constructivo.py
```

## Tablas consolidadas

```bash
python experimento_constructivo/generar_resumen.py
```

Se generan:

- `resultados_resumen/resumen_agregado.csv`;
- `resultados_resumen/comparacion_pareada_C4_fair12s.csv`.

## Interpretación correcta

Los resultados actuales demuestran que la heurística genera soluciones factibles y que SCIP acepta el warm start. También muestran una ventaja primal temprana en presupuestos cortos. No demuestran todavía una reducción del tiempo oficial de 3600 segundos ni una mejora de la prueba de optimalidad.

El 8 de octubre se completó una primera réplica pareada oficial (C=4, i=8): ambos métodos probaron el óptimo 5, con 137,83 s de SCIP base y 176,19 s de pipeline con warm start. Para el resto de las 29 réplicas, seguir `PROTOCOLO_BENCHMARK_OFICIAL.md`. El Excel de resultados disponible conserva vacíos los campos oficiales pendientes.

# Comparación oficial: SCIP base frente a SCIP + warm start

El constructivo y la búsqueda local están implementados en `experimento_constructivo/constructivo.py`. El modelo vigente permanece en `src_referencia/modelo.py` sin cambios. El script `comparar_oficial_checkpoint.py` vuelve a ejecutar el constructivo en la máquina de la prueba, valida la asignación y corre un par por instancia con la misma semilla SCIP.

## Presupuesto y alcance

- Familias incluidas en este paquete: L=9, P=3, C∈{4,5,6}, diez réplicas por familia.
- Para cada condición se presupuestan 3600 s de **tiempo SCIP + construcción**. SCIP base recibe 3600 s; la condición warm recibe `3600 − tiempo_constructivo` segundos de SCIP. Un hilo, gap objetivo cero y λ₀=λ₁=1.
- El armado del modelo y la serialización se registran indirectamente en el tiempo de pared, pero no están incluidos en ese presupuesto. Por ello la columna `tiempo_pipeline_s` se define como tiempo de SCIP más tiempo del constructivo, no tiempo total del proceso Python.
- Las dos condiciones se ejecutan secuencialmente en el mismo nodo y con semilla `seed_scip + réplica`. Las réplicas son unidades experimentales independientes; no comparar tiempos de entornos o cargas diferentes sin advertirlo.
- Cada par completo se guarda atómicamente en `pares/<instancia>.json`. Reejecutar el mismo comando conserva los pares completos y continúa lo pendiente; cambiar parámetros o código requiere otra carpeta.

## Una réplica local

Desde la raíz del paquete, con PySCIPOpt 6.2.1 instalado:

```bash
python experimento_constructivo/comparar_oficial_checkpoint.py \
  --patron 'c_n_9_l_3_s_4_i_8.txt' \
  --salida resultados_warm_start/oficial_3600s/C4_i8 \
  --presupuesto 3600 --intentos 20 --limite-nodos 50000
```

El resultado se escribe en el JSON del par, `comparacion_warm_start.csv`, `trayectorias.jsonl` y `protocolo.json`.

## Treinta réplicas en NLHPC

Copiar el paquete completo al repositorio de trabajo del clúster; activar el entorno con PySCIPOpt 6.2.1 y SCIP 10.0.2. Desde la raíz:

```bash
mkdir -p logs
sbatch experimento_constructivo/benchmark_oficial_nlhpc.slurm
```

El arreglo Slurm ejecuta 30 trabajos con máximo ocho simultáneos. Cada tarea pide un núcleo, 4 GB y tres horas de ventana para dos solves de hasta una hora. Ajustar partición y memoria según las normas del clúster antes de enviar si fueran diferentes. Los checkpoints se conservan por réplica.

Al terminar, consolidar la tabla y exigir cobertura completa:

```bash
python experimento_constructivo/consolidar_benchmark.py --exigir-completo
```

Si alguna tarea no terminó, el consolidador retorna código 2 y deja su fila marcada `pendiente` en `resultados_resumen/tabla_oficial_3600s.csv`. Volver a enviar los índices faltantes del arreglo. Revisar en cada par la aceptación del warm start, la validación de la solución final, el estado de SCIP, el objetivo, la cota dual, el gap y el tiempo.

## Lectura científica

Una solución factible inicial puede mejorar el objetivo temprano, pero no garantiza menor tiempo para cerrar la cota dual. Reportar separados: objetivo al terminar, tiempo hasta mejor incumbente, primal integral, gap final, cantidad de óptimos probados y tiempo de solución. La búsqueda local certifica solo que no encontró mejoras en las vecindades exploradas. SCIP certifica óptimo global únicamente cuando su estado y brecha lo respaldan.

El archivo `Tabla_resultados_SCRP_2026-10-08.xlsx` refleja las 30 soluciones constructivas y los diagnósticos cortos anteriores a este protocolo; los campos oficiales aparecen vacíos hasta completar las corridas y consolidar sus registros.

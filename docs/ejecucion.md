# Cómo correr el experimento completo

El benchmark se ejecuta en una máquina local o servidor persistente: son hasta
480 × 3600 s de cómputo.

## 1. Requisitos (una sola vez)

```bash
python -m pip install -r requirements.txt
```

## 2. Generar las 480 instancias

Ya vienen generadas en `instancias/`. Si quieres rehacerlas (son idénticas,
la semilla depende solo de los parámetros), el comando reemplaza los archivos
generados de cualquier grilla anterior:

```bash
python src/generar_instancias.py --todas
```

## 3. Resolver

```bash
python src/resolver_lote.py --instancias instancias --tiempo 3600 --hilos 1
```

Esto escribe:

- `resultados/resultados.csv` → nombre de instancia, tiempo y gap (+ columnas de análisis)
- `soluciones/sol_<instancia>.txt` → la solución de cada instancia

**Es reanudable.** Si lo cortas con Ctrl+C, al volver a lanzarlo omite las
instancias ya registradas. Puedes cerrarlo y retomarlo cuantas veces quieras.

### Correr por partes (recomendado)

Empieza por lo barato para tener datos rápido:

```bash
python src/resolver_lote.py --patron "c_n_*_s_4_*.txt" --tiempo 3600   # 160 instancias
python src/resolver_lote.py --patron "c_n_*_s_5_*.txt" --tiempo 3600   # 160 instancias
python src/resolver_lote.py --patron "c_n_*_s_6_*.txt" --tiempo 3600   # 160 instancias
```

### Ejecución paralela exploratoria

Si el objetivo es obtener soluciones con mayor rapidez, se puede lanzar una
terminal por familia con salidas separadas y después concatenar los CSV:

```bash
python src/resolver_lote.py --patron "c_n_9_*"  --salida res_n9  --soluciones soluciones &
python src/resolver_lote.py --patron "c_n_18_*" --salida res_n18 --soluciones soluciones &
python src/resolver_lote.py --patron "c_n_36_*" --salida res_n36 --soluciones soluciones &
python src/resolver_lote.py --patron "c_n_72_*" --salida res_n72 --soluciones soluciones &
```

Mantén `--hilos 1` en cada proceso. Sin embargo, los tiempos obtenidos mediante
procesos concurrentes pueden verse afectados por la competencia por CPU y RAM.
Para el benchmark que se reportará en el artículo, ejecuta las instancias de
forma secuencial o en recursos aislados y documenta el hardware utilizado.

## 4. Construir las tablas del reporte

```bash
python src/analizar_resultados.py --resultados resultados/resultados.csv --salida analisis
```

Produce, en el estilo de Pérez-Galarce et al. (2014):

| Archivo | Contenido |
|---|---|
| `tabla1_optimalidad.txt` | instancias resueltas a optimalidad por celda (n,l,s) |
| `tabla2_tiempos.txt` | Min / Prom / Mediana / Máx del tiempo, sobre las que cerraron |
| `tabla3_gaps.txt` | gap promedio y máximo de las que llegaron al límite |
| `efecto_marginal.txt` | efecto aislado de l, de s y de n — la pregunta del experimento |
| `perfil_desempeno.csv` | perfil de desempeño (% acumulado vs. tiempo) |

## Estimación de tiempo

La calibración de 15 segundos disponible corresponde a la grilla anterior de
360 instancias y no debe extrapolarse al protocolo final. Antes del benchmark
se recomienda calibrar una réplica por cada una de las 48 configuraciones.

La cota máxima teórica es de **480 horas de cómputo secuencial** si todas las
instancias agotan el límite de 3600 segundos. El tiempo real solo podrá
estimarse con rigor después de la nueva calibración.

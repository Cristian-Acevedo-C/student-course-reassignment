# Cómo correr el experimento completo

Todo esto se corre **en tu máquina**, no en la sesión de Claude: son hasta
360 × 3600 s de cómputo y la sesión es efímera.

## 1. Requisitos (una sola vez)

```bash
pip install pyscipopt
```

## 2. Generar las 360 instancias

Ya vienen generadas en `instancias/`. Si quieres rehacerlas (son idénticas,
la semilla depende solo de los parámetros):

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
python src/resolver_lote.py --patron "c_n_*_s_2_*.txt" --tiempo 3600   # 120 inst, rápidas
python src/resolver_lote.py --patron "c_n_*_s_3_*.txt" --tiempo 3600   # 120 inst, duras
python src/resolver_lote.py --patron "c_n_*_s_4_*.txt" --tiempo 3600   # 120 inst, muy duras
```

### Correr en paralelo

Si tienes varios núcleos, lanza una terminal por familia con salidas
separadas y después concatena los CSV:

```bash
python src/resolver_lote.py --patron "c_n_9_*"  --salida res_n9  --soluciones soluciones &
python src/resolver_lote.py --patron "c_n_18_*" --salida res_n18 --soluciones soluciones &
python src/resolver_lote.py --patron "c_n_27_*" --salida res_n27 --soluciones soluciones &
python src/resolver_lote.py --patron "c_n_36_*" --salida res_n36 --soluciones soluciones &
```

Deja `--hilos 1` en cada uno: el protocolo pide un hilo por instancia, y así
los tiempos son comparables entre sí.

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

De la calibración a 15 s (36 celdas, réplica 0):

- `s=2` → 12 de 12 cerraron, la más lenta en 13 s
- `s=3` → 2 de 12 cerraron
- `s=4` → 0 de 12 cerraron

Si esa proporción se mantiene, las 120 instancias con `s=2` se resuelven en
minutos, y buena parte de las 240 con `s=3` y `s=4` consumirán los 3600 s
completos. Cota superior realista: **200-240 horas de cómputo secuencial**.
Repartido en 4 procesos paralelos, del orden de 2-3 días.

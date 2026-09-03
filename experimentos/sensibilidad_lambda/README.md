# Sensibilidad de los pesos en I00C

Paquete reproducible del análisis de sensibilidad de la función objetivo sobre
la instancia sintética `I00C_DRAFT_ILUSTRATIVO_27`. Este experimento resuelve
solo siete escenarios pequeños; no recorre las 480 instancias del benchmark.

## Contenido

```text
sensibilidad_lambda/
├── instancia/I00C_DRAFT_ILUSTRATIVO_27/  # datos y solución de referencia
├── scripts/                              # resolución y figura
├── resultados/                           # CSV, JSON y asignaciones
├── figuras/                              # PDF vectorial y vista PNG
├── latex/                                # texto y tabla para el manuscrito
├── analisis_sensibilidad_lambda.md       # lectura académica de resultados
└── README.md
```

## Diseño

Se mantiene la formulación ponderada vigente:

\[
\min\;\lambda_0\left(|S|-\sum_i z_i\right)+\lambda_1T.
\]

Los pesos evaluados son:

```text
(0.10,1.00), (0.25,1.00), (0.50,1.00), (1.00,1.00),
(1.00,0.50), (1.00,0.25), (1.00,0.10)
```

Todos son positivos, cubren razones `lambda_0/lambda_1` entre 0.1 y 10 e
incluyen el caso base `(1,1)` del draft. No se utiliza epsilon-constraint,
optimización lexicográfica ni una formulación biobjetivo diferente.

## Resultado resumido

Los siete escenarios terminaron con estado óptimo y brecha cero. Entre los
pesos evaluados aparecen tres pares de componentes:

| Estudiantes satisfechos | `U` no satisfechos | `T` |
|---:|---:|---:|
| 24/27 | 3 | 8/3 |
| 26/27 | 1 | 14/3 |
| 27/27 | 0 | 20/3 |

La tabla completa y la interpretación están en
[`analisis_sensibilidad_lambda.md`](analisis_sensibilidad_lambda.md).

## Reproducción

Desde la raíz del repositorio:

```powershell
python -m pip install -r requirements.txt
python experimentos\sensibilidad_lambda\scripts\run_lambda_sensitivity_i00c.py
python experimentos\sensibilidad_lambda\scripts\make_i00c_flow_figure.py
python src\validar_repositorio.py
```

El primer script exige optimalidad, reconstruye las métricas desde la
asignación y regenera los CSV, JSON y la tabla LaTeX. El segundo reconstruye la
figura PDF desde `reference_solution.csv`. La imagen PNG se conserva como vista
previa para GitHub.

En el escenario base existen óptimos múltiples. Para mantener el ejemplo del
draft, el reporte usa `reference_solution.csv` solo después de comprobar que es
factible y que alcanza el mismo valor óptimo certificado por SCIP. El JSON
conserva además la asignación bruta devuelta por el solver. Esto es una regla de
presentación; no agrega una segunda función objetivo ni cambia el MILP.

La ejecución documentada utilizó PySCIPOpt 6.2.1 con SCIP 10.0.2, un hilo,
brecha objetivo cero y 120 segundos como límite por escenario.

## Incorporación al manuscrito

- Copiar `figuras/fig_i00c_flujos_origen_destino.pdf` a la carpeta `figuras/`
  del proyecto LaTeX.
- Copiar `latex/tabla_sensibilidad_lambda_i00c.tex` a `tablas/`.
- Incorporar el contenido de
  `latex/DRAFT_UPDATE_I00C_LAMBDA_SENSITIVITY.tex` en el draft.

Las rutas de `\includegraphics` y `\input` del bloque están escritas para esa
estructura del manuscrito.

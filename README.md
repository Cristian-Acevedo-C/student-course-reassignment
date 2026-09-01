# Student Course Reassignment

Implementación reproducible del modelo MILP exacto para reasignar estudiantes
entre cursos, considerando restricciones educativas y sociales. El repositorio
reúne el generador de instancias, el modelo, el protocolo de ejecución, las
auditorías de factibilidad y los materiales de dos análisis de sensibilidad.

## Estado actual

| Componente | Estado | Evidencia disponible |
|---|---|---|
| Grilla experimental | Completa | 360 instancias en `instancias/` |
| Factibilidad por construcción | Verificada | 360 testigos en `testigos/` |
| Calibración exploratoria | Completa | 36 corridas con límite de 15 s |
| Benchmark definitivo | Pendiente | Debe ejecutarse con 3600 s e hilo único |
| Sensibilidad de pesos \(\lambda\) | Documentada | Sección de análisis para el manuscrito |

La calibración de 15 segundos **no constituye el resultado final**. El
protocolo vigente exige un límite de **3600 segundos por instancia**.

## Preguntas experimentales

El repositorio separa dos estudios complementarios:

1. **Sensibilidad computacional:** compara el efecto del tamaño del curso
   (`n`), la cantidad de preferencias (`l`) y el número de cursos (`s`) sobre
   tiempo, gap, nodos y tamaño del modelo.
2. **Sensibilidad de los pesos:** estudia el compromiso entre estudiantes sin
   una preferencia satisfecha y dispersión de perfiles al variar
   \(\lambda_0\) y \(\lambda_1\).

## Diseño del benchmark

| Parámetro | Valores | Interpretación |
|---|---|---|
| `n` | 9, 18, 27, 36 | estudiantes por curso destino |
| `l` | 3, 5, 7 | preferencias por estudiante |
| `s` | 2, 3, 4 | cursos de origen y destino |
| `i` | 0, …, 9 | réplica independiente |

La grilla contiene

$$
4\times 3\times 3\times 10=360
$$

instancias, con poblaciones totales entre 18 y 144 estudiantes. El nombre
`c_n_[N]_l_[L]_s_[S]_i_[I].txt` codifica todos los factores.

## Estructura

```text
.
├── README.md
├── requirements.txt
├── correr.ps1
├── src/                              # generación, modelo, resolución y análisis
├── instancias/                       # 360 entradas del benchmark
├── testigos/                         # factibilidad; nunca se usan como warm start
├── experimentos/
│   ├── sensibilidad_computacional/
│   │   └── calibracion_15s/          # referencia exploratoria, no resultado final
│   └── sensibilidad_lambda/          # análisis de pesos para el manuscrito
└── docs/
    ├── ejecucion.md                  # protocolo y comandos
    └── guia_windows.md               # instrucciones detalladas para PowerShell
```

Las carpetas `resultados/`, `soluciones/` y `analisis/` se generan durante la
ejecución. Las soluciones individuales se ignoran por defecto; el CSV agregado
y las tablas finales quedan visibles para incorporarlos al repositorio una vez
completado y auditado el protocolo definitivo.

## Inicio rápido

### 1. Preparar el entorno

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

En PowerShell, activa primero el entorno con:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Ejecutar una prueba corta

```powershell
.\correr.ps1 -Modo prueba
```

La prueba resuelve nueve instancias pequeñas con un límite de 30 segundos y
genera tablas de control. No reemplaza el benchmark definitivo.

### 3. Ejecutar el protocolo final

```powershell
.\correr.ps1 -Modo s2 -Tiempo 3600
.\correr.ps1 -Modo s3 -Tiempo 3600
.\correr.ps1 -Modo s4 -Tiempo 3600
```

También puede ejecutarse directamente desde Python:

```bash
python src/resolver_lote.py \
  --instancias instancias \
  --tiempo 3600 \
  --hilos 1 \
  --lambda-0 1 \
  --lambda-1 1
```

El proceso es reanudable. Una instancia solo se omite si su resultado previo
es compatible con el límite, los pesos, el número de hilos y el gap objetivo
de la nueva corrida.

## Protocolo vigente

- Solver: SCIP 10.0.2 mediante PySCIPOpt 6.2.1.
- Límite: 3600 segundos por instancia.
- Paralelismo interno: 1 hilo por instancia.
- Gap objetivo: 0.
- Pesos del benchmark: \(\lambda_0=\lambda_1=1\).
- Testigos factibles: solo auditoría; no se entregan al solver.
- Semilla de generación:

```text
(n·1000003 + l·10007 + s·101 + i·7) mod 1000000
```

Para reportar resultados finales también deben registrarse el procesador, la
memoria RAM, el sistema operativo y las versiones de Python, PySCIPOpt y SCIP.
La versión actual fue validada con Python 3.12.13, PySCIPOpt 6.2.1 y SCIP
10.0.2.

## Salidas

`resultados/resultados.csv` registra estado, tiempo, gap, objetivo, cota dual,
satisfacción social, dispersión, nodos, variables, restricciones y parámetros
del protocolo. Cada asignación se guarda en
`soluciones/sol_<instancia>.txt`.

Las tablas se generan con:

```bash
python src/analizar_resultados.py \
  --resultados resultados/resultados.csv \
  --salida analisis \
  --limite 3600
```

## Generación y auditoría

Las instancias son factibles por construcción. Cada una se genera alrededor de
una asignación testigo que satisface capacidad, separaciones, balance de género
y representación por curso de origen. Las preferencias se sortean sin
auto-nominaciones ni duplicados, y las separaciones se crean entre estudiantes
que el testigo ubica en cursos distintos.

Para reproducir la grilla completa:

```bash
python src/generar_instancias.py --todas
```

Para auditar una instancia sin instalar el solver:

```bash
python src/auditar_instancia.py \
  --instancia instancias/c_n_9_l_3_s_2_i_0.txt \
  --testigo testigos/testigo_c_n_9_l_3_s_2_i_0.txt
```

## Documentación

- [Ejecución del experimento](docs/ejecucion.md)
- [Guía paso a paso para Windows](docs/guia_windows.md)
- [Sensibilidad computacional](experimentos/sensibilidad_computacional/README.md)
- [Sensibilidad de los pesos](experimentos/sensibilidad_lambda/README.md)

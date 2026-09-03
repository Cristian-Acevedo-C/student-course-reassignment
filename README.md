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

Este comando se documenta para uso futuro; no es necesario ejecutarlo para
revisar el repositorio o incorporar el ejemplo al manuscrito.

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
├── correr.ps1
├── requirements.txt
└── README.md
```

Las carpetas raíz `resultados/`, `soluciones/` y `analisis/` se crean solo al
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

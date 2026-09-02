# Student–Course Reassignment

Repositorio reproducible para el modelo exacto de reasignación de estudiantes con restricciones sociales y educativas.

## Protocolo experimental definitivo

El experimento computacional considera:

| Factor | Valores |
|---|---|
| Estudiantes por curso \(L\) | 9, 18, 27, 36 |
| Preferencias por estudiante \(P\) | 3, 5, 7 |
| Número de cursos \(C\) | 4, 5, 6, 7 |
| Réplicas | 10 por combinación |
| Límite exacto | 3600 s por instancia |
| Hilos | 1 |

Por tanto:

\[
4 \times 3 \times 4 \times 10 = \mathbf{480}
\]

instancias.

Cada combinación \((L,P,C)\) tiene 10 réplicas independientes, con identificadores \(i=0,\ldots,9\).

### Familias por número de cursos

Cada valor de \(C\) contiene:

\[
4 \times 3 \times 10 = 120
\]

instancias:

- `s4`: 120
- `s5`: 120
- `s6`: 120
- `s7`: 120

Total: **480**.

## Convención de nombres

```text
c_n_[L]_l_[P]_s_[C]_i_[i].txt
```

Ejemplo:

```text
c_n_36_l_7_s_4_i_0.txt
```

## Generación

Para regenerar exactamente la grilla:

```powershell
python src\generar_instancias.py --todas
```

El modo `--todas` elimina primero las instancias/testigos generados por la grilla anterior y crea nuevamente las 480 instancias de la grilla vigente.

Una instancia individual:

```powershell
python src\generar_instancias.py --caso 36 7 4 0
```

## Ejecución exacta

Cada instancia se resuelve con un límite de **3600 segundos** y un hilo:

```powershell
python src\resolver_lote.py --instancias instancias --tiempo 3600 --hilos 1
```

También se puede ejecutar por familia:

```powershell
.\correr.ps1 -Modo s4
.\correr.ps1 -Modo s5
.\correr.ps1 -Modo s6
.\correr.ps1 -Modo s7
```

o todo el experimento:

```powershell
.\correr.ps1 -Modo todo
```

## Resultados

Para cada instancia se registra como mínimo:

- nombre de la instancia;
- tiempo de resolución;
- gap de optimalidad.

Además, el registro contiene las métricas necesarias para el análisis:

- estado;
- objetivo;
- mejor cota;
- número de nodos;
- variables y restricciones;
- componente social;
- \(T\).

Las soluciones se almacenan separadamente como:

```text
soluciones/sol_<nombre_de_instancia>.txt
```

## Pregunta experimental

El análisis busca determinar qué características de la instancia aumentan principalmente la dificultad computacional del modelo exacto:

1. tamaño de cada curso \(L\);
2. densidad de preferencias \(P\);
3. número de cursos \(C\).

Se reportará:

- número y porcentaje de instancias resueltas a optimalidad;
- tiempos de resolución;
- gaps de las instancias que alcanzan el límite;
- comportamiento por familia;
- relación entre tamaño del modelo y esfuerzo de búsqueda.

## Sensibilidad de los pesos \(\lambda\)

La sensibilidad de los pesos de la función objetivo se mantiene separada del benchmark de las 480 instancias.

La grilla principal es:

| \(\lambda_0\) | \(\lambda_1\) |
|---:|---:|
| 0,00 | 1,00 |
| 0,25 | 0,75 |
| 0,50 | 0,50 |
| 0,75 | 0,25 |
| 1,00 | 0,00 |

con:

\[
\lambda_0+\lambda_1=1.
\]

Esta sensibilidad se utiliza para estudiar el compromiso entre satisfacción de preferencias y balance educativo en el ejemplo ilustrativo.

## Reproducibilidad

La instancia contiene todos sus datos de entrada. La semilla se deriva determinísticamente de \(L,P,C,i\), de modo que la misma combinación reproduce la misma instancia.

Los testigos factibles se almacenan en `testigos/` únicamente para auditar el generador. No se utilizan como warm start durante el benchmark exacto.

## Estructura

```text
student-course-reassignment/
├── instancias/
├── testigos/
├── src/
│   ├── generar_instancias.py
│   ├── modelo.py
│   ├── resolver_lote.py
│   ├── auditar_instancia.py
│   └── analizar_resultados.py
├── resultados/
├── soluciones/
├── analisis/
├── calibracion_15s_referencia/
├── COMO_CORRER.md
├── PASO_A_PASO.md
├── correr.ps1
└── README.md
```

La carpeta `calibracion_15s_referencia/` corresponde a una etapa exploratoria anterior y no forma parte del benchmark definitivo de 3600 s.
# Studentâ€“Course Reassignment

Repositorio reproducible para el modelo exacto de reasignaciÃ³n de estudiantes con restricciones sociales y educativas.

## Protocolo experimental definitivo

El experimento computacional considera:

| Factor | Valores |
|---|---|
| Estudiantes por curso \(L\) | 9, 18, 27, 36 |
| Preferencias por estudiante \(P\) | 3, 5, 7 |
| NÃºmero de cursos \(C\) | 4, 5, 6, 7 |
| RÃ©plicas | 10 por combinaciÃ³n |
| LÃ­mite exacto | 3600 s por instancia |
| Hilos | 1 |

Por tanto:

\[
4 \times 3 \times 4 \times 10 = \mathbf{480}
\]

instancias.

Cada combinaciÃ³n \((L,P,C)\) tiene 10 rÃ©plicas independientes, con identificadores \(i=0,\ldots,9\).

### Familias por nÃºmero de cursos

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

## ConvenciÃ³n de nombres

```text
c_n_[L]_l_[P]_s_[C]_i_[i].txt
```

Ejemplo:

```text
c_n_36_l_7_s_4_i_0.txt
```

## GeneraciÃ³n

Para regenerar exactamente la grilla:

```powershell
python src\generar_instancias.py --todas
```

El modo `--todas` elimina primero las instancias/testigos generados por la grilla anterior y crea nuevamente las 480 instancias de la grilla vigente.

Una instancia individual:

```powershell
python src\generar_instancias.py --caso 36 7 4 0
```

## EjecuciÃ³n exacta

Cada instancia se resuelve con un lÃ­mite de **3600 segundos** y un hilo:

```powershell
python src\resolver_lote.py --instancias instancias --tiempo 3600 --hilos 1
```

TambiÃ©n se puede ejecutar por familia:

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

Para cada instancia se registra como mÃ­nimo:

- nombre de la instancia;
- tiempo de resoluciÃ³n;
- gap de optimalidad.

AdemÃ¡s, el registro contiene las mÃ©tricas necesarias para el anÃ¡lisis:

- estado;
- objetivo;
- mejor cota;
- nÃºmero de nodos;
- variables y restricciones;
- componente social;
- \(T\).

Las soluciones se almacenan separadamente como:

```text
soluciones/sol_<nombre_de_instancia>.txt
```

## Pregunta experimental

El anÃ¡lisis busca determinar quÃ© caracterÃ­sticas de la instancia aumentan principalmente la dificultad computacional del modelo exacto:

1. tamaÃ±o de cada curso \(L\);
2. densidad de preferencias \(P\);
3. nÃºmero de cursos \(C\).

Se reportarÃ¡:

- nÃºmero y porcentaje de instancias resueltas a optimalidad;
- tiempos de resoluciÃ³n;
- gaps de las instancias que alcanzan el lÃ­mite;
- comportamiento por familia;
- relaciÃ³n entre tamaÃ±o del modelo y esfuerzo de bÃºsqueda.

## Sensibilidad de los pesos \(\lambda\)

La sensibilidad de los pesos de la funciÃ³n objetivo se mantiene separada del benchmark de las 480 instancias.

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

Esta sensibilidad se utiliza para estudiar el compromiso entre satisfacciÃ³n de preferencias y balance educativo en el ejemplo ilustrativo.

## Reproducibilidad

La instancia contiene todos sus datos de entrada. La semilla se deriva determinÃ­sticamente de \(L,P,C,i\), de modo que la misma combinaciÃ³n reproduce la misma instancia.

Los testigos factibles se almacenan en `testigos/` Ãºnicamente para auditar el generador. No se utilizan como warm start durante el benchmark exacto.

## Estructura

```text
student-course-reassignment/
â”œâ”€â”€ instancias/
â”œâ”€â”€ testigos/
â”œâ”€â”€ src/
â”‚   â”œâ”€â”€ generar_instancias.py
â”‚   â”œâ”€â”€ modelo.py
â”‚   â”œâ”€â”€ resolver_lote.py
â”‚   â”œâ”€â”€ auditar_instancia.py
â”‚   â””â”€â”€ analizar_resultados.py
â”œâ”€â”€ resultados/
â”œâ”€â”€ soluciones/
â”œâ”€â”€ analisis/
â”œâ”€â”€ calibracion_15s_referencia/
â”œâ”€â”€ COMO_CORRER.md
â”œâ”€â”€ PASO_A_PASO.md
â”œâ”€â”€ correr.ps1
â””â”€â”€ README.md
```

La carpeta `calibracion_15s_referencia/` corresponde a una etapa exploratoria anterior y no forma parte del benchmark definitivo de 3600 s.
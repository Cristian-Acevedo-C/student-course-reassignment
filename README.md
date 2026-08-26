# Experimento de sensibilidad — densidad de preferencias vs. fragmentación de cursos

Objetivo: someter el modelo exacto a escenarios de estrés para identificar qué
factor incrementa más el tiempo de cómputo — el aumento de la **densidad de la
red de preferencias** (`l`) o la **fragmentación de la demanda** (`s`).

## Grilla experimental (360 instancias)

| Parámetro | Valores | Significado |
|---|---|---|
| `n` | 9, 18, 27, 36 | alumnos por curso |
| `l` | 3, 5, 7 | preferencias declaradas por alumno |
| `s` | 2, 3, 4 | cantidad de cursos |
| `i` | 0 … 9 | réplica independiente |

4 × 3 × 3 × 10 = **360 instancias**. Población total = `n × s`, entre 18 y 144
alumnos. Nombre de archivo: `c_n_[N]_l_[L]_s_[S]_i_[I].txt`.

> **Nota:** el documento de diseño interno indicaba `n∈{9,18,36,72}`,
> `l∈{4,5,6,7}`, `s∈{4,5,6}`, lo que da 480 instancias y no 360. Aquí se usa la
> grilla del investigador jefe, que es la que cuadra con las 360.

## Archivos

```
src/generar_instancias.py    genera una instancia o las 360
src/modelo.py                lee el .txt y construye el MILP
src/resolver_lote.py         resuelve en lote y deja el registro
src/auditar_instancia.py     verifica coherencia y factibilidad
instancias/                  las instancias .txt
testigos/                    testigo factible de cada instancia (solo auditoría)
resultados/resultados.csv    nombre de instancia, tiempo y gap
soluciones/sol_<nombre>.txt  la solución entregada por el solver
```

## Uso

```bash
# una instancia
python src/generar_instancias.py --caso 36 7 4 0

# las 360
python src/generar_instancias.py --todas

# resolver, 3600 s por instancia, 1 hilo
python src/resolver_lote.py --instancias instancias --tiempo 3600 --hilos 1

# resolver solo una familia
python src/resolver_lote.py --patron "c_n_36_*"
```

`resolver_lote.py` es **reanudable**: si se interrumpe, al volver a lanzarlo
omite las instancias ya registradas en `resultados.csv`. Con `--rehacer` las
reprocesa.

## Registro de resultados

`resultados/resultados.csv` incluye lo que pidió el investigador jefe —
**nombre de la instancia, tiempo y gap** — más las columnas necesarias para el
análisis de sensibilidad:

| Columna | Contenido |
|---|---|
| `instancia` | nombre completo del archivo |
| `n`, `l`, `s`, `i`, `N` | parámetros, extraídos del nombre |
| `estado` | `optimal`, `timelimit`, `infeasible`, … |
| `tiempo_seg` | tiempo de resolución |
| `gap` | 0 = óptimo demostrado; > 0 = cortado por tiempo |
| `objetivo`, `cota_dual` | valor incumbente y cota inferior |
| `suma_z`, `no_satisfechos` | componente social de la función objetivo |
| `T` | dispersión máxima de perfiles |
| `nodos`, `variables`, `restricciones` | tamaño del árbol y del modelo |

La distinción entre `gap = 0` y `gap > 0` es el corazón del experimento: dice
si la instancia se cerró o si se agotaron los 3600 s. Las columnas `nodos` y
`variables` permiten separar «el modelo creció» de «el árbol de búsqueda
explotó», que es justamente lo que distingue el efecto de `l` del de `s`.

Cada solución se escribe aparte en `soluciones/sol_<nombre>.txt`, con la
asignación alumno → curso y un resumen por curso.

## Cómo se construyen las instancias

Cada instancia se arma alrededor de una **asignación testigo** que cumple todas
las restricciones duras, de modo que la instancia es factible por construcción:

1. Se crean `n × s` alumnos, repartidos en `s` cursos de origen.
   El género queda balanceado ~50/50 dentro de cada curso de origen.
2. Los tres criterios de perfil (académico, socioemocional, convivencia) se
   sortean **de forma independiente**, para no introducir correlaciones ni
   simetrías que contaminen la medición de tiempo.
3. Se construye el testigo con un puntero rotatorio continuo sobre los grupos
   (origen, género). Como `N = n·s` es divisible por `s`, la capacidad queda
   exacta para cualquier `n`, par o impar. El equilibrio de género y de origen
   se afina con intercambios entre cursos, que preservan el tamaño de cada uno.
4. Las **preferencias** se sortean uniformemente entre todos los demás alumnos,
   sin repeticiones y sin auto-nominación, `l` por alumno.
5. Las **separaciones** (≈ `N/4` pares) se sortean **siempre entre alumnos que
   el testigo deja en cursos distintos**. Esto es lo que garantiza que la
   instancia sea factible.

El testigo se guarda en `testigos/` **solo para auditoría**. No debe pasarse
como warm start al solver: eso invalidaría la medición de tiempo.

### Parámetros derivados

- Capacidad de cada curso destino: `U_c = n` (exacta, sin holgura).
- Mínimo por curso de origen: `α_o = ⌊n/s⌋ − 1` (reparto proporcional relajado
  en una unidad, misma convención que el ejemplo ilustrativo del manuscrito).
- Diferencia máxima de género: `Δ_g = 1`.
- Pesos de la función objetivo: `λ₀ = λ₁ = 1`, definidos en el runner y no en
  la instancia (`--lambda-0`, `--lambda-1`).

### Reproducibilidad

La semilla de cada instancia se deriva de sus parámetros:

```
semilla = (n·1000003 + l·10007 + s·101 + i·7) mod 1000000
```

Volver a correr el generador con los mismos parámetros reproduce exactamente
el mismo archivo.

## Verificación

`auditar_instancia.py` revisa dos cosas: que el archivo sea coherente
(cantidad de preferencias por alumno, sin auto-nominaciones ni repetidos,
capacidades que suman `N`, separaciones sin duplicados) y que el testigo
cumpla capacidad, separaciones, balance de género y representación por origen.

Las 36 combinaciones (n, l, s) fueron auditadas: **0 violaciones**.

# 3.4.6. Análisis de sensibilidad de los pesos de la función objetivo

*(Sección lista para incorporar al draft, a continuación de 3.4.5.)*

---

Los resultados de la Sección 3.4.5 corresponden a una elección particular de
pesos, λ₀ = λ₁ = 1. Esta sección examina cómo cambia la solución óptima cuando
esa elección varía. Para que los pesos sean comparables entre sí se adopta la
normalización

$$\lambda_0 + \lambda_1 = 1,$$

que no altera el conjunto de soluciones óptimas de (6) —solo reescala el valor
objetivo— y permite leer λ₀ directamente como la fracción de importancia
asignada a la componente social. Bajo esta normalización λ₁ no es un parámetro
libre: queda determinado como λ₁ = 1 − λ₀, de modo que el análisis recorre un
solo grado de libertad, λ₀ ∈ [0, 1]. Bajo esta normalización, la elección empleada
en 3.4.5 equivale a λ₀ = λ₁ = 1/2.

Se denota

$$F_1 = |S| - \sum_{i \in S} z_i, \qquad F_2 = T,$$

de modo que (6) se escribe min λ₀F₁ + λ₁F₂. Siguiendo la nota al pie de la
Sección 3.4.4, ambas magnitudes se reconstruyen a partir de los conteos
derivados de xᵢc y no de las variables auxiliares: cuando λ₁ = 0 la variable T
desaparece de la función objetivo y deja de estar acotada superiormente, por lo
que su valor en la solución devuelta por el solver no es informativo.

## Método

El análisis se apoya en la **frontera de compromiso** entre ambas componentes.
Para cada valor factible de F₁ se resolvió el problema auxiliar de minimizar T
sujeto a las restricciones (7)–(22) y a |S| − Σzᵢ = F₁. Los pares (F₁, T)
resultantes que no son dominados por ningún otro constituyen el conjunto de
soluciones eficientes; dado que la función objetivo es una combinación lineal de
F₁ y F₂ con pesos no negativos, toda solución óptima de (6) para algún λ es uno
de esos puntos.

Para cada valor de λ se resolvió (6) y, a continuación, se determinaron el
mínimo y el máximo de F₁ entre las soluciones que alcanzan el valor objetivo
óptimo. Cuando ambos difieren, existen soluciones óptimas alternativas
estructuralmente distintas y así se reporta. La solución que se exhibe en cada
fila se selecciona con una regla lexicográfica fija —F₁ mínimo, luego T mínimo,
luego un desempate canónico determinístico— de modo que la tabla es reproducible
y no depende de decisiones internas del solver.

Por último, como los tres cursos destino son intercambiables, cada solución
representa una clase de seis asignaciones equivalentes que difieren solo en el
etiquetado. Todas las comparaciones entre filas se hacen módulo ese renombre.

## Resultados

La frontera de compromiso contiene **tres** puntos eficientes:

$$(F_1, F_2) \in \{(3,\ 8/3),\ (1,\ 14/3),\ (0,\ 20/3)\}.$$

Los pares (2, 14/3) y (4, 8/3) son factibles pero dominados. El punto (3, 8/3)
alcanza el piso aritmético T ≥ 8/3 establecido en la Sección 3.4.4; el punto
(0, 20/3) satisface a los veintisiete estudiantes.

**Tabla 4.** Análisis de sensibilidad de los pesos sobre la grilla
λ₀ ∈ {0; 0,25; 0,50; 0,75; 1}, con λ₁ = 1 − λ₀. Los identificadores se muestran
sin el prefijo SYN-. La fila λ₀ = 0,50 no admite una entrada única: en ese punto
dos asignaciones estructuralmente distintas alcanzan el mismo valor objetivo
Z = 17/6.

| λ₀ | λ₁ | Preferencias no satisfechas $F_1$ | Dispersión $F_2 = T$ | Asignación |
|---|---|---|---|---|
| 0,00 | 1,00 | 3 | 8/3 | $C_1$ = {8, 9, 13, 18, 19, 20, 25, 26, 27}<br>$C_2$ = {1, 6, 7, 14, 15, 16, 17, 21, 24}<br>$C_3$ = {2, 3, 4, 5, 10, 11, 12, 22, 23} |
| 0,25 | 0,75 | 3 | 8/3 | $C_1$ = {8, 9, 13, 18, 19, 20, 25, 26, 27}<br>$C_2$ = {1, 6, 7, 14, 15, 16, 17, 21, 24}<br>$C_3$ = {2, 3, 4, 5, 10, 11, 12, 22, 23} |
| 0,50 | 0,50 | **3 ó 1** | **8/3 ó 14/3** | **Dos óptimos.** (A) idéntica a la fila anterior.<br>(B) $C_1$ = {2, 3, 4, 12, 15, 24, 25, 26, 27}<br>$C_2$ = {5, 8, 9, 13, 16, 17, 21, 22, 23}<br>$C_3$ = {1, 6, 7, 10, 11, 14, 18, 19, 20} |
| 0,75 | 0,25 | 0 | 20/3 | $C_1$ = {5, 8, 9, 13, 18, 21, 22, 23, 27}<br>$C_2$ = {1, 6, 7, 14, 15, 16, 24, 25, 26}<br>$C_3$ = {2, 3, 4, 10, 11, 12, 17, 19, 20} |
| 1,00 | 0,00 | 0 | 20/3 | $C_1$ = {5, 8, 9, 13, 18, 21, 22, 23, 27}<br>$C_2$ = {1, 6, 7, 14, 15, 16, 24, 25, 26}<br>$C_3$ = {2, 3, 4, 10, 11, 12, 17, 19, 20} |

La tabla responde directamente la pregunta de si la asignación cambia al variar
los pesos: **sí cambia, pero solo dos veces**. Las filas λ₀ = 0 y λ₀ = 0,25
producen la misma asignación, y lo mismo ocurre entre λ₀ = 0,75 y λ₀ = 1. El
cambio se concentra en torno a λ₀ = 0,50, fila que además resulta ambigua. La
Sección siguiente localiza exactamente dónde ocurren los cambios.

### Grilla ampliada y localización de los quiebres

La grilla anterior no permite ver *dónde* cambia la solución, ni distingue
si un cambio ocurre justo en el valor probado o entre dos de ellos. La
Tabla 5 añade valores intermedios y los dos puntos en que la solución
óptima cambia.

**Tabla 5.** Grilla ampliada. Las filas marcadas con † son
puntos de quiebre: en ellas dos soluciones estructuralmente distintas alcanzan
el mismo valor objetivo. La última columna informa cuántos de los 27
estudiantes deben cambiar de curso respecto de la fila anterior, módulo
renombre de los cursos destino.

| λ₀ | λ₁ | F₁ | F₂ = T | Z | Solución | Cambian |
|---|---|---|---|---|---|---|
| 0,000 | 1,000 | 3 | 8/3 | 2,667 | S_balance † | — |
| 0,250 | 0,750 | 3 | 8/3 | 2,750 | S_balance | 0 |
| 0,400 | 0,600 | 3 | 8/3 | 2,800 | S_balance | 0 |
| **1/2** | **1/2** | — | — | 17/6 ≈ 2,833 | **S_balance ó S_media †** | — |
| 0,550 | 0,450 | 1 | 14/3 | 2,650 | S_media | 16 |
| 0,600 | 0,400 | 1 | 14/3 | 2,467 | S_media | 0 |
| **2/3** | **1/3** | — | — | 20/9 ≈ 2,222 | **S_media ó S_social †** | — |
| 0,750 | 0,250 | 0 | 20/3 | 1,667 | S_social | 12 |
| 0,900 | 0,100 | 0 | 20/3 | 0,667 | S_social | 0 |
| 1,000 | 0,000 | 0 | 20/3 | 0,000 | S_social | 0 |

Los **puntos de quiebre** son exactamente λ₀ = 1/2 y λ₀ = 2/3, y definen tres
regímenes:

| Rango de λ₀ | Solución | F₁ | F₂ = T |
|---|---|---|---|
| [0, 1/2) | S_balance | 3 | 8/3 |
| (1/2, 2/3) | S_media | 1 | 14/3 |
| (2/3, 1] | S_social | 0 | 20/3 |

**Tabla 6.** Las tres asignaciones. Los nombres son etiquetas de este análisis:
S_balance prioriza el reparto de perfiles, S_social prioriza la satisfacción de
preferencias y S_media es el régimen intermedio, que corresponde a la solución
reportada en la Tabla 1. Los identificadores se muestran sin el
prefijo SYN-.

| | 1M-A | 1M-B | 1M-C | Sin preferidos |
|---|---|---|---|---|
| **S_balance** | 8, 9, 13, 18, 19, 20, 25, 26, 27 | 1, 6, 7, 14, 15, 16, 17, 21, 24 | 2, 3, 4, 5, 10, 11, 12, 22, 23 | 0013, 0021, 0024 |
| **S_media** | 2, 3, 4, 12, 15, 24, 25, 26, 27 | 5, 8, 9, 13, 16, 17, 21, 22, 23 | 1, 6, 7, 10, 11, 14, 18, 19, 20 | 0015 |
| **S_social** | 5, 8, 9, 13, 18, 21, 22, 23, 27 | 1, 6, 7, 14, 15, 16, 24, 25, 26 | 2, 3, 4, 10, 11, 12, 17, 19, 20 | ninguno |

**S_media coincide exactamente con la solución reportada en la Tabla 1**, módulo
el renombre de los cursos destino: cero estudiantes difieren entre ambas. Esto
confirma que los pesos empleados en 3.4.5 seleccionan el régimen intermedio.

La Figura 2 resume ambos resultados: el panel (a) muestra la frontera de
compromiso en el plano (F₁, F₂) y el panel (b) el valor objetivo de cada punto
eficiente en función de λ₀, cuya envolvente inferior identifica el régimen
óptimo y sus dos quiebres.


### Qué queda invariante al mover los pesos

Los pesos alteran la asignación, pero no el conjunto factible: las
restricciones (7)–(12) se cumplen con cualquier λ y no se negocian. En las tres
soluciones eficientes la capacidad se satura en 9 + 9 + 9, ninguno de los ocho
pares de separación queda junto, y la diferencia de género entre cursos es 1 en
todos los casos, con holgura respecto de Δg = 2: en esta instancia la
restricción de género nunca es activa, y ningún valor de λ la activa. La
representación por origen sí cambia de estado —las tres restricciones están
activas en S_balance, mientras que en S_media y S_social el curso 8A queda
repartido 3/3/3, con holgura.

Más relevante es lo que ocurre con la satisfacción social agregada. Aunque F₁
decrece de 3 a 1 y a 0, el número total de nominaciones efectivamente cumplidas
es 29, 29 y 30 de 49 respectivamente, y en las tres soluciones quedan juntas
exactamente 12 parejas recíprocas.

| | Estudiantes con al menos un preferido | Nominaciones cumplidas | Parejas recíprocas juntas |
|---|---|---|---|
| S_balance | 24 de 27 | 29 de 49 | 12 |
| S_media | 26 de 27 | 29 de 49 | 12 |
| S_social | 27 de 27 | 30 de 49 | 12 |

Aumentar λ₀ no produce, entonces, más satisfacción agregada: **la redistribuye**.
La solución pasa de concentrar los vínculos cumplidos en menos estudiantes a
repartirlos de modo que ninguno quede en cero, con un total de vínculos
prácticamente constante. Esto es consecuencia directa de la definición de zᵢ,
que registra si el estudiante conserva *al menos un* preferido y no cuántos: la
componente social de (6) es un criterio de equidad entre estudiantes, no de
eficiencia agregada del sistema. La distinción es relevante para el decisor,
porque un establecimiento que buscara maximizar el total de vínculos conservados
requeriría una componente objetivo distinta, definida sobre wᵢⱼ en lugar de zᵢ.

Por último, el valor de λ afecta también el esfuerzo computacional. En un
barrido de λ₀ ∈ {0; 0,05; …; 1} resolviendo el modelo en cada punto, los tiempos
oscilaron entre 0,8 y 35 segundos, con los máximos en las vecindades de los dos
puntos de quiebre: cerca de un empate el solver debe descartar dos soluciones de
calidad casi idéntica antes de certificar optimalidad.

## Interpretación

**El compromiso existe y es monótono.** Al aumentar λ₀, F₁ decrece de 3 a 1 y a
0, mientras F₂ crece de 8/3 a 14/3 y a 20/3. Dar más importancia al balance deja
más estudiantes sin ninguno de sus preferidos; dar más importancia a la
componente social se paga con mayor dispersión de perfiles. Esto confirma la
tensión anticipada al final de la Sección 3.4.5.

**El compromiso es discreto, no gradual.** Solo existen tres puntos eficientes.
Barrer λ₀ de forma continua no produce un continuo de soluciones intermedias:
la decisión salta de un régimen a otro en dos valores precisos. Por lo tanto λ₀
no opera como un dial de ajuste fino, sino como un selector entre tres políticas
de asignación cualitativamente distintas.

**El costo marginal del último estudiante se duplica.** Pasar de S_balance a S_media
satisface a dos estudiantes adicionales al precio de 2 unidades de dispersión, es
decir 1 unidad por estudiante. Pasar de S_media a S_social satisface a un estudiante
más al precio de otras 2 unidades: 2 unidades por estudiante. Satisfacer al
último estudiante cuesta el doble que satisfacer a los dos anteriores, un patrón
de rendimientos decrecientes que el decisor debería conocer antes de fijar los
pesos.

**Los saltos entre regímenes son masivos.** Cruzar λ₀ = 1/2 obliga a que 16 de
los 27 estudiantes cambien de curso (59 %); cruzar λ₀ = 2/3, a que cambien 12
(44 %). Una variación pequeña de λ₀ en torno a un quiebre reasigna a más de la
mitad del nivel. En términos prácticos, esto significa que el establecimiento no
puede tratar los pesos como un parámetro técnico interno: su elección es una
decisión de política con consecuencias visibles para las familias. Nótese además
que S_balance y S_social difieren entre sí en solo 9 estudiantes (33 %), menos que
cualquiera de los dos pares consecutivos: el régimen intermedio no se sitúa
"entre" los extremos en el espacio de asignaciones.

**Los extremos son degenerados y no deben reportarse sin cuidado.** Con λ₀ = 0
la componente social desaparece del objetivo y cualquier valor de F₁ entre 3 y
27 resulta óptimo: el modelo se vuelve indiferente a las preferencias, y el
valor de F₁ que se reporte depende enteramente de la regla de desempate. Con
λ₁ = 0 ocurre lo simétrico con T. Ambas filas de la Tabla 5 se completaron
mediante una segunda etapa lexicográfica y esa dependencia queda explicitada.

**Los pesos empleados en 3.4.5 caen exactamente sobre un punto de quiebre.** La
elección λ₀ = λ₁ = 1, equivalente a λ₀ = 1/2 normalizado, es precisamente el
valor en que S_balance y S_media alcanzan el mismo valor objetivo 17/6. Es el único
punto del intervalo [0, 1/2] en que la solución de 3.4.5 no es la única óptima,
y explica por qué el problema admite dos soluciones óptimas estructuralmente
distintas bajo esos pesos. Se sugiere una de dos correcciones editoriales:
declarar explícitamente que la solución de la Tabla 1 es *una* solución óptima
entre dos, y que corresponde al régimen λ₀ ∈ (1/2, 2/3); o bien reportar el
ejemplo con un peso interior a ese régimen, por ejemplo λ₀ = 0,6, en cuyo caso
la solución exhibida es la única óptima y todas las cifras de la Sección 3.4.5
se mantienen sin cambios.

Conviene subrayar el alcance de estas conclusiones. Se refieren a una única
instancia sintética de veintisiete estudiantes y tres cursos; la cantidad de
puntos eficientes y la ubicación de los quiebres dependen de la instancia. Lo
que el ejemplo ilustra es el tipo de estructura —frontera discreta, quiebres
nítidos, saltos grandes de asignación— que el decisor debe esperar al fijar los
pesos, no valores transferibles a otro establecimiento.

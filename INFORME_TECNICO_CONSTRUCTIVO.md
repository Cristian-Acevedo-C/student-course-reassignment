# Informe técnico breve: heurística constructiva y warm start para el SCRP

## 1. Objetivo

Desarrollar una heurística constructiva propia, independiente de los testigos, que produzca una solución factible del Student Course Reassignment Problem (SCRP) y pueda cargarse en SCIP como incumbente inicial sin modificar el modelo matemático vigente.

Pregunta científica:

> ¿Una solución inicial factible construida específicamente para este problema permite a SCIP comenzar con un incumbente de mejor calidad y mejorar su desempeño?

## 2. Auditoría del modelo

Se contrastaron el manuscrito, `src_referencia/modelo.py`, las 30 instancias y `tools/evaluar_asignacion.py`. Para la implementación se adoptó como autoridad operacional el código vigente, conservando exactamente su formulación.

| Componente | Ecuaciones | Tratamiento en el constructivo |
|---|---:|---|
| Asignación única | (7) | Se garantiza mediante un diccionario con una única entrada por estudiante. |
| Capacidad | (8) | Se controla antes de cada inserción; swaps y ciclos preservan capacidad. |
| Separaciones | (9) | Se descartan cursos que ya contienen un estudiante incompatible. |
| Balance de género | (10)-(11) | Se generan patrones conjuntos compatibles con capacidades y diferencia máxima; cada inserción debe conservar al menos un patrón alcanzable. |
| Representación por origen | (12) | Look-ahead reserva cupos y estudiantes suficientes para cubrir cada mínimo pendiente. |
| Preferencias | (13)-(19) | Son blandas: guían la selección y determinan estudiantes insatisfechos. |
| Balance de perfiles | (20)-(22) | Guía greedy y criterio de mejora; se reportan los valores oficiales `F_k` y `T`. |

Restricciones duras durante la construcción: asignación única, capacidad, separaciones, género y representación por curso de origen.

### Inconsistencias documentadas

1. El manuscrito combina una función ponderada en (6) con una sección posterior de optimización jerárquica. El código vigente implementa la función ponderada `lambda_0(N-sum z)+lambda_1*T`; esa es la usada sin cambios.
2. El manuscrito contiene marcadores editoriales y referencias `R.1/R.2` todavía no definidas. La implementación se vinculó directamente con las ecuaciones (7)-(29).
3. El manuscrito propone `U_c=ceil(N/C)` cuando no hay capacidades externas. Las instancias ya contienen capacidades explícitas y el modelo usa esas capacidades.
4. En PySCIPOpt 6.2.1, `trySol()` no puede llamarse antes de iniciar el proceso de solución. La alternativa conservadora fue construir las 796 variables, verificar con `checkSol(..., original=True)` y cargar con `addSol()` antes de `optimize()`.

El SHA-256 auditado de `src_referencia/modelo.py` es `a79f8ec7df1cc63c64f9a588af5b9fb5169a1464355524abede25c16986c0bb6`.

## 3. Algoritmo implementado

### 3.1 Preprocesamiento

- Grafo de separaciones por estudiante.
- Preferencias inversas para medir cuántos estudiantes demandan a cada candidato.
- Patrones finales de género compatibles con la diferencia máxima y las capacidades.
- Conteos totales por origen, género, criterio y nivel.
- Prioridad base `3·separaciones + 2·preferencias recibidas + preferencias propias`.

### 3.2 Construcción greedy adaptativa

En cada iteración:

1. Se calculan los cursos todavía factibles de cada estudiante no asignado.
2. Se elige primero al estudiante con menos alternativas; los empates favorecen mayor dificultad.
3. Se descartan inserciones que excedan capacidad, violen separaciones, destruyan todos los patrones de género o hagan imposible cubrir los mínimos por origen.
4. Los cursos restantes se ordenan mediante una puntuación que considera perfiles, urgencia de origen, preferencias propias, preferencias recibidas y flexibilidad remanente.
5. Si una rama bloquea la factibilidad, se retrocede de forma acotada y se prueba la siguiente alternativa.

Se ejecutan varios intentos reproducibles: el primero determinista y los siguientes con perturbaciones pequeñas de desempate.

### 3.3 Reparación y mejora

- Fallback min-conflicts con swaps si la construcción con look-ahead no encuentra una solución dentro del límite de nodos.
- Búsqueda local best-improvement mediante swaps factibles.
- Reubicaciones cuando existe capacidad libre.
- Cadenas cíclicas de tres estudiantes al alcanzar una meseta de swaps.
- Todos los movimientos se reauditan contra las restricciones duras.

El criterio de aceptación conserva primero el objetivo oficial; solo usa `no_satisfechos`, `T`, suma de `F_k` y multiplicidad de preferencias como desempates internos.

## 4. Validación del constructivo

Parámetros: `lambda_0=lambda_1=1`; sin testigos; semillas y comandos registrados en cada `metadata.json`.

| Familia | Instancias factibles | Verificador independiente | Tiempo medio | Objetivo medio | T medio | Insatisfechos medios |
|---|---:|---:|---:|---:|---:|---:|
| L=9, P=3, C=4 | 10/10 | 10/10 | 5,72 s | 6,85 | 5,45 | 1,40 |
| L=9, P=3, C=5 | 10/10 | 10/10 | 6,21 s | 10,48 | 7,28 | 3,20 |
| L=9, P=3, C=6 | 10/10 | 10/10 | 14,53 s | 13,27 | 8,77 | 4,50 |

En las 30 soluciones las violaciones de asignación, capacidad, separación, género y origen fueron cero.

## 5. Integración con SCIP

Para cada asignación se calcularon explícitamente `x`, `y`, `w`, `z`, `d+`, `d-`, `F` y `T`. La cobertura de variables y la factibilidad se verificaron antes de cargar la solución.

Resultado: 30/30 warm starts fueron verificados y aceptados por SCIP.

## 6. Comparación experimental

### 6.1 C=4, presupuesto total igualado a 12 segundos

El tiempo de construcción se descontó del tiempo disponible para SCIP en la condición warm start. Cada par usó la misma instancia y semilla de SCIP.

| Métrica media | SCIP default | SCIP + warm start |
|---|---:|---:|
| Presupuesto total observado | 12,000 s | 12,001 s |
| Tiempo a primer incumbente | 0,0756 s | 0 s |
| Calidad del primer incumbente | 33,50 | 6,85 |
| Mejor objetivo al finalizar | 13,10 | 6,85 |
| Gap final | 1,965 | 0,568 |
| Integral primal normalizada* | 7,994 | 0,000 |
| Warm starts aceptados | No aplica | 10/10 |

*Área del gap primal normalizado respecto del mejor objetivo observado en cada par; se usa 1 antes del primer incumbente. Es una métrica post hoc del experimento y no debe confundirse con `getPrimalDualIntegral()` de SCIP, que también se conserva en los CSV.

El warm start terminó con mejor incumbente y menor gap en las 10 réplicas dentro de este horizonte corto. SCIP no mejoró el incumbente heurístico durante el tiempo restante, por lo que el tiempo al mejor incumbente fue 0 en esta prueba.

### 6.2 Diagnósticos de escalabilidad con igual tiempo de SCIP

Estas pruebas entregaron 3 segundos de solver a ambas condiciones y, por tanto, no igualan el tiempo total del pipeline.

| Familia | Objetivo final medio default | Objetivo final medio warm | Warm aceptados |
|---|---:|---:|---:|
| C=5 | 39,84 | 10,48 | 10/10 |
| C=6 | 53,80 | 13,27 | 10/10 |

La ventaja observada es estrictamente de arranque primal temprano. Los tiempos medios de construcción fueron 6,21 s para C=5 y 14,53 s para C=6, por lo que deben incluirse en cualquier comparación de tiempo total.

## 7. Respuesta científica provisional

Sí existe evidencia de que la solución específica del dominio permite a SCIP comenzar con un incumbente sustancialmente mejor. La evidencia es consistente en las 30 instancias y todas las soluciones fueron aceptadas realmente por SCIP.

Todavía no existe evidencia suficiente para afirmar que el warm start reduce el tiempo total oficial o acelera la demostración de optimalidad. Los resultados previos de C=4 muestran que SCIP alcanza soluciones finales de objetivo 4-6 bajo horizontes largos, mejores que varias soluciones constructivas actuales, y que gran parte del tiempo puede corresponder al lado dual. La afirmación defendible en esta etapa es:

> La heurística mejora de forma consistente el desempeño primal temprano; su efecto sobre el tiempo total y la prueba de optimalidad permanece abierto y debe evaluarse con el protocolo oficial de 3600 segundos.

### Actualización del 8 de octubre de 2026: primer par a 3600 s

En la réplica C=4, i=8, con semilla SCIP 8, ambos métodos certificaron el mismo óptimo (objetivo 5, cota dual 5, gap 0). SCIP base tardó 137,83 s. La condición warm tardó 176,19 s de pipeline, incluidos 8,32 s de construcción. El incumbente inicial mejoró de 34 a 7, pero el tiempo para probar optimalidad fue mayor. Es un solo par; los 29 restantes siguen pendientes. El registro auditable está en `resultados_warm_start/oficial_C4_i8_3600s/`.

## 8. Próximos experimentos necesarios

1. Ejecutar C=4 con 3600 s e igual presupuesto total, varias semillas de SCIP y el mismo entorno del baseline oficial.
2. Separar instancias de calibración y evaluación antes de ajustar pesos o número de intentos.
3. Comparar la calidad del constructivo contra los mejores valores conocidos, no solo contra el primer incumbente.
4. Analizar primal integral, tiempo al mejor incumbente, gap y tiempo de prueba por separado.
5. Solo después de esa evidencia, decidir si ampliar hacia GRASP/VNS o concentrarse en refuerzos del lado dual.


# Instancias CSV del procesador escolar (paquete Colab/SCIP)

Instancias sintéticas del flujo "procesar CSV escolar con SCIP": un `.csv` con
una fila por estudiante y un `.json` con la configuración de cursos destino.
Son distintas de la grilla de 480 instancias de `instancias/`.

| Prefijo | Qué prueba |
|---|---|
| `S01`–`S08` | Casos de estrés: control sano, estrella de popularidad, cadena de preferencias, clique de separaciones, género con Δ = 0, académico y origen sin holgura, desafío integral. Los `R` (`S02R`, `S03R`, …) son las versiones reparadas. |
| `R01`–`R04` | Colegios realistas de 56, 90, 102 y 113 estudiantes. |
| `I00`, `I02` | Ejemplo ilustrativo de 18 y frontera de Pareto tensionada de 60. |

Formato del CSV: `instance_id, student_id, origin_course, grade_average, gender,
socioemotional_level, convivencia_level, pref_1 … pref_5, separate_with`
(`separate_with` separa varios IDs con `|`).

## Procedencia e integridad

Los nombres se asignaron por SHA-256 contra los manifiestos de las entregas v2
y v3 (`manifiestos/`): cada archivo calza byte a byte con la ruta que figura
ahí. Esta carpeta trae solo los archivos de datos que estaban disponibles; los
manifiestos listan el paquete completo (`src/reassignment/`, notebook de Colab,
scripts y salidas), que no está versionado aquí todavía.

# Sensibilidad computacional

## Pregunta

Este experimento estudiará cómo los estudiantes por curso (`L`), las
preferencias por estudiante (`P`) y la cantidad de cursos (`C`) se relacionan
con el esfuerzo necesario para resolver el MILP.

## Protocolo vigente

- `L ∈ {9,18,27,36}`;
- `P ∈ {3,5,7}`;
- `C ∈ {4,5,6,7}`;
- 10 réplicas por combinación;
- 480 instancias en total;
- 3600 segundos y un hilo por instancia.

Las entradas están en `../../instancias/` y los testigos de factibilidad en
`../../testigos/`. Los testigos no se usan como *warm start*.

## Estado de la evidencia

- La grilla completa está versionada y puede validarse con
  `python src/validar_repositorio.py`.
- La campaña definitiva todavía no se ha ejecutado ni se incluyen tiempos,
  brechas o conclusiones globales.
- `calibracion_15s_grilla_360/` conserva 36 corridas exploratorias de una grilla
  anterior. Es material histórico y no representa las 48 configuraciones del
  protocolo vigente.

Por lo tanto, todavía no corresponde afirmar qué factor domina la dificultad
computacional. Esa conclusión deberá basarse en una corrida homogénea y en la
separación entre optimalidad certificada, límite con incumbente, límite sin
incumbente, infactibilidad demostrada y errores.

Consulta [el protocolo de ejecución](../../docs/ejecucion.md) antes de iniciar
la campaña.

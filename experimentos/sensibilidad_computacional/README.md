# Sensibilidad computacional

Este experimento estudia el efecto de `n`, `l` y `s` sobre el tiempo de
resolución, el gap, los nodos explorados y el tamaño del modelo exacto.

## Estado

- Las 360 instancias y sus testigos están versionados en la raíz del proyecto.
- La carpeta [`calibracion_15s/`](calibracion_15s/) contiene 36 corridas
  exploratorias, una por configuración y con límite de 15 segundos.
- Los resultados definitivos con límite de 3600 segundos todavía no están
  incluidos.

La calibración sirve para validar el flujo y estimar duración; no debe mezclarse
con `resultados/resultados.csv` ni citarse como evidencia final.

Consulta [la guía de ejecución](../../docs/ejecucion.md) para correr el
protocolo vigente.

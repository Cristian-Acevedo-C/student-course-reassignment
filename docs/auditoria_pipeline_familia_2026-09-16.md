# Auditoría del pipeline de una familia — 16 de septiembre de 2026

Rama: `pipeline-familia-piloto`. Base revisada: `ca09d15`.
Cambios locales sin commit. Se conservó el pipeline existente y no se modificó
`src/modelo.py`, ninguna instancia ni ningún testigo.

## Alcance ejecutado y veredicto

**Preflight técnico aprobado. Corrida oficial no ejecutada.** Se invocó una sola
optimización: `c_n_9_l_3_s_4_i_0`, con límite SCIP de 60 s. Posteriormente se
ejecutó `-Reanudar` sobre esa misma salida: cero pendientes, cero optimizaciones
adicionales y CSV idéntico por SHA-256. No se ejecutaron las diez réplicas oficiales
ni el benchmark de 480. Los testigos se leyeron exclusivamente en la validación
estructural; nunca se entregaron como warm start.

La ejecución de una familia completa recorre `i_0` a `i_9` secuencialmente. El
retorno por optimalidad o time limit, con o sin incumbente, permite la siguiente
réplica. Esto quedó verificado por inspección y pruebas con solver simulado;
no constituye una prueba real de duración de diez horas.

## Hallazgos y correcciones

| Severidad | Hallazgo inicial | Corrección |
|---|---|---|
| Alta | La auditoría aceptaba `suma_z` menor al número de satisfechos y afirmaba que z solo estaba acotada arriba | Igualdad exacta de conteos; documentación corregida: también existe `z_i >= w_ij` |
| Alta | SCIP se mostraba, pero no se exigía 10.0.2; el acceso directo por Python podía marcar oficial sin comprobar versiones | Se exigen PySCIPOpt 6.2.1 y SCIP 10.0.2 antes de crear una salida oficial, en ambos puntos de entrada |
| Alta | `lp/threads` conservaba su valor por defecto 0 | Se fija explícitamente en 1, junto con `parallel/maxnthreads=1`; verificado en el solver instalado |
| Alta | Reanudar confiaba en filas del CSV sin verificar entradas, código ni archivos | Manifiesto y hashes; solo se omiten réplicas terminadas con artefactos íntegros |
| Alta | Una segunda interrupción podía perder filas terminadas posteriores; la escritura directa podía truncar el CSV | Se conservan todas las terminadas y se reemplaza el CSV atómicamente |
| Alta | Una fila de error con campos vacíos podía hacer fallar la conversión de parámetros al reanudar | Se detectan pendientes antes de convertir sus campos; prueba de regresión específica |
| Media | Solo se exportaba la asignación legible, no todas las variables del MILP | Exportación `.sol` con ceros incluidos y auditoría separada en JSON |
| Media | El tiempo llamado total medía únicamente `optimize()`; solo ese tiempo se resumía | Total por réplica, tiempo SCIP y tiempo de pared de `optimize()` separados; media y desviación de total y SCIP |
| Media | Fallos de stats JSON o de `checkSol` podían ocultarse | Stats JSON obligatorias; auditoría no aprobada si `checkSol` no confirma factibilidad |
| Media | `--preflight` directo en Python conservaba por defecto diez réplicas y 3600 s | Defaults seguros: réplica 0 y 60 s; subconjuntos reservados a preflight |
| Media | Una interrupción podía finalizar con código de éxito | Código 130 en interrupción y 1 ante errores, auditoría fallida o pendientes |

## Evidencia de validación

- 11 pruebas automatizadas aprobadas con `python -m unittest discover -s tests -v`.
- Se probaron los diez índices en orden, optimalidad y ambos time limits,
  continuación de pendientes, reanudación ya completa, segunda interrupción,
  fila de error, rechazo de protocolo/versión incompatible, escritura atómica,
  igualdad exacta de satisfacción, parámetros efectivos y estadísticos conocidos.
- Validación estructural aprobada: 480 instancias únicas, 480 testigos factibles,
  120 instancias para cada C y siete escenarios I00C consistentes. Sin optimización.
- Análisis sintáctico PowerShell, compilación Python y `git diff --check` aprobados.
- `git diff --exit-code -- src/modelo.py instancias testigos`: sin cambios.

## Resultado observado del preflight

Entorno: Windows 11, Intel Core Ultra 7 255H, 14.9 GiB RAM; Python 3.13.13,
PySCIPOpt 6.2.1, SCIP 10.0.2. Reloj SCIP de pared; ambos parámetros de hilos en 1.

| Métrica | Resultado |
|---|---:|
| Estado | timelimit_with_incumbent |
| Tiempo SCIP | 60.000000 s |
| Tiempo total por réplica | 60.415726 s |
| Pared alrededor de optimize() | 59.500577 s |
| Construcción | 0.035497 s |
| Objetivo / primal | 11 |
| Dual / dual en raíz | 5 / 5 |
| Gap relativo SCIP | 1.2 = 120 % |
| Gap absoluto | 6 |
| T | 8 |
| suma_z / satisfechos recalculados | 33 / 33 |
| Nodos | 1145 |
| Primera solución | objetivo 40, tiempo SCIP registrado 0.00 s |
| Mejor incumbente | objetivo 11, tiempo SCIP registrado 31.00 s |
| Mejoras de incumbente registradas | 6 |
| Soluciones encontradas por SCIP | 7 |
| Variables originales exportadas | 796, incluidos los 144 x_ic y los ceros |
| Auditoría / checkSol | TRUE / TRUE |
| Violaciones / inconsistencias | 0 / 0 |

Los eventos y las estadísticas coinciden (`eventhdlr=stats`). La trayectoria
de objetivos es 40 → 27.5 → 23 → 22 → 16 → 11. Siete soluciones encontradas no
implican siete mejoras: el contador de soluciones y el de incumbentes difieren.
Los tiempos SCIP observados tienen valores de segundos enteros; el 0.00 s de
primera solución no prueba tiempo real nulo ni precisión subsegundo. El tiempo
de pared de Python se conserva aparte, sin forzarlo a coincidir con SCIP.

Salida local (excluida de Git):
`corridas/preflight/prueba_familia_L9_P3_C4_T60s_i0/`.
Se verificaron los ocho artefactos por réplica mediante existencia, contenido y
SHA-256: log, stats texto/JSON, ambas trayectorias, solución legible/completa y
auditoría JSON. El `.sol` contiene exactamente las 796 variables originales.
La exportación usa `writeBestSol(..., write_zeros=True)` conforme a la
[API de PySCIPOpt](https://pyscipopt.readthedocs.io/en/latest/api/model.html#pyscipopt.Model.writeBestSol).

Ambos CSV se generaron automáticamente. Con n=1, las medias son los valores
observados y las desviaciones muestrales quedan vacías, no cero. El resumen
indica `numero_pendientes=0` para la selección de preflight y
`familia_completa=FALSE` porque no se resolvieron las diez réplicas.

Después de `-Reanudar`, se observó `ya resuelta, se conserva`, salida 0 y ninguna
llamada a optimización. SHA-256 de `resultados_familia.csv` antes y después:
`ad2a99f2ceda98cd3e28819fd3c43476067d7b53a100ed5835f1fe70a261c523`.
Transcripciones locales: `corridas/preflight_auditoria_console.txt` y
`corridas/reanudacion_auditoria_console.txt`.

## Operación oficial y riesgos residuales

Desde la raíz del repositorio, para ejecutar las diez réplicas:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\correr_familia.ps1 -L 9 -P 3 -C 4 -Tiempo 3600
```

Para reanudar, añadir `-Reanudar` al mismo comando. Si se utiliza una salida
personalizada, repetir la misma `-Salida`.

- El preflight acredita funcionamiento técnico, no optimalidad futura. La cota
  dual permaneció en 5 y el gap final fue 120 %: gastar una hora por réplica no
  garantiza cerrar el gap.
- Diez horas es la suma de límites SCIP; el tiempo de pared total puede ser mayor.
  Mantener alimentación, evitar suspensión y cargas intensivas.
- La reanudación conserva réplicas completas; una réplica interrumpida vuelve a
  comenzar. No recupera el árbol SCIP.
- No cambiar código, instancias, versiones ni parámetros si se pretende reanudar.
  Corridas previas a este manifiesto requieren otra carpeta; no se migran ni mezclan.
- Ejecutar un solo proceso por salida y no bloquear los CSV con Excel. No hay un
  bloqueo de concurrencia entre procesos. Hay protección atómica del CSV frente
  a interrupciones de escritura, pero no una garantía frente a toda falla de disco.
- SCIP mantiene su límite de memoria por defecto, prácticamente sin límite.
  El preflight no demuestra el consumo máximo de una corrida de 3600 s.
- Los artefactos en `corridas/` están ignorados por Git: respaldarlos al finalizar.
  `modo=oficial` acredita protocolo; comprobar además `familia_completa=TRUE`,
  cero errores y auditorías aprobadas antes de usar resultados académicos.

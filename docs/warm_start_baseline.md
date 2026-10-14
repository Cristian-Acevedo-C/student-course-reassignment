# Warm start del constructivo contra el baseline (opción A)

## Qué se compara

Para cada una de las 30 réplicas (L=9, P=3, C ∈ {4, 5, 6}, i = 0..9):

| Condición | Cómo se obtiene |
|---|---|
| **Baseline** | la corrida oficial ya hecha con `correr_familia.ps1` (no se repite) |
| **Warm start** | la misma corrida, pero SCIP parte con la solución del constructivo |

Las soluciones son las 30 de `resultados_constructivo/` (rama
`feat/constructivo-warm-start-20261008`), copiadas sin cambios en
`warm_start/constructivo/L9_P3_C{4,5,6}/`. Todas son factibles y
validadas de forma independiente.

## Por qué no se vuelve a correr el baseline

Con PySCIPOpt 6.2.1 / SCIP 10.0.2 y los mismos parámetros, SCIP es
determinista: al reproducir `c_n_9_l_3_s_4_i_8` se obtuvieron los mismos 6188
nodos y el mismo óptimo 5.0 de la corrida oficial. Repetirlo no aporta
información. A cambio, **cada familia warm debe correrse en el mismo PC que su
baseline**: los nodos se reproducen entre máquinas, los tiempos no.

## Qué cambia y qué no

`src/resolver_familia_warm.py` ejecuta `resolver_familia.py` y `modelo.py`
**sin modificarlos** (verifica sus SHA-256 y se detiene si no coinciden con
los del baseline). Solo intercepta la construcción del modelo para:

1. leer `heur_<instancia>.txt` y auditarlo con el mismo auditor del baseline
   (si es infactible o su objetivo no calza, la réplica se aborta);
2. construir la solución completa (x, y, w, z, d⁺, d⁻, F, T), verificarla con
   `checkSol(original=True)` y cargarla con `addSol` antes de optimizar;
3. fijar el límite de SCIP en 3600 s − tiempo del constructivo.

Todo lo demás es idéntico: reloj de pared, 1 hilo, gap 0, λ₀ = λ₁ = 1, semilla
por defecto, logs, estadísticas, auditoría y formato de `resultados_familia.csv`.

**Presupuesto.** El tiempo del constructivo (5–15 s según la familia) viene de
`resultados_constructivo.csv`; se midió cuando se generaron las soluciones,
no en el PC del benchmark. Frente a 3600 s su efecto es despreciable salvo en
réplicas que cierran en segundos. El comparador suma ese tiempo al de la
corrida warm.

## Cómo correrlo

Copiar el paquete en la carpeta donde se corrió el baseline y, en PowerShell:

```powershell
.\correr_familia_warm.ps1 -C 4 -Preflight     # 1 réplica, 60 s, ~1 min
.\correr_familia_warm.ps1 -C 4                # oficial: 10 × hasta 3600 s
.\correr_familia_warm.ps1 -C 5
.\correr_familia_warm.ps1 -C 6
```

Si se interrumpe, `-Reanudar` conserva las réplicas terminadas. Al terminar
compara solo contra `corridas/prueba_familia_L9_P3_C{C}_T3600s/`; si el
baseline está en otra carpeta:

```powershell
.\correr_familia_warm.ps1 -C 5 -SoloComparar -Base <carpeta del baseline C=5>
```

Peor caso: 10 h por familia (30 h las tres). En C=6 el baseline no cerró
ninguna, así que lo esperable es cerca de 10 h.

## Qué entrega la comparación

Todo resultado queda en **.txt** (en el formato `[instancia]` + `campo = valor`
del baseline), con su gemelo .csv al lado:

- en la carpeta de la corrida warm, los mismos .txt del baseline
  (`resultados_familia.txt`, `resumen_familia.txt`,
  `resumen_global_familia_L9_P3_C{C}.txt`, `soluciones/sol_*.txt`, logs y
  estadísticas) más `warm_start.txt` con la solución entregada en cada réplica;
- en `comparacion_warm/L9_P3_C{C}/`:

- `comparacion_base_warm.txt` (y .csv): por réplica, ambas condiciones (estado, tiempo,
  primal, cota dual de raíz y final, gap, nodos, mejor incumbente) y las
  diferencias warm − base, con una clasificación: *solo warm cierra*,
  *ambos cierran: warm más rápido*, *ninguno cierra: warm mejor primal*, etc.
- `resumen_base_warm.txt` (tablas legibles + chequeos) y
  `resumen_base_warm_detalle.txt` (y .csv): por familia y global, óptimos de cada
  condición, media geométrica desplazada del tiempo (s = 10 s), cuántas veces
  el warm resuelve antes o después (prueba de signo exacta), y cuántas veces
  mejora o empeora el primal y la cota dual.
- `tab_base_warm.tex`: tabla para el manuscrito.

Chequeos automáticos: instancias idénticas (SHA-256), mismo protocolo, mismo
óptimo cuando ambas cierran, ningún primal bajo la cota dual de la otra
condición, auditoría aprobada y réplicas pendientes.

## Cómo leerlo

- Ganar en tiempo significa **probar el óptimo antes**; una corrida que no
  cierra cuenta como tiempo infinito. Si ninguna cierra, se compara primal y
  cota dual.
- Una sola semilla por réplica: con 10 pares por familia la variabilidad de
  MILP es grande. La conclusión sale del conjunto de las 30 pareadas, no de
  casos sueltos. El único par oficial previo (C=4, i_8, con otra semilla)
  mostró al warm start más lento (176 s contra 138 s).
- En C=4 el constructivo entrega soluciones de objetivo 6–8; el baseline ya
  llega a 4–6. El margen para mejorar el primal está sobre todo en C=5 y C=6.

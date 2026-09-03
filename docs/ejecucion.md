# Protocolo de ejecución del benchmark

Este documento describe la campaña futura de 480 instancias. No es necesario
ejecutarla para revisar el código, validar la grilla o reproducir el ejemplo
I00C.

## 1. Condiciones que deben registrarse

Para que los tiempos sean comparables, la corrida reportada en el artículo debe
usar:

- límite de 3600 segundos por instancia;
- un hilo por proceso;
- brecha objetivo igual a cero;
- ejecución secuencial o recursos aislados;
- versión de Python, PySCIPOpt y SCIP;
- procesador, memoria RAM y sistema operativo;
- fecha y comando de ejecución.

La cota máxima teórica es de 480 horas de cómputo secuencial si todas las
instancias agotan el límite. Esto no es una estimación del tiempo real.

## 2. Preparación y validación

```powershell
python -m pip install -r requirements.txt
python src\validar_repositorio.py
```

Las 480 instancias ya están en `instancias/`. Solo para regenerarlas de manera
determinística:

```powershell
python src\generar_instancias.py --todas
```

Ese comando reemplaza los archivos de la grilla; no debe ejecutarse si solo se
quiere revisar o resolver las instancias existentes.

## 3. Ejecución secuencial

La campaña completa:

```powershell
python src\resolver_lote.py --instancias instancias --tiempo 3600 --hilos 1
```

Por familia de número de cursos:

```powershell
python src\resolver_lote.py --patron "c_n_*_s_4_*.txt" --tiempo 3600 --hilos 1  # 120
python src\resolver_lote.py --patron "c_n_*_s_5_*.txt" --tiempo 3600 --hilos 1  # 120
python src\resolver_lote.py --patron "c_n_*_s_6_*.txt" --tiempo 3600 --hilos 1  # 120
python src\resolver_lote.py --patron "c_n_*_s_7_*.txt" --tiempo 3600 --hilos 1  # 120
```

La alternativa equivalente en PowerShell es:

```powershell
.\correr.ps1 -Modo s4
.\correr.ps1 -Modo s5
.\correr.ps1 -Modo s6
.\correr.ps1 -Modo s7
```

El ejecutor es reanudable. Conserva una fila previa solo cuando corresponde al
mismo protocolo y ya terminó a óptimo o alcanzó un límite igual o mayor al
solicitado.

## 4. Salidas

| Ruta | Contenido |
|---|---|
| `resultados/resultados.csv` | estado, tiempo, brecha, objetivo, cota y métricas |
| `soluciones/sol_<instancia>.txt` | mejor solución disponible de cada caso |
| `analisis/` | tablas construidas desde el CSV |

En resultados con límite de tiempo deben distinguirse al menos:

- óptimo certificado;
- límite de tiempo con incumbente;
- límite de tiempo sin incumbente;
- infactibilidad demostrada;
- error de ejecución.

Un caso sin incumbente al alcanzar el límite no constituye una demostración de
infactibilidad.

## 5. Construcción de tablas

```powershell
python src\analizar_resultados.py --resultados resultados\resultados.csv --salida analisis
```

Las tablas resumen optimalidad, tiempos de los casos certificados, brechas de
los casos truncados y efectos por factor. No deben combinarse con la
calibración histórica de 15 segundos.

## 6. Paralelización exploratoria

Para obtener soluciones preliminares pueden separarse los cuatro tamaños:

```powershell
python src\resolver_lote.py --patron "c_n_9_*"  --tiempo 3600 --hilos 1 --salida res_n9
python src\resolver_lote.py --patron "c_n_18_*" --tiempo 3600 --hilos 1 --salida res_n18
python src\resolver_lote.py --patron "c_n_27_*" --tiempo 3600 --hilos 1 --salida res_n27
python src\resolver_lote.py --patron "c_n_36_*" --tiempo 3600 --hilos 1 --salida res_n36
```

Si se ejecutan simultáneamente, la competencia por CPU y memoria puede sesgar
los tiempos. Esas mediciones no deben presentarse como benchmark final salvo que
los recursos estén aislados y la configuración quede documentada.

## 7. Alcance de la evidencia actual

La carpeta `calibracion_15s_grilla_360/` contiene 36 corridas exploratorias de
una grilla anterior. No representa las 48 configuraciones vigentes y no permite
concluir cuál factor domina la dificultad del protocolo de 480 instancias.

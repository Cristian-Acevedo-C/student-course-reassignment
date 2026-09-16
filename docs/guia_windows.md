# Guía paso a paso para Windows

Esta guía está pensada para la persona que ejecutará posteriormente el
benchmark. Para revisar el repositorio no es necesario iniciar la campaña.

## 1. Obtener el proyecto

En GitHub selecciona **Code → Download ZIP** y extrae el archivo, o clona el
repositorio. Abre PowerShell en la carpeta `student-course-reassignment`.

Comprueba que estás en la raíz:

```powershell
dir
```

Debes ver `instancias`, `testigos`, `src`, `experimentos` y `correr.ps1`.

## 2. Preparar Python

Si `python --version` no funciona, instala Python desde python.org y activa
**Add Python to PATH**. Luego abre una nueva ventana de PowerShell.

Instala las dependencias:

```powershell
python -m pip install -r requirements.txt
```

## 3. Validar sin resolver

```powershell
python src\validar_repositorio.py
```

Este comando revisa las 480 instancias, los 480 testigos y el paquete I00C. No
usa SCIP y no genera resultados masivos.

## 4. Prueba técnica corta

PowerShell puede requerir habilitar scripts solo para la ventana actual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\correr.ps1 -Modo prueba
```

El modo `prueba` resuelve **una** instancia pequeña con un límite de 30 segundos
y comprueba que el flujo completo funciona. Sus salidas son técnicas y no deben
mezclarse con el benchmark del artículo.

## 5. Familia piloto (antes de la campaña)

```powershell
.\correr_familia.ps1 -L 9 -P 3 -C 4 -Preflight
.\correr_familia.ps1 -L 9 -P 3 -C 4 -Tiempo 3600
```

Detalles en [prueba_familia.md](prueba_familia.md). La campaña de la sección
siguiente se lanza solo después de validar esta familia con los profesores.

## 6. Campaña definitiva

Cada bloque por número de cursos `C` contiene 120 instancias (12 familias
`(L, P)` × 10 réplicas):

```powershell
.\correr.ps1 -Modo s4
.\correr.ps1 -Modo s5
.\correr.ps1 -Modo s6
.\correr.ps1 -Modo s7
```

Para ejecutar las 480 de manera secuencial:

```powershell
.\correr.ps1 -Modo todo
```

El límite predeterminado es 3600 segundos y se usa un hilo. La ejecución puede
interrumpirse con `Ctrl+C` y reanudarse después.

La opción `-Limpiar` elimina las salidas previas de `resultados`, `soluciones` y
`analisis`; úsala solo cuando realmente se quiera comenzar desde cero.

## 7. Regenerar tablas sin resolver

```powershell
.\correr.ps1 -Modo analizar
```

Las tablas se escriben en `analisis/`. Las soluciones individuales quedan en
`soluciones/` y el registro consolidado en `resultados/resultados.csv`.

## 8. Paralelización exploratoria

Los cuatro tamaños vigentes son 9, 18, 27 y 36 estudiantes por curso:

```powershell
python src\resolver_lote.py --patron "c_n_9_*"  --tiempo 3600 --hilos 1 --salida res_n9
python src\resolver_lote.py --patron "c_n_18_*" --tiempo 3600 --hilos 1 --salida res_n18
python src\resolver_lote.py --patron "c_n_27_*" --tiempo 3600 --hilos 1 --salida res_n27
python src\resolver_lote.py --patron "c_n_36_*" --tiempo 3600 --hilos 1 --salida res_n36
```

Para combinar las salidas:

```powershell
$destino = "resultados\resultados.csv"
New-Item -ItemType Directory -Force -Path resultados | Out-Null
Get-Content res_n9\resultados.csv | Select-Object -First 1 | Set-Content $destino
foreach ($d in @("res_n9","res_n18","res_n27","res_n36")) {
    Get-Content "$d\resultados.csv" | Select-Object -Skip 1 | Add-Content $destino
}
python src\analizar_resultados.py --resultados $destino --salida analisis
```

La ejecución simultánea puede sesgar los tiempos por competencia de recursos.
Consulta [el protocolo de ejecución](ejecucion.md) antes de producir resultados
para el artículo.

# Paso a paso en PowerShell (Windows)

## Qué trae el zip, en simple

| Carpeta | Qué es |
|---|---|
| `instancias\` | **Los 360 casos de prueba.** Un archivo `.txt` por caso. Son los datos de entrada: alumnos, preferencias, separaciones. |
| `src\` | **Los 4 programas.** Uno genera los casos, uno los resuelve, uno arma las tablas, uno verifica que estén bien. |
| `testigos\` | Una solución de ejemplo de cada caso, usada solo para comprobar que el caso tiene solución. **No se usa al resolver.** |
| `resultados\` | **Todavía no existe.** Se crea sola en la primera corrida, con el `resultados.csv`: nombre, tiempo y gap de cada caso. |
| `soluciones\` | Se crea sola. Van los `sol_<caso>.txt`, uno por caso resuelto. |
| `analisis\` | Se crea sola. Las tablas finales, estilo artículo. |
| `calibracion_15s_referencia\` | Una corrida exploratoria mía de 15 segundos, **solo para que veas cómo se ven las tablas**. No son resultados del experimento y no hay que copiarla a `resultados\`. |
| `correr.ps1` | **El botón grande.** Hace todo lo de abajo por vos. |

En una frase: `instancias\` son las preguntas, `soluciones\` son las respuestas,
y `resultados\resultados.csv` es la planilla con cuánto costó cada una.

---

## Paso 1 — Descomprimir

Descargá el zip, botón derecho → **Extraer todo**. Te queda una carpeta `exp`.
Anotá dónde quedó, por ejemplo `C:\Users\TuNombre\Downloads\exp`.

## Paso 2 — Abrir PowerShell en esa carpeta

Abrí la carpeta `exp` en el Explorador de Windows. En la barra de direcciones
escribí `powershell` y apretá Enter. Se abre una ventana ya parada en la carpeta.

Para confirmar que estás bien parado, escribí:

```powershell
dir
```

Tenés que ver `instancias`, `src`, `correr.ps1`, etc.

## Paso 3 — Permitir que corran scripts

Windows bloquea los `.ps1` por defecto. Escribí esto una vez por ventana:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Solo afecta a esta ventana, no cambia nada permanente en tu PC.

## Paso 4 — Prueba corta (5 minutos)

Antes de comprometer días de cómputo, verificá que todo funciona:

```powershell
.\correr.ps1 -Modo prueba
```

Esto instala el solver si falta, resuelve 9 casos chicos con 30 segundos de
tope, y arma las tablas. Si termina diciendo **LISTO**, todo está en orden.

> Si te dice que no encuentra Python, instalalo desde python.org y **marcá
> la casilla "Add Python to PATH"** durante la instalación. Después cerrá y
> volvé a abrir PowerShell.

## Paso 5 — La corrida en serio

Van por partes, de la más fácil a la más difícil. Cada una es un comando:

```powershell
.\correr.ps1 -Modo s2        # 120 casos de 2 cursos. Rápido: minutos u horas.
.\correr.ps1 -Modo s3        # 120 casos de 3 cursos. Lento.
.\correr.ps1 -Modo s4        # 120 casos de 4 cursos. Muy lento.
```

Todo va sumándose al mismo `resultados\resultados.csv`.

**Podés cortar cuando quieras con Ctrl+C.** Al volver a lanzar el mismo
comando, salta los casos que ya resolvió y sigue por donde iba. No perdés nada.

Un caso se salta solo si ya cerró a óptimo, o si ya se corrió con un límite de
tiempo **igual o mayor** al que estás pidiendo ahora. Si subís el límite, los
casos que habían quedado cortados se vuelven a resolver solos, para que el CSV
no mezcle dos protocolos distintos.

Si en algún momento querés arrancar todo de cero:

```powershell
.\correr.ps1 -Modo s2 -Limpiar
```

Si preferís largarlo todo de una y dejar el PC trabajando:

```powershell
.\correr.ps1 -Modo todo
```

## Paso 6 — Ver las tablas

Se generan solas al final de cada corrida. Si querés regenerarlas sin resolver
nada:

```powershell
.\correr.ps1 -Modo analizar
```

Quedan en la carpeta `analisis\`:

| Archivo | Qué muestra |
|---|---|
| `tabla1_optimalidad.txt` | Cuántos casos cerraron a óptimo, por combinación |
| `tabla2_tiempos.txt` | Mínimo, promedio y máximo de tiempo |
| `tabla3_gaps.txt` | El gap de los que no alcanzaron a cerrar |
| `efecto_marginal.txt` | **La respuesta a tu pregunta**: cuánto pesa `l` vs. `s` |
| `perfil_desempeno.csv` | Para graficar el % acumulado de casos resueltos |

Abrilos con el Bloc de notas, o arrastrálos a Excel si son `.csv`.

---

## Ir más rápido: cuatro ventanas a la vez

Si tu PC tiene 4 núcleos o más, abrí **4 ventanas de PowerShell** en la carpeta
`exp` y corré una línea distinta en cada una:

```powershell
# ventana 1
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python src\resolver_lote.py --patron "c_n_9_*"  --tiempo 3600 --hilos 1 --salida res_n9

# ventana 2
python src\resolver_lote.py --patron "c_n_18_*" --tiempo 3600 --hilos 1 --salida res_n18

# ventana 3
python src\resolver_lote.py --patron "c_n_27_*" --tiempo 3600 --hilos 1 --salida res_n27

# ventana 4
python src\resolver_lote.py --patron "c_n_36_*" --tiempo 3600 --hilos 1 --salida res_n36
```

Dejá `--hilos 1` en todas. El protocolo pide un hilo por instancia, y así los
tiempos siguen siendo comparables entre sí.

Cuando terminen, juntá los cuatro CSV en uno:

```powershell
$destino = "resultados\resultados.csv"
New-Item -ItemType Directory -Force -Path resultados | Out-Null
Get-Content res_n9\resultados.csv | Select-Object -First 1 | Set-Content $destino
foreach ($d in @("res_n9","res_n18","res_n27","res_n36")) {
    Get-Content "$d\resultados.csv" | Select-Object -Skip 1 | Add-Content $destino
}
python src\analizar_resultados.py --resultados $destino --salida analisis
```

---

## Cuánto va a demorar

De la calibración con 15 segundos de tope:

- **2 cursos** → cerraron los 12 de 12 probados. Minutos.
- **3 cursos** → cerraron 2 de 12.
- **4 cursos** → cerró 0 de 12.

Con el tope real de 3600 s, esperá que buena parte de los 240 casos de 3 y 4
cursos consuma la hora completa. En una sola ventana eso son del orden de
**200 horas**. Con 4 ventanas en paralelo, **2 a 3 días**.

Por eso conviene largar `-Modo s2` primero: en poco rato ya tenés 120 casos
resueltos y podés mostrar resultados mientras el resto sigue corriendo.

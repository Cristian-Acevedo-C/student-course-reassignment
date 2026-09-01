# =====================================================================
#  Experimento de sensibilidad - modelo exacto de reasignacion
#  Script para Windows PowerShell
#
#  Uso:
#     .\correr.ps1 -Modo prueba     # 5 min, para verificar que todo anda
#     .\correr.ps1 -Modo s2         # 120 instancias faciles (2 cursos)
#     .\correr.ps1 -Modo s3         # 120 instancias duras   (3 cursos)
#     .\correr.ps1 -Modo s4         # 120 instancias muy duras (4 cursos)
#     .\correr.ps1 -Modo todo       # las 360 de corrido
#     .\correr.ps1 -Modo analizar   # solo construye las tablas
# =====================================================================

param(
    [ValidateSet("prueba", "s2", "s3", "s4", "todo", "analizar")]
    [string]$Modo = "prueba",

    [double]$Tiempo = 3600,

    [string]$Salida = "resultados",
    [string]$Soluciones = "soluciones",

    # Borra resultados previos y empieza de cero.
    [switch]$Limpiar
)

$ErrorActionPreference = "Stop"

# --- ubicarse en la carpeta del script -------------------------------
Set-Location -Path $PSScriptRoot

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " Experimento de sensibilidad - modo: $Modo" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

# --- 0. limpieza opcional --------------------------------------------
if ($Limpiar) {
    Write-Host "Borrando resultados previos..." -ForegroundColor Yellow
    foreach ($d in @($Salida, $Soluciones, "analisis")) {
        if (Test-Path $d) { Remove-Item -Recurse -Force $d }
    }
    Write-Host "Listo, se empieza de cero." -ForegroundColor Green
    Write-Host ""
}

# --- 1. verificar Python ---------------------------------------------
$python = $null
foreach ($cmd in @("python", "py")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { $python = $cmd; break }
}
if (-not $python) {
    Write-Host "ERROR: no encuentro Python." -ForegroundColor Red
    Write-Host "Instalalo desde https://www.python.org/downloads/ y marca"
    Write-Host "la casilla 'Add Python to PATH' durante la instalacion."
    exit 1
}
$version = & $python --version
Write-Host "Python encontrado: $version" -ForegroundColor Green

# --- 2. verificar / instalar pyscipopt -------------------------------
& $python -c "import pyscipopt" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando las dependencias del experimento..." -ForegroundColor Yellow
    & $python -m pip install --quiet -r requirements.txt
    & $python -c "import pyscipopt" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: no se pudo instalar pyscipopt." -ForegroundColor Red
        Write-Host "Prueba a mano:  $python -m pip install -r requirements.txt"
        exit 1
    }
}
$v = & $python -c "import pyscipopt; print(pyscipopt.__version__)"
Write-Host "PySCIPOpt listo: version $v" -ForegroundColor Green
Write-Host ""

# --- 3. verificar que existan las instancias -------------------------
if (-not (Test-Path "instancias")) {
    Write-Host "No hay carpeta 'instancias'. Generando las 360..." -ForegroundColor Yellow
    & $python src\generar_instancias.py --todas
}
$cuantas = (Get-ChildItem "instancias\*.txt" | Measure-Object).Count
Write-Host "Instancias disponibles: $cuantas" -ForegroundColor Green
Write-Host ""

# --- 4. elegir que resolver ------------------------------------------
switch ($Modo) {
    "prueba"   { $patron = "c_n_9_*_i_0.txt";  $limite = 30 }
    "s2"       { $patron = "c_n_*_s_2_*.txt";  $limite = $Tiempo }
    "s3"       { $patron = "c_n_*_s_3_*.txt";  $limite = $Tiempo }
    "s4"       { $patron = "c_n_*_s_4_*.txt";  $limite = $Tiempo }
    "todo"     { $patron = "c_n_*.txt";        $limite = $Tiempo }
    "analizar" { $patron = $null;              $limite = $Tiempo }
}

if ($patron) {
    Write-Host "Resolviendo: $patron" -ForegroundColor Cyan
    Write-Host "Limite por instancia: $limite segundos"
    Write-Host "Podes cortar con Ctrl+C: al relanzar retoma donde quedo."
    Write-Host ""

    $inicio = Get-Date
    & $python src\resolver_lote.py `
        --instancias instancias `
        --patron $patron `
        --tiempo $limite `
        --hilos 1 `
        --salida $Salida `
        --soluciones $Soluciones
    $duracion = (Get-Date) - $inicio
    Write-Host ""
    Write-Host ("Tiempo total: {0:hh\:mm\:ss}" -f $duracion) -ForegroundColor Green
    Write-Host ""
}

# --- 5. construir las tablas -----------------------------------------
$csv = Join-Path $Salida "resultados.csv"
if (Test-Path $csv) {
    Write-Host "Construyendo las tablas de analisis..." -ForegroundColor Cyan
    & $python src\analizar_resultados.py --resultados $csv --salida analisis --limite $Tiempo
    Write-Host ""
    Write-Host "LISTO." -ForegroundColor Green
    Write-Host "  Registro  : $csv"
    Write-Host "  Soluciones: $Soluciones\"
    Write-Host "  Tablas    : analisis\"
} else {
    Write-Host "Todavia no hay resultados que analizar." -ForegroundColor Yellow
}

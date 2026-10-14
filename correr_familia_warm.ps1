# =====================================================================
#  Familia (L=9, P=3, C) con WARM START del constructivo  -  opcion A
#
#  Mismo codigo y parametros que el baseline (correr_familia.ps1); la unica
#  diferencia es que SCIP parte con la solucion constructiva cargada y recibe
#  3600 s menos el tiempo del constructivo. NO vuelve a correr el baseline.
#
#  IMPORTANTE: correr cada familia en el MISMO PC donde se corrio su baseline.
#
#  Preflight (1 replica, 60 s, para ver que todo funciona):
#     .\correr_familia_warm.ps1 -C 4 -Preflight
#
#  Corrida oficial de una familia (10 x 3600 s):
#     .\correr_familia_warm.ps1 -C 4
#
#  Continuar una corrida interrumpida:
#     .\correr_familia_warm.ps1 -C 4 -Reanudar
#
#  Solo comparar (sin resolver), con el baseline en otra carpeta:
#     .\correr_familia_warm.ps1 -C 4 -SoloComparar -Base corridas\prueba_familia_L9_P3_C4_T3600s
#
#  (Archivo en ASCII para Windows PowerShell 5.1.)
# =====================================================================

param(
    [Parameter(Mandatory = $true)][ValidateSet(4, 5, 6)][int]$C,
    [int]$L = 9,
    [int]$P = 3,
    [double]$Tiempo = 3600,
    [switch]$Preflight,
    [switch]$Reanudar,
    [switch]$SoloComparar,
    [string]$Salida,
    # carpeta (o resultados_familia.csv/.txt) del baseline de esta familia
    [string]$Base
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"

if ($Preflight -and -not $PSBoundParameters.ContainsKey("Tiempo")) { $Tiempo = 60 }
$familia = "L$($L)_P$($P)_C$($C)"
$soluciones = "warm_start/constructivo/$familia"
if (-not $Salida) {
    if ($Preflight) { $Salida = "corridas/preflight/warm_familia_$($familia)_T$($Tiempo)s" }
    else            { $Salida = "corridas/warm_familia_$($familia)_T$($Tiempo)s" }
}
if (-not $Base) { $Base = "corridas/prueba_familia_$($familia)_T3600s" }

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " WARM START constructivo - familia $familia - $Tiempo s" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

# --- Python y versiones (las mismas exigencias del baseline) ----------
$python = $null
if (Test-Path -LiteralPath "$PSScriptRoot\.venv\Scripts\python.exe") {
    $python = "$PSScriptRoot\.venv\Scripts\python.exe"
}
foreach ($cmd in @("python", "py", "python3")) {
    if ($python) { break }
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { $python = $cmd; break }
}
if (-not $python) { Write-Host "ERROR: no encuentro Python." -ForegroundColor Red; exit 1 }
$instalada = & $python -c "import pyscipopt; print(pyscipopt.__version__)" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: falta PySCIPOpt." -ForegroundColor Red; exit 1 }
$scip = & $python -c "import pyscipopt; m = pyscipopt.Model(); print('%d.%d.%d' % (m.getMajorVersion(), m.getMinorVersion(), m.getTechVersion()))"
Write-Host "PySCIPOpt : $instalada   SCIP: $scip"
if (($instalada -ne "6.2.1" -or $scip -ne "10.0.2") -and -not $Preflight) {
    Write-Host "La comparacion exige PySCIPOpt 6.2.1 y SCIP 10.0.2 (las del baseline)." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath $soluciones)) {
    Write-Host "ERROR: no encuentro las soluciones constructivas en $soluciones" -ForegroundColor Red
    exit 1
}

# --- Resolver ------------------------------------------------------------
$codigo = 0
if (-not $SoloComparar) {
    $argumentos = @("src/resolver_familia_warm.py", "--L", $L, "--P", $P, "--C", $C,
                    "--tiempo", $Tiempo, "--hilos", 1, "--gap", 0,
                    "--lambda-0", 1, "--lambda-1", 1,
                    "--salida", $Salida, "--soluciones-ws", $soluciones,
                    "--presupuesto", "igual_total")
    if ($Preflight) { $argumentos += @("--preflight", "--replicas", 8) }
    if ($Reanudar)  { $argumentos += "--reanudar" }
    # (el string se arma aparte: dentro de @(...) la coma se evalua antes que +)
    $comando = ".\correr_familia_warm.ps1 -C $C  =>  $python " + ($argumentos -join " ")
    $argumentos += @("--comando", $comando)

    $inicio = Get-Date
    & $python @argumentos
    $codigo = $LASTEXITCODE
    Write-Host ("Duracion total: {0:hh\:mm\:ss}" -f ((Get-Date) - $inicio))
    if ($codigo -ne 0) { Write-Host "El ejecutor termino con codigo $codigo." -ForegroundColor Red }
}

# --- Comparar con el baseline -------------------------------------------
$resWarm = Join-Path $Salida "resultados_familia.csv"
$baseOk = (Test-Path -LiteralPath $Base) -or (Test-Path -LiteralPath ([IO.Path]::ChangeExtension($Base, ".txt")))
if ((Test-Path -LiteralPath $resWarm) -and $baseOk) {
    Write-Host ""
    Write-Host "Comparando contra el baseline: $Base" -ForegroundColor Cyan
    & $python src/comparar_base_warm.py --base $Base --warm $resWarm --salida "comparacion_warm/$familia"
} else {
    Write-Host ""
    Write-Host "No compare: falta el baseline en '$Base' o los resultados warm." -ForegroundColor Yellow
    Write-Host "Indica la carpeta del baseline con -Base y usa -SoloComparar."
}
exit $codigo

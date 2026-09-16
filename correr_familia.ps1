# =====================================================================
#  Prueba de UNA familia (L, P, C) = 10 replicas del benchmark exacto
#
#  Corrida oficial de la familia piloto (10 x 3600 s, 1 hilo, gap 0,
#  lambda_0 = lambda_1 = 1):
#     .\correr_familia.ps1 -L 9 -P 3 -C 4 -Tiempo 3600
#
#  Preflight tecnico (1 replica, 60 s; se guarda en corridas\preflight\):
#     .\correr_familia.ps1 -L 9 -P 3 -C 4 -Preflight
#
#  Continuar una corrida interrumpida (conserva replicas terminadas):
#     .\correr_familia.ps1 -L 9 -P 3 -C 4 -Tiempo 3600 -Reanudar
#
#  Este script no ejecuta las 480 instancias ni usa los testigos.
#  (Archivo en ASCII para que Windows PowerShell 5.1 lo lea sin errores.)
# =====================================================================

param(
    [Parameter(Mandatory = $true)][ValidateSet(9, 18, 27, 36)][int]$L,
    [Parameter(Mandatory = $true)][ValidateSet(3, 5, 7)][int]$P,
    [Parameter(Mandatory = $true)][ValidateSet(4, 5, 6, 7)][int]$C,
    [double]$Tiempo = 3600,
    [switch]$Preflight,
    [int[]]$Replicas,
    [switch]$Reanudar,
    [string]$Salida
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Un hilo tambien para librerias numericas que respeten estas variables.
$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"

if ($Preflight) {
    if (-not $PSBoundParameters.ContainsKey("Tiempo")) { $Tiempo = 60 }
    if ($null -eq $Replicas -or $Replicas.Count -eq 0) { $Replicas = @(0) }
}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
if ($Preflight) {
    Write-Host " PREFLIGHT tecnico - L=$L P=$P C=$C - $Tiempo s" -ForegroundColor Yellow
} else {
    Write-Host " Familia L=$L P=$P C=$C - limite $Tiempo s por replica" -ForegroundColor Cyan
}
Write-Host "=====================================================" -ForegroundColor Cyan

# --- 1. Python --------------------------------------------------------
$python = $null
if (Test-Path -LiteralPath "$PSScriptRoot\.venv\Scripts\python.exe") {
    $python = "$PSScriptRoot\.venv\Scripts\python.exe"
}
foreach ($cmd in @("python", "py", "python3")) {
    if ($python) { break }
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { $python = $cmd; break }
}
if (-not $python) {
    Write-Host "ERROR: no encuentro Python en el PATH." -ForegroundColor Red
    exit 1
}
Write-Host ("Python    : " + (& $python --version 2>&1))

# --- 2. PySCIPOpt con la version fijada en requirements.txt -----------
$esperada = "6.2.1"
$instalada = & $python -c "import pyscipopt; print(pyscipopt.__version__)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PySCIPOpt no esta instalado. Ejecuta:" -ForegroundColor Red
    Write-Host "  $python -m pip install -r requirements.txt"
    exit 1
}
$scip = & $python -c "import pyscipopt; m = pyscipopt.Model(); print('%d.%d.%d' % (m.getMajorVersion(), m.getMinorVersion(), m.getTechVersion()))"
Write-Host "PySCIPOpt : $instalada (requirements.txt fija $esperada)"
Write-Host "SCIP      : $scip"
if ($LASTEXITCODE -ne 0) { exit 1 }
if ($instalada -ne $esperada -or $scip -ne "10.0.2") {
    Write-Host "ADVERTENCIA: el protocolo requiere PySCIPOpt 6.2.1 y SCIP 10.0.2." -ForegroundColor Yellow
    if (-not $Preflight) {
        Write-Host "La corrida oficial requiere la version fijada. Abortando." -ForegroundColor Red
        exit 1
    }
}

# --- 3. Validacion estructural de la grilla (no usa SCIP) -------------
Write-Host ""
Write-Host "Validando la grilla de 480 instancias y los testigos..." -ForegroundColor Cyan
& $python src/validar_repositorio.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: la validacion del repositorio fallo. No se resuelve nada." -ForegroundColor Red
    exit 1
}

# --- 4. Resolver la familia --------------------------------------------
$argumentos = @("src/resolver_familia.py", "--L", $L, "--P", $P, "--C", $C,
                "--tiempo", $Tiempo, "--hilos", 1, "--gap", 0,
                "--lambda-0", 1, "--lambda-1", 1)
if ($null -ne $Replicas -and $Replicas.Count -gt 0) { $argumentos += @("--replicas") + $Replicas }
if ($Preflight) { $argumentos += "--preflight" }
if ($Reanudar)  { $argumentos += "--reanudar" }
if ($Salida)    { $argumentos += @("--salida", $Salida) }

$comando = ".\correr_familia.ps1 " + (($PSBoundParameters.GetEnumerator() | ForEach-Object {
    if ($_.Value -is [switch]) { "-$($_.Key)" } else { "-$($_.Key) $($_.Value -join ',')" }
}) -join " ") + "  =>  $python " + ($argumentos -join " ")
$argumentos += @("--comando", $comando)

Write-Host ""
$inicio = Get-Date
& $python @argumentos
$codigo = $LASTEXITCODE
$duracion = (Get-Date) - $inicio
Write-Host ""
Write-Host ("Duracion total: {0:hh\:mm\:ss}" -f $duracion)
if ($codigo -ne 0) {
    Write-Host "El ejecutor termino con codigo $codigo (ver mensajes arriba)." -ForegroundColor Red
} else {
    Write-Host "LISTO." -ForegroundColor Green
}
exit $codigo

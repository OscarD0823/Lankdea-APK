param([switch]$ActualizarDependencias)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ProgramRoot = Join-Path $RepositoryRoot '1-programa'
$VirtualPython = Join-Path $ProgramRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $ProgramRoot -PathType Container)) {
    throw "No se encontró la carpeta del programa: $ProgramRoot"
}

if (-not (Test-Path -LiteralPath $VirtualPython -PathType Leaf)) {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    $PythonArguments = @()
    if (-not $Python) {
        $Python = Get-Command py -ErrorAction SilentlyContinue
        $PythonArguments = @('-3')
    }
    if (-not $Python) {
        throw 'Instala Python 3.10 o posterior para ejecutar el código fuente.'
    }
    Write-Host 'Preparando el entorno de Lankdea por primera vez...'
    & $Python.Source @PythonArguments -m venv (Join-Path $ProgramRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno de Python.' }
    $ActualizarDependencias = $true
}

Set-Location -LiteralPath $ProgramRoot
if ($ActualizarDependencias) {
    & $VirtualPython -m pip install -e '.[desktop]'
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
}

& $VirtualPython main.py
if ($LASTEXITCODE -ne 0) { throw 'Lankdea terminó con un error.' }

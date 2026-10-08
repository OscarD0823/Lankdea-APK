param([switch]$Recompilar)
$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepositoryRoot

function Run-Gh {
    param([string[]]$Arguments)
    $result = & gh @Arguments
    if ($LASTEXITCODE -ne 0) { throw "GitHub CLI falló: gh $($Arguments[0])" }
    return $result
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Instala GitHub CLI y ejecuta gh auth login.' }
$commit = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[0-9a-f]{40}$') { throw 'No se pudo identificar el commit.' }
$branch = (& git branch --show-current).Trim()
if (-not $branch) { throw 'Abre una rama antes de generar el paquete.' }
$changes = & git status --porcelain --untracked-files=normal
if ($changes) { throw 'Haz commit y push de los cambios antes de generar el paquete.' }
$remote = & git ls-remote origin "refs/heads/$branch"
if ($LASTEXITCODE -ne 0 -or -not $remote -or -not $remote.StartsWith($commit)) {
    throw 'El commit local no coincide con la rama remota. Haz git push primero.'
}

$runs = @(Run-Gh -Arguments @('run','list','--workflow','build-apk.yml','--commit',$commit,'--branch',$branch,'--event','push','--limit','10','--json','databaseId,status,conclusion') | ConvertFrom-Json)
$selected = $runs | Where-Object { $_.status -ne 'completed' -or $_.conclusion -eq 'success' } | Select-Object -First 1
if ($Recompilar -or -not $selected) {
    $previous = @(Run-Gh -Arguments @('run','list','--workflow','build-apk.yml','--commit',$commit,'--branch',$branch,'--event','workflow_dispatch','--limit','10','--json','databaseId') | ConvertFrom-Json)
    $previousIds = @($previous | ForEach-Object { $_.databaseId })
    Run-Gh -Arguments @('workflow','run','build-apk.yml','--ref',$branch) | Out-Host
    for ($attempt = 0; $attempt -lt 12; $attempt++) {
        Start-Sleep -Seconds 5
        $runs = @(Run-Gh -Arguments @('run','list','--workflow','build-apk.yml','--commit',$commit,'--branch',$branch,'--event','workflow_dispatch','--limit','10','--json','databaseId,status,conclusion') | ConvertFrom-Json)
        $selected = $runs | Where-Object { $_.databaseId -notin $previousIds } | Select-Object -First 1
        if ($selected) { break }
    }
}
if (-not $selected) { throw 'GitHub aún no muestra la ejecución. Revisa Actions.' }
if ($selected.status -ne 'completed') {
    Run-Gh -Arguments @('run','watch',[string]$selected.databaseId,'--exit-status') | Out-Host
} elseif ($selected.conclusion -ne 'success') {
    throw 'La compilación falló. Revisa Actions; no se combinarán archivos antiguos.'
}

$destination = Join-Path $PSScriptRoot ("ci-" + $commit.Substring(0,12) + '-' + $selected.databaseId)
if (Test-Path -LiteralPath $destination) { throw "La descarga ya existe en $destination. No se sobrescribirá." }
New-Item -ItemType Directory -Path $destination | Out-Null
Run-Gh -Arguments @('run','download',[string]$selected.databaseId,'--name','Lankdea-Paquete-Completo','--dir',$destination) | Out-Host
$packages = @(Get-ChildItem -LiteralPath $destination -Filter '*.zip' -File)
if ($packages.Count -ne 1) { throw 'No se recibió exactamente un ZIP completo.' }
Get-FileHash -LiteralPath $packages[0].FullName -Algorithm SHA256 | Format-List
Write-Host "Paquete listo: $($packages[0].FullName)"
if ($packages[0].Name -like '*-PRUEBAS.zip') {
    Write-Warning 'APK debug: no garantiza actualización sobre otra instalación. No borres tu cofre.'
}

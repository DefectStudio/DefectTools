$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$buildPython = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
Push-Location $repositoryRoot
try {
    if (-not (Test-Path -LiteralPath $buildPython)) {
        & py -3.13 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.13 to build the EXE.' }
    }
    & $buildPython -m pip install --disable-pip-version-check -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Build dependencies could not be installed.' }
    & $buildPython -m PyInstaller --noconfirm packaging\RenderWorker.spec
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
    $executable = Join-Path $repositoryRoot 'dist\RenderWorker.exe'
    Write-Output "Built $executable"
} finally {
    Pop-Location
}

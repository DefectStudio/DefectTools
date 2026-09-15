param([ValidateSet('folder', 'single')][string]$Mode = 'single')
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
    $env:RENDER_WORKER_BUILD_MODE = $Mode
    & $buildPython -m PyInstaller --noconfirm --distpath "dist\$Mode" --workpath "build\$Mode" packaging\RenderWorkerV2.spec
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
    $relativeExecutable = if ($Mode -eq 'folder') { 'dist\folder\RenderWorkerV2\RenderWorkerV2.exe' } else { 'dist\single\RenderWorkerV2.exe' }
    $executable = Join-Path $repositoryRoot $relativeExecutable
    Write-Output "Built $executable"
} finally {
    Pop-Location
}

[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory=$true)][string]$ProjectFile,
    [string]$KritaResourceDirectory = (Join-Path $env:APPDATA 'krita')
)
$ErrorActionPreference = 'Stop'
$project = Get-Item -LiteralPath $ProjectFile
if ($project.PSIsContainer -or $project.Extension -ne '.uproject') { throw 'Choose the checked-out Unreal .uproject file.' }
$pluginPath = Join-Path $project.Directory.FullName 'Plugins\UnrealKritaBridge\UnrealKritaBridge.uplugin'
if (-not (Test-Path -LiteralPath $pluginPath -PathType Leaf)) { throw 'UnrealKritaBridge plugin was not found in this project.' }
$configPath = Join-Path $KritaResourceDirectory 'pykrita\ironwidow_krita\project.json'
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { throw 'Import the Krita plugin ZIP first, then close Krita before configuring.' }
if (Get-Process -Name krita -ErrorAction SilentlyContinue) { throw 'Close Krita before changing its project configuration. Save your work first.' }
$dataRoot = [IO.Path]::GetFullPath((Join-Path $project.Directory.FullName 'Saved\UnrealKritaBridge'))
$json = @{data_root = $dataRoot.Replace('\','/')} | ConvertTo-Json
if ($PSCmdlet.ShouldProcess($configPath, "Configure bridge for $($project.FullName)")) {
    $backup = "$configPath.before-configure-$([Guid]::NewGuid().ToString('N'))"
    Copy-Item -LiteralPath $configPath -Destination $backup
    [IO.File]::WriteAllText($configPath, $json, (New-Object Text.UTF8Encoding($false)))
    Write-Output "Configured: $configPath"
    Write-Output "Bridge data: $dataRoot"
    Write-Output 'Start Unreal to initialize its bridge data folders, then restart Krita.'
}

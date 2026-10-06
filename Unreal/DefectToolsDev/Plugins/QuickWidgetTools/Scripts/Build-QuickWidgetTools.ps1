#requires -Version 5.1
<#
.SYNOPSIS
Builds a portable Win64 QuickWidgetTools package in I:\AICache.
.DESCRIPTION
Builds the editor modules and the CloudGeneratorTools runtime module for
Development and Shipping. Never installs build output into the source checkout.
Use the generated version-files.txt and build-report.json when reviewing the
compiled products to distribute alongside the matching source and content.
#>
[CmdletBinding()]
param(
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8',
    [string]$PluginRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputRoot = 'I:\AICache\quickwidgettools-build',
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$cacheBase = [IO.Path]::GetFullPath('I:\AICache').TrimEnd('\')
$pluginRootPath = [IO.Path]::GetFullPath($PluginRoot).TrimEnd('\')
$engineRootPath = [IO.Path]::GetFullPath($EngineRoot).TrimEnd('\')
$outputRootPath = [IO.Path]::GetFullPath($OutputRoot).TrimEnd('\')
$moduleNames = @('QuickWidgetTools', 'CloudGeneratorTools', 'OnlyCloudsEditor')

function Assert-NoReparseAncestor([string]$Path) {
    $candidate = [IO.Path]::GetFullPath($Path)
    while ($candidate) {
        if (Test-Path -LiteralPath $candidate) {
            if ((Get-Item -LiteralPath $candidate -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "A build path must not pass through a junction or symbolic link: $candidate"
            }
        }
        $parent = [IO.Path]::GetDirectoryName($candidate)
        if (-not $parent -or $parent -eq $candidate) { break }
        $candidate = $parent
    }
}

function Assert-ScratchPath([string]$Path) {
    $absolute = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    if (-not $absolute.StartsWith($cacheBase + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Build output must be in a task subfolder beneath $cacheBase; received $absolute"
    }
    Assert-NoReparseAncestor $absolute
    return $absolute
}

function Assert-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file is missing: $Path"
    }
}

if (-not (Test-Path -LiteralPath $cacheBase -PathType Container)) {
    throw "The scratch drive is unavailable: $cacheBase. Restore access before building."
}
$outputRootPath = Assert-ScratchPath $outputRootPath
Assert-NoReparseAncestor $pluginRootPath
if ($pluginRootPath.StartsWith($outputRootPath + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $outputRootPath.StartsWith($pluginRootPath + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $pluginRootPath -eq $outputRootPath) {
    throw 'Source and output roots must be separate, with neither containing the other.'
}
$descriptorPath = Join-Path $pluginRootPath 'QuickWidgetTools.uplugin'
$dotnet = Join-Path $engineRootPath 'Engine\Binaries\ThirdParty\DotNet\10.0\win-x64\dotnet.exe'
$ubt = Join-Path $engineRootPath 'Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.dll'
$engineVersionPath = Join-Path $engineRootPath 'Engine\Build\Build.version'
$engineManifestPath = Join-Path $engineRootPath 'Engine\Binaries\Win64\UnrealEditor.modules'
foreach ($path in @($descriptorPath, $dotnet, $ubt, $engineVersionPath, $engineManifestPath,
                    (Join-Path $pluginRootPath 'Config\FilterPlugin.ini'))) { Assert-File $path }

$descriptor = Get-Content -LiteralPath $descriptorPath -Raw | ConvertFrom-Json
$engineVersion = Get-Content -LiteralPath $engineVersionPath -Raw | ConvertFrom-Json
$engineManifest = Get-Content -LiteralPath $engineManifestPath -Raw | ConvertFrom-Json
$version = '{0}.{1}.{2}' -f $engineVersion.MajorVersion, $engineVersion.MinorVersion, $engineVersion.PatchVersion
if ($engineVersion.MajorVersion -ne 5 -or $engineVersion.MinorVersion -ne 8) {
    throw "This distribution workflow targets UE 5.8 Win64; selected engine is $version."
}
if (-not $descriptor.CanContainContent -or $descriptor.EngineVersion -ne '5.8.0') {
    throw 'The source descriptor must contain content and use the UE 5.8 compatibility baseline 5.8.0.'
}
foreach ($moduleName in $moduleNames) {
    if (-not @($descriptor.Modules | Where-Object Name -eq $moduleName).Count) {
        throw "The combined plugin descriptor is missing module $moduleName."
    }
    Assert-File (Join-Path $pluginRootPath "Source\$moduleName\$moduleName.Build.cs")
}
if (@($descriptor.Modules | Where-Object { $_.Name -eq 'CloudGeneratorTools' -and $_.Type -eq 'Runtime' }).Count -ne 1) {
    throw 'CloudGeneratorTools must remain a Runtime module so placed clouds work outside the editor.'
}

$requiredContent = @(
    'Content\EditorWidgets\WBP_08_FX_Tools.uasset',
    'Content\OnlyClouds\WorldClouds\BP_UDSOnlyClouds.uasset',
    'Content\OnlyClouds\PlacedClouds\BP_CloudPreset.uasset',
    'Content\OnlyClouds\PlacedClouds\Presets\CP_Cumulus.uasset',
    'Content\OnlyClouds\PlacedClouds\Presets\CP_Cumulonimbus.uasset',
    'Content\OnlyClouds\Templates\LVL_BasicLiteRigg.umap'
)
foreach ($relative in $requiredContent) { Assert-File (Join-Path $pluginRootPath $relative) }

# Fail before copying if a clone still contains Git LFS pointer text in place of assets.
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $pluginRootPath 'Content') -Recurse -File) {
    if ($file.Extension -notin @('.uasset', '.umap', '.ubulk', '.uexp')) { continue }
    if ($file.Length -le 1024 -and
        (Get-Content -LiteralPath $file.FullName -TotalCount 1) -eq 'version https://git-lfs.github.com/spec/v1') {
        throw "Git LFS content is missing: $($file.FullName). Download LFS files before building."
    }
}
if ($ValidateOnly) {
    [pscustomobject]@{
        Status = 'Preflight passed; no build was started'
        EngineVersion = $version
        EngineBuildId = $engineManifest.BuildId
        Source = $pluginRootPath
        OutputRoot = $outputRootPath
        Modules = $moduleNames
    }
    return
}

# A fresh run directory keeps each build separate from prior packages and checkouts.
$runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmssfff') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$runRoot = Assert-ScratchPath (Join-Path $outputRootPath $runId)
if (Test-Path -LiteralPath $runRoot) { throw "Run directory already exists: $runRoot" }
$hostRoot = Join-Path $runRoot 'HostProject'
$hostProject = Join-Path $hostRoot 'HostProject.uproject'
$sourceRoot = Join-Path $hostRoot 'Plugins\QuickWidgetTools'
$packageRoot = Join-Path $runRoot 'Package\QuickWidgetTools'
$cacheRoot = Join-Path $runRoot 'Cache'
$logRoot = Join-Path $runRoot 'Logs'
$reportPath = Join-Path $runRoot 'build-report.json'
$versionListPath = Join-Path $runRoot 'version-files.txt'
$started = [DateTime]::UtcNow
$exitCode = $null
$failure = $null
$savedEnvironment = @{}
$pushedLocation = $false
$versionFiles = @()
$buildManifests = @()

try {
    New-Item -ItemType Directory -Path $sourceRoot, $cacheRoot, $logRoot -Force | Out-Null
    foreach ($directoryName in @('Source', 'Content', 'Resources', 'Shaders', 'Config', 'Docs', 'Scripts')) {
        $sourceDirectory = Join-Path $pluginRootPath $directoryName
        if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) { continue }
        $reparse = Get-ChildItem -LiteralPath $sourceDirectory -Recurse -Force |
            Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } | Select-Object -First 1
        if ($reparse) { throw "Refusing to copy a linked source path: $($reparse.FullName)" }
        Copy-Item -LiteralPath $sourceDirectory -Destination $sourceRoot -Recurse
    }
    Copy-Item -LiteralPath $descriptorPath -Destination $sourceRoot
    '{"FileVersion":3,"Plugins":[{"Name":"QuickWidgetTools","Enabled":true}]}' |
        Set-Content -LiteralPath $hostProject -Encoding utf8

    $environment = @{
        TEMP = (Join-Path $cacheRoot 'Temp')
        TMP = (Join-Path $cacheRoot 'Temp')
        TMPDIR = (Join-Path $cacheRoot 'Temp')
        UBA_ROOT = (Join-Path $cacheRoot 'UBA')
        DOTNET_CLI_HOME = (Join-Path $cacheRoot 'Dotnet')
        NUGET_PACKAGES = (Join-Path $cacheRoot 'NugetPackages')
        DOTNET_CLI_TELEMETRY_OPTOUT = '1'
        DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
        UBT_EXTRA_ARGS = ''
        DOTNET_STARTUP_HOOKS = ''
        QWT_UBT_TRACE_PATH = ''
        PYTHONDONTWRITEBYTECODE = '1'
        LOCALAPPDATA = (Join-Path $cacheRoot 'LocalAppData')
        APPDATA = (Join-Path $cacheRoot 'RoamingAppData')
        'UE-LocalDataCachePath' = (Join-Path $cacheRoot 'DerivedDataCache')
        'UE-SharedDataCachePath' = 'None'
        uebp_EngineSavedFolder = (Join-Path $cacheRoot 'AutomationToolSaved')
        uebp_LogFolder = (Join-Path $logRoot 'UAT')
        uebp_FinalLogFolder = (Join-Path $logRoot 'UAT')
    }
    foreach ($name in $environment.Keys) {
        $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $environment[$name], 'Process')
    }
    foreach ($name in @('TEMP', 'UBA_ROOT', 'DOTNET_CLI_HOME', 'NUGET_PACKAGES', 'LOCALAPPDATA',
                        'APPDATA', 'UE-LocalDataCachePath', 'uebp_EngineSavedFolder', 'uebp_LogFolder')) {
        New-Item -ItemType Directory -Path (Assert-ScratchPath $environment[$name]) -Force | Out-Null
    }

    # UE 5.8's supported XML-cache override avoids generation in Windows profile
    # folders. XmlConfigData serialization v2: version, input count, type count.
    # No overrides means reproducible engine defaults, plus explicit flags below.
    $xmlCache = Join-Path $cacheRoot 'XmlConfigCache.bin'
    $writer = [IO.BinaryWriter]::new([IO.File]::Create($xmlCache))
    try { $writer.Write([int]2); $writer.Write([int]0); $writer.Write([int]0) }
    finally { $writer.Dispose() }

    # UE5.8 always uses UBA locally; -NoUBA disables detouring rather than the
    # executor itself. Initialize its public trace API in a process-local startup
    # hook. The explicit -Session then preserves this trace instead of creating
    # an unconfigurable trace under the Windows profile. No engine files change.
    $hookRoot = Join-Path $cacheRoot 'TraceHook'
    New-Item -ItemType Directory -Path $hookRoot -Force | Out-Null
    $hookCode = @'
using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
internal static class StartupHook
{
    private static IDisposable trace;
    public static void Initialize()
    {
        if (Assembly.GetEntryAssembly()?.GetName().Name != "UnrealBuildTool") return;
        string path = Environment.GetEnvironmentVariable("QWT_UBT_TRACE_PATH");
        if (String.IsNullOrWhiteSpace(path)) throw new InvalidOperationException("Missing scratch UBT trace path.");
        path = Path.GetFullPath(path);
        if (!path.StartsWith(@"I:\AICache\", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("UBT trace must be inside I:\\AICache.");
        Assembly uba = Assembly.Load("EpicGames.UBA");
        NativeLibrary.Load(Path.Combine(Path.GetDirectoryName(uba.Location), "runtimes", "win-x64", "native", "UbaHost.dll"));
        Type api = uba.GetType("EpicGames.UBA.ITrace", true);
        trace = (IDisposable)api.GetMethod("Create", BindingFlags.Public | BindingFlags.Static).Invoke(null,
            new object[] { "QuickWidgetToolsBuild", path, true, null });
        object global = api.GetProperty("GlobalTrace", BindingFlags.Public | BindingFlags.Static).GetValue(null);
        if (global == null || (string)api.GetProperty("Path").GetValue(global) != path)
            throw new InvalidOperationException("Could not initialize the scratch UBT trace.");
        AppDomain.CurrentDomain.ProcessExit += delegate { trace.Dispose(); };
        Console.WriteLine("UBT scratch trace: " + path);
    }
}
'@
    $hookSource = Join-Path $hookRoot 'StartupHook.cs'
    $hookDll = Join-Path $hookRoot 'StartupHook.dll'
    $hookResponse = Join-Path $hookRoot 'compile.rsp'
    $hookCode | Set-Content -LiteralPath $hookSource -Encoding utf8
    $dotnetRoot = Split-Path -Parent $dotnet
    $sdk = Get-ChildItem -LiteralPath (Join-Path $dotnetRoot 'sdk') -Directory |
        Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
    $referencePack = Get-ChildItem -LiteralPath (Join-Path $dotnetRoot 'packs\Microsoft.NETCore.App.Ref') -Directory |
        Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
    if (-not $sdk -or -not $referencePack) { throw 'The bundled .NET SDK and reference pack are required.' }
    $csc = Join-Path $sdk.FullName 'Roslyn\bincore\csc.dll'
    $referenceRoot = Join-Path $referencePack.FullName 'ref\net10.0'
    Assert-File $csc
    $compilerArgs = @('-nologo', '-target:library', ('-out:"' + $hookDll + '"'), ('"' + $hookSource + '"'))
    $compilerArgs += Get-ChildItem -LiteralPath $referenceRoot -Filter *.dll -File |
        ForEach-Object { '-reference:"' + $_.FullName + '"' }
    $compilerArgs | Set-Content -LiteralPath $hookResponse -Encoding utf8
    & $dotnet $csc ('@' + $hookResponse)
    if ($LASTEXITCODE -ne 0) { throw "Scratch trace-hook compilation failed: $LASTEXITCODE" }
    $env:DOTNET_STARTUP_HOOKS = $hookDll

    # These are the three builds performed by UE5.8 BuildPlugin. Invoke UBT
    # directly so -Session is present before global trace setup. UAT BuildPlugin
    # has no argument passthrough at that point. Disable UBA and remote executors.
    Push-Location -LiteralPath $runRoot
    $pushedLocation = $true
    foreach ($target in @(
        @('UnrealEditor', 'Development'),
        @('UnrealGame', 'Development'),
        @('UnrealGame', 'Shipping')
    )) {
        $targetName = $target[0]
        $configuration = $target[1]
        $manifestPath = Join-Path $logRoot "Manifest-$targetName-Win64-$configuration.xml"
        $logPath = Join-Path $logRoot "$targetName-Win64-$configuration.log"
        $env:QWT_UBT_TRACE_PATH = Join-Path $logRoot "$targetName-Win64-$configuration.uba"
        $ubtArguments = @(
            $ubt, $targetName, 'Win64', $configuration, "-Project=$hostProject",
            "-plugin=$sourceRoot\QuickWidgetTools.uplugin", '-noubtmakefiles',
            "-manifest=$manifestPath", '-nohotreload', '-WaitMutex',
            "-Session=$runId", "-XmlConfigCache=$xmlCache", "-log=$logPath",
            "-UBARootDir=$cacheRoot\UBA", '-NoUBA', '-NoXGE', '-NoFASTBuild', '-NoSNDBS'
        )
        & $dotnet @ubtArguments 2>&1 | Tee-Object -FilePath ($logPath + '-console.txt')
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) { throw "$targetName $configuration failed with exit code $exitCode. See $logPath." }
        Assert-File $manifestPath
        $buildManifests += $manifestPath
    }

    # Match BuildPlugin's package inputs without copying its temporary HostProject:
    # source/content/config plus exact manifest products and generated Inc trees.
    $null = Assert-ScratchPath $packageRoot
    New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
    foreach ($directoryName in @('Source', 'Content', 'Resources', 'Shaders', 'Config', 'Docs', 'Scripts')) {
        $sourceDirectory = Join-Path $sourceRoot $directoryName
        if (Test-Path -LiteralPath $sourceDirectory -PathType Container) {
            foreach ($file in Get-ChildItem -LiteralPath $sourceDirectory -Recurse -File) {
                $relative = $file.FullName.Substring($sourceRoot.Length + 1)
                if ($relative -match '[\\/](__pycache__|\.pytest_cache)[\\/]' -or $file.Extension -in @('.pyc', '.pyo')) { continue }
                $destination = Join-Path $packageRoot $relative
                New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
                Copy-Item -LiteralPath $file.FullName -Destination $destination
            }
        }
    }
    $packageDescriptor = Get-Content -LiteralPath (Join-Path $sourceRoot 'QuickWidgetTools.uplugin') -Raw | ConvertFrom-Json
    $packageDescriptor | Add-Member -MemberType NoteProperty -Name Installed -Value $true -Force
    $packageDescriptor.PSObject.Properties.Remove('EnabledByDefault')
    $packageDescriptor | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $packageRoot 'QuickWidgetTools.uplugin') -Encoding utf8
    $productsToCopy = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($manifestPath in $buildManifests) {
        [xml]$buildManifest = Get-Content -LiteralPath $manifestPath -Raw
        $paths = @($buildManifest.SelectNodes('//*[local-name()="BuildProducts"]/*'))
        if (-not $paths.Count) { throw "Build manifest contains no products: $manifestPath" }
        foreach ($pathNode in $paths) {
            $product = [IO.Path]::GetFullPath($pathNode.InnerText)
            if (-not $product.StartsWith($sourceRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
                throw "Build product falls outside the staged plugin: $product"
            }
            $null = $productsToCopy.Add($product)
        }
    }
    foreach ($generated in Get-ChildItem -LiteralPath (Join-Path $sourceRoot 'Intermediate\Build') -Recurse -File) {
        if ($generated.FullName -match '[\\/]Inc[\\/]') { $null = $productsToCopy.Add($generated.FullName) }
    }
    foreach ($product in $productsToCopy) {
        Assert-File $product
        $destination = Join-Path $packageRoot $product.Substring($sourceRoot.Length + 1)
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $product -Destination $destination
    }

    foreach ($relative in @('QuickWidgetTools.uplugin', 'Binaries\Win64\UnrealEditor.modules', 'Config\FilterPlugin.ini') + $requiredContent) {
        Assert-File (Join-Path $packageRoot $relative)
    }
    $packageManifest = Get-Content -LiteralPath (Join-Path $packageRoot 'Binaries\Win64\UnrealEditor.modules') -Raw | ConvertFrom-Json
    if ($packageManifest.BuildId -ne $engineManifest.BuildId) {
        throw "The packaged DLL manifest does not match the selected engine BuildId $($engineManifest.BuildId)."
    }
    foreach ($moduleName in $moduleNames) {
        $dllName = "UnrealEditor-$moduleName.dll"
        if ($packageManifest.Modules.$moduleName -ne $dllName) { throw "Missing DLL manifest entry: $moduleName" }
        Assert-File (Join-Path $packageRoot "Binaries\Win64\$dllName")
    }
    foreach ($configuration in @('Development', 'Shipping')) {
        $precompiledDir = Join-Path $packageRoot "Intermediate\Build\Win64\x64\UnrealGame\$configuration\CloudGeneratorTools"
        $manifestPath = Join-Path $precompiledDir 'CloudGeneratorTools.precompiled'
        Assert-File $manifestPath
        $precompiled = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        if (-not @($precompiled.OutputFiles).Count) { throw "Empty runtime precompile manifest: $manifestPath" }
        foreach ($objectFile in $precompiled.OutputFiles) {
            $objectPath = [IO.Path]::GetFullPath((Join-Path $precompiledDir $objectFile))
            if (-not $objectPath.StartsWith($packageRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
                throw "Precompiled output escapes the package: $objectPath"
            }
            Assert-File $objectPath
        }
    }

    # Keep the manifest-listed precompiled objects,
    # manifests, import libraries and generated headers together, not the HostProject.
    $versionFiles = @(Get-ChildItem -LiteralPath $packageRoot -Recurse -File |
        Where-Object {
            $relative = $_.FullName.Substring($packageRoot.Length + 1).Replace('\', '/')
            ($relative -like 'Binaries/Win64/*.dll' -or $relative -eq 'Binaries/Win64/UnrealEditor.modules' -or
             $relative -like 'Intermediate/Build/*') -and $_.Extension -ne '.pdb'
        } | ForEach-Object { $_.FullName.Substring($packageRoot.Length + 1).Replace('\', '/') } | Sort-Object)
    $versionFiles | Set-Content -LiteralPath $versionListPath -Encoding utf8
    $products = @($versionFiles | ForEach-Object {
        $path = Join-Path $packageRoot $_
        [ordered]@{path = $_; bytes = (Get-Item -LiteralPath $path).Length; sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
    })
    $products | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runRoot 'build-products.json') -Encoding utf8
}
catch { $failure = $_.Exception.Message }
finally {
    if ($pushedLocation) { Pop-Location }
    $finished = [DateTime]::UtcNow
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    if (Test-Path -LiteralPath $runRoot -PathType Container) {
        [ordered]@{
            status = $(if ($failure) { 'failed' } else { 'passed' })
            exitCode = $exitCode
            engineVersion = $version
            engineBuildId = $engineManifest.BuildId
            source = $pluginRootPath
            package = $packageRoot
            logs = $logRoot
            versionFiles = $versionListPath
            productCount = $versionFiles.Count
            startedUtc = $started.ToString('o')
            finishedUtc = $finished.ToString('o')
            buildManifests = $buildManifests
            error = $failure
        } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding utf8
    }
}
if ($failure) { throw $failure }
Write-Output "Portable package ready: $packageRoot"
Write-Output "Version these build products with the matching source/content: $versionListPath"
Write-Output "Build report: $reportPath"
Write-Output 'No files were installed into the plugin checkout; nothing was committed or pushed.'

#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Updater = '',
    [string]$ScratchRoot = 'I:\AICache\QuickWidgetToolsUpdater-tests',
    [string[]]$Only = @()
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Updater)) {
    $Updater = Join-Path (Split-Path -Parent $PSScriptRoot) 'UpdateQuickWidgetTools.ps1'
}
$scratch = [IO.Path]::GetFullPath($ScratchRoot).TrimEnd('\')
if (-not $scratch.StartsWith('I:\AICache\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'All integration-test output must remain beneath I:\AICache.'
}
if (-not (Test-Path -LiteralPath $Updater -PathType Leaf)) { throw "Updater is not ready: $Updater" }
$runRoot = Join-Path $scratch ('integration-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmssfff') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 6))
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$temp = Join-Path $runRoot 'Temp'
New-Item -ItemType Directory -Path $temp | Out-Null
$env:TEMP = $temp
$env:TMP = $temp
$env:GIT_CONFIG_NOSYSTEM = '1'
$env:GIT_ATTR_NOSYSTEM = '1'
$env:GIT_CONFIG_GLOBAL = Join-Path $runRoot 'empty.gitconfig'
[IO.File]::WriteAllText($env:GIT_CONFIG_GLOBAL, '')
$git = (Get-Command git.exe -ErrorAction Stop).Source
$windowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$results = New-Object 'System.Collections.Generic.List[object]'

function Quote-Native([string]$Value) {
    '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}

function Run-Native([string]$File, [string[]]$Arguments, [string]$Directory, [switch]$AllowFailure) {
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $File
    $start.Arguments = ($Arguments | ForEach-Object { Quote-Native $_ }) -join ' '
    $start.WorkingDirectory = $Directory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    [void]$process.Start()
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $result = [pscustomobject]@{ ExitCode = $process.ExitCode; Output = $stdout.Result + $stderr.Result }
    $process.Dispose()
    if ($result.ExitCode -ne 0 -and -not $AllowFailure) {
        throw "Native command failed ($($result.ExitCode)): $File $($Arguments -join ' ')`n$($result.Output)"
    }
    $result
}

function Git([string]$Repository, [string[]]$Arguments, [switch]$AllowFailure) {
    (Run-Native $git (@('-C', $Repository, '--no-pager') + $Arguments) $runRoot -AllowFailure:$AllowFailure)
}

function Write-Text([string]$Path, [string]$Value) {
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [IO.File]::WriteAllText($Path, $Value, (New-Object Text.UTF8Encoding($false)))
}

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Init-Git([string]$Repository, [switch]$Bare) {
    New-Item -ItemType Directory -Path $Repository -Force | Out-Null
    $init = @('init', '-b', 'main')
    if ($Bare) { $init += '--bare' }
    [void](Git $Repository $init)
    [void](Git $Repository @('config', 'user.name', 'Updater Integration Fixture'))
    [void](Git $Repository @('config', 'user.email', 'updater-fixture@defect.invalid'))
    [void](Git $Repository @('config', 'commit.gpgsign', 'false'))
    [void](Git $Repository @('config', 'core.autocrlf', 'false'))
    if (-not $Bare) {
        [void](Git $Repository @('config', 'core.hooksPath', (Join-Path $Repository '.git\hooks')))
        [void](Git $Repository @('lfs', 'install', '--local'))
    }
}

function Write-Plugin([string]$Plugin, [int]$Version) {
    Write-Text (Join-Path $Plugin 'QuickWidgetTools.uplugin') ('{"FileVersion":3,"Version":' + $Version + ',"VersionName":"fixture-' + $Version + '","FriendlyName":"Quick Widget Tools Fixture","EngineVersion":"5.8.0","CanContainContent":true,"Modules":[{"Name":"QuickWidgetTools","Type":"Editor","LoadingPhase":"Default"}]}')
    Write-Text (Join-Path $Plugin 'Resources\fixture.txt') "canonical-fixture-version-$Version`n"
    Write-Text (Join-Path $Plugin '.gitattributes') @'
# Fixture mirrors the canonical package's plugin-owned binary and text rules.
*.uasset filter=lfs diff=lfs merge=lfs -text
*.umap filter=lfs diff=lfs merge=lfs -text
*.dll filter=lfs diff=lfs merge=lfs -text
/Intermediate/Build/**/*.obj filter=lfs diff=lfs merge=lfs -text
/Intermediate/Build/**/*.lib filter=lfs diff=lfs merge=lfs -text
*.obj filter=lfs diff=lfs merge=lfs -text
*.lib filter=lfs diff=lfs merge=lfs -text
*.modules text
*.precompiled text
/Resources/** -filter -diff -merge -text
*.ini text
'@
    Write-Text (Join-Path $Plugin 'Config\DefaultQuickWidgetTools.ini') "[QuickWidgetTools]`nFixtureVersion=$Version`n"
    Write-Text (Join-Path $Plugin 'Source\QuickWidgetTools\QuickWidgetTools.Build.cs') "// fixture source version $Version`n"
    Write-Text (Join-Path $Plugin 'Binaries\Win64\UnrealEditor.modules') '{"BuildId":"fixture-build-id","Modules":{"QuickWidgetTools":"UnrealEditor-QuickWidgetTools.dll"}}'
    $asset = Join-Path $Plugin 'Content\Fixture.uasset'
    New-Item -ItemType Directory -Path (Split-Path -Parent $asset) -Force | Out-Null
    [IO.File]::WriteAllBytes($asset, [byte[]]@(193, 131, 42, 158, $Version, 0, 1, 2, 3, 4, 5, 6))
    [IO.File]::WriteAllBytes((Join-Path $Plugin 'Binaries\Win64\UnrealEditor-QuickWidgetTools.dll'), [byte[]]@(77, 90, $Version, 0, 1, 2, 3, 4))
}

function New-Fixture([string]$Name, [switch]$Submodule, [switch]$NoRootAttributes) {
    $case = Join-Path $runRoot $Name
    $sourceRepository = Join-Path $case 'Source Repository'
    $source = Join-Path $sourceRepository 'Plugins\QuickWidgetTools'
    $repository = Join-Path $case 'Unreal Project With Spaces'
    $origin = Join-Path $case 'target-origin.git'
    $projectDirectory = $repository
    $project = Join-Path $projectDirectory 'Fixture.uproject'
    Init-Git $sourceRepository
    Write-Text (Join-Path $sourceRepository '.gitattributes') "*.uasset filter=lfs diff=lfs merge=lfs -text`n*.dll filter=lfs diff=lfs merge=lfs -text`n"
    Write-Plugin $source 2
    [void](Git $sourceRepository @('add', '--all'))
    [void](Git $sourceRepository @('commit', '-m', 'Create canonical source fixture'))
    Init-Git $origin -Bare
    Init-Git $repository
    Write-Text $project '{"FileVersion":3,"EngineAssociation":"5.8","Category":"","Description":"Updater test fixture"}'
    Write-Text (Join-Path $repository 'README.txt') "original unrelated project file`n"
    if (-not $NoRootAttributes) { Write-Text (Join-Path $repository '.gitattributes') "*.uasset filter=lfs diff=lfs merge=lfs -text`n*.dll filter=lfs diff=lfs merge=lfs -text`n" }
    $oldPlugin = Join-Path $projectDirectory 'Plugins\QuickWidgetTools'
    $pluginPrefix = $oldPlugin.Substring($repository.Length + 1).Replace('\', '/')
    $childRepository = $null
    if ($Submodule) {
        $childRepository = Join-Path $case 'Original Plugin Repository'
        Init-Git $childRepository
        Write-Plugin $childRepository 1
        Write-Text (Join-Path $childRepository 'obsolete.txt') "keep in backup only`n"
        [void](Git $childRepository @('add', '--all'))
        [void](Git $childRepository @('commit', '-m', 'Original submodule history'))
        [void](Git $repository @('-c', 'protocol.file.allow=always', 'submodule', 'add', $childRepository, $pluginPrefix))
    } else {
        Write-Plugin $oldPlugin 1
        Write-Text (Join-Path $oldPlugin 'obsolete.txt') "keep in backup only`n"
    }
    [void](Git $repository @('add', '--all'))
    [void](Git $repository @('commit', '-m', 'Create target project fixture'))
    [void](Git $repository @('remote', 'add', 'origin', $origin))
    [void](Git $repository @('push', '-u', 'origin', 'main'))
    [pscustomobject]@{ Name = $Name; CaseRoot = $case; SourceRepository = $sourceRepository; Source = $source; Repository = $repository; Origin = $origin; Project = $project; Plugin = $oldPlugin; Prefix = $pluginPrefix; ChildRepository = $childRepository }
}

function Invoke-Worker($Fixture, [string]$Label = 'install', [string]$Source = $null) {
    if (-not $Source) { $Source = $Fixture.Source }
    $operation = Join-Path $Fixture.CaseRoot ('operation-' + $Label)
    New-Item -ItemType Directory -Path $operation -Force | Out-Null
    $run = Run-Native $windowsPowerShell @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $Updater, '-Worker', '-ProjectFile', $Fixture.Project, '-SourcePlugin', $Source, '-OperationDirectory', $operation) $runRoot -AllowFailure
    Write-Text (Join-Path $operation 'worker-console.txt') $run.Output
    $jsonPath = Join-Path $operation 'result.json'
    $json = $null
    if (Test-Path -LiteralPath $jsonPath) { $json = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json }
    [pscustomobject]@{ ExitCode = $run.ExitCode; Console = $run.Output; Directory = $operation; Result = $json }
}

function Assert-Success($Run) {
    Assert ($Run.ExitCode -eq 0) "Worker failed with code $($Run.ExitCode). Console: $($Run.Console) Result: $($Run.Result | ConvertTo-Json -Depth 8 -Compress)"
    Assert ($null -ne $Run.Result) "Worker omitted result.json in $($Run.Directory)"
    Assert ($Run.Result.Status -eq 'Done') "Worker returned a non-Done status: $($Run.Result.Status)"
    Assert (Test-Path -LiteralPath (Join-Path $Run.Directory 'operation.log')) 'Worker omitted operation.log'
}

function Assert-Refused($Run, $Fixture, [string]$HeadBefore) {
    Assert ($Run.ExitCode -ne 0) "Worker unexpectedly accepted unsafe fixture $($Fixture.Name)"
    Assert ((Git $Fixture.Repository @('rev-parse', 'HEAD')).Output.Trim() -eq $HeadBefore) 'Refusal changed local HEAD'
    $remoteHead = (Git $Fixture.Origin @('rev-parse', 'refs/heads/main')).Output.Trim()
    Assert ($remoteHead -eq (Git $Fixture.Repository @('rev-parse', 'origin/main')).Output.Trim()) 'Refusal changed remote unexpectedly'
}

function Assert-Synced($Fixture) {
    $head = (Git $Fixture.Repository @('rev-parse', 'HEAD')).Output.Trim()
    $remote = (Git $Fixture.Origin @('rev-parse', 'refs/heads/main')).Output.Trim()
    Assert ($head -eq $remote) 'Local and remote main do not match'
    Assert ([string]::IsNullOrWhiteSpace((Git $Fixture.Repository @('status', '--porcelain')).Output)) 'Project working tree is dirty'
    Assert ((Git $Fixture.Repository @('ls-files', '--stage', '--', $Fixture.Prefix)).Output -notmatch '(?m)^160000 ') 'Plugin remains a gitlink'
    Assert ((Git $Fixture.Plugin @('rev-parse', '--show-toplevel')).Output.Trim().Replace('/', '\') -eq $Fixture.Repository) 'Plugin remains a nested repository'
    Assert (-not (Test-Path -LiteralPath (Join-Path $Fixture.Plugin 'obsolete.txt'))) 'Old plugin file survived replacement'
    foreach ($file in Get-ChildItem -LiteralPath $Fixture.Source -File -Recurse -Force) {
        $relative = $file.FullName.Substring($Fixture.Source.Length + 1)
        $target = Join-Path $Fixture.Plugin $relative
        Assert (Test-Path -LiteralPath $target -PathType Leaf) "Source file missing from target: $relative"
        Assert ((Get-FileHash -LiteralPath $file.FullName).Hash -eq (Get-FileHash -LiteralPath $target).Hash) "Source/target mismatch: $relative"
    }
}

function Test-Case([string]$Name, [scriptblock]$Body) {
    if ($Only.Count -gt 0 -and $Name -notin $Only) { return }
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        & $Body
        $record = [pscustomobject]@{ Name = $Name; Passed = $true; Seconds = [math]::Round($watch.Elapsed.TotalSeconds, 2); Error = $null }
        Write-Host "PASS $Name"
    } catch {
        $record = [pscustomobject]@{ Name = $Name; Passed = $false; Seconds = [math]::Round($watch.Elapsed.TotalSeconds, 2); Error = $_.Exception.Message }
        Write-Host "FAIL $Name`: $($_.Exception.Message)"
    }
    $watch.Stop()
    $results.Add($record)
    $results | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $runRoot 'test-results.json') -Encoding UTF8
}

Test-Case 'ordinary-folder-and-noop' {
    $f = New-Fixture 'ordinary-folder-and-noop'
    $first = Invoke-Worker $f
    Assert-Success $first
    Assert-Synced $f
    $head = (Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim()
    $second = Invoke-Worker $f 'noop'
    Assert-Success $second
    Assert-Synced $f
    Assert ((Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim() -eq $head) 'No-op created another commit'
}

Test-Case 'legacy-submodule-refusal' {
    $f = New-Fixture 'legacy-submodule-refusal' -Submodule
    $head = (Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim()
    $childHead = (Git $f.Plugin @('rev-parse', 'HEAD')).Output.Trim()
    $run = Invoke-Worker $f
    Assert-Refused $run $f $head
    Assert ((Git $f.Plugin @('rev-parse', 'HEAD')).Output.Trim() -eq $childHead) 'Legacy refusal changed child commit'
    Assert (Test-Path -LiteralPath (Join-Path $f.Plugin '.git')) 'Legacy refusal removed child Git metadata'
}

Test-Case 'unrelated-dirty-refusal' {
    $f = New-Fixture 'unrelated-dirty-refusal'
    Write-Text (Join-Path $f.Repository 'README.txt') "unsubmitted coworker work`n"
    $head = (Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim()
    $before = (Git $f.Repository @('status', '--porcelain')).Output
    Assert-Refused (Invoke-Worker $f) $f $head
    Assert ((Git $f.Repository @('status', '--porcelain')).Output -eq $before) 'Refusal changed dirty-file state'
}

Test-Case 'unrelated-staged-refusal' {
    $f = New-Fixture 'unrelated-staged-refusal'
    Write-Text (Join-Path $f.Repository 'README.txt') "staged coworker work`n"
    [void](Git $f.Repository @('add', '--', 'README.txt'))
    $head = (Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim()
    $before = (Git $f.Repository @('diff', '--cached')).Output
    Assert-Refused (Invoke-Worker $f) $f $head
    Assert ((Git $f.Repository @('diff', '--cached')).Output -eq $before) 'Refusal changed index contents'
}

Test-Case 'self-target-refusal' {
    $f = New-Fixture 'self-target-refusal'
    $head = (Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim()
    Assert-Refused (Invoke-Worker $f 'self' $f.Plugin) $f $head
}

Test-Case 'incoming-fast-forward' {
    $f = New-Fixture 'incoming-fast-forward'
    $other = Join-Path $f.CaseRoot 'Other Checkout'
    [void](Run-Native $git @('clone', $f.Origin, $other) $runRoot)
    [void](Git $other @('config', 'user.name', 'Other Fixture User'))
    [void](Git $other @('config', 'user.email', 'other-fixture@defect.invalid'))
    [void](Git $other @('config', 'commit.gpgsign', 'false'))
    [void](Git $other @('lfs', 'install', '--local'))
    Write-Text (Join-Path $other 'README.txt') "incoming clean remote update`n"
    [void](Git $other @('add', '--', 'README.txt'))
    [void](Git $other @('commit', '-m', 'Incoming unrelated project update'))
    [void](Git $other @('push', 'origin', 'main'))
    Assert-Success (Invoke-Worker $f)
    Assert-Synced $f
    Assert ((Get-Content -LiteralPath (Join-Path $f.Repository 'README.txt') -Raw) -eq "incoming clean remote update`n") 'Remote fast-forward content did not arrive'
}

Test-Case 'unpublished-commit-refusal' {
    $f = New-Fixture 'unpublished-commit-refusal'
    Write-Text (Join-Path $f.Repository 'README.txt') "unpublished project commit`n"
    [void](Git $f.Repository @('add', '--', 'README.txt'))
    [void](Git $f.Repository @('commit', '-m', 'Unpublished unrelated work'))
    $head = (Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim()
    Assert-Refused (Invoke-Worker $f) $f $head
}

Test-Case 'missing-source-refusal' {
    $f = New-Fixture 'missing-source-refusal'
    $head = (Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim()
    Assert-Refused (Invoke-Worker $f 'missing' (Join-Path $f.CaseRoot 'Missing Source')) $f $head
}

Test-Case 'pointer-source-refusal' {
    $f = New-Fixture 'pointer-source-refusal'
    Write-Text (Join-Path $f.Source 'Content\Fixture.uasset') "version https://git-lfs.github.com/spec/v1`noid sha256:$('0' * 64)`nsize 12`n"
    $head = (Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim()
    Assert-Refused (Invoke-Worker $f) $f $head
}

Test-Case 'failed-push-retry' {
    $f = New-Fixture 'failed-push-retry'
    $originalRemote = (Git $f.Origin @('rev-parse', 'refs/heads/main')).Output.Trim()
    $hook = Join-Path $f.Origin 'hooks\pre-receive'
    Write-Text $hook "#!/bin/sh`necho fixture intentionally rejects first push >&2`nexit 1`n"
    $failed = Invoke-Worker $f 'push-fails'
    Assert ($failed.ExitCode -ne 0) 'First push unexpectedly succeeded despite rejection hook'
    Assert ((Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim() -ne $originalRemote) 'Failed push did not retain a local update commit'
    Assert ((Git $f.Origin @('rev-parse', 'refs/heads/main')).Output.Trim() -eq $originalRemote) 'Rejected push changed remote HEAD'
    $checkedHook = [IO.Path]::GetFullPath($hook)
    Assert ($checkedHook.StartsWith($runRoot + '\', [StringComparison]::OrdinalIgnoreCase)) 'Hook deletion escapes fixture run'
    Remove-Item -LiteralPath $checkedHook
    Assert-Success (Invoke-Worker $f 'retry')
    Assert-Synced $f
}

Test-Case 'commit-hook-scope-refusal' {
    $f = New-Fixture 'commit-hook-scope-refusal'
    $originalRemote = (Git $f.Origin @('rev-parse', 'refs/heads/main')).Output.Trim()
    Write-Text (Join-Path $f.Repository '.git\hooks\pre-commit') "#!/bin/sh`nprintf 'unrelated change injected by commit hook\\n' > README.txt`ngit add -- README.txt`nexit 0`n"
    $run = Invoke-Worker $f
    Assert ($run.ExitCode -ne 0) 'Updater published a commit with an unrelated hook-staged file'
    Assert ($run.Result.Status -eq 'Error') 'Hook scope violation did not return Error status'
    Assert ((Git $f.Repository @('rev-parse', 'HEAD')).Output.Trim() -ne $originalRemote) 'Hook-created local commit was not preserved for review'
    Assert ((Git $f.Origin @('rev-parse', 'refs/heads/main')).Output.Trim() -eq $originalRemote) 'Hook-injected unrelated file reached remote'
    $retry = Invoke-Worker $f 'retry'
    Assert ($retry.ExitCode -ne 0) 'Retry accepted a commit containing unrelated hook-staged work'
    Assert ((Git $f.Origin @('rev-parse', 'refs/heads/main')).Output.Trim() -eq $originalRemote) 'Retry published unrelated hook-injected work'
}

Test-Case 'retry-push-hook-file-verification' {
    $f = New-Fixture 'retry-push-hook-file-verification'
    $hook = Join-Path $f.Origin 'hooks\pre-receive'
    Write-Text $hook "#!/bin/sh`nexit 1`n"
    $failed = Invoke-Worker $f 'first-push-fails'
    Assert ($failed.ExitCode -ne 0) 'First push unexpectedly succeeded'
    $checkedHook = [IO.Path]::GetFullPath($hook)
    Assert ($checkedHook.StartsWith($runRoot + '\', [StringComparison]::OrdinalIgnoreCase)) 'Hook deletion escapes scratch run'
    Remove-Item -LiteralPath $checkedHook
    Write-Text (Join-Path $f.Repository '.git\hooks\pre-push') "#!/bin/sh`nprintf 'plugin changed by pre-push hook\\n' > Plugins/QuickWidgetTools/Resources/fixture.txt`nexit 0`n"
    $retry = Invoke-Worker $f 'retry-modifies-files'
    Assert ($retry.ExitCode -ne 0) 'Retry reported Done despite plugin file changing during push'
    Assert ($retry.Result.Status -eq 'Error') 'Retry did not flag post-push file mismatch'
}

Test-Case 'plugin-owned-lfs-attributes' {
    $f = New-Fixture 'plugin-owned-lfs-attributes' -NoRootAttributes
    Assert-Success (Invoke-Worker $f)
    Assert-Synced $f
    Assert (Test-Path -LiteralPath (Join-Path $f.Plugin '.gitattributes')) 'Updater omitted canonical plugin-owned .gitattributes'
    $assetPath = $f.Prefix + '/Content/Fixture.uasset'
    Assert ((Git $f.Repository @('check-attr', 'filter', '--', $assetPath)).Output -match ': filter: lfs') 'Plugin-owned attributes did not configure asset LFS'
    Assert ((Git $f.Repository @('show', ('HEAD:' + $assetPath))).Output.StartsWith('version https://git-lfs.github.com/spec/v1')) 'Plugin asset is not an LFS pointer in Git'
}

Test-Case 'inherited-ini-lfs-filter-correction' {
    $f = New-Fixture 'inherited-ini-lfs-filter-correction'
    [IO.File]::AppendAllText((Join-Path $f.Repository '.gitattributes'), "*.ini filter=lfs diff=lfs merge=lfs -text`n")
    [void](Git $f.Repository @('add', '--all'))
    [void](Git $f.Repository @('commit', '-m', 'Fixture inherited ini LFS rule'))
    [void](Git $f.Repository @('push', 'origin', 'main'))
    Assert-Success (Invoke-Worker $f)
    Assert-Synced $f
    $iniPath = $f.Prefix + '/Config/DefaultQuickWidgetTools.ini'
    Assert ((Git $f.Repository @('check-attr', 'filter', '--', $iniPath)).Output -notmatch ': filter: lfs') 'Inherited ini LFS filter was not corrected'
    Assert (-not (Git $f.Repository @('show', ('HEAD:' + $iniPath))).Output.StartsWith('version https://git-lfs.github.com/spec/v1')) 'Plugin ini remains an LFS pointer in Git'
}

$summary = [pscustomobject]@{ RunRoot = $runRoot; WindowsPowerShell = $windowsPowerShell; PowerShellVersion = $PSVersionTable.PSVersion.ToString(); Passed = @($results | Where-Object Passed).Count; Failed = @($results | Where-Object { -not $_.Passed }).Count; Results = $results.ToArray() }
$summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $runRoot 'summary.json') -Encoding UTF8
Write-Host ($summary | ConvertTo-Json -Depth 10)
if ($summary.Failed -gt 0) { exit 1 }
exit 0

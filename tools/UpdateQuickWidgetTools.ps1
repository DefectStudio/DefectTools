#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$Worker,
    [string]$ProjectFile,
    [string]$SourcePlugin = '',
    [string]$OperationDirectory,
    [switch]$ValidateSource
)
$ErrorActionPreference = 'Stop'
# Keep Windows PowerShell's built-in modules available when launched from pwsh.
$windowsModules = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\Modules'
$env:PSModulePath = $windowsModules + [IO.Path]::PathSeparator + $env:PSModulePath
$script:updaterScriptPath = $PSCommandPath
if (!$SourcePlugin) { $SourcePlugin = Join-Path (Split-Path -Parent $PSScriptRoot) 'Unreal\DefectToolsDev\Plugins\QuickWidgetTools' }
$cacheBase = 'I:\AICache'
$cacheRoot = Join-Path $cacheBase 'QuickWidgetToolsUpdater'
if (!(Test-Path -LiteralPath $cacheBase -PathType Container)) { throw 'I:\AICache is unavailable. Restore access to that drive before using the updater.' }
New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
$env:TEMP = $cacheRoot
$env:TMP = $cacheRoot

# Native stream readers keep upload logging independent of the GUI runspace.
if (!('QwtNative' -as [type])) {
Add-Type -TypeDefinition @"
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
public sealed class QwtCommandResult { public int ExitCode; public string Out; public string Err; }
public static class QwtNative {
    public static string Quote(string s) {
        StringBuilder b = new StringBuilder("\""); int slashes = 0;
        foreach (char c in s) {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { b.Append('\\', slashes * 2 + 1); b.Append(c); slashes = 0; continue; }
            b.Append('\\', slashes); slashes = 0; b.Append(c);
        }
        b.Append('\\', slashes * 2); b.Append('"'); return b.ToString();
    }
    public static string Arguments(string[] args) {
        StringBuilder b = new StringBuilder();
        foreach (string arg in args) { if (b.Length > 0) b.Append(' '); b.Append(Quote(arg)); }
        return b.ToString();
    }
    public static QwtCommandResult Run(string exe, string[] args, string cwd, string log, bool showOutput) {
        ProcessStartInfo si = new ProcessStartInfo(exe, Arguments(args));
        si.WorkingDirectory = cwd; si.UseShellExecute = false; si.CreateNoWindow = true;
        si.RedirectStandardOutput = true; si.RedirectStandardError = true;
        si.StandardOutputEncoding = new UTF8Encoding(false); si.StandardErrorEncoding = new UTF8Encoding(false);
        StringBuilder output = new StringBuilder(), error = new StringBuilder(); object gate = new object();
        using (Process p = new Process()) {
            p.StartInfo = si;
            p.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) {
                if (e.Data == null) return;
                lock (gate) { output.Append(e.Data).Append('\n'); if (showOutput && log != null) File.AppendAllText(log, e.Data + Environment.NewLine, new UTF8Encoding(false)); }
            };
            p.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) {
                if (e.Data == null) return;
                lock (gate) { error.Append(e.Data).Append('\n'); if (showOutput && log != null) File.AppendAllText(log, e.Data + Environment.NewLine, new UTF8Encoding(false)); }
            };
            p.Start(); p.BeginOutputReadLine(); p.BeginErrorReadLine(); p.WaitForExit();
            return new QwtCommandResult { ExitCode = p.ExitCode, Out = output.ToString(), Err = error.ToString() };
        }
    }
}
"@
}
function Full-Path([string]$Path) { [IO.Path]::GetFullPath($Path).TrimEnd('\','/') }
function Under-Path([string]$Path, [string]$Root) { (Full-Path $Path).StartsWith((Full-Path $Root) + '\', [StringComparison]::OrdinalIgnoreCase) }
function Assert-NoLinks([string]$Path, [switch]$Tree) {
    $candidate = Full-Path $Path
    while ($candidate) {
        if ((Test-Path -LiteralPath $candidate) -and ((Get-Item -LiteralPath $candidate -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Junctions and symbolic links are not supported: $candidate" }
        $parent = [IO.Path]::GetDirectoryName($candidate)
        if (!$parent -or $parent -eq $candidate) { break }; $candidate = $parent
    }
    if ($Tree -and (Test-Path -LiteralPath $Path)) {
        $links = @(Get-ChildItem -LiteralPath $Path -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
        if ($links.Count) { throw "The plugin contains a junction or symbolic link: $($links[0].FullName)" }
    }
}
function Assert-OperationPath([string]$Path) {
    $absolute = Full-Path $Path
    if (!(Under-Path $absolute $cacheBase)) { throw 'Operation files must be beneath I:\AICache.' }
    Assert-NoLinks $absolute
    return $absolute
}
function Write-Log([string]$Text) {
    if ($script:logPath) { [IO.File]::AppendAllText($script:logPath, ('[{0}] {1}{2}' -f [DateTime]::Now.ToString('HH:mm:ss'), $Text, [Environment]::NewLine), [Text.UTF8Encoding]::new($false)) }
}
function G([string]$Repo, [string[]]$Arguments, [switch]$AllowFailure, [switch]$Quiet) {
    $all = @('--no-pager','-c','core.quotepath=false','-C',$Repo) + $Arguments
    if (!$Quiet) { Write-Log ('git ' + ($Arguments -join ' ')) }
    $result = [QwtNative]::Run($script:gitExe, [string[]]$all, $Repo, $script:logPath, !$Quiet)
    if ($result.ExitCode -ne 0 -and !$AllowFailure) {
        $detail = ($result.Err + $result.Out).Trim()
        throw "Git command failed ($($result.ExitCode)): $($Arguments -join ' '). $detail"
    }
    return $result
}
function Z-Paths([string]$Text) { @($Text.TrimEnd([char]10,[char]13).Split([char]0) | Where-Object { $_.Length -gt 0 }) }
function Relative-Path([string]$Root, [string]$Path) {
    if (!(Under-Path $Path $Root)) { throw 'The project/plugin is outside its Git repository.' }
    (Full-Path $Path).Substring((Full-Path $Root).Length + 1).Replace('\','/')
}
function In-Plugin([string]$Path, [string]$Prefix) { $Path -eq $Prefix -or $Path.StartsWith($Prefix + '/', [StringComparison]::Ordinal) }
function Manifest([string]$Root) {
    @(Get-ChildItem -LiteralPath $Root -Recurse -File -Force | ForEach-Object {
        [pscustomobject]@{ Path=$_.FullName.Substring($Root.Length + 1).Replace('\','/'); Length=$_.Length; SHA256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    })
}
function Digest([object[]]$Files) {
    $text = (@($Files | Sort-Object Path | ForEach-Object { $_.Path + '|' + $_.SHA256 }) -join "`n")
    $sha = [Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($text)))).Replace('-','').ToLowerInvariant() } finally { $sha.Dispose() }
}
function Copy-Folder([string]$From, [string]$To) {
    if (Test-Path -LiteralPath $To) { throw "Refusing to overwrite a backup/snapshot: $To" }
    New-Item -ItemType Directory -Path $To -Force | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $From -Force) { Copy-Item -LiteralPath $item.FullName -Destination $To -Recurse -Force }
}
function Verify-Files([string]$Root, [object[]]$Expected) {
    if (!(Test-Path -LiteralPath $Root -PathType Container)) { throw "Plugin folder missing: $Root" }
    $actual = @(Manifest $Root); $map = @{}
    foreach ($file in $actual) { $map[$file.Path] = $file.SHA256 }
    if ($actual.Count -ne $Expected.Count -or @($Expected | Where-Object { $map[$_.Path] -ne $_.SHA256 }).Count) { throw "Copied files do not match the source: $Root" }
}
function Check-Source([string]$Plugin) {
    $Plugin = Full-Path $Plugin; Assert-NoLinks $Plugin -Tree
    if (!(Test-Path -LiteralPath (Join-Path $Plugin 'QuickWidgetTools.uplugin') -PathType Leaf)) { throw 'The local QuickWidgetTools source or its descriptor is missing.' }
    $descriptor = Get-Content -LiteralPath (Join-Path $Plugin 'QuickWidgetTools.uplugin') -Raw | ConvertFrom-Json
    if (!$descriptor) { throw 'The source plugin descriptor is invalid.' }
    if (@(Get-ChildItem -LiteralPath $Plugin -Recurse -Force -Filter .git).Count) { throw 'The canonical source must be ordinary files, without nested .git metadata.' }
    $files = @(Manifest $Plugin)
    foreach ($file in $files) {
        if ($file.Length -le 1024) {
            $line = Get-Content -LiteralPath (Join-Path $Plugin $file.Path) -TotalCount 1 -ErrorAction Stop
            if ($line -eq 'version https://git-lfs.github.com/spec/v1') { throw "The source has an undownloaded Git LFS file: $($file.Path). Download the source binaries before installing." }
        }
    }
    $repo = Full-Path (G $Plugin @('rev-parse','--show-toplevel') -Quiet).Out.Trim()
    $prefix = Relative-Path $repo $Plugin
    $paths = @(Z-Paths (G $repo @('ls-files','-z','--cached','--others','--exclude-standard','--',$prefix) -Quiet).Out | Sort-Object -Unique)
    $tracked = @($paths | ForEach-Object { $_.Substring($prefix.Length + 1) })
    foreach ($path in $tracked) { if (!(Test-Path -LiteralPath (Join-Path $Plugin $path) -PathType Leaf)) { throw "Source file recorded by Git is missing: $path" } }
    if ('QuickWidgetTools.uplugin' -notin $tracked) { throw 'The source descriptor is not recorded by its Git repository.' }
    [pscustomobject]@{ Plugin=$Plugin; Repo=$repo; Prefix=$prefix; Files=$files; Tracked=$tracked; LfsPaths=@(Lfs-Paths $repo $prefix $tracked); Digest=(Digest $files) }
}
function Lfs-Paths([string]$Repo, [string]$Prefix, [string[]]$SourcePaths) {
    for ($start = 0; $start -lt $SourcePaths.Count; $start += 40) {
        $end = [Math]::Min($start + 39, $SourcePaths.Count - 1)
        $paths = @($SourcePaths[$start..$end] | ForEach-Object { $Prefix + '/' + $_ })
        $parts = (G $Repo (@('check-attr','-z','filter','--') + $paths) -Quiet).Out.TrimEnd([char]10,[char]13).Split([char]0)
        for ($n = 0; $n + 2 -lt $parts.Count; $n += 3) {
            if ($parts[$n + 2] -eq 'lfs') { $parts[$n].Substring($Prefix.Length + 1) }
        }
    }
}
function Assert-PluginAttributes([string]$Repo, [string]$Prefix, [object]$Source) {
    $targetLfs = @(Lfs-Paths $Repo $Prefix $Source.Tracked)
    if ($targetLfs.Count -ne $Source.LfsPaths.Count -or @($targetLfs | Where-Object { $_ -notin $Source.LfsPaths }).Count) { throw 'The project Git LFS rules do not match the source plugin. Review its plugin-specific .gitattributes before retrying.' }
}
function Backup-Plugin([string]$Dest, [string]$Directory) {
    if (Test-Path -LiteralPath $Dest) {
        Assert-NoLinks $Dest -Tree
        $files = @(Manifest $Dest)
        Copy-Folder $Dest (Join-Path $Directory 'old-plugin-backup')
        Verify-Files (Join-Path $Directory 'old-plugin-backup') $files
        $files | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Directory 'old-plugin-manifest.json') -Encoding UTF8
    } else { [IO.File]::WriteAllText((Join-Path $Directory 'old-plugin-was-absent.txt'), 'No previous plugin folder existed.') }
    Write-Log "Previous plugin backed up: $Directory"
}
function Git-FilePath([string]$Repo, [string]$Name) {
    $p = (G $Repo @('rev-parse','--git-path',$Name) -Quiet).Out.Trim()
    if (![IO.Path]::IsPathRooted($p)) { $p = Join-Path $Repo $p }; Full-Path $p
}
function Capture-Metadata([string]$Repo, [string]$Directory) {
    $records = @()
    foreach ($pair in @(@('index',(Git-FilePath $Repo 'index')), @('gitattributes',(Join-Path $Repo '.gitattributes')))) {
        $exists = Test-Path -LiteralPath $pair[1]
        if ($exists) { Copy-Item -LiteralPath $pair[1] -Destination (Join-Path $Directory ('before-' + $pair[0])) }
        $records += [pscustomobject]@{ Name=$pair[0]; Path=$pair[1]; Existed=$exists }
    }
    return $records
}
function Restore-Metadata([object[]]$Records, [string]$Directory) {
    foreach ($record in $Records) {
        if ($record.Existed) { Copy-Item -LiteralPath (Join-Path $Directory ('before-' + $record.Name)) -Destination $record.Path -Force }
        elseif (Test-Path -LiteralPath $record.Path) { Remove-Item -LiteralPath $record.Path -Force }
    }
}
function Assert-TargetPaths([string]$Dest, [string]$ProjectDir, [string]$Repo) {
    $expected = Full-Path (Join-Path $ProjectDir 'Plugins\QuickWidgetTools')
    if ((Full-Path $Dest) -ne $expected -or !(Under-Path $Dest $Repo)) { throw 'Unsafe plugin replacement path.' }
    Assert-NoLinks $Dest -Tree
}
function Assert-OrdinaryPlugin([string]$Repo, [string]$Prefix, [string]$Dest) {
    if ((G $Repo @('ls-files','--stage','--',$Prefix) -Quiet).Out -match '^160000 ') { throw 'This checkout still records a plugin submodule. Synchronize it in Anchorpoint before updating.' }
    if ((Test-Path -LiteralPath $Dest) -and @(Get-ChildItem -LiteralPath $Dest -Recurse -Force -Filter .git).Count) { throw 'The target plugin contains nested Git metadata. Use an ordinary plugin folder before updating.' }
}
function Verify-Remote([string]$Repo, [string]$Remote, [string]$Ref, [string]$Commit) {
    $lines = (G $Repo @('ls-remote','--exit-code',$Remote,$Ref) -Quiet).Out.Trim() -split "`n"
    if ($lines.Count -ne 1 -or ($lines[0] -split '\s+')[0] -ne $Commit) { throw 'The remote branch does not match the installed commit. Retry INSTALL to verify/push again.' }
}
function Assert-CommitScope([string]$Repo, [string]$Commit, [string]$BaseCommit, [string]$Prefix, [string[]]$AllowedPaths) {
    if (@($AllowedPaths | Where-Object { $_ -ne '.gitattributes' }).Count) { throw 'Unexpected root paths in the saved update receipt.' }
    $parents = (G $Repo @('rev-list','--parents','-n','1',$Commit) -Quiet).Out.Trim() -split '\s+'
    if ($parents.Count -ne 2 -or $parents[0] -ne $Commit -or $parents[1] -ne $BaseCommit) { throw 'The update commit does not have the expected project base. Inspect it in Anchorpoint.' }
    $changed = @(Z-Paths (G $Repo @('diff-tree','--no-commit-id','--no-renames','--name-only','-r','-z',$Commit) -Quiet).Out)
    if (!$changed.Count -or @($changed | Where-Object { !(In-Plugin $_ $Prefix) -and $_ -notin $AllowedPaths }).Count) { throw 'The new commit includes unexpected files. It has been kept locally for review and has not been pushed.' }
}
function Assert-PluginClean([string]$Repo, [string]$Prefix) {
    if ((G $Repo @('status','--porcelain','--',$Prefix) -Quiet).Out.Trim()) { throw 'The plugin changed during the update. Inspect it in Anchorpoint before retrying.' }
}
function Assert-PluginIndex([string]$Repo, [string]$Prefix, [string[]]$SourcePaths) {
    $expected = @($SourcePaths | ForEach-Object { $Prefix + '/' + $_ })
    $indexed = @(Z-Paths (G $Repo @('ls-files','-z','--',$Prefix) -Quiet).Out)
    if ($indexed.Count -ne $expected.Count -or @($indexed | Where-Object { $_ -notin $expected }).Count) { throw 'The target Git index does not contain exactly the source plugin files.' }
    if ((G $Repo @('ls-files','--stage','--',$Prefix) -Quiet).Out -match '^160000 ') { throw 'The plugin still has a submodule gitlink.' }
}
function Publish([string]$Repo, [string]$Remote, [string]$Ref, [string]$Commit) {
    if ((G $Repo @('rev-parse','HEAD') -Quiet).Out.Trim() -ne $Commit) { throw 'The current commit changed during the update. Inspect it in Anchorpoint.' }
    Write-Log 'Uploading plugin binaries and Git changes...'
    G $Repo @('lfs','push',$Remote,$Commit) | Out-Null
    G $Repo @('push',$Remote,($Commit + ':' + $Ref)) | Out-Null
    $head = (G $Repo @('rev-parse','HEAD') -Quiet).Out.Trim()
    if ($head -ne $Commit) { throw 'The current commit changed during publication. Inspect it in Anchorpoint.' }
    Verify-Remote $Repo $Remote $Ref $Commit
    return $Commit
}
function Install-Plugin {
    $mutex = New-Object Threading.Mutex($false, 'Local\DefectStudio_QuickWidgetToolsUpdater')
    $ownsMutex = $false; $mutated = $false; $committed = $false; $metadata = @(); $dest = $null; $backupDir = $null; $receiptPath = $null
    try {
        $ownsMutex = $mutex.WaitOne(0)
        if (!$ownsMutex) { throw 'Another QuickWidgetTools update is running. Let it finish first.' }
        Write-Log 'Checking local source and selected project...'
        $source = Check-Source $SourcePlugin
        $project = Full-Path $ProjectFile
        if ([IO.Path]::GetExtension($project) -ne '.uproject' -or !(Test-Path -LiteralPath $project -PathType Leaf)) { throw 'Choose an existing .uproject file.' }
        Assert-NoLinks $project
        Get-Content -LiteralPath $project -Raw | ConvertFrom-Json | Out-Null
        $projectDir = Split-Path -Parent $project
        $repo = Full-Path (G $projectDir @('rev-parse','--show-toplevel') -Quiet).Out.Trim()
        if ($repo -eq $source.Repo) { throw 'The development/source repository cannot be an installation target.' }
        $dest = Full-Path (Join-Path $projectDir 'Plugins\QuickWidgetTools')
        Assert-TargetPaths $dest $projectDir $repo
        if ((Under-Path $source.Plugin $dest) -or (Under-Path $dest $source.Plugin) -or $dest -eq $source.Plugin) { throw 'Source and destination overlap.' }
        $prefix = Relative-Path $repo $dest
        Assert-OrdinaryPlugin $repo $prefix $dest
        $branch = (G $repo @('symbolic-ref','--quiet','--short','HEAD') -AllowFailure -Quiet).Out.Trim()
        if (!$branch) { throw 'The project is on a detached commit. Switch to its working branch in Anchorpoint first.' }
        $staged = @(Z-Paths (G $repo @('diff','--cached','--name-only','-z') -Quiet).Out)
        if ($staged.Count) { throw 'There are already staged files. Submit or unstage them in Anchorpoint before updating the plugin.' }
        foreach ($state in @('MERGE_HEAD','rebase-merge','rebase-apply','CHERRY_PICK_HEAD')) { if (Test-Path -LiteralPath (Git-FilePath $repo $state)) { throw 'Finish the current Git merge/rebase before updating the plugin.' } }
        $dirty = @(@(Z-Paths (G $repo @('diff','--name-only','-z') -Quiet).Out) + @(Z-Paths (G $repo @('ls-files','--others','--exclude-standard','-z') -Quiet).Out))
        $outside = @($dirty | Where-Object { !(In-Plugin $_ $prefix) })
        if ($outside.Count) { throw "Other project files have local changes. Submit them first in Anchorpoint: $($outside[0])" }
        $remote = (G $repo @('config','--get',('branch.' + $branch + '.remote')) -AllowFailure -Quiet).Out.Trim()
        $remoteRef = (G $repo @('config','--get',('branch.' + $branch + '.merge')) -AllowFailure -Quiet).Out.Trim()
        $upstream = (G $repo @('rev-parse','--symbolic-full-name','@{upstream}') -AllowFailure -Quiet).Out.Trim()
        if (!$remote -or $remote -eq '.' -or !$remoteRef.StartsWith('refs/heads/') -or !$upstream) { throw 'The branch needs a configured remote/upstream. Connect it in Anchorpoint first.' }
        G $repo @('lfs','version') -Quiet | Out-Null
        if (!(G $repo @('config','--get','filter.lfs.process') -AllowFailure -Quiet).Out.Trim()) { throw 'Git LFS is not initialized. Run git lfs install in the project Git console, then retry.' }
        $running = @(Get-CimInstance Win32_Process -Filter "Name LIKE 'UnrealEditor%'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($project, [StringComparison]::OrdinalIgnoreCase) -ge 0 })
        if ($running.Count) { throw 'Close Unreal for the selected project before installing.' }
        Write-Log ('Target: ' + $project)
        Write-Log ('Source: ' + $source.Plugin + ' (' + $source.Tracked.Count + ' tracked files)')
        $keySha = [Security.Cryptography.SHA256]::Create()
        try { $repoKey = ([BitConverter]::ToString($keySha.ComputeHash([Text.Encoding]::UTF8.GetBytes($repo.ToLowerInvariant())))).Replace('-','').Substring(0,20) } finally { $keySha.Dispose() }
        $receiptPath = Join-Path $cacheRoot ('pending-' + $repoKey + '.json')
        G $repo @('fetch','--no-recurse-submodules',$remote) | Out-Null
        $head = (G $repo @('rev-parse','HEAD') -Quiet).Out.Trim()
        $remoteHead = (G $repo @('rev-parse',$upstream) -Quiet).Out.Trim()
        $counts = (G $repo @('rev-list','--left-right','--count',('HEAD...' + $upstream)) -Quiet).Out.Trim() -split '\s+'
        $ahead = [int]$counts[0]; $behind = [int]$counts[1]
        if ($ahead -gt 0) {
            if (!(Test-Path -LiteralPath $receiptPath)) { throw 'The branch has unpublished commits. Push/synchronize your work in Anchorpoint first; this updater only publishes its own plugin commit.' }
            $pending = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
            if ($ahead -ne 1 -or $behind -ne 0 -or $pending.Commit -ne $head -or $pending.BaseCommit -ne $remoteHead -or $pending.SourceDigest -ne $source.Digest -or $pending.Remote -ne $remote -or $pending.RemoteRef -ne $remoteRef -or $pending.Prefix -ne $prefix -or $dirty.Count) { throw 'A previous update is pending, but the project/source has changed. Synchronize the saved commit in Anchorpoint first.' }
            Verify-Files $dest $source.Files
            Assert-CommitScope $repo $head $pending.BaseCommit $prefix @($pending.AllowedPaths)
            Assert-PluginIndex $repo $prefix $source.Tracked
            Assert-PluginAttributes $repo $prefix $source
            Write-Log 'Retrying the verified plugin commit from the previous run.'
            $published = Publish $repo $remote $remoteRef $head
            Assert-PluginClean $repo $prefix
            Verify-Files $dest $source.Files
            Remove-Item -LiteralPath $receiptPath -Force
            return [pscustomobject]@{Status='Done';Commit=$published;Project=$project;Backup=$pending.Backup;Message='Saved plugin update pushed and verified.'}
        }
        if (Test-Path -LiteralPath $receiptPath) { Remove-Item -LiteralPath $receiptPath -Force }
        if ($behind -gt 0) {
            if ($dirty.Count) { throw 'The project has incoming commits and local plugin edits. Synchronize in Anchorpoint first; local files have not been replaced.' }
            $ffBackup = Join-Path $script:operationRoot 'before-sync'
            New-Item -ItemType Directory -Path $ffBackup | Out-Null
            Backup-Plugin $dest $ffBackup
            $ffMeta = @(Capture-Metadata $repo $ffBackup)
            if ((G $repo @('ls-tree',$upstream,'--',$prefix) -Quiet).Out -match '^160000 ') { throw 'The incoming project version records a plugin submodule. Synchronize the project to ordinary files first.' }
            try {
                G $repo @('-c','submodule.recurse=false','merge','--ff-only','--no-stat',$upstream) | Out-Null
            } catch {
                $syncProblem = $_.Exception.Message
                try {
                    $stillOld = (G $repo @('rev-parse','HEAD') -Quiet).Out.Trim() -eq $head
                    if ($stillOld) {
                        Assert-TargetPaths $dest $projectDir $repo
                        if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
                        if (Test-Path -LiteralPath (Join-Path $ffBackup 'old-plugin-backup')) { Copy-Folder (Join-Path $ffBackup 'old-plugin-backup') $dest }
                        Restore-Metadata $ffMeta $ffBackup
                    }
                    $remaining = (G $repo @('status','--porcelain') -Quiet).Out.Trim()
                    if ($remaining) {
                        Write-Log ('Files requiring review after failed synchronization:' + [Environment]::NewLine + $remaining)
                        $syncProblem += ' Additional project files may need review in Anchorpoint after the failed synchronization. See the log.'
                    }
                } catch { $syncProblem += ' Recovery needs attention: ' + $_.Exception.Message + '. Backup: ' + $ffBackup }
                throw $syncProblem
            }
            $head = (G $repo @('rev-parse','HEAD') -Quiet).Out.Trim()
            Assert-OrdinaryPlugin $repo $prefix $dest
            Write-Log 'Project fast-forwarded to its upstream.'
        }
        Copy-Folder $source.Plugin (Join-Path $script:operationRoot 'source-snapshot')
        Verify-Files (Join-Path $script:operationRoot 'source-snapshot') $source.Files
        Verify-Files $source.Plugin $source.Files
        $source.Files | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $script:operationRoot 'source-manifest.json') -Encoding UTF8
        $backupDir = Join-Path $script:operationRoot 'before-install'
        New-Item -ItemType Directory -Path $backupDir | Out-Null
        Backup-Plugin $dest $backupDir
        $metadata = @(Capture-Metadata $repo $backupDir)
        $entries = (G $repo @('ls-files','--stage','--',$prefix) -Quiet).Out
        $mutated = $true
        Assert-TargetPaths $dest $projectDir $repo
        if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
        Copy-Folder (Join-Path $script:operationRoot 'source-snapshot') $dest
        Verify-Files $dest $source.Files
        $allowed = @()
        $iniFiles = @($source.Tracked | Where-Object { $_ -like '*.ini' })
        foreach ($ini in $iniFiles) {
            $sourceFilter = (G $source.Repo @('check-attr','filter','--',($source.Prefix + '/' + $ini)) -Quiet).Out.Trim()
            $targetFilter = (G $repo @('check-attr','filter','--',($prefix + '/' + $ini)) -Quiet).Out.Trim()
            if ($sourceFilter -notmatch ': filter: lfs$' -and $targetFilter -match ': filter: lfs$') {
                $attrs = Join-Path $repo '.gitattributes'
                $line = $prefix + '/**/*.ini -filter !diff !merge text'
                $text = if (Test-Path -LiteralPath $attrs) { [IO.File]::ReadAllText($attrs) } else { '' }
                if (!$text.Contains($line)) { [IO.File]::WriteAllText($attrs, $text.TrimEnd("`r","`n") + "`r`n# Keep QuickWidgetTools configuration as ordinary Git text.`r`n$line`r`n", [Text.UTF8Encoding]::new($false)) }
                G $repo @('add','--','.gitattributes') | Out-Null; $allowed += '.gitattributes'; break
            }
        }
        Assert-PluginAttributes $repo $prefix $source
        if ($entries.Trim()) { G $repo @('add','-u','--',$prefix) | Out-Null }
        $pathspec = Join-Path $script:operationRoot 'plugin-pathspec.txt'
        $paths = @($source.Tracked | ForEach-Object { $prefix + '/' + $_ })
        [IO.File]::WriteAllLines($pathspec, [string[]]$paths, [Text.UTF8Encoding]::new($false))
        G $repo @('add','--force',('--pathspec-from-file=' + $pathspec)) | Out-Null
        Assert-PluginIndex $repo $prefix $source.Tracked
        $staged = @(Z-Paths (G $repo @('diff','--cached','--name-only','-z') -Quiet).Out)
        if (@($staged | Where-Object { !(In-Plugin $_ $prefix) -and $_ -notin $allowed }).Count) { throw 'Unexpected files were staged. The updater will restore the pre-install state.' }
        Verify-Files $dest $source.Files
        Verify-Files $source.Plugin $source.Files
        if (!$staged.Count) {
            Verify-Remote $repo $remote $remoteRef $head
            $mutated = $false
            return [pscustomobject]@{Status='Done';Commit=$head;Project=$project;Backup=$backupDir;Message='Plugin already current; remote verified.'}
        }
        Write-Log ('Verified ' + $source.Files.Count + ' copied files; committing ' + $staged.Count + ' changed paths.')
        G $repo @('commit','-m','Update QuickWidgetTools from the local DefectTools plugin') | Out-Null
        $committed = $true
        $newHead = (G $repo @('rev-parse','HEAD') -Quiet).Out.Trim()
        Assert-CommitScope $repo $newHead $head $prefix $allowed
        Assert-PluginIndex $repo $prefix $source.Tracked
        Assert-PluginAttributes $repo $prefix $source
        Assert-PluginClean $repo $prefix
        Verify-Files $dest $source.Files
        $receipt = [pscustomobject]@{Commit=$newHead;BaseCommit=$head;SourceDigest=$source.Digest;Remote=$remote;RemoteRef=$remoteRef;Prefix=$prefix;AllowedPaths=@($allowed);Backup=$backupDir}
        $receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
        $published = Publish $repo $remote $remoteRef $newHead
        Assert-PluginClean $repo $prefix
        Verify-Files $dest $source.Files
        Remove-Item -LiteralPath $receiptPath -Force
        Write-Log ('Done. Remote verified at ' + $published + '. Backup: ' + $backupDir)
        return [pscustomobject]@{Status='Done';Commit=$published;Project=$project;Backup=$backupDir;Message='Installed, committed, pushed, and verified.'}
    } catch {
        $problem = $_.Exception.Message
        if ($mutated -and !$committed -and $repo -and $head) {
            $currentHead = (G $repo @('rev-parse','HEAD') -Quiet).Out.Trim()
            if ($currentHead -ne $head) { $committed = $true }
        }
        if ($mutated -and !$committed -and $backupDir) {
            Write-Log 'Restoring the pre-install plugin and Git index after the failure...'
            try {
                Assert-TargetPaths $dest $projectDir $repo
                if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
                if (Test-Path -LiteralPath (Join-Path $backupDir 'old-plugin-backup')) { Copy-Folder (Join-Path $backupDir 'old-plugin-backup') $dest }
                Restore-Metadata $metadata $backupDir
                Write-Log 'Pre-install state restored; backup retained.'
            } catch { $problem += ' Restoration needs attention: ' + $_.Exception.Message + '. Backup: ' + $backupDir }
        }
        if ($committed) {
            if ($receiptPath -and (Test-Path -LiteralPath $receiptPath)) { Write-Log 'The local update commit is preserved. Retry INSTALL to push/verify the same commit.' }
            else { Write-Log 'The local commit is preserved for review. Inspect it in Anchorpoint before synchronizing.' }
        }
        throw $problem
    } finally {
        if ($ownsMutex) { $mutex.ReleaseMutex() }; $mutex.Dispose()
    }
}
$script:gitExe = (Get-Command git.exe -ErrorAction Stop).Source
if ($ValidateSource) {
    $script:logPath = $null
    $source = Check-Source $SourcePlugin
    [pscustomobject]@{Status='Source verified';Source=$source.Plugin;Files=$source.Files.Count;TrackedFiles=$source.Tracked.Count;Digest=$source.Digest} | ConvertTo-Json
    exit 0
}
if ($Worker) {
    $script:operationRoot = Assert-OperationPath $OperationDirectory
    New-Item -ItemType Directory -Path $script:operationRoot -Force | Out-Null
    $env:TEMP = $script:operationRoot; $env:TMP = $script:operationRoot
    $script:logPath = Join-Path $script:operationRoot 'operation.log'
    [IO.File]::WriteAllText($script:logPath, '', [Text.UTF8Encoding]::new($false))
    try { $result = Install-Plugin; $code = 0 }
    catch { Write-Log ('ERROR: ' + $_.Exception.Message); $result = [pscustomobject]@{Status='Error';Message=$_.Exception.Message;Log=$script:logPath}; $code = 1 }
    $result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $script:operationRoot 'result.json') -Encoding UTF8
    exit $code
}

# GUI runs in its own STA process; a second hidden process performs the install.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object Windows.Forms.Form
$form.Text = 'Update Quick Widget Tools'; $form.ClientSize = New-Object Drawing.Size(820,555)
$form.MinimumSize = New-Object Drawing.Size(680,480); $form.StartPosition = 'CenterScreen'
$form.BackColor = [Drawing.Color]::FromArgb(29,34,43); $form.ForeColor = [Drawing.Color]::FromArgb(235,239,245)
$form.Font = New-Object Drawing.Font('Segoe UI',10)
$title = New-Object Windows.Forms.Label
$title.Text = 'Update Quick Widget Tools'; $title.Font = New-Object Drawing.Font('Segoe UI',19,[Drawing.FontStyle]::Bold)
$title.Location = New-Object Drawing.Point(24,22); $title.Size = New-Object Drawing.Size(740,40); $form.Controls.Add($title)
$label = New-Object Windows.Forms.Label
$label.Text = 'Choose Unreal project:'; $label.Location = New-Object Drawing.Point(26,82); $label.AutoSize = $true; $form.Controls.Add($label)
$browse = New-Object Windows.Forms.Button
$browse.Text = 'Browse...'; $browse.Location = New-Object Drawing.Point(26,110); $browse.Size = New-Object Drawing.Size(106,35); $browse.FlatStyle = 'Flat'; $form.Controls.Add($browse)
$address = New-Object Windows.Forms.TextBox
$address.Location = New-Object Drawing.Point(145,113); $address.Size = New-Object Drawing.Size(647,30); $address.Anchor = 'Top,Left,Right'
$address.BackColor = [Drawing.Color]::FromArgb(42,49,61); $address.ForeColor = $form.ForeColor; $address.BorderStyle = 'FixedSingle'; $form.Controls.Add($address)
$hint = New-Object Windows.Forms.Label
$hint.Text = 'Close Unreal. INSTALL replaces the plugin, backs up the old copy, and pushes the update.'
$hint.Location = New-Object Drawing.Point(26,157); $hint.Size = New-Object Drawing.Size(768,38); $hint.Anchor = 'Top,Left,Right'; $hint.ForeColor = [Drawing.Color]::FromArgb(168,181,199); $form.Controls.Add($hint)
$install = New-Object Windows.Forms.Button
$install.Text = 'INSTALL'; $install.Location = New-Object Drawing.Point(26,205); $install.Size = New-Object Drawing.Size(140,42); $install.FlatStyle = 'Flat'
$install.BackColor = [Drawing.Color]::FromArgb(58,115,207); $install.ForeColor = [Drawing.Color]::White; $install.Font = New-Object Drawing.Font('Segoe UI',11,[Drawing.FontStyle]::Bold); $form.Controls.Add($install)
$status = New-Object Windows.Forms.Label
$status.Text = 'Ready'; $status.TextAlign = 'MiddleCenter'; $status.Location = New-Object Drawing.Point(183,205); $status.Size = New-Object Drawing.Size(170,42)
$status.BackColor = [Drawing.Color]::FromArgb(57,67,83); $status.Font = New-Object Drawing.Font('Segoe UI',11,[Drawing.FontStyle]::Bold); $form.Controls.Add($status)
$log = New-Object Windows.Forms.TextBox
$log.Location = New-Object Drawing.Point(26,265); $log.Size = New-Object Drawing.Size(768,264); $log.Anchor = 'Top,Bottom,Left,Right'
$log.Multiline = $true; $log.ReadOnly = $true; $log.ScrollBars = 'Vertical'; $log.WordWrap = $true
$log.BackColor = [Drawing.Color]::FromArgb(16,20,27); $log.ForeColor = [Drawing.Color]::FromArgb(200,216,229)
$log.Font = New-Object Drawing.Font('Consolas',9); $log.Text = "Source: $SourcePlugin`r`nBackups and logs: $cacheRoot`r`nChoose a .uproject, then click INSTALL."
$form.Controls.Add($log)
$remembered = Join-Path $cacheRoot 'last-project.txt'
if (Test-Path -LiteralPath $remembered) { $address.Text = [IO.File]::ReadAllText($remembered).Trim() }
$script:workerProcess = $null; $script:uiOperation = $null; $script:lastLogLength = -1
$timer = New-Object Windows.Forms.Timer; $timer.Interval = 250
$browse.Add_Click({
    $dialog = New-Object Windows.Forms.OpenFileDialog
    $dialog.Title = 'Choose Unreal project'; $dialog.Filter = 'Unreal projects (*.uproject)|*.uproject'; $dialog.CheckFileExists = $true; $dialog.Multiselect = $false
    if (Test-Path -LiteralPath $address.Text -PathType Leaf) { $dialog.InitialDirectory = Split-Path -Parent $address.Text }
    if ($dialog.ShowDialog($form) -eq [Windows.Forms.DialogResult]::OK) { $address.Text = $dialog.FileName }
    $dialog.Dispose()
})
$install.Add_Click({
    try {
        $selected = $address.Text.Trim().Trim('"')
        if (Test-Path -LiteralPath $selected -PathType Container) {
            $projects = @(Get-ChildItem -LiteralPath $selected -File -Filter '*.uproject')
            if ($projects.Count -ne 1) { throw 'Browse to the .uproject file; that folder does not contain exactly one Unreal project.' }
            $selected = $projects[0].FullName
        }
        if ([IO.Path]::GetExtension($selected) -ne '.uproject' -or !(Test-Path -LiteralPath $selected -PathType Leaf)) { throw 'Choose an existing .uproject file.' }
        $selected = Full-Path $selected; $address.Text = $selected
        [IO.File]::WriteAllText($remembered, $selected)
        $id = [DateTime]::Now.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
        $script:uiOperation = Join-Path $cacheRoot $id
        New-Item -ItemType Directory -Path $script:uiOperation | Out-Null
        $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$script:updaterScriptPath,'-Worker','-ProjectFile',$selected,'-SourcePlugin',$SourcePlugin,'-OperationDirectory',$script:uiOperation)
        $si = New-Object Diagnostics.ProcessStartInfo
        $si.FileName = $powershell; $si.Arguments = [QwtNative]::Arguments([string[]]$args); $si.UseShellExecute = $false; $si.CreateNoWindow = $true; $si.WindowStyle = 'Hidden'
        $script:workerProcess = [Diagnostics.Process]::Start($si)
        $install.Enabled = $false; $browse.Enabled = $false; $address.Enabled = $false
        $status.Text = 'Installing...'; $status.BackColor = [Drawing.Color]::FromArgb(164,114,31)
        $log.Text = "Starting update...`r`nLog: $script:uiOperation\operation.log"
        $script:lastLogLength = -1; $timer.Start()
    } catch { $status.Text = 'Error'; $status.BackColor = [Drawing.Color]::FromArgb(163,55,59); $log.AppendText("`r`n" + $_.Exception.Message) }
})
$timer.Add_Tick({
    $logFile = Join-Path $script:uiOperation 'operation.log'
    if (Test-Path -LiteralPath $logFile) {
        try {
            $text = [IO.File]::ReadAllText($logFile)
            if ($text.Length -ne $script:lastLogLength) { $log.Text = $text.Replace("`n","`r`n").Replace("`r`r`n","`r`n"); $log.SelectionStart = $log.TextLength; $log.ScrollToCaret(); $script:lastLogLength = $text.Length }
        } catch { }
    }
    if ($script:workerProcess -and $script:workerProcess.HasExited) {
        $timer.Stop(); $install.Enabled = $true; $browse.Enabled = $true; $address.Enabled = $true
        $resultFile = Join-Path $script:uiOperation 'result.json'
        try {
            if (!(Test-Path -LiteralPath $resultFile)) { throw "Updater stopped before reporting a result. Inspect $script:uiOperation." }
            $result = Get-Content -LiteralPath $resultFile -Raw | ConvertFrom-Json
            if ($result.Status -eq 'Done' -and $script:workerProcess.ExitCode -eq 0) { $status.Text = 'Done'; $status.BackColor = [Drawing.Color]::FromArgb(39,128,77); $log.AppendText("`r`n" + $result.Message + "`r`nBackup: " + $result.Backup) }
            else { throw $result.Message }
        } catch { $status.Text = 'Error'; $status.BackColor = [Drawing.Color]::FromArgb(163,55,59); $log.AppendText("`r`n" + $_.Exception.Message) }
        $script:workerProcess.Dispose(); $script:workerProcess = $null
    }
})
$form.Add_FormClosing({ param($sender,$eventArgs) if ($script:workerProcess -and !$script:workerProcess.HasExited) { $eventArgs.Cancel = $true; $log.AppendText("`r`nPlease leave this window open until the update finishes.") } })
$form.Add_Shown({ $form.Activate(); $address.Focus() })
try { [void]$form.ShowDialog() } finally { $timer.Dispose(); $form.Dispose() }

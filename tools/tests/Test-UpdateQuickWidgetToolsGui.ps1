#requires -Version 5.1
[CmdletBinding()]
param([string]$Updater = '', [string]$ScratchRoot = 'I:\AICache\QuickWidgetToolsUpdater-gui-tests')
$ErrorActionPreference = 'Stop'
if (!$Updater) { $Updater = Join-Path (Split-Path -Parent $PSScriptRoot) 'UpdateQuickWidgetTools.ps1' }
$ScratchRoot = [IO.Path]::GetFullPath($ScratchRoot).TrimEnd('\')
if (!$ScratchRoot.StartsWith('I:\AICache\', [StringComparison]::OrdinalIgnoreCase)) { throw 'GUI test files must remain beneath I:\AICache.' }
$runRoot = Join-Path $ScratchRoot ([DateTime]::Now.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$env:TEMP = $runRoot; $env:TMP = $runRoot
$fixture = Join-Path $runRoot 'Project With Spaces\Fixture.uproject'
New-Item -ItemType Directory -Path (Split-Path -Parent $fixture) -Force | Out-Null
[IO.File]::WriteAllText($fixture,'{}')
$body = @'
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class QwtPickerTest {
    private delegate bool EnumProc(IntPtr hwnd, IntPtr data);
    [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] private static extern bool EnumThreadWindows(uint thread, EnumProc callback, IntPtr data);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(IntPtr hwnd, StringBuilder title, int count);
    [DllImport("user32.dll")] private static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr w, IntPtr l);
    public static bool CancelOwnPicker() {
        bool found = false;
        EnumThreadWindows(GetCurrentThreadId(), delegate(IntPtr hwnd, IntPtr data) {
            StringBuilder title = new StringBuilder(512); GetWindowText(hwnd, title, title.Capacity);
            if (title.ToString() == "Choose Unreal project") {
                found = true; PostMessage(hwnd, 0x0010, IntPtr.Zero, IntPtr.Zero);
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
"@
$cases = @()
$pickerTimer = New-Object Windows.Forms.Timer
$pickerTimer.Interval = 150
$pickerTimer.Add_Tick({ if ([QwtPickerTest]::CancelOwnPicker()) { $script:pickerSeen = $true; $pickerTimer.Stop() } })
$form.Show(); [Windows.Forms.Application]::DoEvents()
try {
    foreach ($value in @('', '   ', '""', '__FOLDER__', '"__FIXTURE__"')) {
        $address.Text = $value; $status.Text = 'Ready'; $script:pickerSeen = $false
        $pickerTimer.Start()
        try { $browse.PerformClick() } finally { $pickerTimer.Stop() }
        [Windows.Forms.Application]::DoEvents()
        if (!$script:pickerSeen) { throw ('The real picker did not open for input: [' + $value + ']. ' + $log.Text) }
        if ($status.Text -eq 'Error' -or $address.Text -ne $value -or !$browse.Enabled -or !$install.Enabled) { throw 'Browse cancellation left the GUI in the wrong state.' }
        $cases += [pscustomobject]@{Input=$value;PickerOpened=$true;Cancelled=$true;GuiUsable=$true}
    }
    $address.Text = ''; $status.Text = 'Ready'; $install.PerformClick()
    if ($status.Text -ne 'Error' -or !$log.Text.Contains('Choose an existing .uproject file.') -or $script:workerProcess) { throw 'Empty INSTALL did not give the expected friendly validation message.' }
    $cases += [pscustomobject]@{Input='Empty INSTALL';FriendlyError=$true;WorkerStarted=$false}
    [pscustomobject]@{Passed=$cases.Count;Failed=0;Results=$cases} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath '__REPORT__' -Encoding UTF8
} finally { $pickerTimer.Dispose(); $form.Close(); $timer.Dispose(); $form.Dispose() }
'@
$body = $body.Replace('__FOLDER__',(Split-Path -Parent $fixture).Replace("'","''")).Replace('__FIXTURE__',$fixture.Replace("'","''")).Replace('__REPORT__',(Join-Path $runRoot 'summary.json').Replace("'","''"))
$scriptText = [IO.File]::ReadAllText($Updater)
$entry = 'try { [void]$form.ShowDialog() } finally { $timer.Dispose(); $form.Dispose() }'
if (!$scriptText.Contains($entry)) { throw 'GUI test entry point missing.' }
$scriptText = $scriptText.Replace("Join-Path `$cacheBase 'QuickWidgetToolsUpdater'", "'" + (Join-Path $runRoot 'cache').Replace("'","''") + "'")
$hostFile = Join-Path $runRoot 'GuiTestHost.ps1'
[IO.File]::WriteAllText($hostFile,$scriptText.Replace($entry,$body),[Text.UTF8Encoding]::new($false))
$start = New-Object Diagnostics.ProcessStartInfo
$start.FileName = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$start.Arguments = '-NoProfile -ExecutionPolicy Bypass -STA -File "' + $hostFile + '" -SourcePlugin "' + (Join-Path (Split-Path -Parent (Split-Path -Parent $Updater)) 'Unreal\DefectToolsDev\Plugins\QuickWidgetTools') + '"'
$start.UseShellExecute = $false; $start.CreateNoWindow = $true; $start.WindowStyle = 'Hidden'
$start.RedirectStandardOutput = $true; $start.RedirectStandardError = $true
$process = [Diagnostics.Process]::Start($start)
$stdout = $process.StandardOutput.ReadToEndAsync(); $stderr = $process.StandardError.ReadToEndAsync()
if (!$process.WaitForExit(30000)) { $process.Kill(); $process.WaitForExit(); throw ('GUI test timed out; only its own test process was stopped. Files: ' + $runRoot) }
$exitCode = $process.ExitCode; $process.Dispose()
if ($exitCode) { throw ($stdout.Result + $stderr.Result) }
Get-Content -LiteralPath (Join-Path $runRoot 'summary.json') -Raw